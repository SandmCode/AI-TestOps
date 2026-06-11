"""AI 分析记录：保存、导出。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..models import AnalysisRecord

TYPE_LABELS = {
    "contract": "契约测试",
    "coverage": "覆盖率分析",
    "log": "日志分析",
}


def _extract_summary(analysis_type: str, result: dict[str, Any]) -> str:
    summary = result.get("summary") or result.get("fix_summary") or ""
    if summary:
        return str(summary)[:500]
    if analysis_type == "coverage":
        line = result.get("line_coverage", 0)
        branch = result.get("branch_coverage", 0)
        return f"行覆盖 {line}%，分支覆盖 {branch}%"
    if analysis_type == "log":
        return f"错误 {result.get('error_count', 0)}，警告 {result.get('warning_count', 0)}"
    return "分析完成"


def _build_title(analysis_type: str, result: dict[str, Any]) -> str:
    label = TYPE_LABELS.get(analysis_type, "分析")
    now = datetime.now().strftime("%m-%d %H:%M")
    summary = _extract_summary(analysis_type, result)
    short = summary[:24].replace("\n", " ")
    if analysis_type == "contract":
        passed = result.get("passed")
        status = "通过" if passed else "待修复"
        return f"{label}-{status}-{now}"
    return f"{label}-{short}-{now}" if short else f"{label}-{now}"


def save_analysis_record(
    analysis_type: str,
    input_content: str,
    result: dict[str, Any],
) -> AnalysisRecord:
    payload = {k: v for k, v in result.items() if k != "record_id"}
    return AnalysisRecord.objects.create(
        analysis_type=analysis_type,
        title=_build_title(analysis_type, payload),
        summary=_extract_summary(analysis_type, payload),
        input_content=input_content,
        input_preview=(input_content or "")[:300],
        result=payload,
    )


def export_record_json(record: AnalysisRecord) -> bytes:
    data = {
        "id": record.id,
        "analysis_type": record.analysis_type,
        "analysis_type_display": record.get_analysis_type_display(),
        "title": record.title,
        "summary": record.summary,
        "created_at": record.created_at.isoformat(),
        "input_content": record.input_content,
        "result": record.result,
    }
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def export_record_markdown(record: AnalysisRecord) -> str:
    label = record.get_analysis_type_display()
    lines = [
        f"# {record.title}",
        "",
        f"- **类型**: {label}",
        f"- **时间**: {record.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **摘要**: {record.summary}",
        "",
        "## 输入内容",
        "",
        "```",
        record.input_content or "",
        "```",
        "",
        "## 分析结果",
        "",
        "```json",
        json.dumps(record.result, ensure_ascii=False, indent=2),
        "```",
    ]
    result = record.result or {}
    if record.analysis_type == "contract" and result.get("violations"):
        lines.extend(["", "## 问题列表", ""])
        for v in result["violations"]:
            if not isinstance(v, dict):
                continue
            lines.append(f"- **{v.get('field', '')}** [{v.get('severity', '')}]: {v.get('message', '')}")
            if v.get("fix"):
                lines.append(f"  - 修复建议: {v['fix']}")
    if record.analysis_type == "coverage" and result.get("suggestions"):
        lines.extend(["", "## 改进建议", ""])
        for i, s in enumerate(result["suggestions"], 1):
            lines.append(f"{i}. {s}")
    if record.analysis_type == "log" and result.get("patterns"):
        lines.extend(["", "## 错误模式", ""])
        for p in result["patterns"]:
            if not isinstance(p, dict):
                continue
            lines.append(f"- **{p.get('pattern', '')}** (×{p.get('count', 0)}): {p.get('suggestion', '')}")
    return "\n".join(lines)
