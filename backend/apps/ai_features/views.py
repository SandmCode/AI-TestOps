from django.db import transaction
from django.http import HttpResponse
from django.utils.encoding import iri_to_uri
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, parsers, status, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

from apps.testing.services.ai_service import AIConfig, AIService, AIServiceError

from .models import AIProviderConfig, AISkill, AISkillsSettings, AnalysisRecord, TestReport
from .serializers import (
    AIConfigStatusSerializer,
    AIProviderConfigSerializer,
    AISkillSerializer,
    AISkillsSettingsSerializer,
    AnalysisRecordListSerializer,
    AnalysisRecordSerializer,
    TestReportSerializer,
)
from .services.analysis_record_service import export_record_json, export_record_markdown, save_analysis_record
from .services.system_service import (
    clear_analysis_records,
    clear_runtime_records,
    clear_test_reports,
    format_business_data,
    get_system_stats,
)
from .services.cc_switch_service import CCSwitchService
from .services.skills_service import parse_md_upload, parse_zip_upload, slugify_folder_name, upsert_skill


class AnalysisRecordViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = AnalysisRecord.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["analysis_type"]

    def get_serializer_class(self):
        if self.action == "list":
            return AnalysisRecordListSerializer
        return AnalysisRecordSerializer

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        record = self.get_object()
        fmt = (request.query_params.get("file_type") or "json").lower()
        if fmt == "md":
            content = export_record_markdown(record)
            filename = f"analysis-{record.id}-{record.analysis_type}.md"
            content_type = "text/markdown; charset=utf-8"
        else:
            content = export_record_json(record)
            filename = f"analysis-{record.id}-{record.analysis_type}.json"
            content_type = "application/octet-stream"
        disposition = f"attachment; filename=\"{filename}\"; filename*=UTF-8''{iri_to_uri(filename)}"
        if isinstance(content, bytes):
            body = content
        else:
            body = content.encode("utf-8")
        response = HttpResponse(body, content_type=content_type)
        response["Content-Disposition"] = disposition
        response["Access-Control-Expose-Headers"] = "Content-Disposition"
        return response


