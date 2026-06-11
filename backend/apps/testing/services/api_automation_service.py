"""接口自动化：依赖链执行、变量提取、Python 代码生成。"""

from __future__ import annotations

import copy
import json
import re
from typing import Any

import requests as http_requests

from apps.testing.models import ApiInterface

from .api_dependency_service import (
    DEFAULT_AUTH_MAPPING,
    is_auth_endpoint,
    needs_authorization,
)


def _deep_get(data: Any, path: str) -> Any:
    if not path:
        return data
    current = data
    for part in path.split("."):
        if part in ("body", "response"):
            if isinstance(current, dict) and part in current:
                current = current[part]
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError, TypeError):
                return None
        else:
            return None
        if current is None:
            return None
    return current


def _apply_transform(transform: str, value: Any) -> Any:
    if not transform:
        return value
    text = str(value)
    for placeholder in ("{value}", "{1}", "{0}"):
        if placeholder in transform:
            return transform.replace(placeholder, text)
    return transform + text


def _deep_set(target: dict, path: str, value: Any) -> None:
    parts = path.split(".")
    if not parts:
        return
    root_key = parts[0]
    if root_key not in ("headers", "params", "body"):
        return
    node = target.setdefault(root_key, {})
    for part in parts[1:-1]:
        if not isinstance(node, dict):
            return
        node = node.setdefault(part, {})
    if parts[-1:]:
        if isinstance(node, dict):
            node[parts[-1]] = value


def _apply_mapping_value(request_data: dict[str, Any], target: str, value: Any) -> None:
    """支持 headers/params/body 及 url.order_id 等路径占位符替换。"""
    if target.startswith("url"):
        url = str(request_data.get("url", ""))
        if target == "url":
            request_data["url"] = str(value)
            return
        key = target.split(".", 1)[1]
        request_data["url"] = url.replace(f"{{{key}}}", str(value))
        return
    _deep_set(request_data, target, value)


def _collect_dep_ids(api: ApiInterface) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    if api.depends_on_id and api.depends_on_id not in seen:
        ids.append(api.depends_on_id)
        seen.add(api.depends_on_id)
    for mapping in api.dependency_mappings or []:
        dep_id = mapping.get("depends_on")
        if dep_id and dep_id not in seen:
            ids.append(int(dep_id))
            seen.add(int(dep_id))
    return ids


def _resolve_mapping_dep(
    mapping: dict[str, Any],
    default_dep_id: int | None,
    result_by_id: dict[int, dict[str, Any]],
    auth_session_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    dep_id = mapping.get("depends_on") or default_dep_id
    if dep_id and int(dep_id) in result_by_id:
        return result_by_id[int(dep_id)]
    if auth_session_result and "access_token" in str(mapping.get("source", "")):
        return auth_session_result
    return None


def _apply_all_mappings(
    api: ApiInterface,
    request_data: dict[str, Any],
    result_by_id: dict[int, dict[str, Any]],
    auth_session_result: dict[str, Any] | None = None,
    override_mappings: list[dict[str, Any]] | None = None,
) -> None:
    mappings = list(
        override_mappings if override_mappings is not None else (api.dependency_mappings or [])
    )

    if auth_session_result and needs_authorization(api) and not is_auth_endpoint(api):
        if not any("access_token" in str(m.get("source", "")) for m in mappings):
            mappings = [
                {
                    "source": "body.data.access_token",
                    "target": "headers.Authorization",
                    "transform": "Bearer {value}",
                    "depends_on": auth_session_result.get("interface_id"),
                },
                *mappings,
            ]

    for mapping in mappings:
        source = mapping.get("source", "")
        target = mapping.get("target", "")
        if not source or not target:
            continue
        dep_result = _resolve_mapping_dep(
            mapping, api.depends_on_id, result_by_id, auth_session_result
        )
        if not dep_result:
            continue
        response_data = {
            "status_code": dep_result.get("status_code"),
            "headers": dep_result.get("headers", {}),
            "body": dep_result.get("parsed_body"),
        }
        value = _deep_get(response_data, source)
        if value is None:
            continue
        value = _apply_transform(mapping.get("transform", ""), value)
        _apply_mapping_value(request_data, target, value)


def _replace_variables(text: str, variables: dict[str, Any]) -> str:
    if not isinstance(text, str):
        return text
    for key, val in variables.items():
        text = text.replace(f"{{{{{key}}}}}", str(val))
    return text


def _resolve_url(url: str, variables: dict[str, Any]) -> str:
    """支持 {{baseUrl}} 占位符，并将 /auth/login 这类相对路径拼到 baseUrl 上。"""
    url = _replace_variables(url, variables).strip()
    if url.startswith(("http://", "https://")):
        return url
    base = variables.get("baseUrl") or variables.get("base_url") or ""
    base = str(base).strip().rstrip("/")
    if not base:
        return url
    if url.startswith("/"):
        return f"{base}{url}"
    return f"{base}/{url.lstrip('/')}"


def _apply_variables_obj(obj: Any, variables: dict[str, Any]) -> Any:
    if isinstance(obj, str):
        return _replace_variables(obj, variables)
    if isinstance(obj, dict):
        return {k: _apply_variables_obj(v, variables) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_apply_variables_obj(v, variables) for v in obj]
    return obj


def _parse_response_body(text: str) -> Any:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"_raw": text}


