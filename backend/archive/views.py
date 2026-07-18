import re

from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import Count, F, Q, Sum
from django.http import FileResponse, Http404
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .models import Claim, ClaimCitation, Collection, Document, DocumentRelationship, Entity, EntityMention, Page, SourceFile
from .serializers import (
    ClaimCitationSerializer, ClaimSerializer, CollectionSerializer, DocumentRelationshipSerializer,
    DocumentSerializer, EntityMentionSerializer, EntitySerializer, PageSerializer,
    SearchResultSerializer, SourceFileSerializer,
)


class ReadOnlyUnlessStaff(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.method in permissions.SAFE_METHODS or (request.user.is_authenticated and request.user.is_staff)


class BaseViewSet(viewsets.ModelViewSet):
    permission_classes = (ReadOnlyUnlessStaff,)
    filter_backends = (filters.OrderingFilter,)


class CollectionViewSet(BaseViewSet):
    serializer_class = CollectionSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return Collection.objects.annotate(document_count=Count("documents", distinct=True), page_count=Count("documents__pages", distinct=True)).order_by("display_order", "title")


class DocumentViewSet(BaseViewSet):
    serializer_class = DocumentSerializer
    lookup_field = "stable_id"
    queryset = Document.objects.select_related("collection", "source_file")

    def get_queryset(self):
        queryset = super().get_queryset()
        filter_fields = {
            "collection": "collection__slug",
            "agency": "originating_agency",
            "document_type": "document_type",
            "review_state": "review_state",
        }
        for parameter, field in filter_fields.items():
            value = self.request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{field: value})
        return queryset

    @action(detail=True, methods=("get",))
    def pages(self, request, stable_id=None):
        pages = self.get_object().pages.all()
        return Response(PageSerializer(pages, many=True, context={"request": request}).data)


class PageViewSet(BaseViewSet):
    serializer_class = PageSerializer
    queryset = Page.objects.select_related("document", "source_file")


class SourceFileViewSet(BaseViewSet):
    serializer_class = SourceFileSerializer
    queryset = SourceFile.objects.select_related("collection")

    @action(detail=True, methods=("get",))
    def download(self, request, pk=None):
        source = self.get_object()
        if not source.stored_file:
            raise Http404
        as_attachment = request.query_params.get("download") == "1"
        response = FileResponse(
            source.stored_file.open("rb"),
            content_type=source.mime_type,
            as_attachment=as_attachment,
            filename=source.original_filename,
        )
        response["X-Content-Type-Options"] = "nosniff"
        return response


class EntityViewSet(BaseViewSet):
    serializer_class = EntitySerializer
    lookup_field = "slug"
    queryset = Entity.objects.all()


class EntityMentionViewSet(BaseViewSet):
    serializer_class = EntityMentionSerializer
    queryset = EntityMention.objects.select_related("entity", "document", "page")


class ClaimViewSet(BaseViewSet):
    serializer_class = ClaimSerializer
    lookup_field = "slug"
    queryset = Claim.objects.select_related("claimant").prefetch_related("citations__document", "citations__page")


class ClaimCitationViewSet(BaseViewSet):
    serializer_class = ClaimCitationSerializer
    queryset = ClaimCitation.objects.select_related("claim", "document", "page")


class RelationshipViewSet(BaseViewSet):
    serializer_class = DocumentRelationshipSerializer
    queryset = DocumentRelationship.objects.select_related("source_document", "related_document")


def plain_excerpt(text, query, length=260):
    text = re.sub(r"\s+", " ", text or "").strip()
    if not query:
        return text[:length]
    index = text.lower().find(query.lower())
    start = max(index - 80, 0) if index >= 0 else 0
    excerpt = text[start:start + length]
    return ("…" if start else "") + excerpt + ("…" if start + length < len(text) else "")


