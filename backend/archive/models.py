from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models, transaction


class ReviewState(models.TextChoices):
    UNREVIEWED = "unreviewed", "Unreviewed"
    REVIEWED = "reviewed", "Reviewed"
    NEEDS_ATTENTION = "needs_attention", "Needs attention"


class SourceType(models.TextChoices):
    PRINTED = "printed", "Printed in source"
    EMBEDDED = "embedded", "Embedded metadata"
    INFERRED = "inferred", "Inferred"
    EDITORIAL = "editorial", "Editorial"
    IMPORTED = "imported", "Imported"


class Collection(models.Model):
    slug = models.SlugField(unique=True)
    code = models.CharField(max_length=8, unique=True)
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    source_url = models.URLField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "title")

    def __str__(self):
        return self.title


class ImportRun(models.Model):
    path_label = models.CharField(max_length=500)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    files_seen = models.PositiveIntegerField(default=0)
    files_imported = models.PositiveIntegerField(default=0)
    duplicates = models.PositiveIntegerField(default=0)
    errors = models.PositiveIntegerField(default=0)
    log = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Import {self.pk}: {self.path_label}"


def original_upload_to(instance, filename):
    digest = instance.sha256 or "pending"
    suffix = Path(filename).suffix.lower()
    return f"originals/{digest[:2]}/{digest}{suffix}"


class SourceFile(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETE = "complete", "Complete"
        DUPLICATE = "duplicate", "Duplicate"
        ERROR = "error", "Error"

    original_filename = models.CharField(max_length=500)
    stored_file = models.FileField(upload_to=original_upload_to, max_length=700)
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="source_files")
    sha256 = models.CharField(max_length=64, unique=True, db_index=True)
    size = models.PositiveBigIntegerField()
    mime_type = models.CharField(max_length=100)
    page_count = models.PositiveIntegerField(default=0)
    pdf_metadata = models.JSONField(default=dict, blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    source_url = models.URLField(blank=True)
    import_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    extraction_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    ocr_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    contains_embedded_text = models.BooleanField(default=False)
    ocr_required = models.BooleanField(default=False)
    error_details = models.TextField(blank=True)
    import_run = models.ForeignKey(ImportRun, null=True, blank=True, on_delete=models.SET_NULL, related_name="source_files")

    class Meta:
        ordering = ("-imported_at",)

    def __str__(self):
        return self.original_filename


class Document(models.Model):
    class DatePrecision(models.TextChoices):
        DAY = "day", "Day"
        MONTH = "month", "Month"
        YEAR = "year", "Year"
        UNKNOWN = "unknown", "Unknown"

    stable_id = models.CharField(max_length=32, unique=True, editable=False)
    collection = models.ForeignKey(Collection, on_delete=models.PROTECT, related_name="documents")
    source_file = models.ForeignKey(SourceFile, on_delete=models.PROTECT, related_name="documents")
    title = models.CharField(max_length=500)
    title_source = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.IMPORTED)
    document_type = models.CharField(max_length=160, blank=True)
    originating_agency = models.CharField(max_length=240, blank=True)
    agency_source = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.INFERRED)
    document_date = models.DateField(null=True, blank=True)
    date_precision = models.CharField(max_length=10, choices=DatePrecision.choices, default=DatePrecision.UNKNOWN)
    date_source = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.INFERRED)
    case_number = models.CharField(max_length=160, blank=True)
    printed_identifiers = models.JSONField(default=list, blank=True)
    classification_markings = models.JSONField(default=list, blank=True)
    declassification_markings = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True)
    summary_source = models.CharField(max_length=20, choices=SourceType.choices, default=SourceType.EDITORIAL)
    start_page = models.PositiveIntegerField(default=1)
    end_page = models.PositiveIntegerField(default=1)
    has_redactions = models.BooleanField(default=False)
    review_state = models.CharField(max_length=20, choices=ReviewState.choices, default=ReviewState.UNREVIEWED)
    review_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("stable_id",)
        constraints = [models.CheckConstraint(condition=models.Q(end_page__gte=models.F("start_page")), name="valid_document_page_range")]

    def clean(self):
        if self.source_file_id and self.collection_id != self.source_file.collection_id:
            raise ValidationError("Document and source file must belong to the same collection.")
        if self.source_file_id and self.source_file.page_count and self.end_page > self.source_file.page_count:
            raise ValidationError("Document boundary exceeds the source PDF page count.")

    def save(self, *args, **kwargs):
        if not self.stable_id:
            with transaction.atomic():
                Collection.objects.select_for_update().get(pk=self.collection_id)
                last = Document.objects.filter(collection_id=self.collection_id).order_by("-stable_id").values_list("stable_id", flat=True).first()
                sequence = int(last.rsplit("-", 1)[-1]) + 1 if last else 1
                self.stable_id = f"WH-EI-{self.collection.code}-{sequence:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.stable_id} — {self.title}"


