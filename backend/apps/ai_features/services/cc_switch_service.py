"""从本地 CC Switch 读取大模型 Provider 配置。"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CCSwitchProvider:
    id: str
    name: str
    is_current: bool
    app_type: str
    provider_type: str
    api_key: str
    base_url: str
    model: str
    source_app: str
    mapped_provider: str = "custom"


class CCSwitchService:
    DB_NAME = "cc-switch.db"
    SETTINGS_NAME = "settings.json"

    OPENAI_COMPAT_BASE_MAP = {
        "https://api.deepseek.com/anthropic": "https://api.deepseek.com/v1",
        "https://api.deepseek.com": "https://api.deepseek.com/v1",
    }

    KEY_FIELDS = (
        "OPENAI_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "CODEX_API_KEY",
        "API_KEY",
    )
    URL_FIELDS = (
        "OPENAI_BASE_URL",
        "ANTHROPIC_BASE_URL",
        "GEMINI_BASE_URL",
        "BASE_URL",
    )
    MODEL_FIELDS = (
        "OPENAI_MODEL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "GEMINI_MODEL",
        "MODEL",
    )

    def __init__(self, root: Path | None = None):
        self.root = root or (Path.home() / ".cc-switch")
        self.db_path = self.root / self.DB_NAME
        self.settings_path = self.root / self.SETTINGS_NAME

    @property
    def available(self) -> bool:
        return self.db_path.is_file()

    def get_status(self) -> dict[str, Any]:
        if not self.available:
            return {
                "available": False,
                "path": str(self.root),
                "message": "未检测到 CC Switch，请确认已安装并在 ~/.cc-switch 生成配置",
            }
        settings = self._load_settings()
        providers = self.list_providers()
        current = [p for p in providers if p["is_current"]]
        return {
            "available": True,
            "path": str(self.root),
            "settings_path": str(self.settings_path),
            "provider_count": len(providers),
            "current_providers": current,
            "current_claude_id": settings.get("currentProviderClaude"),
            "current_codex_id": settings.get("currentProviderCodex"),
        }

    def list_providers(self) -> list[dict[str, Any]]:
        if not self.available:
            return []
        settings = self._load_settings()
        current_ids = {
            settings.get("currentProviderClaude"),
            settings.get("currentProviderCodex"),
            settings.get("currentProviderGemini"),
            settings.get("currentProviderOpenCode"),
        }
        current_ids.discard(None)

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, app_type, provider_type, is_current, settings_config
                FROM providers
                ORDER BY is_current DESC, sort_index ASC, name ASC
                """
            ).fetchall()

        result = []
        for row in rows:
            parsed = self._parse_settings_config(row["settings_config"])
            result.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "app_type": row["app_type"],
                    "provider_type": row["provider_type"] or "",
                    "is_current": bool(row["is_current"]) or row["id"] in current_ids,
                    "has_api_key": bool(parsed.get("api_key")),
                    "base_url": parsed.get("base_url", ""),
                    "model": parsed.get("model", ""),
                    "importable": bool(parsed.get("api_key")),
                    "note": parsed.get("note", ""),
                }
            )
        return result

    def import_provider(self, provider_id: str | None = None, source_app: str = "claude") -> CCSwitchProvider:
        if not self.available:
            raise ValueError("未检测到 CC Switch 本地配置")

        settings = self._load_settings()
        if not provider_id:
            key = {
                "claude": "currentProviderClaude",
                "codex": "currentProviderCodex",
                "gemini": "currentProviderGemini",
            }.get(source_app, "currentProviderClaude")
            provider_id = settings.get(key)
        if not provider_id:
            raise ValueError("CC Switch 中未找到当前启用的 Provider")

        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, app_type, provider_type, settings_config FROM providers WHERE id = ?",
                (provider_id,),
            ).fetchone()
        if not row:
            raise ValueError("指定的 CC Switch Provider 不存在")

        parsed = self._parse_settings_config(row["settings_config"])
        if not parsed.get("api_key"):
            raise ValueError(parsed.get("note") or "该 Provider 无可用 API Key（可能是 OAuth 登录）")

        provider_name = (row["name"] or "CC Switch").lower()
        mapped_provider = self._map_provider_type(provider_name, parsed.get("base_url", ""))

        return CCSwitchProvider(
            id=row["id"],
            name=row["name"],
            is_current=True,
            app_type=row["app_type"],
            provider_type=row["provider_type"] or "",
            api_key=parsed["api_key"],
            base_url=parsed.get("base_url", ""),
            model=parsed.get("model", ""),
            source_app=source_app,
            mapped_provider=mapped_provider,
        )

    def _map_provider_type(self, name: str, base_url: str) -> str:
        text = f"{name} {base_url}".lower()
        if "deepseek" in text:
            return "deepseek"
        if "zhipu" in text or "bigmodel" in text:
            return "zhipu"
        if "moonshot" in text or "kimi" in text:
            return "moonshot"
        if "dashscope" in text or "qwen" in text or "aliyun" in text:
            return "qwen"
        if "openai" in text:
            return "openai"
        return "custom"

    def scan_skill_directories(self) -> list[Path]:
        candidates = [
            self.root / "skills",
            Path.home() / ".claude" / "skills",
            Path.home() / ".codex" / "skills",
            Path.home() / ".cursor" / "skills",
        ]
        roots: list[Path] = []
        for path in candidates:
            if path.is_dir():
                roots.append(path)
        return roots

    def discover_local_skills(self) -> list[dict[str, Any]]:
        skills: list[dict[str, Any]] = []
        seen: set[str] = set()
        for root in self.scan_skill_directories():
            for folder in sorted(root.iterdir()):
                if not folder.is_dir() or folder.name.startswith("."):
                    continue
                skill_file = folder / "SKILL.md"
                if not skill_file.is_file():
                    continue
                key = f"{root}::{folder.name}"
                if key in seen:
                    continue
                seen.add(key)
                content = skill_file.read_text(encoding="utf-8", errors="ignore")
                skills.append(
                    {
                        "name": folder.name.replace("-", " ").title(),
                        "folder_name": folder.name,
                        "source_path": str(folder),
                        "source_root": str(root),
                        "content": content,
                        "content_preview": content[:200].strip(),
                    }
                )
        return skills

    def list_cc_switch_skills(self) -> list[dict[str, Any]]:
        if not self.available:
            return []
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name, directory, description,
                       enabled_claude, enabled_codex, enabled_gemini, enabled_opencode
                FROM skills
                ORDER BY name ASC
                """
            ).fetchall()

        discovered = {item["folder_name"]: item for item in self.discover_local_skills()}
        result = []
        for row in rows:
            folder = row["directory"] or row["name"]
            local = discovered.get(folder)
            result.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "folder_name": folder,
                    "description": row["description"] or "",
                    "enabled_in_ccswitch": any(
                        [
                            row["enabled_claude"],
                            row["enabled_codex"],
                            row["enabled_gemini"],
                            row["enabled_opencode"],
                        ]
                    ),
                    "source_path": local["source_path"] if local else "",
                    "has_local_file": local is not None,
                    "content_preview": local["content_preview"] if local else "",
                }
            )
        return result

    def _load_settings(self) -> dict[str, Any]:
        if not self.settings_path.is_file():
            return {}
        return json.loads(self.settings_path.read_text(encoding="utf-8"))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _parse_settings_config(self, raw: str) -> dict[str, Any]:
        try:
            data = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return {"note": "Provider 配置解析失败"}

        if isinstance(data.get("auth"), dict):
            tokens = data["auth"].get("tokens") or {}
            if tokens.get("access_token") and not any(
                data.get("env", {}).get(k) for k in self.KEY_FIELDS if isinstance(data.get("env"), dict)
            ):
                return {
                    "note": "该 Provider 使用 OAuth 登录，无法导出 API Key，请选择 API Key 类型的 Provider",
                }

        env = data.get("env") if isinstance(data.get("env"), dict) else {}
        api_key = ""
        for key in self.KEY_FIELDS:
            value = env.get(key)
            if value and str(value).strip():
                api_key = str(value).strip()
                break

        base_url = ""
        for key in self.URL_FIELDS:
            value = env.get(key)
            if value and str(value).strip():
                base_url = str(value).strip().rstrip("/")
                break
        base_url = self._normalize_base_url(base_url)

        model = ""
        for key in self.MODEL_FIELDS:
            value = env.get(key)
            if value and str(value).strip():
                model = str(value).strip()
                break
        if not model and isinstance(data.get("model"), str):
            model = data["model"]

        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": model,
            "note": "" if api_key else "未找到 API Key",
        }

    def _normalize_base_url(self, base_url: str) -> str:
        if not base_url:
            return ""
        mapped = self.OPENAI_COMPAT_BASE_MAP.get(base_url.rstrip("/"))
        if mapped:
            return mapped
        if base_url.endswith("/anthropic"):
            return base_url.replace("/anthropic", "/v1")
        if base_url.endswith("/v1"):
            return base_url
        return f"{base_url}/v1"
