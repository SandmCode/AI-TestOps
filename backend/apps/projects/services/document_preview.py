import json
import os
import zipfile

import yaml

from .office_convert import convert_doc_to_pdf

def preview_file_api_url(document_id: int) -> str:
    return f"/api/documents/{document_id}/preview-file/"


CODE_LANGUAGE = {
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "xml": "xml",
    "log": "plaintext",
}


def read_raw_text(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def read_text_preview(file_path: str, ext: str) -> str:
    raw = read_raw_text(file_path)

    if ext == "json":
        try:
            return json.dumps(json.loads(raw), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            return raw

    if ext in ("yaml", "yml"):
        try:
            data = yaml.safe_load(raw)
            return yaml.dump(data, allow_unicode=True, default_flow_style=False)
        except Exception:
            return raw

    return raw


def read_office_preview(file_path: str, ext: str) -> str:
    if ext == "docx":
        try:
            from docx import Document as DocxDocument

            doc = DocxDocument(file_path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs) or "文档为空或无法提取文本，请下载原文件查看。"
        except ImportError:
            return "未安装 python-docx，请下载原文件查看。"
        except Exception as exc:
            return f"Word 预览提取失败: {exc}，请下载原文件查看。"

    if ext == "doc":
        return "旧版 .doc 格式暂不支持在线预览，请下载原文件查看。"

    return "暂不支持该格式在线预览，请下载原文件查看。"


def read_archive_preview(file_path: str, ext: str) -> dict:
    if ext != "zip":
        return {"files": [], "total": 0, "message": "该压缩格式暂不支持在线预览"}

    try:
        with zipfile.ZipFile(file_path) as zf:
            files = []
            for info in zf.infolist()[:300]:
                files.append({
                    "name": info.filename,
                    "size": info.file_size,
                    "compressed_size": info.compress_size,
                    "is_dir": info.is_dir(),
                })
            return {"files": files, "total": len(zf.infolist())}
    except Exception as exc:
        return {"files": [], "total": 0, "message": f"压缩包读取失败: {exc}"}


def build_preview_payload(document) -> dict:
    if not document.file:
        return {
            "preview_mode": "text",
            "content": document.content or "暂无文件内容",
            "raw_content": document.content or "",
            "file_url": "",
            "download_url": "",
        }

    file_path = document.file.path
    ext = (document.file_ext or os.path.splitext(file_path)[1].lstrip(".")).lower()
    mode = document.preview_mode

    payload = {
        "preview_mode": mode,
        "file_url": preview_file_api_url(document.id),
        "download_url": f"/api/documents/{document.id}/download/",
        "file_ext": ext,
        "original_name": document.original_name,
        "file_size": document.file_size,
        "content": "",
        "raw_content": "",
        "code_language": CODE_LANGUAGE.get(ext, ""),
    }

    if not os.path.exists(file_path):
        payload["content"] = document.content or "文件不存在或已被删除"
        return payload

    if ext == "docx":
        payload["preview_mode"] = "docx"
        payload["content"] = read_office_preview(file_path, ext)
        payload["raw_content"] = payload["content"]
    elif ext == "doc":
        pdf_path = convert_doc_to_pdf(file_path)
        if pdf_path:
            payload["preview_mode"] = "pdf"
            payload["converted_preview"] = True
            payload["content"] = read_office_preview(file_path, ext)
            payload["raw_content"] = payload["content"]
        else:
            payload["preview_mode"] = "office"
            payload["content"] = read_office_preview(file_path, ext)
            payload["raw_content"] = payload["content"]
    elif ext in document.PREVIEW_MARKDOWN:
        payload["raw_content"] = read_raw_text(file_path)
        payload["content"] = payload["raw_content"]
    elif ext in document.PREVIEW_CODE:
        payload["raw_content"] = read_raw_text(file_path)
        payload["content"] = read_text_preview(file_path, ext)
        payload["code_language"] = CODE_LANGUAGE.get(ext, "plaintext")
    elif ext in document.PREVIEW_CSV:
        payload["raw_content"] = read_raw_text(file_path)
        payload["content"] = payload["raw_content"]
    elif ext in document.PREVIEW_ARCHIVE:
        payload["archive"] = read_archive_preview(file_path, ext)
        payload["content"] = document.content or ""
    elif ext in document.PREVIEW_TEXT:
        payload["raw_content"] = read_raw_text(file_path)
        payload["content"] = payload["raw_content"]
    elif mode == "download":
        payload["content"] = document.content or "该文件类型暂不支持在线预览，请下载查看。"

    return payload
