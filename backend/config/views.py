from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.views.static import serve


def serve_frontend(request, resource_path=""):
    dist: Path = settings.FRONTEND_DIST
    index_file = dist / "index.html"

    if resource_path:
        target = dist / resource_path
        if target.is_file():
            return serve(request, resource_path, document_root=dist)

    if index_file.is_file():
        return FileResponse(index_file.open("rb"), content_type="text/html")

    if settings.DEBUG:
        return HttpResponseRedirect(settings.FRONTEND_DEV_URL)

    raise Http404("前端资源未找到，请先在 frontend 目录执行 npm run build")
