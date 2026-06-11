import os
import uuid

from django.db import models


def document_upload_path(instance, filename):
    safe_name = os.path.basename(filename)
    return f"documents/project_{instance.project_id}/{uuid.uuid4().hex}_{safe_name}"


class Project(models.Model):
    name = models.CharField("项目名称", max_length=200)
    description = models.TextField("项目描述", blank=True)
    owner = models.CharField("项目负责人", max_length=100, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "项目"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Document(models.Model):
    DOC_TYPE_CHOICES = [
        ("requirement", "需求文档"),
        ("api", "接口文档"),
        ("prd", "PRD文档"),
        ("prototype", "原型图"),
        ("other", "其他"),
    ]

    PREVIEW_TEXT = {"txt", "log"}
    PREVIEW_MARKDOWN = {"md", "markdown"}
    PREVIEW_CODE = {"json", "yaml", "yml", "xml"}
    PREVIEW_CSV = {"csv"}
    PREVIEW_ARCHIVE = {"zip"}
    PREVIEW_IMAGE = {"png", "jpg", "jpeg", "gif", "webp", "bmp", "svg"}
    PREVIEW_PDF = {"pdf"}

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="documents", verbose_name="所属项目"
    )
    name = models.CharField("文档名称", max_length=200)
    version = models.CharField("文档版本", max_length=50, blank=True)
    doc_type = models.CharField("文档类型", max_length=20, choices=DOC_TYPE_CHOICES, default="requirement")
    file = models.FileField("文档文件", upload_to=document_upload_path, blank=True, null=True)
    original_name = models.CharField("原始文件名", max_length=255, blank=True)
    file_ext = models.CharField("文件扩展名", max_length=20, blank=True)
    file_size = models.PositiveIntegerField("文件大小(字节)", default=0)
    content = models.TextField("补充说明", blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "需求文档"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.file and self.file.name:
            base = os.path.basename(self.file.name)
            self.original_name = self.original_name or base
            ext = os.path.splitext(base)[1].lstrip(".").lower()
            self.file_ext = ext
            try:
                self.file_size = self.file.size
            except Exception:
                pass
            if not self.pk:
                self._auto_doc_type(ext)
        super().save(*args, **kwargs)

    def _auto_doc_type(self, ext: str):
        if ext in ("json", "yaml", "yml"):
            self.doc_type = "api"
        elif ext in self.PREVIEW_IMAGE:
            self.doc_type = "prototype"
        elif ext in ("doc", "docx", "pdf", "md", "txt"):
            self.doc_type = "requirement"

    @property
    def preview_mode(self) -> str:
        ext = (self.file_ext or "").lower()
        if ext in self.PREVIEW_PDF:
            return "pdf"
        if ext in self.PREVIEW_IMAGE:
            return "image"
        if ext in self.PREVIEW_MARKDOWN:
            return "markdown"
        if ext in self.PREVIEW_CODE:
            return "code"
        if ext in self.PREVIEW_CSV:
            return "csv"
        if ext in self.PREVIEW_ARCHIVE:
            return "archive"
        if ext in self.PREVIEW_TEXT:
            return "text"
        if ext == "docx":
            return "docx"
        if ext == "doc":
            return "doc"
        return "download"

    @property
    def file_url(self) -> str:
        if self.file:
            return self.file.url
        return ""


class ChunkUploadSession(models.Model):
    STATUS_CHOICES = [
        ("uploading", "上传中"),
        ("merging", "合并中"),
        ("completed", "已完成"),
        ("failed", "失败"),
        ("cancelled", "已取消"),
    ]

    upload_id = models.CharField("上传ID", max_length=64, unique=True, db_index=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="chunk_uploads")
    original_name = models.CharField("原始文件名", max_length=255)
    file_size = models.BigIntegerField("文件大小")
    chunk_size = models.PositiveIntegerField("分片大小")
    total_chunks = models.PositiveIntegerField("总分片数")
    uploaded_chunks = models.JSONField("已上传分片", default=list, blank=True)
    form_data = models.JSONField("表单数据", default=dict, blank=True)
    status = models.CharField("状态", max_length=20, choices=STATUS_CHOICES, default="uploading")
    document = models.ForeignKey(
        Document, on_delete=models.SET_NULL, null=True, blank=True, related_name="chunk_session"
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "分片上传会话"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.original_name} ({self.upload_id})"