class Page(models.Model):
    class Method(models.TextChoices):
        EMBEDDED = "embedded", "Embedded text"
        OCR = "ocr", "OCR"
        NONE = "none", "No text"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="pages")
    source_file = models.ForeignKey(SourceFile, on_delete=models.PROTECT, related_name="pages")
    source_page_number = models.PositiveIntegerField()
    logical_page_number = models.PositiveIntegerField()
    stable_page_id = models.CharField(max_length=48, unique=True, editable=False)
    extracted_text = models.TextField(blank=True)
    ocr_text = models.TextField(blank=True)
    preferred_searchable_text = models.TextField(blank=True)
    page_image = models.FileField(upload_to="derived/page-images/", blank=True, max_length=700)
    printed_page_label = models.CharField(max_length=80, blank=True)
    extraction_method = models.CharField(max_length=20, choices=Method.choices, default=Method.NONE)
    extraction_confidence = models.FloatField(default=0, validators=[MinValueValidator(0), MaxValueValidator(1)])
    has_redactions = models.BooleanField(default=False)
    review_state = models.CharField(max_length=20, choices=ReviewState.choices, default=ReviewState.UNREVIEWED)

    class Meta:
        ordering = ("logical_page_number",)
        constraints = [
            models.UniqueConstraint(fields=("document", "logical_page_number"), name="unique_logical_page"),
            models.UniqueConstraint(fields=("source_file", "source_page_number", "document"), name="unique_source_page_per_document"),
        ]

    def save(self, *args, **kwargs):
        self.stable_page_id = f"{self.document.stable_id}-P{self.logical_page_number:03d}"
        self.preferred_searchable_text = self.ocr_text.strip() or self.extracted_text.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.stable_page_id


class EditorialMetadata(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="metadata_entries")
    field_name = models.CharField(max_length=100)
    value = models.TextField()
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    confidence = models.FloatField(default=1, validators=[MinValueValidator(0), MaxValueValidator(1)])
    reviewed = models.BooleanField(default=False)
    reviewer_notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "editorial metadata"


class Entity(models.Model):
    class Type(models.TextChoices):
        PERSON = "person", "Person"
        ORGANIZATION = "organization", "Organization"
        AGENCY = "government_agency", "Government agency"
        STATE = "state", "State"
        COUNTRY = "country", "Country"
        LOCATION = "location", "Location"
        COMPANY = "company", "Company"
        SOFTWARE = "software_system", "Software system"
        VOTING_SYSTEM = "voting_system", "Voting system"
        INVESTIGATION = "investigation", "Investigation"
        OTHER = "other", "Other"

    name = models.CharField(max_length=300)
    slug = models.SlugField(unique=True)
    entity_type = models.CharField(max_length=30, choices=Type.choices)
    aliases = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    review_state = models.CharField(max_length=20, choices=ReviewState.choices, default=ReviewState.UNREVIEWED)

    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("name", "entity_type"), name="unique_named_entity")]

    def __str__(self):
        return self.name


class EntityMention(models.Model):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="mentions")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="entity_mentions")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="entity_mentions")
    quoted_text = models.TextField(blank=True)
    character_start = models.PositiveIntegerField(null=True, blank=True)
    character_end = models.PositiveIntegerField(null=True, blank=True)
    confidence = models.FloatField(default=1, validators=[MinValueValidator(0), MaxValueValidator(1)])
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    review_state = models.CharField(max_length=20, choices=ReviewState.choices, default=ReviewState.UNREVIEWED)


class Claim(models.Model):
    class Status(models.TextChoices):
        ALLEGATION = "allegation", "Allegation"
        PRELIMINARY = "preliminary_finding", "Preliminary finding"
        ASSESSMENT = "agency_assessment", "Agency assessment"
        CONFIRMED = "confirmed_fact", "Confirmed fact"
        DISPUTED = "disputed", "Disputed"
        CONTRADICTED = "contradicted", "Contradicted"
        UNRESOLVED = "unresolved", "Unresolved"
        WITHDRAWN = "withdrawn", "Withdrawn"

    title = models.CharField(max_length=400)
    slug = models.SlugField(unique=True)
    normalized_claim_text = models.TextField()
    detailed_description = models.TextField(blank=True)
    claimant = models.ForeignKey(Entity, null=True, blank=True, on_delete=models.SET_NULL, related_name="claims_made")
    claim_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ALLEGATION)
    evidence_type = models.CharField(max_length=40, blank=True)
    evidence_strength = models.CharField(max_length=40, blank=True)
    unresolved_questions = models.TextField(blank=True)
    editorial_notes = models.TextField(blank=True)
    review_state = models.CharField(max_length=20, choices=ReviewState.choices, default=ReviewState.UNREVIEWED)

    def __str__(self):
        return self.title


class ClaimCitation(models.Model):
    class Relationship(models.TextChoices):
        SUPPORTS = "supports", "Supports"
        QUALIFIES = "qualifies", "Qualifies"
        CONTRADICTS = "contradicts", "Contradicts"
        MENTIONS = "mentions", "Mentions"
        BACKGROUND = "background", "Background"

    claim = models.ForeignKey(Claim, on_delete=models.CASCADE, related_name="citations")
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="claim_citations")
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name="claim_citations")
    excerpt = models.TextField()
    relationship_type = models.CharField(max_length=20, choices=Relationship.choices)
    editorial_explanation = models.TextField(blank=True)
    review_state = models.CharField(max_length=20, choices=ReviewState.choices, default=ReviewState.UNREVIEWED)

    def clean(self):
        if self.page_id and self.document_id != self.page.document_id:
            raise ValidationError("Citation page must belong to the cited document.")


class DocumentRelationship(models.Model):
    class Type(models.TextChoices):
        ATTACHMENT = "attachment", "Attachment"
        RESPONSE = "response", "Response"
        REFERENCES = "references", "References"
        DUPLICATE = "duplicate", "Duplicate"
        RELATED = "related", "Related"

    source_document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="outgoing_relationships")
    related_document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="incoming_relationships")
    relationship_type = models.CharField(max_length=20, choices=Type.choices)
    explanation = models.TextField(blank=True)
    review_state = models.CharField(max_length=20, choices=ReviewState.choices, default=ReviewState.UNREVIEWED)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("source_document", "related_document", "relationship_type"), name="unique_document_relationship")]
