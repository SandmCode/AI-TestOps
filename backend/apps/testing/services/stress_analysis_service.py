"""压测结果分析：瓶颈、拐点、建议。"""

from __future__ import annotations

from typing import Any

from apps.testing.models import StressTestRun


def analyze_stress_run(run: StressTestRun) -> dict[str, Any]:
    summary = run.summary or {}
    time_series = run.time_series or []
    endpoint_stats = run.endpoint_stats or []
    config = run.config or {}

    bottlenecks: list[dict[str, Any]] = []
    inflection_points: list[dict[str, Any]] = []
    recommendations: list[str] = []

    if endpoint_stats:
        slowest = max(endpoint_stats, key=lambda x: float(x.get("avg_ms") or 0))
        bottlenecks.append(
            {
                "type": "latency",
                "name": slowest.get("name"),
                "url": slowest.get("url"),
                "metric": float(slowest.get("avg_ms") or 0),
                "unit": "ms",
                "desc": f"响应最慢接口「{slowest.get('name')}」，平均 {slowest.get('avg_ms')}ms",
            }
        )
        highest_p95 = max(endpoint_stats, key=lambda x: float(x.get("p95_ms") or 0))
        if highest_p95.get("target_id") != slowest.get("target_id"):
            bottlenecks.append(
                {
                    "type": "p95",
                    "name": highest_p95.get("name"),
                    "metric": float(highest_p95.get("p95_ms") or 0),
                    "unit": "ms",
                    "desc": f"P95 最高「{highest_p95.get('name')}」：{highest_p95.get('p95_ms')}ms",
                }
            )
        err_ep = max(endpoint_stats, key=lambda x: float(x.get("error_rate") or 0))
        if float(err_ep.get("error_rate") or 0) > 0:
            bottlenecks.append(
                {
                    "type": "error",
                    "name": err_ep.get("name"),
                    "metric": float(err_ep.get("error_rate") or 0),
                    "unit": "%",
                    "desc": f"错误率最高「{err_ep.get('name')}」：{err_ep.get('error_rate')}%",
                }
            )

    if time_series:
        peak_idx = max(range(len(time_series)), key=lambda i: float(time_series[i].get("rps") or 0))
        peak = time_series[peak_idx]
        inflection_points.append(
            {
                "type": "throughput_peak",
                "elapsed_sec": peak.get("elapsed"),
                "rps": peak.get("rps"),
                "desc": f"吞吐峰值 {peak.get('rps')} req/s（第 {peak.get('elapsed')} 秒）",
            }
        )

        for i in range(1, len(time_series)):
            prev_rps = float(time_series[i - 1].get("rps") or 0)
            cur_rps = float(time_series[i].get("rps") or 0)
            if prev_rps > 0 and cur_rps < prev_rps * 0.7:
                inflection_points.append(
                    {
                        "type": "throughput_drop",
                        "elapsed_sec": time_series[i].get("elapsed"),
                        "rps": cur_rps,
                        "desc": f"吞吐回落拐点：{prev_rps} → {cur_rps} req/s（第 {time_series[i].get('elapsed')} 秒）",
                    }
                )
                break

        for i in range(1, len(time_series)):
            prev_ms = float(time_series[i - 1].get("avg_ms") or 0)
            cur_ms = float(time_series[i].get("avg_ms") or 0)
            if prev_ms > 0 and cur_ms > prev_ms * 1.5 and cur_ms >= 100:
                inflection_points.append(
                    {
                        "type": "latency_jump",
                        "elapsed_sec": time_series[i].get("elapsed"),
                        "avg_ms": cur_ms,
                        "desc": f"时延拐点：{round(prev_ms, 1)}ms → {round(cur_ms, 1)}ms（第 {time_series[i].get('elapsed')} 秒）",
                    }
                )
                break

        for pt in time_series:
            if int(pt.get("errors") or 0) > 0:
                inflection_points.append(
                    {
                        "type": "error_onset",
                        "elapsed_sec": pt.get("elapsed"),
                        "errors": pt.get("errors"),
                        "desc": f"首次出现错误（第 {pt.get('elapsed')} 秒，{pt.get('errors')} 次）",
                    }
                )
                break

    error_rate = float(summary.get("error_rate") or 0)
    throughput = float(summary.get("throughput") or 0)
    p95 = float(summary.get("p95_ms") or 0)
    users = int(config.get("users") or 0)

    if error_rate > 10:
        recommendations.append("错误率超过 10%，系统可能已过载，建议降低并发或排查依赖/token。")
    elif error_rate > 0:
        recommendations.append("存在少量失败请求，建议结合接口明细与错误码分布排查。")

    if p95 > 1000:
        recommendations.append(f"P95 响应 {p95}ms 偏高，关注最慢接口与数据库/外部依赖。")
    elif p95 > 500:
        recommendations.append(f"P95 为 {p95}ms，可继续加压观察是否出现时延拐点。")

    if throughput > 0 and users > 0:
        per_user = round(throughput / users, 2)
        recommendations.append(f"人均吞吐约 {per_user} req/s（总 {throughput} / {users} 用户）。")

    if not recommendations:
        recommendations.append("本次压测指标整体正常，可尝试提高并发或延长持续时间进一步探测上限。")

    health = 100
    health -= min(error_rate * 2, 40)
    health -= min(max(p95 - 200, 0) / 20, 30)
    health = max(int(health), 0)

    return {
        "bottlenecks": bottlenecks[:5],
        "inflection_points": inflection_points[:6],
        "recommendations": recommendations,
        "health_score": health,
        "summary_snapshot": {
            "throughput": throughput,
            "error_rate": error_rate,
            "avg_ms": summary.get("avg_ms"),
            "p95_ms": p95,
            "total_requests": summary.get("total_requests"),
        },
    }
