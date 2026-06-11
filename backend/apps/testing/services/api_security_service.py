"""接口安全检测：基于已导入接口进行模拟攻击与风险分析。"""

from __future__ import annotations

import copy
import json
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests as http_requests

from apps.testing.models import ApiInterface, SecurityScanTarget

from .api_automation_service import (
    _apply_all_mappings,
    _build_request,
    _collect_dep_ids,
    _parse_response_body,
    _sanitize_headers,
    run_single_interface,
)
from .api_dependency_service import is_auth_endpoint, needs_authorization

ATTACK_STRATEGIES: list[dict[str, Any]] = [
    {
        "id": "unauth_access",
        "name": "未授权访问",
        "desc": "移除 Authorization 等鉴权头，检测接口是否仍可访问",
        "severity": "high",
        "default": True,
    },
    {
        "id": "invalid_token",
        "name": "无效 Token",
        "desc": "使用伪造 Bearer Token，检测鉴权是否生效",
        "severity": "high",
        "default": True,
    },
    {
        "id": "sql_injection",
        "name": "SQL 注入探测",
        "desc": "在参数/Body 中注入 SQL 特征 payload，检测错误回显",
        "severity": "high",
        "default": True,
    },
    {
        "id": "xss",
        "name": "XSS 反射探测",
        "desc": "注入脚本片段，检测响应是否原样回显",
        "severity": "medium",
        "default": True,
    },
    {
        "id": "path_traversal",
        "name": "路径遍历",
        "desc": "替换路径参数为 ../ 等 traversal payload",
        "severity": "medium",
        "default": True,
    },
    {
        "id": "oversized_input",
        "name": "超长输入",
        "desc": "发送超长字符串，检测服务异常或崩溃迹象",
        "severity": "medium",
        "default": False,
    },
    {
        "id": "special_chars",
        "name": "特殊字符",
        "desc": "注入引号、空字节等边界字符",
        "severity": "low",
        "default": False,
    },
]

SQL_PAYLOADS = [
    "' OR '1'='1",
    "1' OR '1'='1' --",
    "' UNION SELECT NULL--",
    "1; SELECT SLEEP(0)--",
]
XSS_PAYLOADS = [
    "<script>alert(1)</script>",
    "<img src=x onerror=alert(1)>",
    "\"><svg/onload=alert(1)>",
]
PATH_PAYLOADS = [
    "../../../etc/passwd",
    "..%2f..%2f..%2fetc%2fpasswd",
    "....//....//etc/passwd",
]
SPECIAL_PAYLOADS = ["'", "\"", "\\", "%00", "{{7*7}}", "${7*7}"]
SQL_ERROR_PATTERN = re.compile(
    r"(sql syntax|mysql|sqlite|postgresql|ora-\d+|syntax error|unclosed quotation|"
    r"odbc|jdbc|sqlstate|database error)",
    re.I,
)


def get_security_meta() -> dict[str, Any]:
    return {"strategies": ATTACK_STRATEGIES}


def _resolve_dependencies(api: ApiInterface, variables: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], dict[str, Any] | None]:
    result_by_id: dict[int, dict[str, Any]] = {}
    auth_session: dict[str, Any] | None = None
    for dep_id in _collect_dep_ids(api):
        if dep_id in result_by_id:
            continue
        dep_api = ApiInterface.objects.filter(id=dep_id).first()
        if not dep_api:
            continue
        sub = run_single_interface(
            dep_api,
            variables,
            result_by_id=result_by_id,
            auth_session_result=auth_session,
            _resolve_dep=False,
        )
        result_by_id[dep_id] = sub
        if sub.get("success") and is_auth_endpoint(dep_api):
            auth_session = sub
    return result_by_id, auth_session


def _prepare_request(
    api: ApiInterface,
    variables: dict[str, Any],
    result_by_id: dict[int, dict[str, Any]],
    auth_session: dict[str, Any] | None,
) -> dict[str, Any]:
    request_data = _build_request(api, variables)
    _apply_all_mappings(api, request_data, result_by_id, auth_session)
    return request_data


