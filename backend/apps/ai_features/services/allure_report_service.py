"""Allure 风格测试报告生成（allure-results + 自包含 HTML）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from django.conf import settings

from apps.ai_features.models import TestReport


def _report_dir(report_id: str) -> Path:
    base = Path(settings.MEDIA_ROOT) / "reports" / report_id
    base.mkdir(parents=True, exist_ok=True)
    (base / "allure-results").mkdir(exist_ok=True)
    return base


def _media_url(report_id: str) -> str:
    return f"{settings.MEDIA_URL}reports/{report_id}/index.html"


def _write_allure_result(report_dir: Path, case: dict[str, Any]) -> None:
    result_id = case.get("uuid") or str(uuid.uuid4())
    payload = {
        "uuid": result_id,
        "historyId": case.get("historyId", result_id),
        "name": case.get("name", "未命名"),
        "fullName": case.get("fullName", case.get("name", "")),
        "status": case.get("status", "passed"),
        "statusDetails": {"message": case.get("message", ""), "trace": case.get("trace", "")},
        "stage": "finished",
        "start": case.get("start", 0),
        "stop": case.get("stop", 0),
        "labels": case.get("labels", []),
        "steps": case.get("steps", []),
    }
    path = report_dir / "allure-results" / f"{result_id}-result.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_html(
    title: str,
    subtitle: str,
    stats: dict[str, Any],
    cases: list[dict[str, Any]],
    extra_sections: list[dict[str, Any]] | None = None,
) -> str:
    total = stats.get("total", 0)
    passed = stats.get("passed", 0)
    failed = stats.get("failed", 0)
    broken = stats.get("broken", 0)
    skipped = stats.get("skipped", 0)
    pass_rate = round(passed / total * 100, 1) if total else 0

    rows = []
    for c in cases:
        status = c.get("status", "passed")
        badge = {
            "passed": "#22c55e",
            "failed": "#ef4444",
            "broken": "#f59e0b",
            "skipped": "#6b7280",
        }.get(status, "#6b7280")
        rows.append(
            f"<tr>"
            f"<td><span class='badge' style='background:{badge}'>{escape(status)}</span></td>"
            f"<td>{escape(str(c.get('name', '')))}</td>"
            f"<td>{escape(str(c.get('feature', '')))}</td>"
            f"<td class='mono'>{escape(str(c.get('detail', '')))}</td>"
            f"</tr>"
        )

    extra_html = ""
    for sec in extra_sections or []:
        items = "".join(f"<li>{escape(str(x))}</li>" for x in sec.get("items", []))
        extra_html += f"""
        <section class="card">
          <h2>{escape(sec.get('title', ''))}</h2>
          <ul class="list">{items}</ul>
        </section>"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>{escape(title)}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Segoe UI,system-ui,sans-serif;background:#0f1419;color:#e5e7eb;padding:24px;line-height:1.5}}
