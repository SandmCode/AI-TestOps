from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet, ProjectViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet)
router.register("documents", DocumentViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