def _execute(method: str, request_data: dict[str, Any]) -> dict[str, Any]:
    method = method.upper()
    kwargs: dict[str, Any] = {
        "method": method,
        "url": request_data["url"],
        "headers": _sanitize_headers(request_data.get("headers") or {}),
        "timeout": 12,
    }
    if method == "GET":
        kwargs["params"] = request_data.get("params") or {}
    else:
        kwargs["json"] = request_data.get("body") or None
        if request_data.get("params"):
            kwargs["params"] = request_data["params"]
    try:
        resp = http_requests.request(**kwargs)
        text = resp.text[:8000]
        return {
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": text,
            "parsed_body": _parse_response_body(text),
            "error": "",
        }
    except Exception as exc:
        return {
            "status_code": 0,
            "headers": {},
            "body": "",
            "parsed_body": {},
            "error": str(exc),
        }


def _finding(
    *,
    strategy: str,
    strategy_name: str,
    severity: str,
    title: str,
    detail: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "strategy_name": strategy_name,
        "severity": severity,
        "title": title,
        "detail": detail,
        "evidence": evidence,
    }


def _has_auth_header(headers: dict[str, Any]) -> bool:
    for key, val in (headers or {}).items():
        if str(key).lower() == "authorization":
            return True
        if isinstance(val, str) and "bearer" in val.lower():
            return True
    return False