.header{{margin-bottom:24px}}
.header h1{{font-size:24px;color:#fff}}
.header p{{color:#9aa0a6;margin-top:6px}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin-bottom:24px}}
.stat{{background:#141c28;border:1px solid #2a3544;border-radius:10px;padding:16px}}
.stat span{{display:block;font-size:12px;color:#9aa0a6}}
.stat strong{{font-size:28px;color:#fff}}
.stat.pass strong{{color:#22c55e}}
.stat.fail strong{{color:#ef4444}}
.card{{background:#141c28;border:1px solid #2a3544;border-radius:10px;padding:16px;margin-bottom:16px}}
.card h2{{font-size:16px;color:#fff;margin-bottom:12px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:10px 12px;border-bottom:1px solid #2a3544;text-align:left}}
th{{color:#9aa0a6;font-weight:600}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;color:#fff}}
.mono{{font-family:monospace;font-size:12px;color:#93c5fd;word-break:break-all}}
.list{{padding-left:18px;color:#cbd5e1}}
.list li{{margin:6px 0}}
.footer{{margin-top:24px;font-size:12px;color:#6b7280}}
</style>
</head>
<body>
<div class="header">
  <h1>{escape(title)}</h1>
  <p>{escape(subtitle)} · Allure 风格报告 · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</div>
<div class="stats">
  <div class="stat"><span>总计</span><strong>{total}</strong></div>
  <div class="stat pass"><span>通过</span><strong>{passed}</strong></div>
  <div class="stat fail"><span>失败</span><strong>{failed}</strong></div>
  <div class="stat"><span>异常</span><strong>{broken}</strong></div>
  <div class="stat"><span>跳过</span><strong>{skipped}</strong></div>
  <div class="stat pass"><span>通过率</span><strong>{pass_rate}%</strong></div>
</div>
{extra_html}
<div class="card">
  <h2>用例明细</h2>
  <table>
    <thead><tr><th>状态</th><th>名称</th><th>模块</th><th>详情</th></tr></thead>
    <tbody>{''.join(rows) if rows else '<tr><td colspan="4">无数据</td></tr>'}</tbody>
  </table>
</div>
<p class="footer">Generated by AI Test Platform · allure-results 已写入同目录</p>
</body>
</html>"""


def _save_report(
    *,
    name: str,
    report_type: str,
    source_type: str,
    summary: str,
    pass_rate: float,
    total_cases: int,
    passed_cases: int,
    cases: list[dict[str, Any]],
    stats: dict[str, Any],
    meta: dict[str, Any] | None = None,
    extra_sections: list[dict[str, Any]] | None = None,
    subtitle: str = "",
) -> TestReport:
    report_uuid = str(uuid.uuid4())
    report_dir = _report_dir(report_uuid)
    now_ms = int(datetime.now().timestamp() * 1000)

    allure_cases = []
    for idx, case in enumerate(cases):
        uid = str(uuid.uuid4())
        status = case.get("status", "passed")
        start = case.get("start") or (now_ms + idx * 100)
        stop = case.get("stop") or (start + 100)
        allure_case = {
            "uuid": uid,
            "historyId": case.get("historyId", f"{source_type}-{idx}"),
            "name": case.get("name", f"case-{idx}"),
            "fullName": case.get("fullName", case.get("name", "")),
            "status": status,
            "message": case.get("message", case.get("detail", "")),
            "start": start,
            "stop": stop,
            "labels": case.get("labels", [{"name": "feature", "value": case.get("feature", source_type)}]),
        }
        _write_allure_result(report_dir, allure_case)
        allure_cases.append({**case, "status": status})

    html = _render_html(name, subtitle or source_type, stats, allure_cases, extra_sections)
    (report_dir / "index.html").write_text(html, encoding="utf-8")

    report_url = _media_url(report_uuid)
    return TestReport.objects.create(
        name=name,
        report_type=report_type,
        source_type=source_type,
        summary=summary,
        pass_rate=pass_rate,
        total_cases=total_cases,
        passed_cases=passed_cases,
        report_url=report_url,
        meta={"report_id": report_uuid, **(meta or {})},
    )


def generate_automation_report(
    results: list[dict[str, Any]],
    *,
    project_name: str = "",
    project_id: int | None = None,
) -> TestReport:
    cases = []
    passed = failed = 0
    now_ms = int(datetime.now().timestamp() * 1000)

    for idx, r in enumerate(results):
        ok = bool(r.get("success"))
        if ok:
            passed += 1
            status = "passed"
        else:
            failed += 1
            status = "failed"
        name = f"{r.get('method', 'GET')} {r.get('name', '接口')}"
        detail = r.get("url", "")
        if r.get("error"):
            detail = f"{detail} | {r.get('error')}"
        elif r.get("status_code"):
            detail = f"{detail} | HTTP {r.get('status_code')}"
        cases.append(
            {
                "name": name,
                "feature": r.get("module") or "接口自动化",
                "detail": detail,
                "status": status,
                "message": r.get("error") or f"HTTP {r.get('status_code', '')}",
                "start": now_ms + idx * 200,
                "stop": now_ms + idx * 200 + 150,
            }
        )

    total = len(cases)
    pass_rate = round(passed / total * 100, 1) if total else 0
    title = f"接口自动化报告{(' · ' + project_name) if project_name else ''}"
    summary = f"执行 {total} 个接口，通过 {passed}，失败 {failed}，通过率 {pass_rate}%"

    return _save_report(
        name=title,
        report_type="api",
        source_type="automation",
        summary=summary,
        pass_rate=pass_rate,
        total_cases=total,
        passed_cases=passed,
        cases=cases,
        stats={"total": total, "passed": passed, "failed": failed, "broken": 0, "skipped": 0},
        meta={"project_id": project_id, "project_name": project_name},
        subtitle="接口自动化",
    )


def generate_security_report(
    results: list[dict[str, Any]],
    summary_data: dict[str, Any] | None = None,
    *,
    project_name: str = "",
    project_id: int | None = None,
) -> TestReport:
    cases = []
    passed = failed = broken = 0
    now_ms = int(datetime.now().timestamp() * 1000)
    summary_data = summary_data or {}

    for idx, r in enumerate(results):
        risk = r.get("risk_level", "info")
        findings = r.get("findings") or []
        risk_count = int(r.get("risk_count") or 0)
        if risk in ("high", "medium"):
            status = "failed"
            failed += 1
        elif risk == "low":
            status = "broken"
            broken += 1
        else:
            status = "passed"
            passed += 1

        name = f"{r.get('method', 'GET')} {r.get('name', '目标')}"
        detail_parts = [f"风险: {risk}", f"发现 {len(findings)} 项"]
        if findings:
            detail_parts.append(findings[0].get("title", ""))
        cases.append(
            {
                "name": name,
                "feature": "安全扫描",
                "detail": " · ".join(detail_parts),
                "status": status,
                "message": f"risk={risk}, findings={risk_count}",
                "start": now_ms + idx * 200,
                "stop": now_ms + idx * 200 + 180,
            }
        )

    total = len(cases)
    pass_rate = round(passed / total * 100, 1) if total else 0
    high = summary_data.get("high", 0)
    medium = summary_data.get("medium", 0)
    title = f"安全扫描报告{(' · ' + project_name) if project_name else ''}"
    summary = (
        f"扫描 {total} 个目标，高危 {high}、中危 {medium}；"
        f"通过 {passed}，风险 {failed + broken}，通过率 {pass_rate}%"
    )

    extra = [
        {
            "title": "风险汇总",
            "items": [
                f"高危 {summary_data.get('high', 0)}",
                f"中危 {summary_data.get('medium', 0)}",
                f"低危 {summary_data.get('low', 0)}",
                f"正常 {summary_data.get('info', 0) + summary_data.get('pass', 0)}",
            ],
        }
    ]

    return _save_report(
        name=title,
        report_type="security",
        source_type="security",
        summary=summary,
        pass_rate=pass_rate,
        total_cases=total,
        passed_cases=passed,
        cases=cases,
        stats={"total": total, "passed": passed, "failed": failed, "broken": broken, "skipped": 0},
        meta={"project_id": project_id, "project_name": project_name, "summary": summary_data},
        extra_sections=extra,
        subtitle="接口安全扫描",
    )


def generate_stress_report(
    run_data: dict[str, Any],
    analysis: dict[str, Any],
    *,
    project_name: str = "",
) -> TestReport:
    summary = run_data.get("summary") or {}
    endpoint_stats = run_data.get("endpoint_stats") or []
    total_req = int(summary.get("total_requests") or 0)
    success = int(summary.get("success_count") or 0)
    fail = int(summary.get("fail_count") or 0)
    error_rate = float(summary.get("error_rate") or 0)
    throughput = float(summary.get("throughput") or 0)

    cases = []
    now_ms = int(datetime.now().timestamp() * 1000)
    for idx, ep in enumerate(endpoint_stats):
        err = float(ep.get("error_rate") or 0)
        status = "passed" if err < 5 else ("broken" if err < 20 else "failed")
        cases.append(
            {
                "name": f"{ep.get('method')} {ep.get('name')}",
                "feature": "压测接口",
                "detail": f"请求 {ep.get('total')} · 平均 {ep.get('avg_ms')}ms · P95 {ep.get('p95_ms')}ms · 错误 {err}%",
                "status": status,
                "start": now_ms + idx * 100,
                "stop": now_ms + idx * 100 + 80,
            }
        )

    if not cases:
        cases.append(
            {
                "name": run_data.get("name") or "压测任务",
                "feature": "压测汇总",
                "detail": f"吞吐 {throughput} req/s · 错误率 {error_rate}%",
                "status": "passed" if error_rate < 5 else "failed",
            }
        )

    passed = sum(1 for c in cases if c["status"] == "passed")
    failed = sum(1 for c in cases if c["status"] == "failed")
    broken = sum(1 for c in cases if c["status"] == "broken")
    total = len(cases)
    pass_rate = round(passed / total * 100, 1) if total else (100 - error_rate)

    title = f"压测报告 · {run_data.get('name') or '未命名'}"
    if project_name:
        title = f"{title} ({project_name})"

    summary_text = (
        f"总请求 {total_req}，吞吐 {throughput} req/s，"
        f"平均 {summary.get('avg_ms')}ms，P95 {summary.get('p95_ms')}ms，"
        f"错误率 {error_rate}%，健康分 {analysis.get('health_score', '-')}"
    )

    extra = [
        {
            "title": "性能瓶颈",
            "items": [b.get("desc", "") for b in analysis.get("bottlenecks", [])] or ["未发现明显瓶颈"],
        },
        {
            "title": "拐点分析",
            "items": [p.get("desc", "") for p in analysis.get("inflection_points", [])] or ["未检测到显著拐点"],
        },
        {
            "title": "优化建议",
            "items": analysis.get("recommendations", []),
        },
    ]

    return _save_report(
        name=title,
        report_type="performance",
        source_type="stress",
        summary=summary_text,
        pass_rate=pass_rate,
        total_cases=total,
        passed_cases=passed,
        cases=cases,
        stats={"total": total, "passed": passed, "failed": failed, "broken": broken, "skipped": 0},
        meta={
            "stress_run_id": run_data.get("id"),
            "analysis": analysis,
            "summary": summary,
            "project_name": project_name,
        },
        extra_sections=extra,
        subtitle="接口压测",
    )
