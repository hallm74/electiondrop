from rest_framework import serializers

from .models import (
    Claim, ClaimCitation, Collection, Document, DocumentRelationship, Entity,
    EntityMention, Page, RedactionFinding, SourceFile,
)


class CollectionSerializer(serializers.ModelSerializer):
    document_count = serializers.IntegerField(read_only=True)
    page_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Collection
        fields = ("id", "slug", "code", "title", "description", "source_url", "display_order", "document_count", "page_count")


class SourceFileSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = SourceFile
        exclude = ("stored_file", "error_details", "import_run")

    def get_download_url(self, obj):
        request = self.context.get("request")
        path = f"/api/source-files/{obj.pk}/download/"
        return request.build_absolute_uri(path) if request else path


class PageSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = ("stable_page_id", "source_page_number", "logical_page_number", "printed_page_label", "extraction_method", "review_state")


class DocumentSerializer(serializers.ModelSerializer):
    collection = CollectionSerializer(read_only=True)
    source_filename = serializers.CharField(source="source_file.original_filename", read_only=True)
    source_sha256 = serializers.CharField(source="source_file.sha256", read_only=True)
    page_count = serializers.IntegerField(source="pages.count", read_only=True)

    class Meta:
        model = Document
        fields = "__all__"


class PageSerializer(serializers.ModelSerializer):
    document_stable_id = serializers.CharField(source="document.stable_id", read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Page
        fields = "__all__"

    def get_image_url(self, obj):
        if not obj.page_image:
            return ""
        request = self.context.get("request")
        return request.build_absolute_uri(obj.page_image.url) if request else obj.page_image.url


class RedactionFindingSerializer(serializers.ModelSerializer):
    stable_page_id = serializers.CharField(source="page.stable_page_id", read_only=True)
    page_number = serializers.IntegerField(source="page.logical_page_number", read_only=True)
    document_id = serializers.CharField(source="page.document.stable_id", read_only=True)
    document_title = serializers.CharField(source="page.document.title", read_only=True)
    collection_title = serializers.CharField(source="page.document.collection.title", read_only=True)
    source_sha256 = serializers.CharField(source="page.source_file.sha256", read_only=True)
    method_label = serializers.CharField(source="get_method_display", read_only=True)
    page_url = serializers.SerializerMethodField()

    class Meta:
        model = RedactionFinding
        fields = (
            "id", "stable_page_id", "page_number", "document_id", "document_title",
            "collection_title", "source_sha256", "method", "method_label", "recovered_text",
            "public_explanation", "technical_basis", "coordinates", "page_url",
        )

    def get_page_url(self, obj):
        return f"/documents/{obj.page.document.stable_id}/pages/{obj.page.logical_page_number}"


class EntitySerializer(serializers.ModelSerializer):
    mention_count = serializers.IntegerField(source="mentions.count", read_only=True)

    class Meta:
        model = Entity
        fields = "__all__"


class EntityMentionSerializer(serializers.ModelSerializer):
    entity_name = serializers.CharField(source="entity.name", read_only=True)
    document_stable_id = serializers.CharField(source="document.stable_id", read_only=True)
    stable_page_id = serializers.CharField(source="page.stable_page_id", read_only=True)

    class Meta:
        model = EntityMention
        fields = "__all__"


class ClaimCitationSerializer(serializers.ModelSerializer):
    document_stable_id = serializers.CharField(source="document.stable_id", read_only=True)
    stable_page_id = serializers.CharField(source="page.stable_page_id", read_only=True)
    page_url = serializers.SerializerMethodField()

    class Meta:
        model = ClaimCitation
        fields = "__all__"

    def get_page_url(self, obj):
        return f"/documents/{obj.document.stable_id}/pages/{obj.page.logical_page_number}"


class ClaimSerializer(serializers.ModelSerializer):
    citations = ClaimCitationSerializer(many=True, read_only=True)
    claimant_name = serializers.CharField(source="claimant.name", read_only=True, allow_null=True)

    class Meta:
        model = Claim
        fields = "__all__"


class DocumentRelationshipSerializer(serializers.ModelSerializer):
    source_stable_id = serializers.CharField(source="source_document.stable_id", read_only=True)
    related_stable_id = serializers.CharField(source="related_document.stable_id", read_only=True)

    class Meta:
        model = DocumentRelationship
        fields = "__all__"


class SearchResultSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    document_title = serializers.CharField()
    collection_slug = serializers.CharField()
    collection_title = serializers.CharField()
    page_number = serializers.IntegerField()
    stable_page_id = serializers.CharField()
    excerpt = serializers.CharField()
    agency = serializers.CharField()
    document_type = serializers.CharField()
    document_date = serializers.DateField(allow_null=True)
    extraction_method = serializers.CharField()
    reviewed = serializers.BooleanField()
    page_url = serializers.CharField()
