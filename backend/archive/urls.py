from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("collections", views.CollectionViewSet, basename="collection")
router.register("documents", views.DocumentViewSet, basename="document")
router.register("pages", views.PageViewSet, basename="page")
router.register("source-files", views.SourceFileViewSet, basename="source-file")
router.register("entities", views.EntityViewSet, basename="entity")
router.register("entity-mentions", views.EntityMentionViewSet, basename="entity-mention")
router.register("claims", views.ClaimViewSet, basename="claim")
router.register("claim-citations", views.ClaimCitationViewSet, basename="claim-citation")
router.register("document-relationships", views.RelationshipViewSet, basename="document-relationship")

urlpatterns = [
    path("topics/", views.topics, name="topics"),
    path("redaction-audit/", views.redaction_audit, name="redaction-audit"),
    path("", include(router.urls)),
    path("search/", views.search, name="search"),
    path("statistics/", views.statistics, name="statistics"),
]