def _strip_auth_headers(headers: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(headers or {})
    for key in list(clean.keys()):
        if str(key).lower() in ("authorization", "x-access-token", "x-auth-token"):
            clean.pop(key, None)
    return clean


def _iter_string_paths(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    if isinstance(obj, str):
        paths.append((prefix or "value", obj))
    elif isinstance(obj, dict):
        for key, val in obj.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            paths.extend(_iter_string_paths(val, child))
    elif isinstance(obj, list):
        for idx, val in enumerate(obj):
            child = f"{prefix}[{idx}]"
            paths.extend(_iter_string_paths(val, child))
    return paths


def _set_path(obj: Any, path: str, value: str) -> Any:
    cloned = copy.deepcopy(obj)
    if not path or path == "value":
        return value
    parts = re.split(r"\.(?=[^[\].]+($|\[))|(\[(\d+)\])", path)
    parts = [p for p in parts if p not in (None, "", ".")]
    node = cloned
    for part in parts[:-1]:
        if part.isdigit():
            node = node[int(part)]
        else:
            node = node[part]
    last = parts[-1]
    if last.isdigit():
        node[int(last)] = value
    else:
        node[last] = value
    return cloned


def _response_text(result: dict[str, Any]) -> str:
    body = result.get("body") or ""
    if body:
        return body
    parsed = result.get("parsed_body")
    if isinstance(parsed, dict):
        return json.dumps(parsed, ensure_ascii=False)
    return str(parsed or "")


def _test_unauth(api: ApiInterface, request_data: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    if not needs_authorization(api) and not _has_auth_header(request_data.get("headers") or {}):
        return []
    mutated = copy.deepcopy(request_data)
    mutated["headers"] = _strip_auth_headers(mutated.get("headers") or {})
    result = _execute(api.method, mutated)
    findings: list[dict[str, Any]] = []
    if 200 <= result["status_code"] < 300 and baseline.get("status_code") in (200, 201, 204):
        findings.append(
            _finding(
                strategy="unauth_access",
                strategy_name="未授权访问",
                severity="high",
                title="移除鉴权后仍可访问",
                detail="接口在去掉 Authorization 后仍返回成功，可能存在未授权访问风险。",
                evidence={
                    "payload": "移除 Authorization 请求头",
                    "status_code": result["status_code"],
                    "baseline_status": baseline.get("status_code"),
                    "body_preview": result["body"][:500],
                },
            )
        )
    elif result["status_code"] == 401:
        findings.append(
            _finding(
                strategy="unauth_access",
                strategy_name="未授权访问",
                severity="info",
                title="鉴权校验正常",
                detail="移除 Authorization 后返回 401，未授权访问被正确拒绝。",
                evidence={"status_code": 401},
            )
        )
    return findings


def _test_invalid_token(api: ApiInterface, request_data: dict[str, Any]) -> list[dict[str, Any]]:
    if not needs_authorization(api) and not _has_auth_header(request_data.get("headers") or {}):
        return []
    mutated = copy.deepcopy(request_data)
    headers = copy.deepcopy(mutated.get("headers") or {})
    replaced = False
    for key in list(headers.keys()):
        if str(key).lower() == "authorization":
            headers[key] = "Bearer invalid_token_security_scan"
            replaced = True
    if not replaced:
        headers["Authorization"] = "Bearer invalid_token_security_scan"
    mutated["headers"] = headers
    result = _execute(api.method, mutated)
    if 200 <= result["status_code"] < 300:
        return [
            _finding(
                strategy="invalid_token",
                strategy_name="无效 Token",
                severity="high",
                title="无效 Token 仍被接受",
                detail="使用伪造 Bearer Token 仍返回成功响应，Token 校验可能失效。",
                evidence={
                    "payload": "Bearer invalid_token_security_scan",
                    "status_code": result["status_code"],
                    "body_preview": result["body"][:500],
                },
            )
        ]
    if result["status_code"] == 401:
        return [
            _finding(
                strategy="invalid_token",
                strategy_name="无效 Token",
                severity="info",
                title="无效 Token 被拒绝",
                detail="伪造 Token 返回 401，鉴权逻辑正常。",
                evidence={"status_code": 401},
            )
        ]
    return []


def _inject_query(url: str, payload: str) -> str:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if not query:
        query = {"q": payload, "id": payload}
    else:
        for key in list(query.keys())[:3]:
            query[key] = payload
    return urlunparse(parsed._replace(query=urlencode(query)))


def _test_sql_injection(api: ApiInterface, request_data: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for payload in SQL_PAYLOADS[:3]:
        mutated = copy.deepcopy(request_data)
        if mutated.get("params"):
            for key in list(mutated["params"].keys())[:3]:
                mutated["params"][key] = payload
        else:
            mutated["url"] = _inject_query(mutated["url"], payload)
        if mutated.get("body"):
            for path, _ in _iter_string_paths(mutated["body"])[:2]:
                mutated["body"] = _set_path(mutated["body"], path, payload)
        result = _execute(api.method, mutated)
        text = _response_text(result)
        if SQL_ERROR_PATTERN.search(text):
            findings.append(
                _finding(
                    strategy="sql_injection",
                    strategy_name="SQL 注入探测",
                    severity="high",
                    title="疑似 SQL 错误回显",
                    detail="响应中出现数据库/SQL 相关错误信息，建议检查参数化查询与输入校验。",
                    evidence={
                        "payload": payload,
                        "status_code": result["status_code"],
                        "body_preview": text[:500],
                    },
                )
            )
            break
        if result["status_code"] >= 500:
            findings.append(
                _finding(
                    strategy="sql_injection",
                    strategy_name="SQL 注入探测",
                    severity="medium",
                    title="注入 payload 触发服务端 5xx",
                    detail="注入特殊 SQL 片段后服务端返回 5xx，建议进一步人工确认。",
                    evidence={
                        "payload": payload,
                        "status_code": result["status_code"],
                        "body_preview": text[:300],
                    },
                )
            )
            break
    return findings


def _test_xss(api: ApiInterface, request_data: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    marker = "secxss991"
    payload = f"<script>{marker}</script>"
    mutated = copy.deepcopy(request_data)
    injected = False
    if mutated.get("params"):
        for key in list(mutated["params"].keys())[:2]:
            mutated["params"][key] = payload
            injected = True
    if mutated.get("body"):
        for path, _ in _iter_string_paths(mutated["body"])[:2]:
            mutated["body"] = _set_path(mutated["body"], path, payload)
            injected = True
    if not injected:
        mutated["url"] = _inject_query(mutated["url"], payload)
    result = _execute(api.method, mutated)
    text = _response_text(result)
    if marker in text or payload in text:
        findings.append(
            _finding(
                strategy="xss",
                strategy_name="XSS 反射探测",
                severity="medium",
                title="Payload 在响应中被反射",
                detail="注入的脚本片段出现在响应体中，存在反射型 XSS 风险（需结合 Content-Type 进一步确认）。",
                evidence={
                    "payload": payload,
                    "status_code": result["status_code"],
                    "body_preview": text[:500],
                },
            )
        )
    return findings


def _test_path_traversal(api: ApiInterface, request_data: dict[str, Any]) -> list[dict[str, Any]]:
    url = request_data.get("url") or ""
    if "{" not in url and "/../" not in url:
        # 尝试替换末段路径
        findings: list[dict[str, Any]] = []
        for payload in PATH_PAYLOADS[:2]:
            mutated = copy.deepcopy(request_data)
            parts = urlparse(mutated["url"])
            path = parts.path.rstrip("/")
            if "/" in path:
                base = path.rsplit("/", 1)[0]
                mutated["url"] = urlunparse(parts._replace(path=f"{base}/{payload}"))
            else:
                continue
            result = _execute(api.method, mutated)
            text = _response_text(result)
            if 200 <= result["status_code"] < 300 and any(
                token in text.lower() for token in ("root:", "[extensions]", "passwd", "hosts")
            ):
                findings.append(
                    _finding(
                        strategy="path_traversal",
                        strategy_name="路径遍历",
                        severity="high",
                        title="路径遍历疑似读取敏感文件",
                        detail="Traversal payload 后响应出现系统文件特征内容。",
                        evidence={
                            "payload": payload,
                            "url": mutated["url"],
                            "status_code": result["status_code"],
                            "body_preview": text[:500],
                        },
                    )
                )
                return findings
        return findings

    findings = []
    for payload in PATH_PAYLOADS[:2]:
        mutated = copy.deepcopy(request_data)
        mutated["url"] = re.sub(r"\{[^}]+\}", payload, mutated["url"], count=1)
        result = _execute(api.method, mutated)
        if result["status_code"] >= 500:
            findings.append(
                _finding(
                    strategy="path_traversal",
                    strategy_name="路径遍历",
                    severity="medium",
                    title="路径参数 traversal 导致 5xx",
                    detail="替换路径参数为 traversal payload 后服务端异常。",
                    evidence={
                        "payload": payload,
                        "url": mutated["url"],
                        "status_code": result["status_code"],
                    },
                )
            )
            break
    return findings


def _test_oversized_input(api: ApiInterface, request_data: dict[str, Any]) -> list[dict[str, Any]]:
    payload = "A" * 5000
    mutated = copy.deepcopy(request_data)
    if mutated.get("params"):
        key = next(iter(mutated["params"]))
        mutated["params"][key] = payload
    elif mutated.get("body"):
        path = _iter_string_paths(mutated["body"])[0][0]
        mutated["body"] = _set_path(mutated["body"], path, payload)
    else:
        mutated["url"] = _inject_query(mutated["url"], payload[:200])
    result = _execute(api.method, mutated)
    if result["status_code"] >= 500 or result["error"]:
        return [
            _finding(
                strategy="oversized_input",
                strategy_name="超长输入",
                severity="medium",
                title="超长输入导致服务异常",
                detail="发送 5000 字符超长值后接口返回 5xx 或请求失败。",
                evidence={
                    "payload_size": 5000,
                    "status_code": result["status_code"],
                    "error": result["error"],
                },
            )
        ]
    return []


def _test_special_chars(api: ApiInterface, request_data: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for payload in SPECIAL_PAYLOADS[:4]:
        mutated = copy.deepcopy(request_data)
        if mutated.get("params"):
            key = next(iter(mutated["params"]))
            mutated["params"][key] = payload
        elif mutated.get("body"):
            path = _iter_string_paths(mutated["body"])[0][0]
            mutated["body"] = _set_path(mutated["body"], path, payload)
        else:
            mutated["url"] = _inject_query(mutated["url"], payload)
        result = _execute(api.method, mutated)
        if result["status_code"] >= 500:
            findings.append(
                _finding(
                    strategy="special_chars",
                    strategy_name="特殊字符",
                    severity="low",
                    title="特殊字符触发 5xx",
                    detail=f"输入 {payload!r} 后服务端返回异常状态码。",
                    evidence={
                        "payload": payload,
                        "status_code": result["status_code"],
                        "body_preview": result["body"][:300],
                    },
                )
            )
            break
    return findings


STRATEGY_RUNNERS = {
    "unauth_access": _test_unauth,
    "invalid_token": _test_invalid_token,
    "sql_injection": _test_sql_injection,
    "xss": _test_xss,
    "path_traversal": _test_path_traversal,
    "oversized_input": _test_oversized_input,
    "special_chars": _test_special_chars,
}


def _resolve_target_dependencies(
    target: SecurityScanTarget,
    variables: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any] | None]:
    result_by_id: dict[int, dict[str, Any]] = {}
    auth_session: dict[str, Any] | None = None
    for dep_id in _collect_dep_ids(target):
        if dep_id in result_by_id:
            continue
        dep = SecurityScanTarget.objects.filter(id=dep_id).first()
        if not dep:
            continue
        sub = _execute_target_baseline(dep, variables, result_by_id, auth_session)
        result_by_id[dep_id] = sub
        if sub.get("success") and is_auth_endpoint(dep):
            auth_session = sub
    return result_by_id, auth_session


def _execute_target_baseline(
    target: SecurityScanTarget,
    variables: dict[str, Any],
    result_by_id: dict[int, dict[str, Any]],
    auth_session: dict[str, Any] | None,
) -> dict[str, Any]:
    request_data = _build_request(target, variables)
    _apply_all_mappings(target, request_data, result_by_id, auth_session)
    result = _execute(target.method, request_data)
    parsed = result.get("parsed_body") or _parse_response_body(result.get("body") or "")
    status = result.get("status_code") or 0
    return {
        "interface_id": target.id,
        "name": target.name,
        "method": target.method,
        "url": request_data["url"],
        "success": 200 <= status < 400,
        "status_code": status,
        "headers": result.get("headers") or {},
        "body": result.get("body") or "",
        "parsed_body": parsed,
        "error": result.get("error") or "",
    }


def _prepare_target_request(
    target: SecurityScanTarget,
    variables: dict[str, Any],
    result_by_id: dict[int, dict[str, Any]],
    auth_session: dict[str, Any] | None,
) -> dict[str, Any]:
    request_data = _build_request(target, variables)
    _apply_all_mappings(target, request_data, result_by_id, auth_session)
    return request_data


def scan_target(
    target: SecurityScanTarget,
    variables: dict[str, Any],
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    selected = strategies or [s["id"] for s in ATTACK_STRATEGIES if s.get("default")]
    result_by_id, auth_session = _resolve_target_dependencies(target, variables)
    request_data = _prepare_target_request(target, variables, result_by_id, auth_session)
    baseline = _execute(target.method, request_data)

    findings: list[dict[str, Any]] = []
    for strategy_id in selected:
        runner = STRATEGY_RUNNERS.get(strategy_id)
        if not runner:
            continue
        if strategy_id == "unauth_access":
            findings.extend(runner(target, request_data, baseline))
        elif strategy_id == "invalid_token":
            findings.extend(runner(target, request_data))
        else:
            findings.extend(runner(target, request_data))

    severity_rank = {"high": 3, "medium": 2, "low": 1, "info": 0, "pass": -1}
    risk_findings = [f for f in findings if f["severity"] in ("high", "medium", "low")]
    max_severity = "pass"
    if risk_findings:
        max_severity = max(risk_findings, key=lambda f: severity_rank.get(f["severity"], 0))["severity"]
    elif findings:
        max_severity = "info"

    return {
        "target_id": target.id,
        "source_interface_id": target.source_interface_id,
        "name": target.name,
        "method": target.method,
        "url": request_data["url"],
        "baseline_status": baseline.get("status_code"),
        "baseline_ok": 200 <= baseline.get("status_code", 0) < 400,
        "risk_level": max_severity,
        "findings": findings,
        "finding_count": len(findings),
        "risk_count": len(risk_findings),
    }


def run_security_scan_for_targets(
    target_ids: list[int],
    variables: dict[str, Any] | None = None,
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    variables = dict(variables or {})
    if not target_ids:
        return {
            "results": [],
            "summary": {"total": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "pass": 0},
        }

    targets = list(
        SecurityScanTarget.objects.filter(id__in=target_ids).select_related("depends_on").order_by("sort_order", "id")
    )
    id_order = {i: idx for idx, i in enumerate(target_ids)}
    targets.sort(key=lambda t: id_order.get(t.id, 9999))

    results = [scan_target(t, variables, strategies) for t in targets]
    summary = {"total": len(results), "high": 0, "medium": 0, "low": 0, "info": 0, "pass": 0}
    for item in results:
        level = item.get("risk_level") or "pass"
        if level in summary:
            summary[level] += 1
    return {"results": results, "summary": summary, "strategies": strategies or []}


def scan_interface(
    api: ApiInterface,
    variables: dict[str, Any],
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    selected = strategies or [s["id"] for s in ATTACK_STRATEGIES if s.get("default")]
    result_by_id, auth_session = _resolve_dependencies(api, variables)
    request_data = _prepare_request(api, variables, result_by_id, auth_session)
    baseline = _execute(api.method, request_data)

    findings: list[dict[str, Any]] = []
    for strategy_id in selected:
        runner = STRATEGY_RUNNERS.get(strategy_id)
        if not runner:
            continue
        if strategy_id == "unauth_access":
            findings.extend(runner(api, request_data, baseline))
        elif strategy_id == "invalid_token":
            findings.extend(runner(api, request_data))
        else:
            findings.extend(runner(api, request_data))

    severity_rank = {"high": 3, "medium": 2, "low": 1, "info": 0, "pass": -1}
    risk_findings = [f for f in findings if f["severity"] in ("high", "medium", "low")]
    max_severity = "pass"
    if risk_findings:
        max_severity = max(risk_findings, key=lambda f: severity_rank.get(f["severity"], 0))["severity"]
    elif findings:
        max_severity = "info"

    return {
        "interface_id": api.id,
        "name": api.name,
        "method": api.method,
        "url": request_data["url"],
        "baseline_status": baseline.get("status_code"),
        "baseline_ok": 200 <= baseline.get("status_code", 0) < 400,
        "risk_level": max_severity,
        "findings": findings,
        "finding_count": len(findings),
        "risk_count": len(risk_findings),
    }


def run_security_scan(
    interface_ids: list[int],
    variables: dict[str, Any] | None = None,
    strategies: list[str] | None = None,
) -> dict[str, Any]:
    variables = dict(variables or {})
    if not interface_ids:
        return {
            "results": [],
            "summary": {"total": 0, "high": 0, "medium": 0, "low": 0, "info": 0, "pass": 0},
        }

    apis = list(
        ApiInterface.objects.filter(id__in=interface_ids).select_related("depends_on").order_by("sort_order", "id")
    )
    id_order = {i: idx for idx, i in enumerate(interface_ids)}
    apis.sort(key=lambda a: id_order.get(a.id, 9999))

    results = [scan_interface(api, variables, strategies) for api in apis]
    summary = {"total": len(results), "high": 0, "medium": 0, "low": 0, "info": 0, "pass": 0}
    for item in results:
        level = item.get("risk_level") or "pass"
        if level in summary:
            summary[level] += 1
    return {"results": results, "summary": summary, "strategies": strategies or []}
