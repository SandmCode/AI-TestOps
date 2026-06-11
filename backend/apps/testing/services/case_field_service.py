from __future__ import annotations

from typing import Any

from apps.projects.models import Project

from ..models import TestCase, TestCaseFieldDefinition

DEFAULT_CASE_FIELDS: list[dict[str, Any]] = [
    {
        "key": "case_no",
        "label": "标号",
        "field_type": "text",
        "storage": "column",
        "column_name": "case_no",
        "searchable": True,
        "show_in_list": True,
        "show_in_filter": True,
        "sort_order": 0,
        "is_system": True,
    },
    {
        "key": "title",
        "label": "用例标题",
        "field_type": "text",
        "storage": "column",
        "column_name": "title",
        "required": True,
        "searchable": True,
        "show_in_list": True,
        "sort_order": 1,
        "is_system": True,
    },
    {
        "key": "module",
        "label": "模块",
        "field_type": "text",
        "storage": "column",
        "column_name": "module",
        "searchable": True,
        "show_in_list": True,
        "show_in_filter": True,
        "sort_order": 2,
        "is_system": True,
    },
    {
        "key": "precondition",
        "label": "前置条件",
        "field_type": "textarea",
        "storage": "column",
        "column_name": "precondition",
        "searchable": True,
        "show_in_list": False,
        "sort_order": 3,
        "is_system": True,
    },
    {
        "key": "steps",
        "label": "测试步骤",
        "field_type": "textarea",
        "storage": "column",
        "column_name": "steps",
        "searchable": True,
        "show_in_list": True,
        "sort_order": 4,
        "is_system": True,
    },
    {
        "key": "expected",
        "label": "预期结果",
        "field_type": "textarea",
        "storage": "column",
        "column_name": "expected",
        "searchable": True,
        "show_in_list": True,
        "sort_order": 5,
        "is_system": True,
    },
    {
        "key": "postcondition",
        "label": "后置条件",
        "field_type": "textarea",
        "storage": "column",
        "column_name": "postcondition",
        "searchable": False,
        "show_in_list": False,
        "sort_order": 6,
        "is_system": True,
    },
    {
        "key": "actual",
        "label": "实际结果",
        "field_type": "textarea",
        "storage": "column",
        "column_name": "actual",
        "searchable": False,
        "show_in_list": False,
        "sort_order": 7,
        "is_system": True,
    },
    {
        "key": "priority",
        "label": "优先级",
        "field_type": "priority",
        "storage": "column",
        "column_name": "priority",
        "show_in_list": True,
        "show_in_filter": True,
        "sort_order": 8,
        "is_system": True,
    },
    {
        "key": "executor",
        "label": "执行人",
        "field_type": "text",
        "storage": "column",
        "column_name": "executor",
        "show_in_filter": True,
        "sort_order": 9,
        "is_system": True,
    },
    {
        "key": "passed",
        "label": "是否通过",
        "field_type": "passed",
        "storage": "column",
        "column_name": "passed",
        "show_in_list": True,
        "show_in_filter": True,
        "sort_order": 10,
        "is_system": True,
    },
    {
        "key": "created_at",
        "label": "创建时间",
        "field_type": "date",
        "storage": "column",
        "column_name": "created_at",
        "show_in_list": False,
        "show_in_filter": False,
        "sort_order": 11,
        "is_system": True,
    },
]

COLUMN_FIELDS = {f["column_name"] for f in DEFAULT_CASE_FIELDS if f.get("column_name")}


def ensure_default_field_definitions(project_id: int | None = None) -> list[TestCaseFieldDefinition]:
    qs = TestCaseFieldDefinition.objects.filter(project_id=project_id)
    if qs.exists():
        return list(qs)
    created = []
    for item in DEFAULT_CASE_FIELDS:
        obj = TestCaseFieldDefinition.objects.create(project_id=project_id, **item)
        created.append(obj)
    return created


def get_project_field_definitions(project_id: int) -> list[TestCaseFieldDefinition]:
    defs = list(TestCaseFieldDefinition.objects.filter(project_id=project_id).order_by("sort_order", "id"))
    if defs:
        return defs
    return ensure_default_field_definitions(project_id)


