"""压测目标：从接口自动化复制快照，独立存储。"""

from __future__ import annotations

from typing import Any

from django.db.models import Max

from apps.testing.models import ApiInterface, StressTestTarget


def _snapshot_fields(api: ApiInterface) -> dict[str, Any]:
    return {
        "name": api.name,
        "module": api.module,
        "method": api.method,
        "url": api.url,
        "headers": api.headers or {},
        "params": api.params or {},
        "body": api.body or {},
        "response_example": api.response_example or {},
        "description": api.description or "",
        "dependency_mappings": list(api.dependency_mappings or []),
    }


def _interface_target_map(project_id: int) -> dict[int, StressTestTarget]:
    mapping: dict[int, StressTestTarget] = {}
    for target in StressTestTarget.objects.filter(project_id=project_id):
        if target.source_interface_id:
            mapping[target.source_interface_id] = target
    return mapping


def import_targets_from_interfaces(
    project_id: int,
    interface_ids: list[int],
    *,
    replace: bool = True,
) -> dict[str, Any]:
    if not interface_ids:
        raise ValueError("interface_ids 不能为空")

    apis = list(
        ApiInterface.objects.filter(project_id=project_id, id__in=interface_ids).order_by("sort_order", "id")
    )
    if not apis:
        raise ValueError("未找到可导入的接口")

    id_order = {i: idx for idx, i in enumerate(interface_ids)}
    apis.sort(key=lambda a: id_order.get(a.id, 9999))

    before_count = StressTestTarget.objects.filter(project_id=project_id).count()
    removed_count = 0

    if replace:
        removed_count, _ = StressTestTarget.objects.filter(project_id=project_id).delete()
        max_order = -1
        existing_by_source: dict[int, StressTestTarget] = {}
    else:
        existing_by_source = _interface_target_map(project_id)
        max_order = StressTestTarget.objects.filter(project_id=project_id).aggregate(m=Max("sort_order"))["m"] or -1

    created: list[StressTestTarget] = []
    source_map: dict[int, StressTestTarget] = dict(existing_by_source)
    created_count = 0
    updated_count = 0

    for idx, api in enumerate(apis):
        fields = _snapshot_fields(api)
        if not replace and api.id in existing_by_source:
            target = existing_by_source[api.id]
            for key, val in fields.items():
                setattr(target, key, val)
            target.save()
            source_map[api.id] = target
            created.append(target)
            updated_count += 1
            continue

        target = StressTestTarget.objects.create(
            project_id=project_id,
            source_interface_id=api.id,
            sort_order=max_order + 1 + idx,
            **fields,
        )
        source_map[api.id] = target
        created.append(target)
        created_count += 1

    for api in apis:
        target = source_map.get(api.id)
        if not target or not api.depends_on_id:
            continue
        dep_target = source_map.get(api.depends_on_id)
        if dep_target:
            target.depends_on = dep_target
            target.save(update_fields=["depends_on"])

    for target in created:
        mappings = []
        changed = False
        for mapping in target.dependency_mappings or []:
            item = dict(mapping)
            dep_id = item.get("depends_on")
            if isinstance(dep_id, int) and dep_id in source_map:
                item["depends_on"] = source_map[dep_id].id
                changed = True
            mappings.append(item)
        if changed:
            target.dependency_mappings = mappings
            target.save(update_fields=["dependency_mappings"])

    total_count = StressTestTarget.objects.filter(project_id=project_id).count()

    return {
        "targets": created,
        "count": len(created),
        "replace": replace,
        "before_count": before_count,
        "after_count": total_count,
        "created_count": created_count,
        "updated_count": updated_count,
        "removed_count": removed_count,
    }


def detect_login_target(targets: list[StressTestTarget]) -> StressTestTarget | None:
    from .api_dependency_service import is_auth_endpoint

    for target in targets:
        url = (target.url or "").lower()
        if target.method == "POST" and ("/auth/login" in url or url.rstrip("/").endswith("/login")):
            return target
    for target in targets:
        if target.method == "POST" and is_auth_endpoint(target):
            return target
    return None


def bulk_configure_auth_dependencies(
    project_id: int,
    auth_target_id: int,
    *,
    overwrite: bool = False,
    only_unconfigured: bool = True,
    target_ids: list[int] | None = None,
) -> dict[str, Any]:
    from .api_dependency_service import is_auth_endpoint, needs_authorization

    auth_target = StressTestTarget.objects.filter(id=auth_target_id, project_id=project_id).first()
    if not auth_target:
        raise ValueError("登录接口不存在或不属于当前项目")

    qs = StressTestTarget.objects.filter(project_id=project_id)
    if target_ids:
        qs = qs.filter(id__in=target_ids)

    updated: list[str] = []
    skipped: list[str] = []

    for target in qs:
        if target.id == auth_target.id:
            continue
        if is_auth_endpoint(target):
            skipped.append(target.name)
            continue
        if not needs_authorization(target):
            skipped.append(target.name)
            continue
        if only_unconfigured and not overwrite and target.depends_on_id:
            skipped.append(target.name)
            continue

        target.depends_on = auth_target
        target.dependency_mappings = [
            {
                "source": "body.data.access_token",
                "target": "headers.Authorization",
                "transform": "Bearer {value}",
                "depends_on": auth_target.id,
            }
        ]
        target.save(update_fields=["depends_on", "dependency_mappings"])
        updated.append(target.name)

    return {
        "auth_target_id": auth_target.id,
        "auth_target_name": auth_target.name,
        "updated_count": len(updated),
        "updated": updated,
        "skipped_count": len(skipped),
    }
