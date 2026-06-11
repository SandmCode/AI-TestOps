"""接口文档解析：优先 Markdown 规则解析，失败时回退 AI。"""

from __future__ import annotations

import json
import re
from typing import Any

from .ai_service import AIService, AIServiceError

METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}


def _extract_field(text: str, label: str) -> str:
    m = re.search(rf"- \*\*{re.escape(label)}\*\*[：:]\s*(.+)", text)
    return m.group(1).strip() if m else ""


def _extract_url(text: str) -> str:
    m = re.search(r"- \*\*接口地址\*\*[：:]\s*`([^`]+)`", text)
    if m:
        return m.group(1).strip()
    m = re.search(r"- \*\*接口地址\*\*[：:]\s*(/\S+)", text)
    return m.group(1).strip() if m else ""


def _json_blocks(text: str) -> list[str]:
    return re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)


def _parse_json_obj(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw.strip())
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _slice_after_title(section: str, title: str) -> str:
    """取 title 之后、下一个 **小节** 之前的内容。"""
    if title not in section:
        return ""
    part = section.split(title, 1)[1]
    m = re.search(r"\n\*\*[^*\n]", part)
    return part[: m.start()] if m else part


def _iter_markdown_tables(section: str):
    """按块切分 Markdown 表格（每个表格独立）。"""
    block: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            block.append(stripped)
        elif block:
            if len(block) >= 2:
                yield block
            block = []
    if len(block) >= 2:
        yield block


def _parse_markdown_table(section: str, header_keywords: tuple[str, ...]) -> list[dict[str, str]]:
    """解析 Markdown 表格为行字典列表（只匹配第一个符合 header_keywords 的表格）。"""
    for table_lines in _iter_markdown_tables(section):
        headers = [h.strip() for h in table_lines[0].strip("|").split("|")]
        if not any(any(k in h for k in header_keywords) for h in headers):
            continue
        rows: list[dict[str, str]] = []
        for line in table_lines[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) != len(headers):
                break
            if all(set(c) <= {"-", ":"} for c in cells):
                continue
            row = {headers[i]: cells[i] for i in range(len(headers))}
            if any(row.values()):
                rows.append(row)
        return rows
    return []


def _parse_headers(section: str) -> dict[str, Any]:
    part = _slice_after_title(section, "**请求头**")
    if not part and "**请求头**" not in section:
        part = section
    rows = _parse_markdown_table(part, ("Header", "header", "键"))
    headers: dict[str, Any] = {}
    for row in rows:
        key = row.get("Header") or row.get("header") or row.get("键") or row.get("名称")
        val = row.get("值") or row.get("value") or row.get("Value")
        if key and val and not key.startswith("-"):
            headers[key] = val
    if not headers and "Authorization Bearer" in section:
        headers["Authorization"] = "Bearer {access_token}"
    return headers


def _parse_params(section: str) -> dict[str, Any]:
    part = ""
    for title in ("**Query 参数**", "**Query参数**", "**路径参数**"):
        if title in section:
            part = _slice_after_title(section, title)
            break
    if not part:
        return {}
    rows = _parse_markdown_table(part, ("参数", "字段", "name", "Name"))
    params: dict[str, Any] = {}
    for row in rows:
        key = row.get("参数") or row.get("字段") or row.get("name") or row.get("Name")
        if not key or key.startswith("-"):
            continue
        example = row.get("示例") or row.get("example") or row.get("说明") or row.get("描述") or ""
        if row.get("类型") in ("int", "integer", "number"):
            try:
                params[key] = int(example) if str(example).isdigit() else 0
            except (TypeError, ValueError):
                params[key] = 0
        elif row.get("类型") in ("boolean", "bool"):
            params[key] = str(example).lower() in ("1", "true", "yes")
        else:
            params[key] = example or ""
    return params


def _parse_response_fields(section: str) -> list[dict[str, Any]]:
    part = ""
    for title in ("**返回参数字段", "**响应参数字段", "**返回参数"):
        if title in section:
            part = _slice_after_title(section, title)
            break
    if not part:
        return []
    rows = _parse_markdown_table(part, ("字段", "name", "Name", "参数"))
    fields: list[dict[str, Any]] = []
    for row in rows:
        name = row.get("字段") or row.get("name") or row.get("Name") or row.get("参数")
        if not name or name.startswith("-"):
            continue
        fields.append({
            "name": name,
            "type": row.get("类型") or row.get("type") or "",
            "description": row.get("说明") or row.get("描述") or row.get("description") or "",
            "example": row.get("示例") or row.get("example") or "",
        })
    return fields