def _sanitize_headers(headers: dict[str, Any]) -> dict[str, str]:
    """HTTP 头必须是 latin-1，过滤掉中文等非法键值。"""
    clean: dict[str, str] = {}
    for key, val in (headers or {}).items():
        if not isinstance(key, str):
            continue
        text_val = str(val) if val is not None else ""
        try:
            key.encode("latin-1")
            text_val.encode("latin-1")
        except UnicodeEncodeError:
            continue
        if key.strip():
            clean[key.strip()] = text_val
    return clean


def _build_request(api: ApiInterface, variables: dict[str, Any]) -> dict[str, Any]:
    url = _resolve_url(api.url, variables)
    headers = _sanitize_headers(_apply_variables_obj(copy.deepcopy(api.headers or {}), variables))
    params = _apply_variables_obj(copy.deepcopy(api.params or {}), variables)
    body = _apply_variables_obj(copy.deepcopy(api.body or {}), variables)
    return {"url": url, "headers": headers, "params": params, "body": body}


def _apply_dependency_mappings(
    api: ApiInterface,
    request_data: dict[str, Any],
    dep_result: dict[str, Any],
    mappings: list[dict[str, Any]] | None = None,
) -> None:
    """兼容旧逻辑：所有映射来自同一前置结果。"""
    dep_id = dep_result.get("interface_id")
    wrapped = []
    for mapping in mappings if mappings is not None else (api.dependency_mappings or []):
        item = dict(mapping)
        if not item.get("depends_on") and dep_id:
            item["depends_on"] = dep_id
        wrapped.append(item)
    _apply_all_mappings(api, request_data, {dep_id: dep_result} if dep_id else {}, dep_result, wrapped)


def _topological_order(interfaces: list[ApiInterface]) -> list[ApiInterface]:
    by_id = {item.id: item for item in interfaces}
    selected_ids = set(by_id.keys())
    ordered: list[ApiInterface] = []
    visited: set[int] = set()

    def visit(node: ApiInterface) -> None:
        if node.id in visited:
            return
        if node.depends_on_id and node.depends_on_id in selected_ids:
            visit(by_id[node.depends_on_id])
        visited.add(node.id)
        ordered.append(node)

    for item in interfaces:
        visit(item)
    return ordered


