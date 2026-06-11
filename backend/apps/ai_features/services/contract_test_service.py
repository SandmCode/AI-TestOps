"""OpenAPI 契约校验与自动修复（中文输出）。"""

from __future__ import annotations

import copy
import json
import re
from typing import Any


HTTP_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "trace"})

DEFAULT_SERVER = {"url": "http://127.0.0.1:9000/v1", "description": "开发环境"}
DEFAULT_SUCCESS_RESPONSE = {"description": "成功"}
DEFAULT_JSON_BODY = {"application/json": {"schema": {"type": "object"}}}


def _parse_spec(text: str) -> tuple[dict[str, Any] | None, str | None]:
    raw = text.strip()
    if not raw:
        return None, "API 规范内容为空"
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data, None
        return None, "API 规范根节点必须是 JSON 对象"
    except json.JSONDecodeError:
        pass
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(raw)
        if isinstance(data, dict):
            return data, None
        return None, "API 规范根节点必须是对象"
    except Exception:
        return None, "无法解析 API 规范，请检查 JSON/YAML 格式是否正确"


def _dump_spec(spec: dict[str, Any]) -> str:
    return json.dumps(spec, ensure_ascii=False, indent=2)


def _guess_api_title(spec: dict[str, Any]) -> str:
    info = spec.get("info")
    if isinstance(info, dict) and info.get("title"):
        return str(info["title"])
    paths = spec.get("paths")
    if isinstance(paths, dict) and paths:
        first_path = next(iter(paths.keys()), "")
        segment = [s for s in first_path.split("/") if s and not s.startswith("{")]
        if segment:
            name = segment[-1].replace("-", " ").replace("_", " ")
            return f"{name.title()} API"
    return "API 文档"


def _guess_operation_summary(method: str, path: str) -> str:
    segment = [s for s in path.split("/") if s and not s.startswith("{")]
    resource = segment[-1] if segment else "资源"
    resource = resource.replace("-", "").replace("_", "")
    verbs = {
        "get": "获取",
        "post": "创建",
        "put": "更新",
        "patch": "部分更新",
        "delete": "删除",
    }
    return f"{verbs.get(method, '操作')}{resource}"


def _violation(
    field: str,
    message: str,
    severity: str,
    *,
    fix: str,
    fix_snippet: str = "",
    auto_fixable: bool = False,
    fix_id: str = "",
) -> dict[str, Any]:
    return {
        "field": field,
        "message": message,
        "severity": severity,
        "fix": fix,
        "fix_snippet": fix_snippet,
        "auto_fixable": auto_fixable,
        "fix_id": fix_id or field,
    }


def _severity_counts(violations: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"error": 0, "warning": 0, "info": 0}
    for v in violations:
        sev = v.get("severity", "info")
        if sev in counts:
            counts[sev] += 1
    return counts


def _build_summary(violations: list[dict[str, Any]]) -> str:
    if not violations:
        return "契约检查通过，未发现规范问题"
    counts = _severity_counts(violations)
    parts: list[str] = []
    if counts["error"]:
        parts.append(f"{counts['error']} 个错误")
    if counts["warning"]:
        parts.append(f"{counts['warning']} 个警告")
    if counts["info"]:
        parts.append(f"{counts['info']} 条提示")
    fixable = sum(1 for v in violations if v.get("auto_fixable"))
    base = f"发现 {len(violations)} 项问题（{'，'.join(parts)}）"
    if fixable:
        base += f"，其中 {fixable} 项可一键修复"
    return base


