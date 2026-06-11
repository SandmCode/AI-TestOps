import mimetypes
import os

from django.http import FileResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.testing.services.ai_helpers import ai_error_response
from apps.testing.services.ai_service import AIService, AIServiceError

from .filters import DocumentFilter, ProjectFilter
from .models import Document, Project
from .serializers import (
    DocumentBatchDeleteSerializer,
    DocumentSerializer,
    ProjectBatchDeleteSerializer,
    ProjectSerializer,
)
from .services.chunk_upload import (
    cancel_upload,
    complete_upload,
    get_upload_status,
    init_upload,
    save_chunk,
)
from .services.document_preview import build_preview_payload


ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "md", "markdown", "txt", "json", "yaml", "yml",
    "xml", "csv", "log", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg",
    "xmind", "zip", "rar", "7z",
}


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProjectFilter
    search_fields = ["name", "description", "owner"]
    ordering_fields = ["created_at", "updated_at", "name"]

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        serializer = ProjectBatchDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        deleted, _ = Project.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.select_related("project").all()
    serializer_class = DocumentSerializer
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = DocumentFilter
    search_fields = ["name", "version", "original_name", "content"]
    ordering_fields = ["created_at", "name", "version"]

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        serializer = DocumentBatchDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        docs = Document.objects.filter(id__in=ids)
        for doc in docs:
            if doc.file:
                doc.file.delete(save=False)
        deleted, _ = docs.delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        document = self.get_object()
        data = build_preview_payload(document)
        data.update({
            "id": document.id,
            "name": document.name,
            "version": document.version,
            "doc_type": document.doc_type,
            "doc_type_display": document.get_doc_type_display(),
            "project": document.project_id,
            "project_name": document.project.name,
            "content_note": document.content,
            "created_at": document.created_at,
        })
        return Response(data)

    PREVIEW_CONTENT_TYPES = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "svg": "image/svg+xml",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "json": "application/json",
        "yaml": "text/yaml",
        "yml": "text/yaml",
        "xml": "application/xml",
        "csv": "text/csv",
        "txt": "text/plain",
        "md": "text/markdown",
        "markdown": "text/markdown",
    }

    @action(detail=True, methods=["get"], url_path="preview-file")
    @xframe_options_exempt
    def preview_file(self, request, pk=None):
        """内联预览文件，走 /api 代理，避免 iframe 跨域或直连 8000 端口失败。"""
        document = self.get_object()
        if not document.file:
            return Response({"error": "该文档没有可预览的文件"}, status=status.HTTP_404_NOT_FOUND)

        file_path = document.file.path
        ext = (document.file_ext or os.path.splitext(file_path)[1].lstrip(".")).lower()
        filename = document.original_name or os.path.basename(document.file.name)

        if ext == "doc":
            from .services.office_convert import convert_doc_to_pdf

            pdf_path = convert_doc_to_pdf(file_path)
            if pdf_path:
                file_path = pdf_path
                ext = "pdf"
                filename = f"{os.path.splitext(filename)[0]}.pdf"

        if not os.path.exists(file_path):
            return Response({"error": "文件不存在或已被删除"}, status=status.HTTP_404_NOT_FOUND)

        content_type = self.PREVIEW_CONTENT_TYPES.get(ext) or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        file_handle = open(file_path, "rb")
        response = FileResponse(file_handle, content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        if not document.file:
            return Response({"error": "该文档没有可下载的文件"}, status=status.HTTP_404_NOT_FOUND)
        file_handle = document.file.open("rb")
        filename = document.original_name or os.path.basename(document.file.name)
        response = FileResponse(file_handle, as_attachment=True, filename=filename)
        return response

    def _extract_document_content(self, document):
        from .services.document_preview import read_office_preview, read_text_preview

        content = document.content or ""
        if not document.file:
            return content or document.name
        file_path = document.file.path
        ext = (document.file_ext or "").lower()
        text_exts = (
            Document.PREVIEW_TEXT
            | Document.PREVIEW_MARKDOWN
            | Document.PREVIEW_CODE
            | Document.PREVIEW_CSV
        )
        if ext in text_exts and os.path.exists(file_path):
            return read_text_preview(file_path, ext)
        if ext in ("doc", "docx") and os.path.exists(file_path):
            return read_office_preview(file_path, ext)
        if ext == "pdf":
            try:
                from pypdf import PdfReader

                reader = PdfReader(file_path)
                return "\n".join((page.extract_text() or "") for page in reader.pages[:20])
            except Exception:
                return content or document.name
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()[:8000]
        except Exception:
            return content or document.name

    @action(detail=True, methods=["post"], url_path="ai-parse-detail")
    def ai_parse_detail(self, request, pk=None):
        document = self.get_object()
        content = self._extract_document_content(document)
        try:
            ai = AIService()
            parsed = ai.parse_requirement_detail(content)
        except AIServiceError as exc:
            return ai_error_response(exc)
        return Response({
            "document_id": document.id,
            "document_name": document.name,
            "features": [{**item, "type": "feature"} for item in parsed.get("features", [])],
            "constraints": [{**item, "type": "constraint"} for item in parsed.get("constraints", [])],
            "exceptions": [{**item, "type": "exception"} for item in parsed.get("exceptions", [])],
        })

    @action(detail=True, methods=["post"], url_path="ai-generate-requirements")
    def ai_generate_requirements(self, request, pk=None):
        document = self.get_object()
        content = self._extract_document_content(document)
        try:
            ai = AIService()
            requirements = ai.generate_requirements(content or document.name)
        except AIServiceError as exc:
            return ai_error_response(exc)
        return Response({"requirements": requirements}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="ai-parse-apis")
    def ai_parse_apis(self, request, pk=None):
        from apps.testing.services.api_doc_parse_service import (
            normalize_api_item,
            parse_api_document_content,
        )

        document = self.get_object()
        content = self._extract_document_content(document)
        try:
            interfaces, source = parse_api_document_content(content or document.name)
        except AIServiceError as exc:
            return ai_error_response(exc)
        normalized = []
        for item in interfaces:
            row = normalize_api_item(item)
            if row:
                normalized.append(row)
        if not normalized:
            return Response(
                {"error": "未能从文档中解析出有效接口，请检查文档格式或重试"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({
            "document_id": document.id,
            "document_name": document.name,
            "project_id": document.project_id,
            "parse_source": source,
            "interfaces": normalized,
        })

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        if upload:
            ext = os.path.splitext(upload.name)[1].lstrip(".").lower()
            if ext and ext not in ALLOWED_EXTENSIONS:
                return Response(
                    {"error": f"不支持的文件格式: .{ext}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return super().create(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="chunk-init")
    def chunk_init(self, request):
        try:
            data = init_upload(
                project_id=int(request.data.get("project")),
                filename=request.data.get("filename", ""),
                file_size=int(request.data.get("file_size", 0)),
                form_data={
                    "name": request.data.get("name", ""),
                    "version": request.data.get("version", ""),
                    "doc_type": request.data.get("doc_type", "requirement"),
                    "content": request.data.get("content", ""),
                },
            )
            return Response(data, status=status.HTTP_201_CREATED)
        except Project.DoesNotExist:
            return Response({"error": "项目不存在"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="chunk-status")
    def chunk_status(self, request):
        upload_id = request.query_params.get("upload_id")
        if not upload_id:
            return Response({"error": "缺少 upload_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(get_upload_status(upload_id))
        except Exception:
            return Response({"error": "上传会话不存在"}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["post"], url_path="chunk-upload")
    def chunk_upload(self, request):
        upload_id = request.data.get("upload_id")
        chunk_index = request.data.get("chunk_index")
        chunk = request.FILES.get("chunk")
        if not upload_id or chunk_index is None or not chunk:
            return Response({"error": "参数不完整"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            data = save_chunk(upload_id, int(chunk_index), chunk)
            return Response(data)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="chunk-complete")
    def chunk_complete(self, request):
        upload_id = request.data.get("upload_id")
        if not upload_id:
            return Response({"error": "缺少 upload_id"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            document = complete_upload(upload_id)
            return Response(DocumentSerializer(document).data, status=status.HTTP_201_CREATED)
        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="chunk-cancel")
    def chunk_cancel(self, request):
        upload_id = request.data.get("upload_id")
        if upload_id:
            cancel_upload(upload_id)
        return Response({"cancelled": True})
