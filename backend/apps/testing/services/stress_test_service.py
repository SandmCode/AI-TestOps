"""接口压测：并发请求、吞吐与响应时延统计。"""

from __future__ import annotations

import copy
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Any

import requests as http_requests
from django.utils import timezone

from apps.testing.models import StressTestRun, StressTestTarget

from .api_automation_service import (
    _apply_all_mappings,
    _build_request,
    _collect_dep_ids,
    _parse_response_body,
)
from .api_dependency_service import is_auth_endpoint

_stop_events: dict[int, threading.Event] = {}
MAX_LATENCY_SAMPLES = 50000


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * p / 100.0
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _execute_http(method: str, request_data: dict[str, Any]) -> dict[str, Any]:
    method = (method or "GET").upper()
    kwargs: dict[str, Any] = {
        "method": method,
        "url": request_data["url"],
        "headers": request_data.get("headers") or {},
        "timeout": 30,
    }
    if method == "GET":
        kwargs["params"] = request_data.get("params") or {}
    else:
        body = request_data.get("body")
        kwargs["json"] = body if body else None
        if request_data.get("params"):
            kwargs["params"] = request_data["params"]
    try:
        resp = http_requests.request(**kwargs)
        return {
            "status_code": resp.status_code,
            "success": 200 <= resp.status_code < 400,
            "body": resp.text[:2000],
            "error": "",
        }
    except Exception as exc:
        return {"status_code": 0, "success": False, "body": "", "error": str(exc)}


def _execute_dep_chain(
    dep_ids: set[int],
    variables: dict[str, Any],
) -> tuple[dict[int, dict[str, Any]], dict[str, Any] | None]:
    result_by_id: dict[int, dict[str, Any]] = {}
    auth_session: dict[str, Any] | None = None
    deps = list(StressTestTarget.objects.filter(id__in=dep_ids))
    deps.sort(key=lambda d: (0 if is_auth_endpoint(d) else 1, d.sort_order, d.id))

    for dep in deps:
        if dep.id in result_by_id:
            continue
        request_data = _build_request(dep, variables)
        _apply_all_mappings(dep, request_data, result_by_id, auth_session)
        result = _execute_http(dep.method, request_data)
        parsed = _parse_response_body(result.get("body") or "")
        sub = {
            "interface_id": dep.id,
            "name": dep.name,
            "method": dep.method,
            "url": request_data["url"],
            "success": result["success"],
            "status_code": result["status_code"],
            "parsed_body": parsed,
            "error": result.get("error") or "",
        }
        result_by_id[dep.id] = sub
        if sub.get("success") and is_auth_endpoint(dep):
            auth_session = sub
    return result_by_id, auth_session


class AuthContext:
    """压测联调上下文：解析依赖链、缓存 token，支持定时刷新。"""

    def __init__(
        self,
        variables: dict[str, Any],
        stress_target_ids: list[int],
        refresh_interval_sec: int = 60,
    ) -> None:
        self.variables = variables
        self.stress_target_ids = list(stress_target_ids)
        self.refresh_interval = max(refresh_interval_sec, 0)
        self._lock = threading.Lock()
        self.result_by_id: dict[int, dict[str, Any]] = {}
        self.auth_session: dict[str, Any] | None = None
        self.last_refresh = 0.0
        self._dep_ids: set[int] = set()

    def _collect_dep_ids(self) -> set[int]:
        dep_ids: set[int] = set()
        targets = StressTestTarget.objects.filter(id__in=self.stress_target_ids)
        for target in targets:
            dep_ids.update(_collect_dep_ids(target))
        return dep_ids

    def refresh(self, force: bool = False) -> None:
        now = time.time()
        with self._lock:
            if (
                not force
                and self.refresh_interval > 0
                and self.result_by_id
                and now - self.last_refresh < self.refresh_interval
            ):
                return
            if not force and self.refresh_interval == 0 and self.result_by_id:
                return

        dep_ids = self._collect_dep_ids()
        result_by_id, auth_session = _execute_dep_chain(dep_ids, self.variables)

        with self._lock:
            self._dep_ids = dep_ids
            self.result_by_id = result_by_id
            self.auth_session = auth_session
            self.last_refresh = now

    def build_request(self, target: StressTestTarget) -> dict[str, Any]:
        self.refresh(force=not self.result_by_id)
        with self._lock:
            request_data = _build_request(target, self.variables)
            _apply_all_mappings(target, request_data, self.result_by_id, self.auth_session)
            return copy.deepcopy(request_data)

    def invalidate(self) -> None:
        with self._lock:
            self.result_by_id = {}
            self.auth_session = None
            self.last_refresh = 0.0