class TestReportViewSet(viewsets.ModelViewSet):
    queryset = TestReport.objects.all()
    serializer_class = TestReportSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["report_type", "source_type"]
    search_fields = ["name"]

    @action(detail=False, methods=["post"], url_path="generate-automation")
    def generate_automation(self, request):
        from apps.projects.models import Project

        from .services.allure_report_service import generate_automation_report

        results = request.data.get("results") or []
        if not results:
            return Response({"error": "results 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        project_id = request.data.get("project_id")
        project_name = ""
        if project_id:
            project = Project.objects.filter(id=project_id).first()
            project_name = project.name if project else ""
        report = generate_automation_report(results, project_name=project_name, project_id=project_id)
        return Response(TestReportSerializer(report).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="generate-security")
    def generate_security(self, request):
        from apps.projects.models import Project

        from .services.allure_report_service import generate_security_report

        results = request.data.get("results") or []
        if not results:
            return Response({"error": "results 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        project_id = request.data.get("project_id")
        project_name = ""
        if project_id:
            project = Project.objects.filter(id=project_id).first()
            project_name = project.name if project else ""
        report = generate_security_report(
            results,
            request.data.get("summary"),
            project_name=project_name,
            project_id=project_id,
        )
        return Response(TestReportSerializer(report).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="generate-stress")
    def generate_stress(self, request):
        from apps.projects.models import Project
        from apps.testing.models import StressTestRun
        from apps.testing.services.stress_analysis_service import analyze_stress_run

        from .services.allure_report_service import generate_stress_report

        run_id = request.data.get("stress_run_id")
        if not run_id:
            return Response({"error": "stress_run_id 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        run = StressTestRun.objects.select_related("project").filter(id=run_id).first()
        if not run:
            return Response({"error": "压测记录不存在"}, status=status.HTTP_404_NOT_FOUND)
        if not run.analysis:
            run.analysis = analyze_stress_run(run)
            run.save(update_fields=["analysis"])
        report = generate_stress_report(
            {
                "id": run.id,
                "name": run.name,
                "summary": run.summary,
                "endpoint_stats": run.endpoint_stats,
                "time_series": run.time_series,
                "config": run.config,
            },
            run.analysis,
            project_name=run.project.name if run.project_id else "",
        )
        return Response(TestReportSerializer(report).data, status=status.HTTP_201_CREATED)


class AIProviderConfigViewSet(viewsets.ModelViewSet):
    queryset = AIProviderConfig.objects.all()
    serializer_class = AIProviderConfigSerializer

    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        config = self.get_object()
        AIProviderConfig.objects.exclude(pk=config.pk).update(is_active=False)
        config.is_active = True
        config.save(update_fields=["is_active", "updated_at"])
        return Response(AIProviderConfigSerializer(config).data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        config = self.get_object()
        config.is_active = False
        config.save(update_fields=["is_active", "updated_at"])
        return Response(AIProviderConfigSerializer(config).data)

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        config_obj = self.get_object()
        config = AIConfig(
            provider=config_obj.provider,
            api_key=config_obj.api_key,
            base_url=config_obj.base_url,
            model=config_obj.model,
            temperature=config_obj.temperature,
            max_tokens=config_obj.max_tokens,
            name=config_obj.name,
        )
        try:
            reply = AIService().test_connection(config)
            return Response({"success": True, "reply": reply.strip()})
        except AIServiceError as exc:
            return Response({"success": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            return Response({"success": False, "error": f"连接失败: {exc}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["get"], url_path="cc-switch-status")
    def cc_switch_status(self, request):
        service = CCSwitchService()
        data = service.get_status()
        data["providers"] = service.list_providers()
        return Response(data)

    @action(detail=False, methods=["post"], url_path="import-cc-switch")
    def import_cc_switch(self, request):
        provider_id = request.data.get("provider_id")
        source_app = request.data.get("source_app", "claude")
        activate = request.data.get("activate", True)
        service = CCSwitchService()
        try:
            imported = service.import_provider(provider_id=provider_id, source_app=source_app)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        config_name = f"CC Switch · {imported.name}"
        defaults = {
            "provider": imported.mapped_provider,
            "api_key": imported.api_key,
            "base_url": imported.base_url,
            "model": imported.model or "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 4096,
        }
        if imported.mapped_provider == "zhipu":
            defaults["base_url"] = ""

        with transaction.atomic():
            config, created = AIProviderConfig.objects.update_or_create(
                name=config_name,
                defaults=defaults,
            )
            if activate or not AIProviderConfig.objects.filter(is_active=True).exists():
                AIProviderConfig.objects.exclude(pk=config.pk).update(is_active=False)
                config.is_active = True
                config.save(update_fields=["is_active", "updated_at"])

        return Response(
            {
                "created": created,
                "config": AIProviderConfigSerializer(config).data,
                "source": {
                    "provider_id": imported.id,
                    "provider_name": imported.name,
                    "source_app": imported.source_app,
                },
            }
        )


class AISkillViewSet(viewsets.ModelViewSet):
    queryset = AISkill.objects.all()
    serializer_class = AISkillSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["is_enabled", "source_type"]
    search_fields = ["name", "folder_name"]
    parser_classes = [parsers.JSONParser, parsers.FormParser, parsers.MultiPartParser]

    def perform_create(self, serializer):
        folder_name = serializer.validated_data.get("folder_name", "")
        if not serializer.validated_data.get("source_path"):
            serializer.save(source_path=f"manual://{folder_name}", source_type="manual")
        else:
            serializer.save(source_type=serializer.validated_data.get("source_type", "manual"))

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        ids = request.data.get("ids")
        if ids:
            deleted, _ = AISkill.objects.filter(id__in=ids).delete()
        else:
            deleted, _ = AISkill.objects.all().delete()
        return Response({"deleted": deleted})

    @action(detail=False, methods=["post"], url_path="upload")
    def upload(self, request):
        upload_file = request.FILES.get("file")
        name = (request.data.get("name") or "").strip()
        folder_name = (request.data.get("folder_name") or "").strip()
        content = (request.data.get("content") or "").strip()

        created = updated = 0
        items: list[dict] = []

        try:
            if upload_file:
                fname = upload_file.name.lower()
                if fname.endswith(".zip"):
                    items = parse_zip_upload(upload_file)
                elif fname.endswith(".md"):
                    items = [parse_md_upload(upload_file, name=name, folder_name=folder_name)]
                else:
                    return Response(
                        {"error": "仅支持 .md 或 .zip 文件"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif content:
                fname = folder_name or slugify_folder_name(name or "custom-skill")
                items = [
                    {
                        "name": name or fname.replace("-", " ").title(),
                        "folder_name": fname,
                        "content": content,
                        "source_path": f"manual://{fname}",
                    }
                ]
            else:
                return Response(
                    {"error": "请上传文件或填写 SKILL.md 内容"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        saved = []
        for item in items:
            obj, is_created = upsert_skill(item, source_type="manual")
            if is_created:
                created += 1
            else:
                updated += 1
            saved.append(obj)

        return Response(
            {
                "created": created,
                "updated": updated,
                "skills": AISkillSerializer(saved, many=True).data,
                "total": AISkill.objects.count(),
            }
        )

    @action(detail=False, methods=["get", "patch"], url_path="global-settings")
    def global_settings(self, request):
        obj = AISkillsSettings.get_solo()
        if request.method == "PATCH":
            serializer = AISkillsSettingsSerializer(obj, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(AISkillsSettingsSerializer(obj).data)

    @action(detail=False, methods=["post"], url_path="scan-local")
    def scan_local(self, request):
        service = CCSwitchService()
        discovered = service.discover_local_skills()
        created = updated = 0
        for item in discovered:
            obj, is_created = AISkill.objects.update_or_create(
                folder_name=item["folder_name"],
                source_path=item["source_path"],
                defaults={
                    "name": item["name"],
                    "content": item["content"],
                    "source_type": "local",
                    "is_enabled": True,
                },
            )
            if is_created:
                created += 1
            else:
                updated += 1
        skills = AISkill.objects.all()
        return Response(
            {
                "created": created,
                "updated": updated,
                "total": skills.count(),
                "skills": AISkillSerializer(skills, many=True).data,
            }
        )

    @action(detail=False, methods=["post"], url_path="import-cc-switch")
    def import_cc_switch(self, request):
        service = CCSwitchService()
        if not service.available:
            return Response({"error": "未检测到 CC Switch"}, status=status.HTTP_400_BAD_REQUEST)

        discovered = {item["folder_name"]: item for item in service.discover_local_skills()}
        cc_skills = service.list_cc_switch_skills()
        created = updated = skipped = 0
        for item in cc_skills:
            local = discovered.get(item["folder_name"])
            if not local:
                skipped += 1
                continue
            _, is_created = AISkill.objects.update_or_create(
                folder_name=item["folder_name"],
                source_path=local["source_path"],
                defaults={
                    "name": item["name"],
                    "content": local["content"],
                    "source_type": "ccswitch",
                    "is_enabled": item["enabled_in_ccswitch"],
                },
            )
            if is_created:
                created += 1
            else:
                updated += 1

        skills = AISkill.objects.all()
        return Response(
            {
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "total": skills.count(),
                "skills": AISkillSerializer(skills, many=True).data,
            }
        )

    @action(detail=False, methods=["get"], url_path="cc-switch-preview")
    def cc_switch_preview(self, request):
        service = CCSwitchService()
        return Response(
            {
                "available": service.available,
                "local_skills": service.discover_local_skills(),
                "ccswitch_skills": service.list_cc_switch_skills(),
            }
        )


@api_view(["GET"])
def ai_config_status(request):
    settings_obj = AISkillsSettings.get_solo()
    data = AIService.get_status()
    data["skills_enabled"] = settings_obj.skills_enabled
    data["skills_count"] = AISkill.objects.filter(is_enabled=True).count()
    serializer = AIConfigStatusSerializer(data)
    return Response(serializer.data)


def _run_ai(view_fn):
    try:
        return view_fn()
    except AIServiceError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _analysis_response(analysis_type: str, input_content: str, result: dict) -> Response:
    record = save_analysis_record(analysis_type, input_content, result)
    payload = dict(result)
    payload["record_id"] = record.id
    return Response(payload)


@api_view(["POST"])
def contract_test(request):
    api_spec = request.data.get("api_spec", "")
    if not api_spec.strip():
        return Response({"error": "请提供 API 规范"}, status=status.HTTP_400_BAD_REQUEST)

    from apps.ai_features.services.contract_test_service import run_contract_test

    try:
        ai = AIService()
        result = ai.contract_test(api_spec)
    except AIServiceError:
        result = run_contract_test(api_spec)
    return _analysis_response("contract", api_spec, result)


@api_view(["POST"])
def contract_test_fix(request):
    api_spec = request.data.get("api_spec", "")
    if not api_spec.strip():
        return Response({"error": "请提供 API 规范"}, status=status.HTTP_400_BAD_REQUEST)

    from apps.ai_features.services.contract_test_service import run_contract_fix

    fix_ids = request.data.get("fix_ids")
    if fix_ids is not None and not isinstance(fix_ids, list):
        fix_ids = None
    data = run_contract_fix(api_spec, fix_ids=fix_ids)
    validation = data.get("validation")
    if isinstance(validation, dict) and data.get("fixed_spec"):
        record = save_analysis_record("contract", data["fixed_spec"], validation)
        validation = dict(validation)
        validation["record_id"] = record.id
        data["validation"] = validation
    return Response(data)


@api_view(["POST"])
def coverage_analysis(request):
    content = request.data.get("content", "")
    if not content.strip():
        return Response({"error": "请提供代码或用例内容"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        ai = AIService()
        result = ai.coverage_analysis(content)
    except AIServiceError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return _analysis_response("coverage", content, result)


@api_view(["POST"])
def log_analysis(request):
    logs = request.data.get("logs", "")
    if not logs.strip():
        return Response({"error": "请提供日志内容"}, status=status.HTTP_400_BAD_REQUEST)

    from apps.ai_features.services.log_analysis_service import analyze_logs_local

    try:
        ai = AIService()
        result = ai.log_analysis(logs)
    except AIServiceError:
        result = analyze_logs_local(logs)
    return _analysis_response("log", logs, result)


@api_view(["GET"])
def system_info(request):
    return Response(get_system_stats())


@api_view(["POST"])
def system_maintain(request):
    action = (request.data.get("action") or "").strip()
    if action == "clear_analysis_records":
        deleted = clear_analysis_records()
        return Response({"message": f"已清理 {deleted} 条分析记录", "deleted": deleted})
    if action == "clear_test_reports":
        deleted = clear_test_reports()
        return Response({"message": f"已清理 {deleted} 份测试报告", "deleted": deleted})
    if action == "clear_runtime":
        deleted = clear_runtime_records()
        total = sum(deleted.values())
        return Response({"message": f"已清理 {total} 条运行记录", "deleted": deleted})
    if action == "format_business":
        result = format_business_data()
        return Response(result)
    return Response({"error": "未知操作"}, status=status.HTTP_400_BAD_REQUEST)
