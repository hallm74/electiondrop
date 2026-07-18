import shutil
import tempfile
import zipfile
from pathlib import Path

import fitz
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from archive.importer import ImportRejected, import_path, safe_extract_zip, sha256_file
from archive.models import Claim, ClaimCitation, Collection, Document, Page, SourceFile


def make_pdf(path: Path, text="Election archive fixture page"):
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="election-test-media-"))
class ImportTests(TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="election-test-import-"))
        self.collection = Collection.objects.get(slug="michigan-registration")

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def test_sha256_duplicate_detection_and_repeatable_import(self):
        pdf_path = self.temp / "fixture.pdf"
        make_pdf(pdf_path)
        expected_hash = sha256_file(pdf_path)
        first = import_path(pdf_path, self.collection.slug)
        second = import_path(pdf_path, self.collection.slug)
        self.assertEqual(first.files_imported, 1)
        self.assertEqual(second.duplicates, 1)
        self.assertEqual(SourceFile.objects.filter(sha256=expected_hash).count(), 1)
        self.assertEqual(Document.objects.count(), 1)

    def test_pdf_page_extraction_and_stable_ids(self):
        pdf_path = self.temp / "fixture.pdf"
        make_pdf(pdf_path, "Unique searchable fixture language")
        import_path(pdf_path, self.collection.slug)
        document = Document.objects.get()
        page = Page.objects.get()
        self.assertEqual(document.stable_id, "WH-EI-MICH-0001")
        self.assertEqual(page.stable_page_id, "WH-EI-MICH-0001-P001")
        self.assertIn("Unique searchable", page.preferred_searchable_text)

    def test_safe_zip_rejects_traversal(self):
        archive = self.temp / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("../escape.pdf", b"%PDF-not-valid")
        with self.assertRaises(ImportRejected):
            safe_extract_zip(archive, self.temp / "output")

    def test_invalid_file_is_logged_without_source_record(self):
        bad = self.temp / "bad.pdf"
        bad.write_text("not actually a pdf")
        run = import_path(bad, self.collection.slug)
        self.assertEqual(run.errors, 1)
        self.assertEqual(SourceFile.objects.count(), 0)


class RelationshipAndApiTests(TestCase):
    def setUp(self):
        self.media_temp = tempfile.TemporaryDirectory(prefix="election-test-media-")
        self.media_override = override_settings(MEDIA_ROOT=self.media_temp.name)
        self.media_override.enable()
        self.collection = Collection.objects.get(slug="vulnerabilities")
        self.source = SourceFile.objects.create(
            original_filename="fixture.pdf", stored_file=ContentFile(b"%PDF-fixture", name="fixture.pdf"),
            collection=self.collection, sha256="a" * 64, size=12, mime_type="application/pdf", page_count=2,
        )
        self.document = Document.objects.create(collection=self.collection, source_file=self.source, title="Technical memorandum", start_page=1, end_page=2)
        self.page = Page.objects.create(document=self.document, source_file=self.source, source_page_number=1, logical_page_number=1, extracted_text="A test vulnerability did not establish exploitation.", extraction_method="embedded")
        self.client = APIClient()

    def tearDown(self):
        self.media_override.disable()
        self.media_temp.cleanup()

    def test_document_boundary_validation(self):
        document = Document(collection=self.collection, source_file=self.source, title="Invalid boundary", start_page=2, end_page=3)
        with self.assertRaises(Exception):
            document.full_clean()

    def test_claim_citation_requires_page_from_document(self):
        claim = Claim.objects.create(title="Test claim", slug="test-claim", normalized_claim_text="A test claim", status="allegation")
        citation = ClaimCitation(claim=claim, document=self.document, page=self.page, excerpt="did not establish", relationship_type="qualifies")
        citation.full_clean()
        citation.save()
        self.assertEqual(citation.relationship_type, "qualifies")

    def test_search_returns_page_level_link(self):
        response = self.client.get("/api/search/", {"q": "vulnerability"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["page_url"], f"/documents/{self.document.stable_id}/pages/1")

    def test_document_title_search_does_not_repeat_every_page(self):
        Page.objects.create(document=self.document, source_file=self.source, source_page_number=2, logical_page_number=2, extracted_text="Unrelated second page.", extraction_method="embedded")
        response = self.client.get("/api/search/", {"q": "Technical memorandum"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_document_collection_filter(self):
        response = self.client.get("/api/documents/", {"collection": self.collection.slug})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_api_is_read_only_for_anonymous_users(self):
        response = self.client.post("/api/collections/", {"slug": "x", "code": "X", "title": "X"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_source_preview_is_inline(self):
        response = self.client.get(f"/api/source-files/{self.source.pk}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].startswith("inline;"))
        response.close()

    def test_source_download_is_attachment(self):
        response = self.client.get(f"/api/source-files/{self.source.pk}/download/", {"download": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Disposition"].startswith("attachment;"))
        response.close()

    def test_topics_include_curated_burisma_topic(self):
        self.page.extracted_text = "A source passage mentions Ukraine and Burisma."
        self.page.save(update_fields=("extracted_text", "preferred_searchable_text"))
        response = self.client.get("/api/topics/")
        self.assertEqual(response.status_code, 200)
        topic = next(item for item in response.data if item["slug"] == "burisma-ukraine")
        self.assertEqual(topic["document_count"], 1)
        self.assertEqual(topic["mention_count"], 2)

    def test_topic_search_expands_curated_aliases(self):
        self.page.extracted_text = "A source passage mentions Burisma."
        self.page.save(update_fields=("extracted_text", "preferred_searchable_text"))
        response = self.client.get("/api/search/", {"topic": "burisma-ukraine"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["stable_page_id"], self.page.stable_page_id)