def debug_stress_target(target: StressTestTarget, variables: dict[str, Any]) -> dict[str, Any]:
    ctx = AuthContext(variables, [target.id], refresh_interval_sec=0)
    request_data = ctx.build_request(target)
    result = _execute_http(target.method, request_data)
    return {
        "url": request_data["url"],
        "status_code": result.get("status_code") or 0,
        "headers": request_data.get("headers") or {},
        "body": result.get("body") or "",
        "error": result.get("error") or "",
        "auth_refreshed": bool(ctx.auth_session),
    }


def prepare_endpoints(target_ids: list[int], variables: dict[str, Any]) -> list[dict[str, Any]]:
    """兼容旧逻辑：预解析请求（压测主流程改用 AuthContext 动态构建）。"""
    targets = list(
        StressTestTarget.objects.filter(id__in=target_ids).order_by("sort_order", "id")
    )
    if not targets:
        return []
    id_order = {tid: idx for idx, tid in enumerate(target_ids)}
    targets.sort(key=lambda t: id_order.get(t.id, 9999))
    ctx = AuthContext(variables, target_ids, refresh_interval_sec=0)
    prepared: list[dict[str, Any]] = []
    for target in targets:
        request_data = ctx.build_request(target)
        prepared.append(
            {
                "target_id": target.id,
                "name": target.name,
                "method": target.method,
                "url": request_data["url"],
                "request": request_data,
                "target": target,
            }
        )
    return prepared


class MetricsCollector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total = 0
        self.success = 0
        self.fail = 0
        self.latencies: list[float] = []
        self.endpoint: dict[int, dict[str, Any]] = {}
        self._interval_total = 0
        self._interval_success = 0
        self._interval_fail = 0
        self._interval_latencies: list[float] = []
        self.active_threads = 0

    def record(
        self,
        target_id: int,
        name: str,
        method: str,
        url: str,
        success: bool,
        latency_ms: float,
        status_code: int,
    ) -> None:
        with self._lock:
            self.total += 1
            self._interval_total += 1
            if success:
                self.success += 1
                self._interval_success += 1
            else:
                self.fail += 1
                self._interval_fail += 1
            if len(self.latencies) < MAX_LATENCY_SAMPLES:
                self.latencies.append(latency_ms)
            self._interval_latencies.append(latency_ms)
            ep = self.endpoint.setdefault(
                target_id,
                {
                    "target_id": target_id,
                    "name": name,
                    "method": method,
                    "url": url,
                    "total": 0,
                    "success": 0,
                    "fail": 0,
                    "latencies": [],
                    "status_codes": defaultdict(int),
                },
            )
            ep["total"] += 1
            if success:
                ep["success"] += 1
            else:
                ep["fail"] += 1
            if len(ep["latencies"]) < MAX_LATENCY_SAMPLES:
                ep["latencies"].append(latency_ms)
            ep["status_codes"][status_code] += 1

    def set_active_threads(self, count: int) -> None:
        with self._lock:
            self.active_threads = count

    def snapshot_interval(self, elapsed_sec: int) -> dict[str, Any]:
        with self._lock:
            lat = list(self._interval_latencies)
            count = self._interval_total
            rps = count
            avg_ms = sum(lat) / len(lat) if lat else 0.0
            p95 = _percentile(lat, 95)
            errors = self._interval_fail
            threads = self.active_threads
            self._interval_total = 0
            self._interval_success = 0
            self._interval_fail = 0
            self._interval_latencies = []
        return {
            "elapsed": elapsed_sec,
            "rps": round(rps, 2),
            "avg_ms": round(avg_ms, 2),
            "p95_ms": round(p95, 2),
            "errors": errors,
            "threads": threads,
        }

    def build_summary(self, duration_sec: float) -> dict[str, Any]:
        with self._lock:
            lat = list(self.latencies)
            total = self.total
            success = self.success
            fail = self.fail
        duration = max(duration_sec, 0.001)
        return {
            "total_requests": total,
            "success_count": success,
            "fail_count": fail,
            "error_rate": round(fail / total * 100, 2) if total else 0.0,
            "throughput": round(total / duration, 2),
            "avg_ms": round(sum(lat) / len(lat), 2) if lat else 0.0,
            "min_ms": round(min(lat), 2) if lat else 0.0,
            "max_ms": round(max(lat), 2) if lat else 0.0,
            "p50_ms": round(_percentile(lat, 50), 2),
            "p90_ms": round(_percentile(lat, 90), 2),
            "p95_ms": round(_percentile(lat, 95), 2),
            "p99_ms": round(_percentile(lat, 99), 2),
            "duration_sec": round(duration_sec, 2),
        }

    def build_endpoint_stats(self) -> list[dict[str, Any]]:
        with self._lock:
            endpoint_raw = dict(self.endpoint)
        stats: list[dict[str, Any]] = []
        for ep in endpoint_raw.values():
            lat = ep["latencies"]
            stats.append(
                {
                    "target_id": ep["target_id"],
                    "name": ep["name"],
                    "method": ep["method"],
                    "url": ep["url"],
                    "total": ep["total"],
                    "success": ep["success"],
                    "fail": ep["fail"],
                    "error_rate": round(ep["fail"] / ep["total"] * 100, 2) if ep["total"] else 0.0,
                    "avg_ms": round(sum(lat) / len(lat), 2) if lat else 0.0,
                    "p95_ms": round(_percentile(lat, 95), 2),
                    "status_codes": dict(ep["status_codes"]),
                }
            )
        return sorted(stats, key=lambda x: x["total"], reverse=True)


