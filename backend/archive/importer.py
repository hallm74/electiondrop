import hashlib
import mimetypes
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

import fitz
from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils import timezone

from .models import Collection, Document, ImportRun, Page, SourceFile, SourceType


COLLECTION_HINTS = {
    "vulnerabilities": "vulnerabilities",
    "vulnerability": "vulnerabilities",
    "vuln": "vulnerabilities",
    "china": "china-voter-data",
    "michigan": "michigan-registration",
    "mich": "michigan-registration",
    "noncitizens": "noncitizen-rolls",
    "noncitizen": "noncitizen-rolls",
}

OFFICIAL_SOURCE_URLS = {
    "Vulnerabilities-in-Electronic-Voting-and-Ballot-Counting-Systems.zip": "https://www.whitehouse.gov/wp-content/uploads/2026/07/Vulnerabilities-in-Electronic-Voting-and-Ballot-Counting-Systems.zip",
    "Chinas-Acquisition-and-Exploitation-of-American-Voter-Data.zip": "https://www.whitehouse.gov/wp-content/uploads/2026/07/Chinas-Acquisition-and-Exploitation-of-American-Voter-Data.zip",
    "Michigan-Voter-Registration-Investigation.zip": "https://www.whitehouse.gov/wp-content/uploads/2026/07/Michigan-Voter-Registration-Investigation.zip",
    "Noncitizens-on-State-Voter-Rolls.zip": "https://www.whitehouse.gov/wp-content/uploads/2026/07/Noncitizens-on-State-Voter-Rolls.zip",
}


class ImportRejected(Exception):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_kind(path: Path) -> str | None:
    with path.open("rb") as handle:
        signature = handle.read(8)
    if signature.startswith(b"%PDF-"):
        return "application/pdf"
    if signature.startswith(b"PK\x03\x04") and zipfile.is_zipfile(path):
        return "application/zip"
    return None


def should_ignore(path: Path) -> bool:
    return path.name in {".DS_Store", ".gitkeep"} or path.name.startswith("._")