def validate_openapi_spec(spec_text: str) -> dict[str, Any]:
    """基于 OpenAPI 3.x 常见规则做本地校验，附带修复建议。"""
    spec, parse_err = _parse_spec(spec_text)
    violations: list[dict[str, Any]] = []

    if parse_err:
        violations.append(_violation(
            "根节点", parse_err, "error",
            fix="请检查 JSON 语法：括号是否配对、键名是否用双引号包裹、末尾是否有多余逗号",
            auto_fixable=False,
        ))
        return _pack_result(violations, spec_text, "local")

    assert spec is not None
    title_guess = _guess_api_title(spec)

    openapi_ver = spec.get("openapi")
    if not openapi_ver:
        violations.append(_violation(
            "openapi",
            "缺少 openapi 版本字段，OpenAPI 3.x 文档必须声明版本（如 3.0.0）",
            "error",
            fix='在文档根节点添加 "openapi": "3.0.0"',
            fix_snippet='"openapi": "3.0.0"',
            auto_fixable=True,
            fix_id="add_openapi",
        ))
    elif not re.match(r"^3\.\d+\.\d+$", str(openapi_ver)):
        violations.append(_violation(
            "openapi",
            f"openapi 版本「{openapi_ver}」不符合 OpenAPI 3.x 格式，建议使用 3.0.x 或 3.1.x",
            "warning",
            fix='将 openapi 改为 "3.0.0" 或 "3.1.0"',
            fix_snippet='"openapi": "3.0.0"',
            auto_fixable=True,
            fix_id="normalize_openapi",
        ))

    info = spec.get("info")
    if not info or not isinstance(info, dict):
        snippet = json.dumps(
            {"title": title_guess, "version": "1.0.0", "description": f"{title_guess}接口文档"},
            ensure_ascii=False,
            indent=2,
        )
        violations.append(_violation(
            "info",
            "OpenAPI 3.0 文档缺少必需的 info 对象（应包含 title、version 等基本信息）",
            "error",
            fix="在 openapi 字段后添加 info 对象，至少包含 title 和 version",
            fix_snippet=snippet,
            auto_fixable=True,
            fix_id="add_info",
        ))
    else:
        if not info.get("title"):
            violations.append(_violation(
                "info.title",
                "info 对象缺少 title 字段，无法标识 API 名称",
                "error",
                fix=f'在 info 中添加 "title": "{title_guess}"',
                fix_snippet=f'"title": "{title_guess}"',
                auto_fixable=True,
                fix_id="add_info_title",
            ))
        if not info.get("version"):
            violations.append(_violation(
                "info.version",
                "info 对象缺少 version 字段，无法标识 API 版本",
                "warning",
                fix='在 info 中添加 "version": "1.0.0"',
                fix_snippet='"version": "1.0.0"',
                auto_fixable=True,
                fix_id="add_info_version",
            ))

    if not spec.get("servers"):
        snippet = json.dumps([DEFAULT_SERVER], ensure_ascii=False, indent=2)
        violations.append(_violation(
            "servers",
            "未定义 servers 基址，客户端可能无法确定请求 Host",
            "warning",
            fix="添加 servers 数组，声明 API 基址 URL",
            fix_snippet=f'"servers": {snippet}',
            auto_fixable=True,
            fix_id="add_servers",
        ))

    paths = spec.get("paths")
    if not paths or not isinstance(paths, dict):
        violations.append(_violation(
            "paths",
            "缺少 paths 对象或未定义任何接口路径",
            "error",
            fix='添加 paths 对象并声明至少一个接口，例如 "/api/users": { "get": {...} }',
            fix_snippet='"paths": {\n  "/api/health": {\n    "get": {\n      "summary": "健康检查",\n      "responses": { "200": { "description": "成功" } }\n    }\n  }\n}',
            auto_fixable=False,
        ))
    else:
        if len(paths) == 0:
            violations.append(_violation(
                "paths",
                "paths 为空，文档中未声明任何 API 端点",
                "error",
                fix="在 paths 中至少添加一个接口路径及对应 HTTP 方法",
                auto_fixable=False,
            ))
        for path, item in paths.items():
            if not isinstance(item, dict):
                continue
            if not path.startswith("/"):
                fixed = f"/{path.lstrip('/')}"
                violations.append(_violation(
                    f"paths.{path}",
                    f"路径「{path}」应以 / 开头",
                    "warning",
                    fix=f'将路径改为 "{fixed}"',
                    fix_snippet=f'"{fixed}"',
                    auto_fixable=True,
                    fix_id=f"fix_path:{path}",
                ))
            has_operation = False
            for method, op in item.items():
                if method.startswith("x-"):
                    continue
                if method not in HTTP_METHODS:
                    continue
                has_operation = True
                if not isinstance(op, dict):
                    continue
                op_id = f"{method.upper()} {path}"
                if not op.get("summary") and not op.get("description"):
                    summary = _guess_operation_summary(method, path)
                    violations.append(_violation(
                        f"paths.{path}.{method}",
                        f"接口 {op_id} 缺少 summary 或 description 说明",
                        "info",
                        fix=f'添加 "summary": "{summary}"',
                        fix_snippet=f'"summary": "{summary}"',
                        auto_fixable=True,
                        fix_id=f"add_summary:{path}:{method}",
                    ))
                responses = op.get("responses")
                if not responses or not isinstance(responses, dict):
                    snippet = json.dumps({"200": DEFAULT_SUCCESS_RESPONSE}, ensure_ascii=False, indent=2)
                    violations.append(_violation(
                        f"paths.{path}.{method}.responses",
                        f"接口 {op_id} 缺少 responses 响应定义",
                        "error",
                        fix="添加 responses 对象，至少定义 200 成功响应",
                        fix_snippet=f'"responses": {snippet}',
                        auto_fixable=True,
                        fix_id=f"add_responses:{path}:{method}",
                    ))
                elif "200" not in responses and "201" not in responses and "204" not in responses:
                    violations.append(_violation(
                        f"paths.{path}.{method}.responses",
                        f"接口 {op_id} 未定义成功响应（200/201/204）",
                        "warning",
                        fix='在 responses 中添加 "200": { "description": "成功" }',
                        fix_snippet='"200": { "description": "成功" }',
                        auto_fixable=True,
                        fix_id=f"add_success_response:{path}:{method}",
                    ))
                req_body = op.get("requestBody")
                if req_body and isinstance(req_body, dict):
                    content = req_body.get("content")
                    if not content:
                        snippet = json.dumps(DEFAULT_JSON_BODY, ensure_ascii=False, indent=2)
                        violations.append(_violation(
                            f"paths.{path}.{method}.requestBody",
                            f"接口 {op_id} 的 requestBody 缺少 content 类型定义",
                            "warning",
                            fix='在 requestBody 中添加 content，例如 application/json',
                            fix_snippet=f'"content": {snippet}',
                            auto_fixable=True,
                            fix_id=f"add_request_body_content:{path}:{method}",
                        ))
            if not has_operation:
                violations.append(_violation(
                    f"paths.{path}",
                    f"路径「{path}」下未定义任何 HTTP 方法（get/post 等）",
                    "warning",
                    fix="为该路径添加 get/post/put/delete 等 HTTP 方法定义",
                    auto_fixable=False,
                ))

    components = spec.get("components")
    if components and isinstance(components, dict):
        schemas = components.get("schemas")
        if schemas and isinstance(schemas, dict):
            for name, schema in schemas.items():
                if isinstance(schema, dict) and schema.get("type") == "object" and not schema.get("properties"):
                    violations.append(_violation(
                        f"components.schemas.{name}",
                        f"Schema「{name}」类型为 object 但未定义 properties",
                        "info",
                        fix='添加 "properties": {} 或补充具体字段定义',
                        fix_snippet='"properties": {}',
                        auto_fixable=True,
                        fix_id=f"add_schema_properties:{name}",
                    ))

    return _pack_result(violations, spec_text, "local")


