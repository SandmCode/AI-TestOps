import json
import os
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.utils import timezone

from apps.projects.models import ChunkUploadSession, Document, Project

CHUNK_SIZE = getattr(settings, "UPLOAD_CHUNK_SIZE", 5 * 1024 * 1024)
MAX_FILE_SIZE = getattr(settings, "UPLOAD_MAX_FILE_SIZE", 10 * 1024 * 1024 * 1024)
CHUNK_ROOT = Path(settings.MEDIA_ROOT) / "chunks"


def _session_dir(upload_id: str) -> Path:
    path = CHUNK_ROOT / upload_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_extension(filename: str):
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    allowed = {
        "pdf", "doc", "docx", "md", "markdown", "txt", "json", "yaml", "yml",
        "xml", "csv", "log", "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg",
        "xmind", "zip", "rar", "7z",
    }
    if ext and ext not in allowed:
        raise ValueError(f"不支持的文件格式: .{ext}")
    return ext


def init_upload(project_id: int, filename: str, file_size: int, form_data: dict) -> dict:
    if file_size <= 0:
        raise ValueError("文件大小无效")
    if file_size > MAX_FILE_SIZE:
        raise ValueError(f"文件超过最大限制 {MAX_FILE_SIZE // (1024 ** 3)} GB")

    _validate_extension(filename)
    project = Project.objects.get(pk=project_id)
    upload_id = uuid.uuid4().hex
    total_chunks = (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE

    session = ChunkUploadSession.objects.create(
        upload_id=upload_id,
        project=project,
        original_name=filename,
        file_size=file_size,
        chunk_size=CHUNK_SIZE,
        total_chunks=total_chunks,
        uploaded_chunks=[],
        form_data=form_data,
        status="uploading",
    )
    _session_dir(upload_id)
    return {
        "upload_id": upload_id,
        "chunk_size": CHUNK_SIZE,
        "total_chunks": total_chunks,
        "uploaded_chunks": [],
    }


def get_upload_status(upload_id: str) -> dict:
    session = ChunkUploadSession.objects.get(upload_id=upload_id, status="uploading")
    uploaded = sorted(session.uploaded_chunks or [])
    progress = round(len(uploaded) / session.total_chunks * 100, 2) if session.total_chunks else 0
    return {
        "upload_id": session.upload_id,
        "original_name": session.original_name,
        "file_size": session.file_size,
        "chunk_size": session.chunk_size,
        "total_chunks": session.total_chunks,
        "uploaded_chunks": uploaded,
        "progress": progress,
        "status": session.status,
        "form_data": session.form_data,
    }


def save_chunk(upload_id: str, chunk_index: int, chunk_file) -> dict:
    session = ChunkUploadSession.objects.get(upload_id=upload_id, status="uploading")
    if chunk_index < 0 or chunk_index >= session.total_chunks:
        raise ValueError("分片索引无效")

    uploaded = set(session.uploaded_chunks or [])
    part_path = _session_dir(upload_id) / f"part_{chunk_index:06d}"

    with open(part_path, "wb") as dest:
        for chunk in chunk_file.chunks():
            dest.write(chunk)

    uploaded.add(chunk_index)
    session.uploaded_chunks = sorted(uploaded)
    session.updated_at = timezone.now()
    session.save(update_fields=["uploaded_chunks", "updated_at"])

    progress = round(len(uploaded) / session.total_chunks * 100, 2)
    return {
        "upload_id": upload_id,
        "chunk_index": chunk_index,
        "uploaded_chunks": session.uploaded_chunks,
        "progress": progress,
        "completed": len(uploaded) == session.total_chunks,
    }


def merge_chunks(session: ChunkUploadSession) -> Document:
    session_dir = _session_dir(session.upload_id)
    merged_path = session_dir / "merged_file"
    uploaded = set(session.uploaded_chunks or [])

    if len(uploaded) != session.total_chunks:
        missing = [i for i in range(session.total_chunks) if i not in uploaded]
        raise ValueError(f"分片不完整，缺少: {missing[:5]}{'...' if len(missing) > 5 else ''}")

    session.status = "merging"
    session.save(update_fields=["status"])

    try:
        with open(merged_path, "wb") as outfile:
            for index in range(session.total_chunks):
                part_path = session_dir / f"part_{index:06d}"
                if not part_path.exists():
                    raise ValueError(f"分片文件丢失: {index}")
                with open(part_path, "rb") as infile:
                    shutil.copyfileobj(infile, outfile)

        actual_size = merged_path.stat().st_size
        if actual_size != session.file_size:
            raise ValueError(f"合并后文件大小不一致，期望 {session.file_size}，实际 {actual_size}")

        form = session.form_data or {}
        document = Document(
            project=session.project,
            name=form.get("name") or session.original_name,
            version=form.get("version", ""),
            doc_type=form.get("doc_type", "requirement"),
            content=form.get("content", ""),
            original_name=session.original_name,
        )
        with open(merged_path, "rb") as merged_file:
            document.file.save(session.original_name, File(merged_file), save=True)

        session.status = "completed"
        session.document = document
        session.save(update_fields=["status", "document"])
        cleanup_chunks(session.upload_id)
        return document
    except Exception:
        session.status = "failed"
        session.save(update_fields=["status"])
        raise


def complete_upload(upload_id: str) -> Document:
    session = ChunkUploadSession.objects.get(upload_id=upload_id)
    if session.status == "completed" and session.document_id:
        return session.document
    if session.status != "uploading":
        raise ValueError(f"上传会话状态异常: {session.status}")
    return merge_chunks(session)


def cancel_upload(upload_id: str):
    try:
        session = ChunkUploadSession.objects.get(upload_id=upload_id)
        session.status = "cancelled"
        session.save(update_fields=["status"])
    except ChunkUploadSession.DoesNotExist:
        pass
    cleanup_chunks(upload_id)


def cleanup_chunks(upload_id: str):
    session_dir = CHUNK_ROOT / upload_id
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)
