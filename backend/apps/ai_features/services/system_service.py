"""系统数据维护服务。"""

from __future__ import annotations

from django.core.management import call_command
from django.db import transaction

from apps.ai_features.models import AnalysisRecord, TestReport
from apps.projects.models import ChunkUploadSession, Project
from apps.testing.models import AsyncTask, ExecutionRun, StressTestRun


def get_system_stats() -> dict[str, int]:
    return {
        "projects": Project.objects.count(),
        "analysis_records": AnalysisRecord.objects.count(),
        "test_reports": TestReport.objects.count(),
        "stress_runs": StressTestRun.objects.count(),
        "execution_runs": ExecutionRun.objects.count(),
        "async_tasks": AsyncTask.objects.count(),
        "chunk_sessions": ChunkUploadSession.objects.count(),
    }


@transaction.atomic
def clear_analysis_records() -> int:
    count = AnalysisRecord.objects.count()
    AnalysisRecord.objects.all().delete()
    return count


@transaction.atomic
def clear_test_reports() -> int:
    count = TestReport.objects.count()
    TestReport.objects.all().delete()
    return count


@transaction.atomic
def clear_runtime_records() -> dict[str, int]:
    stress = StressTestRun.objects.count()
    execution = ExecutionRun.objects.count()
    tasks = AsyncTask.objects.count()
    chunks = ChunkUploadSession.objects.count()
    StressTestRun.objects.all().delete()
    ExecutionRun.objects.all().delete()
    AsyncTask.objects.all().delete()
    ChunkUploadSession.objects.all().delete()
    return {
        "stress_runs": stress,
        "execution_runs": execution,
        "async_tasks": tasks,
        "chunk_sessions": chunks,
    }


@transaction.atomic
def format_business_data() -> dict[str, int | str]:
    """清理业务与运行数据，保留 AI 配置，并重建演示数据。"""
    analysis_deleted = AnalysisRecord.objects.count()
    reports_deleted = TestReport.objects.count()
    projects_deleted = Project.objects.count()
    runtime = clear_runtime_records()

    AnalysisRecord.objects.all().delete()
    TestReport.objects.all().delete()
    Project.objects.all().delete()

    call_command("seed_demo")

    return {
        "analysis_records": analysis_deleted,
        "test_reports": reports_deleted,
        "projects": projects_deleted,
        "stress_runs": runtime["stress_runs"],
        "execution_runs": runtime["execution_runs"],
        "message": "业务数据已格式化，演示数据已重建",
    }
