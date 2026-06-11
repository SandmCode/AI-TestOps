"""从大模型输出中稳健提取并解析 JSON。"""

from __future__ import annotations

import json
import re
from typing import Any, Literal


def strip_markdown_fence(text: str) -> str:
    text = (text or "").strip()
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def fix_common_json_issues(text: str) -> str:
    text = strip_markdown_fence(text)
    text = text.replace("\ufeff", "").replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    # 去掉 // 行注释（简单场景）
    text = re.sub(r"//[^\n\"]*", "", text)
    # 去掉 trailing comma
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    return text.strip()


def extract_balanced_json(raw: str, kind: Literal["object", "array"]) -> str | None:
    open_c, close_c = ("{", "}") if kind == "object" else ("[", "]")
    start = raw.find(open_c)
    if start < 0:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(raw)):
        ch = raw[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == open_c:
            depth += 1
        elif ch == close_c:
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return None


def prepare_json_text(raw: str, kind: Literal["object", "array"]) -> str:
    cleaned = fix_common_json_issues(raw)
    extracted = extract_balanced_json(cleaned, kind)
    if extracted:
        return fix_common_json_issues(extracted)
    # 回退：贪婪匹配
    pattern = r"\{.*\}" if kind == "object" else r"\[.*\]"
    match = re.search(pattern, cleaned, re.DOTALL)
    return fix_common_json_issues(match.group()) if match else cleaned


def try_load_json(text: str) -> Any | None:
    for candidate in (text, fix_common_json_issues(text)):
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def parse_json_from_llm(raw: str, kind: Literal["object", "array"]) -> Any:
    text = prepare_json_text(raw, kind)
    data = try_load_json(text)
    if data is not None:
        return data
    raise ValueError(f"无法解析 JSON（{kind}）")