def apply_field_values(case: TestCase, payload: dict[str, Any], definitions: list[TestCaseFieldDefinition]) -> None:
    extra = dict(case.extra_data or {})
    for field_def in definitions:
        if field_def.key not in payload:
            continue
        value = payload[field_def.key]
        if field_def.storage == "column" and field_def.column_name:
            setattr(case, field_def.column_name, value)
        else:
            extra[field_def.key] = value
    case.extra_data = extra


def extract_field_values(case: TestCase, definitions: list[TestCaseFieldDefinition]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    extra = case.extra_data or {}
    for field_def in definitions:
        if field_def.storage == "column" and field_def.column_name:
            data[field_def.key] = getattr(case, field_def.column_name, "")
        else:
            data[field_def.key] = extra.get(field_def.key, "")
    return data


def build_searchable_field_names(definitions: list[TestCaseFieldDefinition]) -> list[str]:
    names: list[str] = []
    for field_def in definitions:
        if not field_def.searchable:
            continue
        if field_def.storage == "column" and field_def.column_name:
            names.append(field_def.column_name)
    return names


def get_ai_field_payload(definitions: list[TestCaseFieldDefinition]) -> list[dict[str, Any]]:
    """AI 生成字段与表单字段配置完全一致（排除只读 created_at）。"""
    payload = []
    for field_def in definitions:
        if field_def.key == "created_at":
            continue
        item: dict[str, Any] = {
            "key": field_def.key,
            "label": field_def.label,
            "field_type": field_def.field_type,
            "required": field_def.required,
        }
        if field_def.field_type == "priority":
            item["options"] = ["P0", "P1", "P2", "P3"]
        elif field_def.field_type == "select" and field_def.options:
            item["options"] = field_def.options
        payload.append(item)
    return payload


def _resolve_title_value(normalized: dict[str, Any], definitions: list[TestCaseFieldDefinition]) -> str:
    if str(normalized.get("title", "")).strip():
        return str(normalized["title"]).strip()
    for field_def in definitions:
        if field_def.key in {"title", "created_at"}:
            continue
        if field_def.required and str(normalized.get(field_def.key, "")).strip():
            return str(normalized[field_def.key]).strip()
    for field_def in sorted(definitions, key=lambda item: item.sort_order):
        if field_def.key in {"title", "created_at"}:
            continue
        if field_def.show_in_list and field_def.field_type in {"text", "textarea"}:
            val = str(normalized.get(field_def.key, "")).strip()
            if val:
                return val
    return "未命名用例"


def _apply_field_defaults(
    normalized: dict[str, Any],
    definitions: list[TestCaseFieldDefinition],
    *,
    apply_defaults: bool,
) -> None:
    if apply_defaults or "title" in normalized:
        if not str(normalized.get("title", "")).strip():
            normalized["title"] = _resolve_title_value(normalized, definitions)
    priority_def = next((d for d in definitions if d.key == "priority"), None)
    if priority_def and (apply_defaults or "priority" in normalized):
        if not str(normalized.get("priority", "")).strip():
            normalized["priority"] = "P2"


def normalize_case_payload(
    payload: dict[str, Any],
    definitions: list[TestCaseFieldDefinition],
    *,
    apply_defaults: bool = True,
) -> dict[str, Any]:
    data = dict(payload)
    key_set = {d.key for d in definitions}
    label_map = {d.label: d.key for d in definitions}
    normalized: dict[str, Any] = {}
    for raw_key, value in data.items():
        if raw_key in {"project", "sort_order", "test_point", "source_type", "id"}:
            normalized[raw_key] = value
            continue
        key = raw_key if raw_key in key_set else label_map.get(raw_key)
        if key:
            normalized[key] = value
    _apply_field_defaults(normalized, definitions, apply_defaults=apply_defaults)
    return normalized


def create_test_case_from_payload(
    project_id: int,
    payload: dict[str, Any],
    definitions: list[TestCaseFieldDefinition],
    *,
    test_point=None,
    source_type: str = "manual",
    sort_order: int = 0,
) -> TestCase:
    data = normalize_case_payload(payload, definitions)
    title = str(data.get("title") or "未命名用例").strip()
    tc = TestCase(
        project_id=project_id,
        test_point=test_point,
        title=title,
        source_type=source_type,
        sort_order=sort_order,
    )
    apply_field_values(tc, data, definitions)
    if not tc.title:
        tc.title = title
    tc.save()
    return tc
