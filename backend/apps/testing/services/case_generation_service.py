from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import close_old_connections

from ..models import AsyncTask, KnowledgeItem, TestCase, TestPoint
from .ai_service import AIService, AIServiceError

MAX_PARALLEL_WORKERS = 8

STRATEGY_LABELS = {
    "default": "综合策略",
    "equivalence": "等价类",
    "boundary": "边界值",
    "scenario": "场景法",
    "state": "状态迁移",
}


def _recall_rag(project_id: int, keyword: str) -> str:
    from django.db.models import Q

    items = KnowledgeItem.objects.filter(Q(project_id=project_id) | Q(project__isnull=True))
    if keyword:
        items = items.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
    return "\n".join(f"[{item.category}] {item.title}: {item.content[:150]}" for item in items[:3])


def _update_task_progress(task_id: int, *, completed: int, total: int, current_step: str) -> None:
    progress = int(completed / total * 100) if total else 0
    AsyncTask.objects.filter(pk=task_id).update(
        status="running",
        completed_steps=completed,
        total_steps=total,
        progress=progress,
        current_step=current_step,
    )


def _match_test_point(points: list[TestPoint], name: str) -> TestPoint | None:
    name = (name or "").strip()
    for tp in points:
        if tp.name == name:
            return tp
    for tp in points:
        if name in tp.name or tp.name in name:
            return tp
    return None


def _save_batch_cases(
    project_id: int,
    points: list[TestPoint],
    raw_cases: list[dict],
    *,
    sort_counter: list[int],
    save_lock: threading.Lock,
) -> int:
    saved = 0
    to_create: list[TestCase] = []
    with save_lock:
        point_map = {tp.name: tp for tp in points}
        for item in raw_cases:
            tp_name = str(item.get("test_point") or item.get("test_point_name") or "").strip()
            tp = point_map.get(tp_name) or _match_test_point(points, tp_name)
            if not tp:
                continue
            sort_counter[0] += 1
            to_create.append(
                TestCase(
                    project_id=project_id,
                    test_point=tp,
                    title=str(item.get("title") or tp.name).strip()[:300],
                    module=str(item.get("module") or tp.requirement.module or "").strip()[:100],
                    steps=str(item.get("steps") or "").strip(),
                    expected=str(item.get("expected") or "").strip(),
                    priority=str(item.get("priority") or "P2").strip()[:5] or "P2",
                    source_type="test_point",
                    sort_order=sort_counter[0],
                )
            )
        if to_create:
            TestCase.objects.bulk_create(to_create)
            saved = len(to_create)
    return saved


def run_batch_case_generation(task_id: int) -> None:
    close_old_connections()
    task = AsyncTask.objects.get(pk=task_id)
    meta = task.meta or {}
    test_point_ids: list[int] = meta.get("test_point_ids", [])
    strategies: list[str] = meta.get("strategies", ["default"])
    use_rag: bool = bool(meta.get("use_rag", False))

    points = list(
        TestPoint.objects.filter(id__in=test_point_ids).select_related("requirement", "requirement__project")
    )
    if not points:
        AsyncTask.objects.filter(pk=task_id).update(
            status="failed",
            error_message="未找到测试点",
            progress=0,
        )
        return

    project = points[0].requirement.project
    project_id = project.id
    total = len(strategies)

    AsyncTask.objects.filter(pk=task_id).update(
        status="running",
        total_steps=total,
        completed_steps=0,
        progress=0,
        current_step="准备生成...",
    )

    tp_payload = [
        {
            "name": tp.name,
            "module": tp.requirement.module,
            "point_type": tp.point_type,
            "description": tp.description,
        }
        for tp in points
    ]

    rag_context = ""
    if use_rag:
        keywords = " ".join(tp.name for tp in points[:5])
        rag_context = _recall_rag(project_id, keywords)

    ai = AIService()
    completed = 0
    created_count = 0
    errors: list[str] = []
    progress_lock = threading.Lock()
    save_lock = threading.Lock()
    sort_counter = [TestCase.objects.filter(project_id=project_id).count()]

    def _run_strategy(strategy: str) -> tuple[str, list[dict]]:
        close_old_connections()
        return strategy, ai.generate_test_cases_batch(tp_payload, strategy=strategy, rag_context=rag_context)

    workers = min(MAX_PARALLEL_WORKERS, total)
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_map = {executor.submit(_run_strategy, s): s for s in strategies}
            for future in as_completed(future_map):
                strategy = future_map[future]
                strategy_label = STRATEGY_LABELS.get(strategy, strategy)
                try:
                    _, raw_cases = future.result()
                    created_count += _save_batch_cases(
                        project_id,
                        points,
                        raw_cases,
                        sort_counter=sort_counter,
                        save_lock=save_lock,
                    )
                except AIServiceError as exc:
                    errors.append(str(exc))
                except Exception as exc:
                    errors.append(f"{strategy_label} 失败: {exc}")

                with progress_lock:
                    completed += 1
                    _update_task_progress(
                        task_id,
                        completed=completed,
                        total=total,
                        current_step=strategy_label,
                    )
    except Exception as exc:
        AsyncTask.objects.filter(pk=task_id).update(
            status="failed",
            error_message=str(exc),
            result=json.dumps({"count": created_count}, ensure_ascii=False),
        )
        return

    if created_count == 0:
        AsyncTask.objects.filter(pk=task_id).update(
            status="failed",
            error_message=errors[0] if errors else "未生成任何用例",
            progress=100,
            result=json.dumps({"count": 0, "errors": errors}, ensure_ascii=False),
        )
        return

    AsyncTask.objects.filter(pk=task_id).update(
        status="success",
        progress=100,
        completed_steps=total,
        current_step="完成",
        error_message="; ".join(errors[:3]),
        result=json.dumps({"count": created_count, "errors": errors}, ensure_ascii=False),
    )


def start_batch_case_generation(
    *,
    project_id: int,
    test_point_ids: list[int],
    strategies: list[str],
    use_rag: bool,
) -> AsyncTask:
    point_count = TestPoint.objects.filter(id__in=test_point_ids).count()
    task = AsyncTask.objects.create(
        task_name=f"AI 生成用例（{point_count} 测试点 × {len(strategies)} 策略）",
        task_type="case_generation",
        status="pending",
        project_id=project_id,
        total_steps=len(strategies),
        meta={
            "test_point_ids": test_point_ids,
            "strategies": strategies,
            "use_rag": use_rag,
        },
    )
    thread = threading.Thread(target=run_batch_case_generation, args=(task.id,), daemon=True)
    thread.start()
    return task
