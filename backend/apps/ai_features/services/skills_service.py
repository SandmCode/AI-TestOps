"""Skills 上传解析与入库。"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any


def slugify_folder_name(name: str) -> str:
    base = name.rsplit(".", 1)[0] if "." in name else name
    slug = re.sub(r"[^\w\-]", "-", base.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "skill"


def parse_md_upload(file_obj, name: str = "", folder_name: str = "") -> dict[str, str]:
    content = file_obj.read().decode("utf-8", errors="ignore")
    if not content.strip():
        raise ValueError("SKILL.md 内容为空")
    fname = folder_name or slugify_folder_name(getattr(file_obj, "name", "skill"))
    display = name or fname.replace("-", " ").title()
    return {
        "name": display,
        "folder_name": fname,
        "content": content,
        "source_path": f"upload://{fname}",
    }


def parse_zip_upload(file_obj) -> list[dict[str, str]]:
    raw = file_obj.read()
    skills: list[dict[str, str]] = []
    seen: set[str] = set()

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            normalized = info.filename.replace("\\", "/")
            if not normalized.lower().endswith("skill.md"):
                continue
            parts = normalized.strip("/").split("/")
            folder = parts[-2] if len(parts) >= 2 else slugify_folder_name(parts[-1])
            if folder in seen:
                continue
            seen.add(folder)
            content = zf.read(info).decode("utf-8", errors="ignore")
            if not content.strip():
                continue
            skills.append(
                {
                    "name": folder.replace("-", " ").title(),
                    "folder_name": folder,
                    "content": content,
                    "source_path": f"upload://{folder}",
                }
            )

    if not skills:
        raise ValueError("ZIP 中未找到 SKILL.md，请按「文件夹/SKILL.md」结构打包")
    return skills


def upsert_skill(item: dict[str, Any], source_type: str = "manual"):
    from apps.ai_features.models import AISkill

    obj, created = AISkill.objects.update_or_create(
        folder_name=item["folder_name"],
        source_path=item.get("source_path") or f"upload://{item['folder_name']}",
        defaults={
            "name": item["name"],
            "content": item["content"],
            "source_type": source_type,
            "is_enabled": item.get("is_enabled", True),
        },
    )
    return obj, created


def get_skills_prompt_prefix() -> str:
    from apps.ai_features.models import AISkill, AISkillsSettings

    settings = AISkillsSettings.get_solo()
    if not settings.skills_enabled:
        return ""

    skills = AISkill.objects.filter(is_enabled=True).order_by("sort_order", "name")
    if not skills.exists():
        return ""

    blocks = []
    for skill in skills:
        content = (skill.content or "").strip()
        if not content:
            continue
        blocks.append(f"### Skill: {skill.name}\n{content}")

    if not blocks:
        return ""

    joined = "\n\n".join(blocks)
    max_chars = 12000
    if len(joined) > max_chars:
        joined = joined[:max_chars] + "\n\n...(后续 Skills 内容已截断)"
    return (
        "以下 Skills 文档定义了你在执行任务时应遵循的能力与规范，请优先参考：\n\n"
        f"{joined}\n\n---\n\n"
    )