def _pack_result(violations: list[dict[str, Any]], spec_text: str, source: str) -> dict[str, Any]:
    fixable = sum(1 for v in violations if v.get("auto_fixable"))
    fix_preview = apply_auto_fixes(spec_text) if fixable else None
    return {
        "summary": _build_summary(violations),
        "violations": violations,
        "passed": len(violations) == 0,
        "stats": _severity_counts(violations),
        "fixable_count": fixable,
        "fixed_spec": fix_preview["fixed_spec"] if fix_preview else None,
        "source": source,
    }


def _fix_enabled(fix_id: str, only_fix_ids: set[str] | None) -> bool:
    return only_fix_ids is None or fix_id in only_fix_ids


def apply_auto_fixes(spec_text: str, only_fix_ids: list[str] | None = None) -> dict[str, Any]:
    """自动修复可处理的 OpenAPI 规范问题，返回修复后的 JSON 文本。"""
    spec, parse_err = _parse_spec(spec_text)
    if spec is None:
        return {
            "fixed_spec": spec_text,
            "applied": [],
            "applied_labels": [],
            "error": parse_err,
        }

    spec = copy.deepcopy(spec)
    applied: list[str] = []
    labels: list[str] = []
    only_set = set(only_fix_ids) if only_fix_ids else None

    def mark(fix_id: str, label: str) -> None:
        applied.append(fix_id)
        labels.append(label)

    if _fix_enabled("add_openapi", only_set) and not spec.get("openapi"):
        spec["openapi"] = "3.0.0"
        mark("add_openapi", "补充 openapi 版本号 3.0.0")
    elif _fix_enabled("normalize_openapi", only_set) and not re.match(r"^3\.\d+\.\d+$", str(spec.get("openapi"))):
        spec["openapi"] = "3.0.0"
        mark("normalize_openapi", "规范化 openapi 版本为 3.0.0")

    title_guess = _guess_api_title(spec)
    if _fix_enabled("add_info", only_set) and (not spec.get("info") or not isinstance(spec.get("info"), dict)):
        spec["info"] = {
            "title": title_guess,
            "version": "1.0.0",
            "description": f"{title_guess}接口文档",
        }
        mark("add_info", f"添加 info 对象（title: {title_guess}）")
    elif isinstance(spec.get("info"), dict):
        info = spec["info"]
        if _fix_enabled("add_info_title", only_set) and not info.get("title"):
            info["title"] = title_guess
            mark("add_info_title", f"补充 info.title: {title_guess}")
        if _fix_enabled("add_info_version", only_set) and not info.get("version"):
            info["version"] = "1.0.0"
            mark("add_info_version", "补充 info.version: 1.0.0")

    if _fix_enabled("add_servers", only_set) and not spec.get("servers"):
        spec["servers"] = [copy.deepcopy(DEFAULT_SERVER)]
        mark("add_servers", "添加默认 servers 基址")

    paths = spec.get("paths")
    if isinstance(paths, dict):
        renamed: dict[str, Any] = {}
        for path, item in list(paths.items()):
            if not isinstance(item, dict):
                renamed[path] = item
                continue
            fixed_path = path if path.startswith("/") else f"/{path.lstrip('/')}"
            fix_path_id = f"fix_path:{path}"
            if fixed_path != path and _fix_enabled(fix_path_id, only_set):
                mark(fix_path_id, f"修正路径 {path} → {fixed_path}")
            for method, op in item.items():
                if method not in HTTP_METHODS or not isinstance(op, dict):
                    continue
                summary_id = f"add_summary:{fixed_path}:{method}"
                if _fix_enabled(summary_id, only_set) and not op.get("summary") and not op.get("description"):
                    op["summary"] = _guess_operation_summary(method, fixed_path)
                    mark(summary_id, f"补充 {method.upper()} {fixed_path} 的 summary")
                responses = op.get("responses")
                resp_id = f"add_responses:{fixed_path}:{method}"
                if _fix_enabled(resp_id, only_set) and (not responses or not isinstance(responses, dict)):
                    op["responses"] = {"200": copy.deepcopy(DEFAULT_SUCCESS_RESPONSE)}
                    mark(resp_id, f"补充 {method.upper()} {fixed_path} 的 responses")
                elif isinstance(responses, dict):
                    success_id = f"add_success_response:{fixed_path}:{method}"
                    if (
                        _fix_enabled(success_id, only_set)
                        and "200" not in responses
                        and "201" not in responses
                        and "204" not in responses
                    ):
                        responses["200"] = copy.deepcopy(DEFAULT_SUCCESS_RESPONSE)
                        mark(success_id, f"补充 {method.upper()} {fixed_path} 的 200 响应")
                req_body = op.get("requestBody")
                body_id = f"add_request_body_content:{fixed_path}:{method}"
                if (
                    _fix_enabled(body_id, only_set)
                    and req_body
                    and isinstance(req_body, dict)
                    and not req_body.get("content")
                ):
                    req_body["content"] = copy.deepcopy(DEFAULT_JSON_BODY)
                    mark(body_id, f"补充 {method.upper()} {fixed_path} 的 requestBody.content")
            renamed[fixed_path] = item
        spec["paths"] = renamed

    components = spec.get("components")
    if components and isinstance(components, dict):
        schemas = components.get("schemas")
        if schemas and isinstance(schemas, dict):
            for name, schema in schemas.items():
                schema_id = f"add_schema_properties:{name}"
                if (
                    _fix_enabled(schema_id, only_set)
                    and isinstance(schema, dict)
                    and schema.get("type") == "object"
                    and not schema.get("properties")
                ):
                    schema["properties"] = {}
                    mark(schema_id, f"补充 Schema {name} 的 properties")

    ordered = _reorder_spec(spec)
    return {
        "fixed_spec": _dump_spec(ordered),
        "applied": applied,
        "applied_labels": labels,
    }


