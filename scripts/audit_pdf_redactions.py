#!/usr/bin/env python3
"""Audit archived PDFs for text that remains recoverable beneath redactions.

The report is intentionally written to the ignored tmp/pdfs directory. Findings
are candidates for human review, not an automatic assertion that a redaction
failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import fitz


DEFAULT_FIXTURE = Path("backend/archive/fixtures/production.json")
DEFAULT_OUTPUT = Path("tmp/pdfs/redaction-audit")
DEFAULT_MEDIA_ORIGIN = "https://electiondrop-archive.us-ord-10.linodeobjects.com/media"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_sources(fixture_path: Path) -> list[dict]:
    rows = json.loads(fixture_path.read_text())
    documents = {
        row["fields"]["source_file"]: row["fields"]["stable_id"]
        for row in rows
        if row["model"] == "archive.document"
    }
    sources = []
    for row in rows:
        if row["model"] != "archive.sourcefile":
            continue
        fields = row["fields"]
        if fields["mime_type"] != "application/pdf":
            continue
        sources.append(
            {
                "pk": row["pk"],
                "stable_id": documents.get(row["pk"], ""),
                "filename": fields["original_filename"],
                "stored_file": fields["stored_file"],
                "sha256": fields["sha256"],
                "page_count": fields["page_count"],
                "size": fields["size"],
            }
        )
    return sources


def download_source(source: dict, originals_dir: Path, media_origin: str) -> Path:
    destination = originals_dir / f'{source["sha256"]}.pdf'
    if destination.exists() and sha256_file(destination) == source["sha256"]:
        return destination
    if destination.exists():
        destination.unlink()
    quoted_path = urllib.parse.quote(source["stored_file"], safe="/")
    url = f"{media_origin.rstrip('/')}/{quoted_path}"
    temporary = destination.with_suffix(".download")
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    actual_hash = sha256_file(temporary)
    if actual_hash != source["sha256"]:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(f"SHA-256 mismatch for {source['filename']}: {actual_hash}")
    temporary.replace(destination)
    return destination


def overlap_fraction(first: fitz.Rect, second: fitz.Rect) -> float:
    intersection = first & second
    if intersection.is_empty or first.get_area() <= 0:
        return 0.0
    return intersection.get_area() / first.get_area()


def trace_text(trace: dict, cover: fitz.Rect | None = None) -> str:
    characters = []
    for character in trace.get("chars", []):
        codepoint, _glyph, _origin, bbox = character
        char_rect = fitz.Rect(bbox)
        if cover is None or overlap_fraction(char_rect, cover) >= 0.35:
            try:
                characters.append(chr(codepoint))
            except (TypeError, ValueError):
                continue
    return "".join(characters).strip()


def normalize_text(parts: list[str]) -> str:
    text = " ".join(part for part in parts if part)
    return re.sub(r"\s+", " ", text).strip()


def color_luminance(color) -> float | None:
    if color is None:
        return None
    if isinstance(color, (float, int)):
        return float(color)
    if len(color) >= 3:
        red, green, blue = color[:3]
        return 0.2126 * red + 0.7152 * green + 0.0722 * blue
    return None


def words_in_rect(words: list[tuple], rect: fitz.Rect, threshold: float = 0.35) -> list[str]:
    matches = []
    for word in words:
        word_rect = fitz.Rect(word[:4])
        if overlap_fraction(word_rect, rect) >= threshold:
            matches.append(word[4])
    return matches


def solid_dark_word_candidates(page: fitz.Page, words: list[tuple], traces: list[dict]) -> list[dict]:
    if not words:
        return []
    scale = 1.5
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
    samples = pixmap.samples_mv
    channels = pixmap.n
    candidates = []
    for word in words:
        text = word[4].strip()
        if len(re.sub(r"\W", "", text)) < 2:
            continue
        rect = fitz.Rect(word[:4])
        visibly_contrasting = False
        for trace in traces:
            if overlap_fraction(rect, fitz.Rect(trace["bbox"])) < 0.25:
                continue
            trace_luminance = color_luminance(trace.get("color"))
            if (
                trace.get("type", 0) != 3
                and trace.get("opacity", 1) > 0.05
                and trace_luminance is not None
                and trace_luminance > 0.08
            ):
                visibly_contrasting = True
                break
        if visibly_contrasting:
            continue
        box = (
            max(0, int(rect.x0 * scale)),
            max(0, int(rect.y0 * scale)),
            min(pixmap.width, max(1, int(rect.x1 * scale))),
            min(pixmap.height, max(1, int(rect.y1 * scale))),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        dark_pixels = 0
        luminance_sum = 0.0
        pixels = 0
        for y in range(box[1], box[3], 2):
            for x in range(box[0], box[2], 2):
                offset = (y * pixmap.width + x) * channels
                red, green, blue = samples[offset : offset + 3]
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                dark_pixels += luminance < 55
                luminance_sum += luminance
                pixels += 1
        pixels = max(1, pixels)
        dark_fraction = dark_pixels / pixels
        mean = luminance_sum / pixels
        if dark_fraction >= 0.78 and mean <= 52:
            candidates.append(
                {
                    "text": text,
                    "bbox": [round(value, 2) for value in rect],
                    "dark_fraction": round(dark_fraction, 3),
                    "mean_luminance": round(mean, 1),
                }
            )
    return candidates


def audit_page(page: fitz.Page) -> list[dict]:
    findings = []
    words = page.get_text("words", sort=True)
    traces = page.get_texttrace()

    annotations = page.annots()
    if annotations:
        for annotation in annotations:
            if annotation.type[1].lower() != "redact":
                continue
            covered = normalize_text(words_in_rect(words, annotation.rect))
            findings.append(
                {
                    "kind": "unapplied_redaction_annotation",
                    "confidence": "high" if covered else "medium",
                    "bbox": [round(value, 2) for value in annotation.rect],
                    "recoverable_text": covered,
                    "reason": "A live PDF redaction annotation remains over extractable page text.",
                }
            )

    for drawing in page.get_drawings():
        fill_luminance = color_luminance(drawing.get("fill"))
        if fill_luminance is None or drawing.get("fill_opacity", 1) < 0.9:
            continue
        rect = fitz.Rect(drawing["rect"])
        if rect.get_area() < 24 or rect.width < 4 or rect.height < 3:
            continue
        if fill_luminance > 0.18:
            continue
        drawing_sequence = drawing.get("seqno", sys.maxsize)
        covered_parts = []
        for trace in traces:
            if trace.get("seqno", -1) >= drawing_sequence:
                continue
            if overlap_fraction(fitz.Rect(trace["bbox"]), rect) <= 0:
                continue
            covered_parts.append(trace_text(trace, rect))
        covered = normalize_text(covered_parts)
        if covered:
            findings.append(
                {
                    "kind": "opaque_rectangle_over_text",
                    "confidence": "high",
                    "bbox": [round(value, 2) for value in rect],
                    "recoverable_text": covered,
                    "reason": "An opaque dark rectangle is painted after and over recoverable PDF text.",
                }
            )

    hidden_parts = []
    for trace in traces:
        render_mode = trace.get("type", 0)
        opacity = trace.get("opacity", 1)
        if render_mode == 3 or opacity <= 0.05:
            hidden = trace_text(trace)
            if hidden:
                hidden_parts.append(hidden)
    dark_words = solid_dark_word_candidates(page, words, traces)
    dark_text = normalize_text([candidate["text"] for candidate in dark_words])
    if dark_text:
        hidden_text = normalize_text(hidden_parts)
        findings.append(
            {
                "kind": "extractable_text_in_solid_dark_area",
                "confidence": "medium",
                "bbox": dark_words[0]["bbox"],
                "recoverable_text": dark_text,
                "hidden_text_layer_present": bool(hidden_text),
                "reason": "Extractable words occupy pixels rendered as a nearly solid dark area; visual review is required.",
                "samples": dark_words[:20],
            }
        )
    return findings


def audit_source(source: dict, pdf_path: Path, evidence_dir: Path) -> dict:
    raw = pdf_path.read_bytes()
    document = fitz.open(pdf_path)
    pages = []
    for page_number, page in enumerate(document, start=1):
        findings = audit_page(page)
        if not findings:
            continue
        evidence_path = evidence_dir / f'{source["stable_id"]}-P{page_number:03d}.png'
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False, colorspace=fitz.csRGB)
        pixmap.save(evidence_path)
        pages.append(
            {
                "page_number": page_number,
                "stable_page_id": f'{source["stable_id"]}-P{page_number:03d}',
                "evidence_image": str(evidence_path),
                "findings": findings,
            }
        )
    layer_configs = []
    try:
        layer_configs = document.layer_ui_configs() or []
    except (AttributeError, RuntimeError, ValueError):
        pass
    try:
        embedded_files = document.embfile_names() or []
    except (AttributeError, RuntimeError, ValueError):
        embedded_files = []
    linearized_match = re.search(rb"/Linearized\s+1\b.*?/L\s+(\d+)\b", raw[:2048], re.DOTALL)
    linearized_length = int(linearized_match.group(1)) if linearized_match else None
    appended_bytes = max(0, len(raw) - linearized_length) if linearized_length else 0
    revision_pages = []
    if linearized_length and appended_bytes:
        try:
            previous_document = fitz.open(stream=raw[:linearized_length], filetype="pdf")
            revision_dir = evidence_dir / "revisions"
            revision_dir.mkdir(exist_ok=True)
            for page_index in range(min(document.page_count, previous_document.page_count)):
                current_page = document[page_index]
                previous_page = previous_document[page_index]
                matrix = fitz.Matrix(1, 1)
                current_pixmap = current_page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
                previous_pixmap = previous_page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
                if (current_pixmap.width, current_pixmap.height) != (previous_pixmap.width, previous_pixmap.height):
                    changed_fraction = 1.0
                else:
                    current_samples = current_pixmap.samples_mv
                    previous_samples = previous_pixmap.samples_mv
                    pixels = max(1, current_pixmap.width * current_pixmap.height)
                    changed_pixels = 0
                    channels = current_pixmap.n
                    for offset in range(0, len(current_samples), channels):
                        difference = sum(
                            abs(current_samples[offset + channel] - previous_samples[offset + channel])
                            for channel in range(3)
                        )
                        changed_pixels += difference > 30
                    changed_fraction = changed_pixels / pixels
                current_text = current_page.get_text("text", sort=True).strip()
                previous_text = previous_page.get_text("text", sort=True).strip()
                if changed_fraction < 0.0001 and current_text == previous_text:
                    continue
                page_number = page_index + 1
                prefix = f'{source["stable_id"]}-P{page_number:03d}'
                previous_path = revision_dir / f"{prefix}-previous.png"
                current_path = revision_dir / f"{prefix}-current.png"
                previous_page.get_pixmap(
                    matrix=fitz.Matrix(2, 2), alpha=False, colorspace=fitz.csRGB
                ).save(previous_path)
                current_page.get_pixmap(
                    matrix=fitz.Matrix(2, 2), alpha=False, colorspace=fitz.csRGB
                ).save(current_path)
                revision_pages.append(
                    {
                        "page_number": page_number,
                        "stable_page_id": prefix,
                        "changed_pixel_fraction": round(changed_fraction, 6),
                        "text_changed": current_text != previous_text,
                        "previous_text": previous_text if current_text != previous_text else "",
                        "current_text": current_text if current_text != previous_text else "",
                        "previous_evidence_image": str(previous_path),
                        "current_evidence_image": str(current_path),
                    }
                )
            previous_document.close()
        except (RuntimeError, ValueError) as exc:
            revision_pages.append({"error": str(exc)})
    document.close()
    return {
        **source,
        "eof_markers": raw.count(b"%%EOF"),
        "linearized": bool(linearized_match),
        "linearized_length": linearized_length,
        "appended_bytes": appended_bytes,
        "optional_content_layers": len(layer_configs),
        "embedded_files": embedded_files,
        "revision_changed_pages": revision_pages,
        "flagged_pages": pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--media-origin", default=DEFAULT_MEDIA_ORIGIN)
    args = parser.parse_args()

    originals_dir = args.output / "originals"
    evidence_dir = args.output / "evidence"
    originals_dir.mkdir(parents=True, exist_ok=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    sources = load_sources(args.fixture)
    results = []
    for index, source in enumerate(sources, start=1):
        print(f"[{index}/{len(sources)}] {source['filename']}", flush=True)
        pdf_path = download_source(source, originals_dir, args.media_origin)
        results.append(audit_source(source, pdf_path, evidence_dir))

    report = {
        "methodology": {
            "scope": "Immutable public PDF originals matched by SHA-256 to the production archive fixture.",
            "warning": "Candidates require visual human review before publication.",
            "checks": [
                "live redaction annotations over extractable text",
                "opaque dark vector rectangles painted over earlier text",
                "extractable text spatially located in nearly solid dark rendered pixels",
                "content appended after a complete linearized PDF revision",
                "optional content layers",
            ],
        },
        "source_count": len(results),
        "flagged_document_count": sum(bool(result["flagged_pages"]) for result in results),
        "flagged_page_count": sum(len(result["flagged_pages"]) for result in results),
        "documents": results,
    }
    report_path = args.output / "report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"Wrote {report_path}")
    print(
        f"Flagged {report['flagged_page_count']} pages in "
        f"{report['flagged_document_count']} documents."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
