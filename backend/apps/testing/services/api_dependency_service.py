"""接口依赖批量配置与自动识别。"""

from __future__ import annotations

from typing import Any

from apps.testing.models import ApiInterface

DEFAULT_AUTH_MAPPING: list[dict[str, str]] = [
    {"source": "body.data.access_token", "target": "headers.Authorization", "transform": "Bearer {value}"},
]


def needs_authorization(api: ApiInterface) -> bool:
    headers = api.headers or {}
    for key, val in headers.items():
        if str(key).lower() == "authorization":
            return True
        if isinstance(val, str) and "bearer" in val.lower():
            return True
    url = (api.url or "").lower()
    if is_auth_endpoint(api):
        return False
    protected_prefixes = ("/users/", "/products", "/cart", "/orders")
    return any(p in url for p in protected_prefixes)


def is_auth_endpoint(api: ApiInterface) -> bool:
    url = (api.url or "").lower()
    name = api.name or ""
    if "/auth/" in url or url.rstrip("/").endswith("/login"):
        return True
    if "登录" in name or "login" in name.lower():
        return True
    if "/auth/refresh" in url or "refresh" in url.lower() and api.method == "POST":
        return True
    return False


def detect_login_api(apis: list[ApiInterface]) -> ApiInterface | None:
    for api in apis:
        url = (api.url or "").lower()
        if api.method == "POST" and ("/auth/login" in url or url.rstrip("/").endswith("/login")):
            return api
    for api in apis:
        if api.method == "POST" and ("登录" in (api.name or "") or "login" in (api.name or "").lower()):
            return api
    return None


def bulk_configure_auth_dependencies(
    project_id: int,
    auth_api_id: int,
    *,
    overwrite: bool = False,
    only_unconfigured: bool = True,
    interface_ids: list[int] | None = None,
    mappings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """为需要 Authorization 的接口批量配置登录关联。"""
    auth_api = ApiInterface.objects.filter(id=auth_api_id, project_id=project_id).first()
    if not auth_api:
        raise ValueError("登录接口不存在或不属于当前项目")

    qs = ApiInterface.objects.filter(project_id=project_id)
    if interface_ids:
        qs = qs.filter(id__in=interface_ids)

    updated: list[str] = []
    skipped: list[str] = []

    for api in qs:
        if api.id == auth_api.id:
            continue
        if is_auth_endpoint(api):
            skipped.append(api.name)
            continue
        if not needs_authorization(api):
            skipped.append(api.name)
            continue
        if only_unconfigured and not overwrite and api.depends_on_id:
            skipped.append(api.name)
            continue

        api.depends_on = auth_api
        api.dependency_mappings = [
            {
                "source": "body.data.access_token",
                "target": "headers.Authorization",
                "transform": "Bearer {value}",
                "depends_on": auth_api.id,
            }
        ]
        api.save(update_fields=["depends_on", "dependency_mappings"])
        updated.append(api.name)

    return {
        "auth_api_id": auth_api.id,
        "auth_api_name": auth_api.name,
        "updated_count": len(updated),
        "updated": updated,
        "skipped_count": len(skipped),
    }


def auto_configure_after_import(project_id: int, created_ids: list[int]) -> dict[str, Any]:
    """导入后自动配置登录关联。"""
    apis = list(ApiInterface.objects.filter(project_id=project_id, id__in=created_ids))
    login = detect_login_api(apis)
    if not login:
        return {"auto_configured": False, "reason": "未找到登录接口"}
    return {
        "auto_configured": True,
        **bulk_configure_auth_dependencies(
            project_id,
            login.id,
            overwrite=False,
            only_unconfigured=True,
            interface_ids=created_ids,
        ),
    }