def _reorder_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """将常见顶层字段按 OpenAPI 推荐顺序排列，便于阅读。"""
    order = ["openapi", "info", "servers", "paths", "components", "tags", "security"]
    ordered: dict[str, Any] = {}
    for key in order:
        if key in spec:
            ordered[key] = spec[key]
    for key, value in spec.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def merge_violations(
    local: list[dict[str, Any]],
    ai_violations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for item in local + ai_violations:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field", ""))
        message = str(item.get("message", ""))
        key = f"{field}|{message}"
        if key in seen or not message:
            continue
        seen.add(key)
        severity = item.get("severity", "info")
        if severity not in ("error", "warning", "info"):
            severity = "info"
        merged.append({
            "field": field,
            "message": message,
            "severity": severity,
            "fix": item.get("fix") or "请根据问题描述手动调整对应字段",
            "fix_snippet": item.get("fix_snippet") or "",
            "auto_fixable": bool(item.get("auto_fixable")),
            "fix_id": item.get("fix_id") or field,
        })
    merged.sort(key=lambda x: {"error": 0, "warning": 1, "info": 2}.get(x["severity"], 3))
    return merged


def run_contract_test(api_spec: str, ai_result: dict[str, Any] | None = None) -> dict[str, Any]:
    local_result = validate_openapi_spec(api_spec)
    if not ai_result:
        return local_result

    ai_violations = ai_result.get("violations") or []
    if not isinstance(ai_violations, list):
        ai_violations = []
    merged = merge_violations(local_result["violations"], ai_violations)
    summary = ai_result.get("summary") if isinstance(ai_result.get("summary"), str) else ""
    if not summary or not re.search(r"[\u4e00-\u9fff]", summary):
        summary = _build_summary(merged)
    fixable = sum(1 for v in merged if v.get("auto_fixable"))
    fix_preview = apply_auto_fixes(api_spec) if fixable else None
    return {
        "summary": summary,
        "violations": merged,
        "passed": len(merged) == 0,
        "stats": _severity_counts(merged),
        "fixable_count": fixable,
        "fixed_spec": fix_preview["fixed_spec"] if fix_preview else None,
        "source": "local+ai" if ai_violations else "local",
    }


def run_contract_fix(api_spec: str, fix_ids: list[str] | None = None) -> dict[str, Any]:
    """执行一键或单项修复并返回修复结果与复检报告。"""
    fix_result = apply_auto_fixes(api_spec, only_fix_ids=fix_ids)
    if fix_result.get("error"):
        return {
            "fixed_spec": api_spec,
            "applied": [],
            "applied_labels": [],
            "error": fix_result["error"],
            "validation": validate_openapi_spec(api_spec),
        }
    fixed_spec = fix_result["fixed_spec"]
    validation = validate_openapi_spec(fixed_spec)
    remaining = len(validation.get("violations") or [])
    applied_n = len(fix_result.get("applied_labels") or [])
    validation["fix_summary"] = (
        f"已自动修复 {applied_n} 项"
        + (f"，仍有 {remaining} 项需手动处理" if remaining else "，规范已通过检查")
    )
    return {
        "fixed_spec": fixed_spec,
        "applied": fix_result.get("applied") or [],
        "applied_labels": fix_result.get("applied_labels") or [],
        "validation": validation,
    }