def _sample_resources() -> dict[str, Any]:
    try:
        import psutil

        proc = psutil.Process()
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=None), 2),
            "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 2),
            "system_memory_percent": round(psutil.virtual_memory().percent, 2),
        }
    except Exception:
        return {"cpu_percent": 0, "memory_mb": 0, "system_memory_percent": 0}


def stop_stress_run(run_id: int) -> bool:
    event = _stop_events.get(run_id)
    if event:
        event.set()
        return True
    return False


def _worker_loop(
    stress_targets: list[StressTestTarget],
    auth_ctx: AuthContext,
    collector: MetricsCollector,
    stop_event: threading.Event,
    end_time: float,
    think_time_ms: int,
    index_counter: list[int],
    index_lock: threading.Lock,
) -> None:
    while not stop_event.is_set() and time.time() < end_time:
        with index_lock:
            idx = index_counter[0]
            index_counter[0] = (idx + 1) % len(stress_targets)
        target = stress_targets[idx]
        request_data = auth_ctx.build_request(target)
        start = time.perf_counter()
        result = _execute_http(target.method, request_data)
        if result.get("status_code") in (401, 403):
            auth_ctx.invalidate()
            request_data = auth_ctx.build_request(target)
            result = _execute_http(target.method, request_data)
        latency_ms = (time.perf_counter() - start) * 1000
        collector.record(
            target.id,
            target.name,
            target.method,
            request_data["url"],
            result["success"],
            latency_ms,
            result.get("status_code") or 0,
        )
        if think_time_ms > 0 and not stop_event.is_set():
            time.sleep(think_time_ms / 1000.0)