@api_view(("GET",))
@permission_classes((permissions.AllowAny,))
def search(request):
    query_text = request.query_params.get("q", "").strip()
    pages = Page.objects.select_related("document__collection", "document")
    filters_map = {
        "collection": "document__collection__slug",
        "agency": "document__originating_agency",
        "document_type": "document__document_type",
        "state": "entity_mentions__entity__name",
        "country": "entity_mentions__entity__name",
        "entity": "entity_mentions__entity__slug",
        "claim_status": "claim_citations__claim__status",
        "evidence_type": "claim_citations__claim__evidence_type",
        "extraction_method": "extraction_method",
    }
    for parameter, field in filters_map.items():
        value = request.query_params.get(parameter)
        if value:
            pages = pages.filter(**{field: value})
    if request.query_params.get("reviewed") in {"true", "false"}:
        pages = pages.filter(review_state="reviewed" if request.query_params["reviewed"] == "true" else "unreviewed")
    if request.query_params.get("redactions") == "true":
        pages = pages.filter(Q(has_redactions=True) | Q(document__has_redactions=True))
    if request.query_params.get("date_from"):
        pages = pages.filter(document__document_date__gte=request.query_params["date_from"])
    if request.query_params.get("date_to"):
        pages = pages.filter(document__document_date__lte=request.query_params["date_to"])

    if query_text:
        if connection.vendor == "postgresql":
            page_vector = (
                SearchVector("preferred_searchable_text", weight="A") +
                SearchVector("claim_citations__claim__title", weight="B") +
                SearchVector("claim_citations__claim__normalized_claim_text", weight="B") +
                SearchVector("entity_mentions__entity__name", weight="B")
            )
            document_vector = (
                SearchVector("document__title", weight="A") +
                SearchVector("document__summary", weight="B") +
                SearchVector("document__originating_agency", weight="C") +
                SearchVector("document__document_type", weight="C") +
                SearchVector("document__printed_identifiers", weight="C")
            )
            search_query = SearchQuery(query_text, search_type="websearch")
            pages = pages.annotate(
                page_rank=SearchRank(page_vector, search_query),
                document_rank=SearchRank(document_vector, search_query),
            ).filter(
                Q(page_rank__gte=0.01) | Q(logical_page_number=1, document_rank__gte=0.01)
            ).annotate(rank=F("page_rank") + F("document_rank")).order_by("-rank")
        else:
            pages = pages.filter(
                Q(preferred_searchable_text__icontains=query_text) |
                Q(entity_mentions__entity__name__icontains=query_text) |
                Q(claim_citations__claim__title__icontains=query_text) |
                Q(claim_citations__claim__normalized_claim_text__icontains=query_text) |
                Q(
                    Q(logical_page_number=1),
                    Q(document__title__icontains=query_text) |
                    Q(document__summary__icontains=query_text) |
                    Q(document__originating_agency__icontains=query_text) |
                    Q(document__document_type__icontains=query_text) |
                    Q(document__printed_identifiers__icontains=query_text),
                )
            )
    else:
        pages = pages.order_by("document__stable_id", "logical_page_number")
    pages = pages.distinct()
    paginator = PageNumberPagination()
    page_items = paginator.paginate_queryset(pages, request)
    results = [{
        "document_id": page.document.stable_id,
        "document_title": page.document.title,
        "collection_slug": page.document.collection.slug,
        "collection_title": page.document.collection.title,
        "page_number": page.logical_page_number,
        "stable_page_id": page.stable_page_id,
        "excerpt": plain_excerpt(page.preferred_searchable_text, query_text),
        "agency": page.document.originating_agency,
        "document_type": page.document.document_type,
        "document_date": page.document.document_date,
        "extraction_method": page.extraction_method,
        "reviewed": page.review_state == "reviewed",
        "page_url": f"/documents/{page.document.stable_id}/pages/{page.logical_page_number}",
    } for page in page_items]
    return paginator.get_paginated_response(SearchResultSerializer(results, many=True).data)


@api_view(("GET",))
@permission_classes((permissions.AllowAny,))
def statistics(request):
    totals = {
        "source_files": SourceFile.objects.filter(import_status=SourceFile.Status.COMPLETE).count(),
        "documents": Document.objects.count(),
        "pages": Page.objects.count(),
        "searchable_pages": Page.objects.exclude(preferred_searchable_text="").count(),
        "ocr_pending_pages": Page.objects.filter(extraction_method=Page.Method.NONE).count(),
        "reviewed_documents": Document.objects.filter(review_state="reviewed").count(),
    }
    recent = DocumentSerializer(Document.objects.select_related("collection", "source_file").order_by("-created_at")[:6], many=True, context={"request": request}).data
    return Response({"totals": totals, "recent_documents": recent})
