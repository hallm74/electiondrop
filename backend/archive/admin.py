from django.contrib import admin

from .models import (
    Claim, ClaimCitation, Collection, Document, DocumentRelationship, EditorialMetadata,
    Entity, EntityMention, ImportRun, Page, RedactionFinding, SourceFile,
)


class PageInline(admin.TabularInline):
    model = Page
    extra = 0
    fields = ("stable_page_id", "source_page_number", "logical_page_number", "printed_page_label", "extraction_method", "review_state")
    readonly_fields = ("stable_page_id", "extraction_method")
    show_change_link = True


class MetadataInline(admin.TabularInline):
    model = EditorialMetadata
    extra = 0


class CitationInline(admin.TabularInline):
    model = ClaimCitation
    extra = 0
    autocomplete_fields = ("document", "page")


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "display_order")
    list_editable = ("display_order",)
    search_fields = ("title", "description")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(SourceFile)
class SourceFileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "collection", "page_count", "import_status", "extraction_status", "ocr_required", "imported_at")
    list_filter = ("collection", "import_status", "extraction_status", "ocr_status", "contains_embedded_text", "ocr_required")
    search_fields = ("original_filename", "sha256", "error_details")
    readonly_fields = ("sha256", "size", "mime_type", "page_count", "pdf_metadata", "imported_at", "stored_file")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("stable_id", "title", "collection", "originating_agency", "document_date", "start_page", "end_page", "review_state")
    list_filter = ("collection", "review_state", "title_source", "date_source", "document_type", "originating_agency", "has_redactions")
    search_fields = ("stable_id", "title", "summary", "case_number", "originating_agency")
    readonly_fields = ("stable_id", "created_at")
    autocomplete_fields = ("source_file",)
    inlines = (MetadataInline, PageInline)
    fieldsets = (
        ("Source boundary", {"fields": ("stable_id", "collection", "source_file", "start_page", "end_page")}),
        ("Descriptive metadata", {"fields": ("title", "title_source", "document_type", "originating_agency", "agency_source", "document_date", "date_precision", "date_source", "summary", "summary_source")}),
        ("Printed markings", {"fields": ("case_number", "printed_identifiers", "classification_markings", "declassification_markings", "has_redactions")}),
        ("Review", {"fields": ("review_state", "review_notes", "created_at")}),
    )


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("stable_page_id", "document", "source_page_number", "extraction_method", "extraction_confidence", "review_state")
    list_filter = ("extraction_method", "review_state", "has_redactions", "document__collection")
    search_fields = ("stable_page_id", "extracted_text", "ocr_text", "printed_page_label")
    readonly_fields = ("stable_page_id", "preferred_searchable_text")
    autocomplete_fields = ("document", "source_file")


@admin.register(RedactionFinding)
class RedactionFindingAdmin(admin.ModelAdmin):
    list_display = ("page", "method", "review_state", "published", "created_at")
    list_filter = ("method", "review_state", "published", "page__document__collection")
    search_fields = ("page__stable_page_id", "page__document__stable_id", "recovered_text", "public_explanation")
    autocomplete_fields = ("page",)
    readonly_fields = ("created_at",)


@admin.register(Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("name", "entity_type", "review_state")
    list_filter = ("entity_type", "review_state")
    search_fields = ("name", "aliases", "description")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(EntityMention)
class EntityMentionAdmin(admin.ModelAdmin):
    list_display = ("entity", "document", "page", "source_type", "confidence", "review_state")
    list_filter = ("source_type", "review_state", "entity__entity_type")
    search_fields = ("entity__name", "document__stable_id", "quoted_text")
    autocomplete_fields = ("entity", "document", "page")


@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ("title", "claimant", "status", "evidence_type", "review_state")
    list_filter = ("status", "evidence_type", "evidence_strength", "review_state")
    search_fields = ("title", "normalized_claim_text", "detailed_description", "editorial_notes")
    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("claimant",)
    inlines = (CitationInline,)


@admin.register(ClaimCitation)
class ClaimCitationAdmin(admin.ModelAdmin):
    list_display = ("claim", "document", "page", "relationship_type", "review_state")
    list_filter = ("relationship_type", "review_state")
    search_fields = ("claim__title", "document__stable_id", "excerpt", "editorial_explanation")
    autocomplete_fields = ("claim", "document", "page")


@admin.register(DocumentRelationship)
class DocumentRelationshipAdmin(admin.ModelAdmin):
    list_display = ("source_document", "relationship_type", "related_document", "review_state")
    list_filter = ("relationship_type", "review_state")
    autocomplete_fields = ("source_document", "related_document")


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ("id", "path_label", "started_at", "completed_at", "files_imported", "duplicates", "errors")
    readonly_fields = ("path_label", "started_at", "completed_at", "files_seen", "files_imported", "duplicates", "errors", "log")

admin.site.site_header = "Election Release Archive — Review"
admin.site.site_title = "Archive Review"
admin.site.index_title = "Source review and editorial workflow"