def _run_stress_worker(run_id: int) -> None:
    run = StressTestRun.objects.filter(pk=run_id).first()
    if not run:
        return

    config = run.config or {}
    users = int(config.get("users") or 10)
    spawn_rate = max(int(config.get("spawn_rate") or 2), 1)
    duration_sec = int(config.get("duration_sec") or 30)
    think_time_ms = int(config.get("think_time_ms") or 0)
    token_refresh_sec = int(config.get("token_refresh_sec") or 60)
    target_ids = list(config.get("target_ids") or [])
    variables = dict(config.get("variables") or {})

    stop_event = threading.Event()
    _stop_events[run_id] = stop_event

    try:
        stress_targets = list(
            StressTestTarget.objects.filter(id__in=target_ids).order_by("sort_order", "id")
        )
        if not stress_targets:
            raise ValueError("没有可压测的接口目标")

        id_order = {tid: idx for idx, tid in enumerate(target_ids)}
        stress_targets.sort(key=lambda t: id_order.get(t.id, 9999))

        auth_ctx = AuthContext(variables, target_ids, refresh_interval_sec=token_refresh_sec)
        auth_ctx.refresh(force=True)

        run.status = "running"
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at"])

        collector = MetricsCollector()
        end_time = time.time() + duration_sec
        index_counter = [0]
        index_lock = threading.Lock()
        threads: list[threading.Thread] = []
        time_series: list[dict[str, Any]] = []
        resource_series: list[dict[str, Any]] = []

        def spawn_user(_worker_id: int) -> None:
            t = threading.Thread(
                target=_worker_loop,
                args=(
                    stress_targets,
                    auth_ctx,
                    collector,
                    stop_event,
                    end_time,
                    think_time_ms,
                    index_counter,
                    index_lock,
                ),
                daemon=True,
            )
            t.start()
            threads.append(t)

        spawn_interval = 1.0 / spawn_rate
        for i in range(users):
            if stop_event.is_set():
                break
            spawn_user(i)
            collector.set_active_threads(min(i + 1, users))
            if i < users - 1:
                time.sleep(spawn_interval)

        start_ts = time.time()
        while time.time() < end_time and not stop_event.is_set():
            time.sleep(1)
            elapsed = int(time.time() - start_ts)
            auth_ctx.refresh()
            snap = collector.snapshot_interval(elapsed)
            time_series.append(snap)
            res = _sample_resources()
            res["elapsed"] = elapsed
            resource_series.append(res)
            StressTestRun.objects.filter(pk=run_id).update(
                time_series=time_series,
                resource_series=resource_series,
                summary=collector.build_summary(elapsed),
                endpoint_stats=collector.build_endpoint_stats(),
            )

        stop_event.set()
        for t in threads:
            t.join(timeout=2)

        actual_duration = time.time() - start_ts
        summary = collector.build_summary(actual_duration)
        endpoint_stats = collector.build_endpoint_stats()
        final_status = "stopped" if actual_duration < duration_sec - 0.5 else "completed"

        run.refresh_from_db()
        run.status = final_status
        run.summary = summary
        run.time_series = time_series
        run.endpoint_stats = endpoint_stats
        run.resource_series = resource_series
        from .stress_analysis_service import analyze_stress_run

        run.analysis = analyze_stress_run(run)
        run.finished_at = timezone.now()
        run.save()
    except Exception as exc:
        run.refresh_from_db()
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.save()
    finally:
        _stop_events.pop(run_id, None)


def start_stress_run(
    project_id: int,
    target_ids: list[int],
    variables: dict[str, Any],
    *,
    users: int = 10,
    spawn_rate: int = 2,
    duration_sec: int = 30,
    think_time_ms: int = 0,
    token_refresh_sec: int = 60,
    name: str = "",
) -> StressTestRun:
    if not target_ids:
        raise ValueError("target_ids 不能为空")
    if users < 1:
        raise ValueError("并发用户数至少为 1")
    if duration_sec < 1:
        raise ValueError("持续时间至少 1 秒")

    run = StressTestRun.objects.create(
        project_id=project_id,
        name=name or f"压测 {datetime.now().strftime('%H:%M:%S')}",
        status="pending",
        config={
            "target_ids": target_ids,
            "variables": variables,
            "users": users,
            "spawn_rate": spawn_rate,
            "duration_sec": duration_sec,
            "think_time_ms": think_time_ms,
            "token_refresh_sec": token_refresh_sec,
        },
    )
    threading.Thread(target=_run_stress_worker, args=(run.id,), daemon=True).start()
    return run