def run_single_interface(
    api: ApiInterface,
    variables: dict[str, Any],
    dep_result: dict[str, Any] | None = None,
    *,
    result_by_id: dict[int, dict[str, Any]] | None = None,
    auth_session_result: dict[str, Any] | None = None,
    _resolve_dep: bool = True,
    override_mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if result_by_id is None:
        result_by_id = {}
    if _resolve_dep:
        for dep_id in _collect_dep_ids(api):
            if dep_id not in result_by_id:
                dep_api = ApiInterface.objects.filter(id=dep_id).first()
                if dep_api:
                    sub = run_single_interface(
                        dep_api,
                        variables,
                        result_by_id=result_by_id,
                        auth_session_result=auth_session_result,
                        _resolve_dep=True,
                    )
                    result_by_id[dep_id] = sub
                    if sub.get("success") and is_auth_endpoint(dep_api):
                        auth_session_result = sub
    request_data = _build_request(api, variables)
    if result_by_id:
        _apply_all_mappings(
            api,
            request_data,
            result_by_id,
            auth_session_result,
            override_mappings,
        )
    elif dep_result:
        _apply_dependency_mappings(api, request_data, dep_result, override_mappings)

    method = api.method.upper()
    kwargs: dict[str, Any] = {
        "method": method,
        "url": request_data["url"],
        "headers": request_data["headers"],
        "timeout": 15,
    }
    if method == "GET":
        kwargs["params"] = request_data["params"]
    else:
        kwargs["json"] = request_data["body"] if request_data["body"] else None
        if request_data["params"]:
            kwargs["params"] = request_data["params"]

    try:
        resp = http_requests.request(**kwargs)
        parsed = _parse_response_body(resp.text)
        error = ""
        if resp.status_code >= 400:
            if resp.status_code == 405:
                error = (
                    f"HTTP 405：{request_data['url']} 不支持 {method} 请求。"
                    f"请检查请求方法是否与接口文档一致（如登录应为 POST，查询应为 GET）。"
                )
            elif isinstance(parsed, dict):
                error = str(
                    parsed.get("detail")
                    or parsed.get("message")
                    or parsed.get("error")
                    or f"HTTP {resp.status_code}"
                )
            else:
                error = f"HTTP {resp.status_code}"
        return {
            "interface_id": api.id,
            "name": api.name,
            "method": api.method,
            "url": request_data["url"],
            "success": 200 <= resp.status_code < 400,
            "status_code": resp.status_code,
            "headers": dict(resp.headers),
            "body": resp.text[:5000],
            "parsed_body": parsed,
            "error": error,
        }
    except Exception as exc:
        return {
            "interface_id": api.id,
            "name": api.name,
            "method": api.method,
            "url": request_data["url"],
            "success": False,
            "status_code": 0,
            "headers": {},
            "body": "",
            "parsed_body": {},
            "error": str(exc),
        }


def run_automation(
    interface_ids: list[int],
    initial_variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    variables = dict(initial_variables or {})
    if not interface_ids:
        return {"results": [], "passed": 0, "failed": 0, "total": 0}

    by_id = {
        api.id: api
        for api in ApiInterface.objects.filter(id__in=interface_ids).select_related("depends_on")
    }
    ordered = [by_id[i] for i in interface_ids if i in by_id]
    if not ordered:
        return {"results": [], "passed": 0, "failed": 0, "total": 0}

    results: list[dict[str, Any]] = []
    result_by_id: dict[int, dict[str, Any]] = {}
    auth_session_result: dict[str, Any] | None = None

    for api in ordered:
        item = run_single_interface(
            api,
            variables,
            result_by_id=result_by_id,
            auth_session_result=auth_session_result,
            _resolve_dep=False,
        )
        results.append(item)
        result_by_id[api.id] = item

        if item.get("success") and is_auth_endpoint(api) and item.get("parsed_body"):
            auth_session_result = item

    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    return {"results": results, "passed": passed, "failed": failed, "total": len(results)}


_PYTHON_RUNNER_TEMPLATE = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接口自动化脚本（按勾选顺序执行）
生成后可直接运行: python api_automation.py
依赖: pip install requests
"""
from __future__ import annotations

import json
import sys

import requests

BASE_URL = __BASE_URL__
DEFAULT_AUTH_MAPPING = json.loads(__AUTH_MAPPING_JSON__)
STEPS = json.loads(__STEPS_JSON__)


def deep_get(data, path):
    current = data
    for part in path.split("."):
        if part in ("body", "response"):
            if isinstance(current, dict) and part in current:
                current = current[part]
            continue
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def apply_transform(transform, value):
    if not transform:
        return value
    text = str(value)
    for placeholder in ("{value}", "{1}", "{0}"):
        if placeholder in transform:
            return transform.replace(placeholder, text)
    return transform + text


def apply_mapping_value(request_data, target, value):
    if target.startswith("url"):
        url = str(request_data.get("url", ""))
        if target == "url":
            request_data["url"] = str(value)
            return
        key = target.split(".", 1)[1]
        request_data["url"] = url.replace("{" + key + "}", str(value))
        return
    parts = target.split(".")
    root = parts[0]
    if root not in ("headers", "params", "body"):
        return
    node = request_data.setdefault(root, {})
    for part in parts[1:-1]:
        node = node.setdefault(part, {})
    if parts[1:]:
        node[parts[-1]] = value


def apply_all_mappings(step, request_data, results_by_id, auth_session):
    mappings = list(step.get("mappings") or [])
    default_dep = step.get("depends_on")
    if auth_session and needs_auth(step) and not is_auth_step(step):
        if not any("access_token" in str(m.get("source", "")) for m in mappings):
            mappings = [{
                "source": "body.data.access_token",
                "target": "headers.Authorization",
                "transform": "Bearer {value}",
                "depends_on": auth_session.get("id"),
            }, *mappings]
    for mapping in mappings:
        source = mapping.get("source", "")
        target = mapping.get("target", "")
        if not source or not target:
            continue
        dep_id = mapping.get("depends_on") or default_dep
        dep_result = None
        if dep_id and dep_id in results_by_id:
            dep_result = results_by_id[dep_id]
        elif auth_session and "access_token" in str(source):
            dep_result = auth_session
        if not dep_result:
            continue
        response_data = {
            "status_code": dep_result.get("status_code"),
            "headers": dep_result.get("headers", {}),
            "body": dep_result.get("parsed_body"),
        }
        value = deep_get(response_data, source)
        if value is None:
            continue
        value = apply_transform(mapping.get("transform", ""), value)
        apply_mapping_value(request_data, target, value)


def build_url(path):
    path = (path or "").strip()
    if path.startswith(("http://", "https://")):
        return path
    base = BASE_URL.rstrip("/")
    return base + (path if path.startswith("/") else "/" + path.lstrip("/"))


def sanitize_headers(headers):
    clean = {}
    for key, val in (headers or {}).items():
        if not isinstance(key, str):
            continue
        text_val = str(val) if val is not None else ""
        try:
            key.encode("latin-1")
            text_val.encode("latin-1")
        except UnicodeEncodeError:
            continue
        if key.strip():
            clean[key.strip()] = text_val
    return clean


def needs_auth(step):
    headers = step.get("headers") or {}
    for key, val in headers.items():
        if str(key).lower() == "authorization":
            return True
        if isinstance(val, str) and "bearer" in val.lower():
            return True
    url = (step.get("url") or "").lower()
    if is_auth_step(step):
        return False
    for prefix in ("/users/", "/products", "/cart", "/orders"):
        if prefix in url:
            return True
    return False


def is_auth_step(step):
    url = (step.get("url") or "").lower()
    name = step.get("name") or ""
    if "/auth/" in url or url.rstrip("/").endswith("/login"):
        return True
    if "登录" in name or "login" in name.lower():
        return True
    if "/auth/refresh" in url:
        return True
    return False


def build_request(step):
    return {
        "url": build_url(step.get("url", "")),
        "headers": sanitize_headers(step.get("headers") or {}),
        "params": step.get("params") or {},
        "body": step.get("body") or {},
    }


def execute_step(method, req):
    method = (method or "GET").upper()
    kwargs = {"url": req["url"], "headers": req.get("headers") or {}, "timeout": 15}
    if method == "GET":
        kwargs["params"] = req.get("params") or {}
        return requests.get(**kwargs)
    kwargs["json"] = req.get("body") or None
    if req.get("params"):
        kwargs["params"] = req["params"]
    return requests.request(method, **kwargs)


def run():
    results_by_id = {}
    auth_session = None
    all_results = []
    total = len(STEPS)

    for index, step in enumerate(STEPS, start=1):
        name = step.get("name") or "未命名接口"
        method = step.get("method", "GET")
        print(f"\\n[{index}/{total}] {method} {name}")
        print(f"  -> {build_url(step.get('url', ''))}")

        req = build_request(step)
        apply_all_mappings(step, req, results_by_id, auth_session)

        try:
            resp = execute_step(method, req)
        except requests.RequestException as exc:
            print(f"  !! 请求异常: {exc}")
            sys.exit(1)

        parsed = None
        try:
            parsed = resp.json()
        except Exception:
            parsed = {"_raw": resp.text}

        result = {
            "id": step.get("id"),
            "name": name,
            "method": method,
            "url": req["url"],
            "status_code": resp.status_code,
            "success": 200 <= resp.status_code < 400,
            "parsed_body": parsed,
        }
        all_results.append(result)
        if step.get("id") is not None:
            results_by_id[step["id"]] = result

        if result["success"]:
            print(f"  OK {resp.status_code}")
            if is_auth_step(step) and parsed:
                auth_session = result
        else:
            print(f"  FAIL {resp.status_code}")
            print(json.dumps(parsed, ensure_ascii=False, indent=2))
            sys.exit(1)

    print("\\n全部接口执行成功")
    print(json.dumps(all_results, ensure_ascii=False, indent=2))
    return all_results


if __name__ == "__main__":
    run()
'''


def generate_python_script(
    interface_ids: list[int],
    variables: dict[str, Any] | None = None,
) -> str:
    """按勾选顺序生成可直接 python 执行的接口自动化脚本。"""
    if not interface_ids:
        return "# 未选择接口\n"

    variables = variables or {}
    base_url = str(
        variables.get("baseUrl") or variables.get("base_url") or "http://127.0.0.1:9000/v1"
    ).strip().rstrip("/")

    by_id = {
        api.id: api
        for api in ApiInterface.objects.filter(id__in=interface_ids).select_related("depends_on")
    }
    ordered = [by_id[i] for i in interface_ids if i in by_id]
    if not ordered:
        return "# 未选择接口\n"

    steps = [
        {
            "id": api.id,
            "name": api.name,
            "method": api.method.upper(),
            "url": api.url or "",
            "headers": api.headers or {},
            "params": api.params or {},
            "body": api.body or {},
            "depends_on": api.depends_on_id,
            "mappings": api.dependency_mappings or [],
        }
        for api in ordered
    ]

    steps_json = json.dumps(steps, ensure_ascii=False)
    auth_json = json.dumps(DEFAULT_AUTH_MAPPING, ensure_ascii=False)
    return (
        _PYTHON_RUNNER_TEMPLATE.replace("__BASE_URL__", json.dumps(base_url, ensure_ascii=False))
        .replace("__AUTH_MAPPING_JSON__", json.dumps(auth_json, ensure_ascii=False))
        .replace("__STEPS_JSON__", json.dumps(steps_json, ensure_ascii=False))
    )
