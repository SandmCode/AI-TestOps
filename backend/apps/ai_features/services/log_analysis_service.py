"""日志本地预分析（中文输出）。"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any


ERROR_PATTERNS = [
    (re.compile(r"ConnectionTimeout|connection (?:failed|refused|timeout)", re.I), "连接超时/失败"),
    (re.compile(r"ValidationError|invalid|required field", re.I), "参数校验失败"),
    (re.compile(r"401|403|Unauthorized|Forbidden", re.I), "认证/权限异常"),
    (re.compile(r"500|Internal Server Error", re.I), "服务端内部错误"),
    (re.compile(r"NullPointer|NoneType|undefined is not", re.I), "空指针/空值异常"),
]


def analyze_logs_local(logs: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in logs.splitlines() if ln.strip()]
    error_count = 0
    warning_count = 0
    info_count = 0
    pattern_counter: Counter[str] = Counter()

    for line in lines:
        upper = line.upper()
        if " ERROR " in f" {upper} " or upper.startswith("ERROR") or "[ERROR]" in upper:
            error_count += 1
        elif " WARN " in f" {upper} " or " WARNING " in f" {upper} " or upper.startswith("WARN"):
            warning_count += 1
        elif " INFO " in f" {upper} " or upper.startswith("INFO"):
            info_count += 1

        for regex, label in ERROR_PATTERNS:
            if regex.search(line):
                pattern_counter[label] += 1

    patterns: list[dict[str, Any]] = []
    suggestions_map = {
        "连接超时/失败": "检查 Redis/数据库/下游服务地址与网络连通性，适当增大超时时间",
        "参数校验失败": "对照接口文档核对必填字段与数据类型，补充边界用例",
        "认证/权限异常": "确认 Token 是否过期、权限范围是否正确",
        "服务端内部错误": "查看服务端堆栈日志，定位异常模块并复现请求",
        "空指针/空值异常": "检查上游返回值是否为空，增加空值防护与断言",
    }
    for label, count in pattern_counter.most_common(8):
        patterns.append({
            "pattern": label,
            "count": count,
            "suggestion": suggestions_map.get(label, "结合上下文日志进一步定位根因"),
        })

    if error_count == 0 and warning_count == 0:
        summary = f"共分析 {len(lines)} 行日志，未发现明显 ERROR/WARN 记录"
    else:
        summary = (
            f"共分析 {len(lines)} 行日志，发现 {error_count} 条错误、"
            f"{warning_count} 条警告、{info_count} 条信息"
        )

    return {
        "summary": summary,
        "error_count": error_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "patterns": patterns,
        "line_count": len(lines),
        "source": "local",
    }


def merge_log_analysis(local: dict[str, Any], ai: dict[str, Any]) -> dict[str, Any]:
    """合并本地统计与 AI 深度分析，优先保留本地计数。"""
    patterns = ai.get("patterns") if isinstance(ai.get("patterns"), list) else []
    if not patterns:
        patterns = local.get("patterns", [])
    else:
        local_patterns = {p["pattern"]: p for p in local.get("patterns", []) if isinstance(p, dict)}
        for p in patterns:
            if isinstance(p, dict) and p.get("pattern") in local_patterns:
                p["count"] = max(int(p.get("count") or 0), int(local_patterns[p["pattern"]].get("count") or 0))

    summary = ai.get("summary") if isinstance(ai.get("summary"), str) else ""
    if not summary or not re.search(r"[\u4e00-\u9fff]", summary):
        summary = local["summary"]

    return {
        "summary": summary,
        "error_count": local.get("error_count", ai.get("error_count", 0)),
        "warning_count": local.get("warning_count", ai.get("warning_count", 0)),
        "info_count": local.get("info_count", 0),
        "patterns": patterns,
        "line_count": local.get("line_count", 0),
        "source": "local+ai",
    }