def _pick_request_response_body(section: str) -> tuple[dict[str, Any], dict[str, Any]]:
    blocks = _json_blocks(section)
    body: dict[str, Any] = {}
    response: dict[str, Any] = {}

    req_idx = None
    resp_idx = None
    if "**请求示例**" in section:
        req_pos = section.index("**请求示例**")
        for i, block in enumerate(blocks):
            pos = section.find(f"```json\n{block}")
            if pos < 0:
                pos = section.find(f"```\n{block}")
            if pos >= req_pos:
                req_idx = i
                break
    if "**响应示例**" in section:
        resp_pos = section.index("**响应示例**")
        fail_pos = section.find("**失败响应示例**")
        for i, block in enumerate(blocks):
            pos = section.find(block)
            if pos >= resp_pos and (fail_pos < 0 or pos < fail_pos):
                resp_idx = i
                break

    if req_idx is not None and req_idx < len(blocks):
        body = _parse_json_obj(blocks[req_idx])
    elif blocks:
        first = _parse_json_obj(blocks[0])
        if "username" in first or "product_id" in first or "cart_item_ids" in first or "nickname" in first:
            body = first

    if resp_idx is not None and resp_idx < len(blocks):
        response = _parse_json_obj(blocks[resp_idx])
    elif len(blocks) >= 2:
        candidate = _parse_json_obj(blocks[1])
        if "code" in candidate:
            response = candidate

    return body, response


def parse_markdown_api_doc(content: str) -> list[dict[str, Any]]:
    """从 Markdown 接口文档（mock-api-doc 格式）规则提取接口列表。"""
    if not content or len(content.strip()) < 50:
        return []

    sections = re.split(r"(?=^###\s+\d+\.\d+\s+)", content, flags=re.MULTILINE)
    results: list[dict[str, Any]] = []

    for section in sections:
        if not re.match(r"^###\s+\d+\.\d+\s+", section.strip()):
            continue
        method = _extract_field(section, "请求方式").upper()
        if method not in METHODS:
            continue
        url = _extract_url(section)
        if not url:
            continue

        name = _extract_field(section, "接口名称")
        if not name:
            title = re.match(r"^###\s+\d+\.\d+\s+(.+)", section.strip())
            name = title.group(1).strip() if title else "未命名接口"

        module = _extract_field(section, "模块")
        headers = _parse_headers(section)
        params = _parse_params(section)
        body, response = _pick_request_response_body(section)
        response_fields = _parse_response_fields(section)

        desc_parts = []
        if "**接口描述**" in section:
            desc_parts.append(_extract_field(section, "接口描述"))
        title_line = re.search(r"^###\s+\d+\.\d+\s+(.+)$", section, re.MULTILINE)
        if title_line:
            desc_parts.append(title_line.group(1).strip())

        results.append({
            "name": name,
            "module": module,
            "method": method,
            "url": url,
            "headers": headers,
            "params": params,
            "body": body,
            "response": response,
            "response_fields": response_fields,
            "description": " — ".join(p for p in desc_parts if p),
        })

    return results


def parse_api_document_content(content: str) -> tuple[list[dict[str, Any]], str]:
    """
    解析接口文档内容。
    返回 (interfaces, source) source 为 markdown / ai。
    """
    structured = parse_markdown_api_doc(content)
    if len(structured) >= 2:
        return structured, "markdown"

    try:
        ai = AIService()
        return ai.parse_api_document(content), "ai"
    except AIServiceError:
        if structured:
            return structured, "markdown"
        raise


def normalize_api_item(item: dict[str, Any]) -> dict[str, Any] | None:
    method = str(item.get("method", "GET")).upper()
    if method not in METHODS:
        method = "GET"
    url = (item.get("url") or "").strip()
    name = (item.get("name") or "").strip()
    if not url and not name:
        return None
    return {
        "name": name or "未命名接口",
        "module": item.get("module") or "",
        "method": method,
        "url": url,
        "headers": item.get("headers") if isinstance(item.get("headers"), dict) else {},
        "params": item.get("params") if isinstance(item.get("params"), dict) else {},
        "body": item.get("body") if isinstance(item.get("body"), dict) else {},
        "response": item.get("response") if isinstance(item.get("response"), dict) else {},
        "response_fields": item.get("response_fields") if isinstance(item.get("response_fields"), list) else [],
        "description": item.get("description") or "",
    }
