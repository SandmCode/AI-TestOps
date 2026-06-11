from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path

from .views import serve_frontend

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.projects.urls")),
    path("api/", include("apps.testing.urls")),
    path("api/", include("apps.tools.urls")),
    path("api/", include("apps.ai_features.urls")),
    re_path(r"^(?!api/|admin/|media/).*$", serve_frontend, name="frontend"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