def safe_extract_zip(archive_path: Path, destination: Path) -> list[Path]:
    extracted = []
    total_size = 0
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        if len(members) > settings.MAX_ARCHIVE_FILES:
            raise ImportRejected("Archive contains too many files.")
        for member in members:
            parts = PurePosixPath(member.filename).parts
            if member.is_dir():
                continue
            if not parts or member.filename.startswith(("/", "\\")) or ".." in parts:
                raise ImportRejected(f"Unsafe archive path: {member.filename}")
            total_size += member.file_size
            if total_size > settings.MAX_ARCHIVE_EXPANDED_SIZE:
                raise ImportRejected("Archive expands beyond the configured size limit.")
            target = destination.joinpath(*parts).resolve()
            if destination.resolve() not in target.parents:
                raise ImportRejected(f"Archive path escapes destination: {member.filename}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)
            extracted.append(target)
    return extracted


def collection_for_path(path: Path, forced_slug: str | None = None) -> Collection:
    if forced_slug:
        return Collection.objects.get(slug=forced_slug)
    lowered = " ".join(part.lower() for part in path.parts)
    for hint, slug in COLLECTION_HINTS.items():
        if hint in lowered:
            return Collection.objects.get(slug=slug)
    raise ImportRejected(
        "Could not infer a collection. Place the file in a collection-named folder or use --collection."
    )


def import_path(root: Path, collection_slug: str | None = None) -> ImportRun:
    root = root.resolve()
    run = ImportRun.objects.create(path_label=root.name)
    initial_paths = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
    queue = [(path, collection_slug, OFFICIAL_SOURCE_URLS.get(path.name, "")) for path in initial_paths]
    with tempfile.TemporaryDirectory(prefix="election-import-") as temp_name:
        temp_root = Path(temp_name)
        seen_paths = set()
        while queue:
            path, inherited_collection, inherited_source_url = queue.pop(0)
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            if should_ignore(path):
                append_log(run, path.name, "ignored", "Packaging metadata")
                continue
            run.files_seen += 1
            try:
                size = path.stat().st_size
                if size > settings.MAX_IMPORT_FILE_SIZE:
                    raise ImportRejected("File exceeds the configured size limit.")
                kind = detect_kind(path)
                if kind not in {"application/pdf", "application/zip"}:
                    raise ImportRejected("Unsupported or invalid file type.")
                collection = collection_for_path(path, inherited_collection)
                source, created = store_source_file(path, kind, collection, run, inherited_source_url)
                if not created:
                    run.duplicates += 1
                    append_log(run, path.name, "duplicate", source.sha256)
                    if kind == "application/zip":
                        archive_dir = temp_root / f"duplicate-{source.sha256}"
                        archive_dir.mkdir(exist_ok=True)
                        queue.extend((item, source.collection.slug, source.source_url) for item in safe_extract_zip(path, archive_dir))
                    continue
                run.files_imported += 1
                if kind == "application/zip":
                    archive_dir = temp_root / source.sha256
                    archive_dir.mkdir()
                    queue.extend((item, collection.slug, source.source_url) for item in safe_extract_zip(path, archive_dir))
                    source.import_status = SourceFile.Status.COMPLETE
                    source.extraction_status = SourceFile.Status.COMPLETE
                    source.save(update_fields=("import_status", "extraction_status"))
                else:
                    inspect_pdf(path, source)
                append_log(run, path.name, "imported", source.sha256)
            except Exception as exc:
                run.errors += 1
                append_log(run, path.name, "error", str(exc))
    run.completed_at = timezone.now()
    run.save()
    return run


def append_log(run: ImportRun, filename: str, status: str, detail: str):
    run.log = [*run.log, {"filename": filename, "status": status, "detail": detail}]


@transaction.atomic
def store_source_file(path: Path, kind: str, collection: Collection, run: ImportRun, source_url: str = ""):
    digest = sha256_file(path)
    existing = SourceFile.objects.filter(sha256=digest).first()
    if existing:
        if source_url and not existing.source_url:
            existing.source_url = source_url
            existing.save(update_fields=("source_url",))
        return existing, False
    source = SourceFile(
        original_filename=path.name,
        collection=collection,
        sha256=digest,
        size=path.stat().st_size,
        mime_type=kind or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        source_url=source_url,
        import_run=run,
    )
    with path.open("rb") as handle:
        source.stored_file.save(path.name, File(handle), save=False)
    source.save()
    return source, True


@transaction.atomic
def inspect_pdf(path: Path, source: SourceFile):
    try:
        pdf = fitz.open(path)
        source.page_count = pdf.page_count
        source.pdf_metadata = {k: v for k, v in (pdf.metadata or {}).items() if v}
        title = source.pdf_metadata.get("title") or Path(source.original_filename).stem.replace("_", " ").replace("-", " ")
        document = Document.objects.create(
            collection=source.collection,
            source_file=source,
            title=title,
            title_source=SourceType.EMBEDDED if source.pdf_metadata.get("title") else SourceType.IMPORTED,
            start_page=1,
            end_page=max(pdf.page_count, 1),
        )
        embedded_pages = 0
        for index, pdf_page in enumerate(pdf, start=1):
            text = pdf_page.get_text("text").strip()
            method = Page.Method.EMBEDDED if text else Page.Method.NONE
            embedded_pages += bool(text)
            page = Page.objects.create(
                document=document,
                source_file=source,
                source_page_number=index,
                logical_page_number=index,
                extracted_text=text,
                extraction_method=method,
                extraction_confidence=1 if text else 0,
            )
            pixmap = pdf_page.get_pixmap(matrix=fitz.Matrix(0.35, 0.35), alpha=False)
            image_name = f"{page.stable_page_id}.png"
            from django.core.files.base import ContentFile
            page.page_image.save(image_name, ContentFile(pixmap.tobytes("png")), save=True)
        source.contains_embedded_text = embedded_pages > 0
        source.ocr_required = embedded_pages < pdf.page_count
        source.ocr_status = SourceFile.Status.PENDING if source.ocr_required else SourceFile.Status.COMPLETE
        source.import_status = SourceFile.Status.COMPLETE
        source.extraction_status = SourceFile.Status.COMPLETE
        source.save()
        pdf.close()
    except Exception as exc:
        source.import_status = SourceFile.Status.ERROR
        source.extraction_status = SourceFile.Status.ERROR
        source.error_details = str(exc)
        source.save()
        raise
