import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

PREVIEW_CACHE = Path(settings.MEDIA_ROOT) / "preview_cache"


def _find_soffice() -> str | None:
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def convert_doc_to_pdf(source_path: str) -> str | None:
    """将旧版 .doc 转为 PDF，用于浏览器预览。需要本机安装 LibreOffice。"""
    if not source_path.lower().endswith(".doc"):
        return None
    if not os.path.exists(source_path):
        return None

    PREVIEW_CACHE.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.md5(
        f"{source_path}_{os.path.getmtime(source_path)}_{os.path.getsize(source_path)}".encode()
    ).hexdigest()
    out_pdf = PREVIEW_CACHE / f"{cache_key}.pdf"
    if out_pdf.exists():
        return str(out_pdf)

    soffice = _find_soffice()
    if not soffice:
        return None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir", tmp, source_path],
                check=True,
                timeout=180,
                capture_output=True,
            )
            base = os.path.splitext(os.path.basename(source_path))[0]
            converted = os.path.join(tmp, f"{base}.pdf")
            if os.path.exists(converted):
                shutil.copy2(converted, out_pdf)
                return str(out_pdf)
    except Exception as exc:
        logger.warning("doc to pdf conversion failed: %s", exc)
    return None


def preview_cache_url(pdf_path: str) -> str:
    relative = os.path.relpath(pdf_path, settings.MEDIA_ROOT).replace("\\", "/")
    return f"{settings.MEDIA_URL}{relative}"
