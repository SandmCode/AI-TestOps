import json

from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from .filters import TestCaseFilter
from .models import (
    ApiInterface,
    ApiTestCase,
    AsyncTask,
    CaseTemplate,
    ExecutionRun,
    KnowledgeItem,
    Requirement,
    SecurityScanTarget,
    StressTestRun,
    StressTestTarget,
    TestCase,
    TestCaseFieldDefinition,
    TestPoint,
    TestSuite,
)
from .serializers import (
    ApiInterfaceBatchDeleteSerializer,
    ApiInterfaceReorderSerializer,
    ApiInterfaceSerializer,
    ApiTestCaseSerializer,
    AsyncTaskSerializer,
    CaseTemplateSerializer,
    ExecutionRunSerializer,
    KnowledgeItemSerializer,
    RequirementBatchCreateSerializer,
    RequirementSerializer,
    SecurityScanTargetBatchDeleteSerializer,
    SecurityScanTargetImportSerializer,
    SecurityScanTargetSerializer,
    StressTestRunCreateSerializer,
    StressTestRunSerializer,
    StressTestTargetBatchDeleteSerializer,
    StressTestTargetImportSerializer,
    StressTestTargetSerializer,
    TestCaseApplyTemplateSerializer,
    TestCaseBatchDeleteSerializer,
    TestCaseBatchUpdateStatusSerializer,
    TestCaseConvertSerializer,
    TestCaseFieldDefinitionReorderSerializer,
    TestCaseFieldDefinitionSerializer,
    TestCaseReorderSerializer,
    TestCaseSerializer,
    TestPointBatchCreateSerializer,
    TestPointBatchGenerateCasesSerializer,
    TestPointSerializer,
    TestSuiteSerializer,
)
from .services.ai_helpers import ai_error_response
from .services.ai_service import AIService, AIServiceError
from .services.case_generation_service import start_batch_case_generation
from .services.case_field_service import (
    apply_field_values,
    create_test_case_from_payload,
    get_ai_field_payload,
    get_project_field_definitions,
    normalize_case_payload,
)


class RequirementViewSet(viewsets.ModelViewSet):
    queryset = Requirement.objects.select_related("project", "document", "parent").all()
    serializer_class = RequirementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["project", "module", "document", "requirement_type"]
    search_fields = ["name", "description", "module"]

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        project_id = request.query_params.get("project")
        qs = self.get_queryset().filter(parent__isnull=True)
        if project_id:
            qs = qs.filter(project_id=project_id)

        def build_node(req):
            children = req.children.all()
            return {
                "id": req.id,
                "label": req.name,
                "module": req.module,
                "type": req.requirement_type,
                "description": req.description,
                "children": [build_node(c) for c in children] if children.exists() else [],
            }

        modules: dict[str, list] = {}
        for req in qs:
            mod = req.module or "未分类模块"
            modules.setdefault(mod, []).append(build_node(req))

        tree = [{"id": f"mod-{k}", "label": k, "type": "module", "children": v} for k, v in modules.items()]
        return Response(tree)

    @action(detail=False, methods=["post"], url_path="batch-create")
    def batch_create(self, request):
        serializer = RequirementBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        document_id = data["document_id"]
        project_id = data["project_id"]
        replace = data.get("replace", True)

        replaced_count = 0
        if replace and document_id:
            replaced_count, _ = Requirement.objects.filter(
                document_id=document_id,
                project_id=project_id,
            ).delete()

        created = []
        type_map = {"feature": "feature", "constraint": "constraint", "exception": "exception"}
        for item in data["items"]:
            req_type = type_map.get(item.get("type", "feature"), "feature")
            req = Requirement.objects.create(
                project_id=project_id,
                document_id=document_id,
                module=item.get("module", ""),
                name=item.get("name", "未命名"),
                description=item.get("description", ""),
                requirement_type=req_type,
            )
            created.append(RequirementSerializer(req).data)
        return Response({
            "requirements": created,
            "count": len(created),
            "replaced_count": replaced_count,
            "replace": replace,
        })

    @action(detail=True, methods=["post"])
    def ai_generate_test_points(self, request, pk=None):
        requirement = self.get_object()
        strategy = request.data.get("strategy", "default")
        rag_context = request.data.get("rag_context", "")
        use_rag = request.data.get("use_rag", False)

        if use_rag and not rag_context:
            items = KnowledgeItem.objects.filter(
                Q(project=requirement.project) | Q(project__isnull=True)
            )[:5]
            rag_context = "\n".join(f"[{i.category}] {i.title}: {i.content[:200]}" for i in items)

        try:
            ai = AIService()
            points = ai.generate_test_points(
                requirement.name, requirement.description, strategy=strategy, rag_context=rag_context
            )
        except AIServiceError as exc:
            return ai_error_response(exc)
        created = []
        for idx, item in enumerate(points):
            tp = TestPoint.objects.create(
                requirement=requirement,
                name=item.get("name", f"测试点{idx+1}"),
                description=item.get("description", ""),
                point_type=item.get("point_type", "functional"),
                design_strategy=strategy,
                rag_context=rag_context[:1000],
            )
            created.append(TestPointSerializer(tp).data)
        return Response({"test_points": created})


class TestPointViewSet(viewsets.ModelViewSet):
    queryset = TestPoint.objects.select_related("requirement", "requirement__project").all()
    serializer_class = TestPointSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["requirement", "point_type", "design_strategy", "requirement__project"]
    search_fields = ["name", "description"]

    def create(self, request, *args, **kwargs):
        data = request.data.copy()
        if not data.get("requirement") and data.get("project"):
            req = Requirement.objects.create(
                project_id=data["project"],
                module=data.pop("module", "") or "",
                name=data.get("name", "未命名"),
                description=data.get("description", ""),
                requirement_type="feature",
            )
            data["requirement"] = req.id
            data.pop("project", None)
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        project_id = request.query_params.get("project")
        qs = self.get_queryset()
        if project_id:
            qs = qs.filter(requirement__project_id=project_id)

        modules: dict[str, list] = {}
        for tp in qs:
            mod = tp.requirement.module or "未分类"
            modules.setdefault(mod, []).append({
                "id": tp.id,
                "label": tp.name,
                "type": "test_point",
                "module": mod,
                "description": tp.description,
                "point_type": tp.point_type,
                "design_strategy": tp.design_strategy,
            })

        tree = [{"id": f"mod-{k}", "label": k, "type": "module", "children": v} for k, v in modules.items()]
        return Response(tree)

    @action(detail=False, methods=["post"], url_path="batch-create")
    def batch_create(self, request):
        serializer = TestPointBatchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        document_id = data["document_id"]
        project_id = data["project_id"]
        replace = data.get("replace", True)

        replaced_count = 0
        if replace and document_id:
            replaced_count, _ = TestPoint.objects.filter(
                requirement__document_id=document_id,
                requirement__project_id=project_id,
            ).delete()
            Requirement.objects.filter(document_id=document_id, project_id=project_id).delete()

        type_map = {"feature": "feature", "constraint": "constraint", "exception": "exception"}
        point_type_map = {"feature": "functional", "constraint": "functional", "exception": "exception"}
        created = []
        for item in data["items"]:
            req_type = type_map.get(item.get("type", "feature"), "feature")
            req = Requirement.objects.create(
                project_id=project_id,
                document_id=document_id,
                module=item.get("module", ""),
                name=item.get("name", "未命名"),
                description=item.get("description", ""),
                requirement_type=req_type,
            )
            tp = TestPoint.objects.create(
                requirement=req,
                name=item.get("name", "未命名"),
                description=item.get("description", ""),
                point_type=point_type_map.get(item.get("type", "feature"), "functional"),
                design_strategy="default",
            )
            created.append(tp)

        return Response({
            "test_points": TestPointSerializer(created, many=True).data,
            "count": len(created),
            "replaced_count": replaced_count,
            "replace": replace,
        })

    def _recall_rag(self, project_id, keyword: str) -> str:
        items = KnowledgeItem.objects.filter(Q(project_id=project_id) | Q(project__isnull=True))
        if keyword:
            items = items.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
        return "\n".join(f"[{i.category}] {i.title}: {i.content[:200]}" for i in items[:5])

    @action(detail=False, methods=["post"], url_path="ai-generate-cases")
    def ai_generate_cases_batch(self, request):
        serializer = TestPointBatchGenerateCasesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        test_point_ids = data["test_point_ids"]
        strategies = data["strategies"]
        use_rag = data["use_rag"]

        points = list(
            TestPoint.objects.filter(id__in=test_point_ids).select_related("requirement", "requirement__project")
        )
        if not points:
            return Response({"error": "未找到测试点"}, status=status.HTTP_400_BAD_REQUEST)

        project_ids = {tp.requirement.project_id for tp in points}
        if len(project_ids) > 1:
            return Response({"error": "请选择同一项目下的测试点"}, status=status.HTTP_400_BAD_REQUEST)

        project_id = next(iter(project_ids))
        try:
            AIService()._require_config()
        except AIServiceError as exc:
            return ai_error_response(exc)

        task = start_batch_case_generation(
            project_id=project_id,
            test_point_ids=test_point_ids,
            strategies=strategies,
            use_rag=use_rag,
        )
        return Response(AsyncTaskSerializer(task).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def ai_generate_cases(self, request, pk=None):
        test_point = self.get_object()
        strategy = request.data.get("strategy", "default")
        use_rag = request.data.get("use_rag", False)
        rag_context = request.data.get("rag_context", "")
        if use_rag and not rag_context:
            rag_context = self._recall_rag(test_point.requirement.project_id, test_point.name)
        project = test_point.requirement.project
        field_defs = get_project_field_definitions(project.id)
        field_payload = get_ai_field_payload(field_defs)
        try:
            ai = AIService()
            cases = ai.generate_test_cases(
                test_point.name,
                description=test_point.description,
                strategy=strategy,
                point_type=test_point.point_type,
                rag_context=rag_context,
                field_definitions=field_payload,
                module_hint=test_point.requirement.module,
            )
        except AIServiceError as exc:
            return ai_error_response(exc)
        created = []
        max_order = TestCase.objects.filter(project=project).count()
        for idx, item in enumerate(cases):
            normalized = normalize_case_payload(item, field_defs)
            if not normalized.get("module"):
                normalized["module"] = test_point.requirement.module
            tc = create_test_case_from_payload(
                project.id,
                normalized,
                field_defs,
                test_point=test_point,
                source_type="test_point",
                sort_order=max_order + idx,
            )
            created.append(TestCaseSerializer(tc).data)
        return Response({"test_cases": created})


class KnowledgeItemViewSet(viewsets.ModelViewSet):
    queryset = KnowledgeItem.objects.all()
    serializer_class = KnowledgeItemSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["category", "project"]
    search_fields = ["title", "content", "tags"]

    @action(detail=False, methods=["get"], url_path="recall")
    def recall(self, request):
        keyword = request.query_params.get("keyword", "")
        project_id = request.query_params.get("project")
        qs = self.get_queryset()
        if project_id:
            qs = qs.filter(Q(project_id=project_id) | Q(project__isnull=True))
        if keyword:
            qs = qs.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
        items = qs[:10]
        return Response(KnowledgeItemSerializer(items, many=True).data)


class CaseTemplateViewSet(viewsets.ModelViewSet):
    queryset = CaseTemplate.objects.all()
    serializer_class = CaseTemplateSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["category"]
    search_fields = ["name"]


class TestCaseFieldDefinitionViewSet(viewsets.ModelViewSet):
    queryset = TestCaseFieldDefinition.objects.select_related("project").all()
    serializer_class = TestCaseFieldDefinitionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project"]

    def get_queryset(self):
        qs = super().get_queryset()
        project_id = self.request.query_params.get("project")
        if project_id and not qs.filter(project_id=project_id).exists():
            get_project_field_definitions(int(project_id))
            qs = super().get_queryset()
        return qs

    def perform_create(self, serializer):
        import re
        import time

        key = serializer.validated_data.get("key", "").strip()
        if not key:
            label = serializer.validated_data.get("label", "field")
            slug = re.sub(r"[^a-zA-Z0-9_]", "", label.replace(" ", "_").lower())
            key = slug or f"field_{int(time.time())}"
        serializer.save(
            key=key,
            storage=serializer.validated_data.get("storage", "extra"),
            is_system=False,
        )

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.is_system:
            return Response({"error": "系统字段不可删除，可修改显示名或隐藏"}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        serializer = TestCaseFieldDefinitionReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        with transaction.atomic():
            for order, field_id in enumerate(ids):
                TestCaseFieldDefinition.objects.filter(id=field_id).update(sort_order=order)
        fields = TestCaseFieldDefinition.objects.filter(id__in=ids).order_by("sort_order")
        return Response(TestCaseFieldDefinitionSerializer(fields, many=True).data)

    @action(detail=False, methods=["post"], url_path="reset-defaults")
    def reset_defaults(self, request):
        project_id = request.data.get("project")
        if not project_id:
            return Response({"error": "请指定项目"}, status=status.HTTP_400_BAD_REQUEST)
        TestCaseFieldDefinition.objects.filter(project_id=project_id).delete()
        fields = get_project_field_definitions(int(project_id))
        return Response(TestCaseFieldDefinitionSerializer(fields, many=True).data)


class TestCaseViewSet(viewsets.ModelViewSet):
    queryset = TestCase.objects.select_related("project", "test_point", "depends_on", "template").all()
    serializer_class = TestCaseSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = TestCaseFilter
    ordering_fields = ["sort_order", "created_at", "priority"]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        serializer = TestCaseReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        with transaction.atomic():
            for order, case_id in enumerate(ids):
                TestCase.objects.filter(id=case_id).update(sort_order=order)
        cases = TestCase.objects.filter(id__in=ids).order_by("sort_order")
        return Response(TestCaseSerializer(cases, many=True).data)

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        serializer = TestCaseBatchDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        deleted, _ = TestCase.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="batch-update-status")
    def batch_update_status(self, request):
        serializer = TestCaseBatchUpdateStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        passed = serializer.validated_data["passed"]
        updated = TestCase.objects.filter(id__in=ids).update(passed=passed)
        return Response({"updated": updated, "passed": passed})

    @action(detail=False, methods=["get"], url_path="export-excel")
    def export_excel(self, request):
        from .services.test_case_export_service import build_export_filename, build_test_cases_excel

        queryset = self.filter_queryset(self.get_queryset()).select_related("project", "test_point")
        ids_raw = request.query_params.get("ids", "")
        if ids_raw.strip():
            id_list = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()]
            if id_list:
                queryset = queryset.filter(id__in=id_list)

        cases = list(queryset.order_by("sort_order", "id"))
        if not cases:
            return Response({"error": "没有可导出的测试用例"}, status=status.HTTP_400_BAD_REQUEST)

        content = build_test_cases_excel(cases)
        project_name = cases[0].project.name if cases[0].project_id else ""
        filename = build_export_filename(project_name)
        from urllib.parse import quote

        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return response

    @action(detail=False, methods=["post"], url_path="apply-template")
    def apply_template(self, request):
        serializer = TestCaseApplyTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        tpl = CaseTemplate.objects.get(pk=data["template_id"])
        max_order = TestCase.objects.filter(project_id=data["project_id"]).count()
        case = TestCase.objects.create(
            project_id=data["project_id"],
            template=tpl,
            title=data["title"],
            precondition=tpl.precondition,
            steps=tpl.steps,
            expected=tpl.expected,
            postcondition=tpl.postcondition,
            source_type="template",
            sort_order=max_order,
        )
        return Response(TestCaseSerializer(case).data)

    @action(detail=False, methods=["post"], url_path="convert")
    def convert(self, request):
        serializer = TestCaseConvertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fmt = serializer.validated_data["format"]
        cases = TestCase.objects.filter(id__in=serializer.validated_data["ids"])

        if fmt == "pytest":
            lines = ["import pytest", ""]
            for c in cases:
                fn = f"test_{c.id}_{c.title.replace(' ', '_')[:30]}"
                lines.append(f"def {fn}():")
                lines.append(f'    """{c.title}"""')
                if c.precondition:
                    lines.append(f"    # 前置: {c.precondition[:80]}")
                for step in (c.steps or "").split("\n"):
                    if step.strip():
                        lines.append(f"    # {step.strip()}")
                lines.append(f"    assert True  # 预期: {(c.expected or '')[:60]}")
                lines.append("")
            content = "\n".join(lines)
        elif fmt == "postman":
            items = []
            for c in cases:
                items.append({
                    "name": c.title,
                    "request": {"method": "GET", "url": "{{baseUrl}}/api/placeholder"},
                    "event": [{"listen": "test", "script": {"exec": [f"// {c.expected}"]}}],
                })
            content = json.dumps({"info": {"name": "Exported Cases"}, "item": items}, ensure_ascii=False, indent=2)
        else:
            lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<jmeterTestPlan version="1.2">', "  <hashTree>"]
            for c in cases:
                lines.append(f'    <HTTPSamplerProxy testname="{c.title}"/>')
            lines.extend(["  </hashTree>", "</jmeterTestPlan>"])
            content = "\n".join(lines)

        return Response({"format": fmt, "content": content, "count": cases.count()})


class TestSuiteViewSet(viewsets.ModelViewSet):
    queryset = TestSuite.objects.select_related("project").all()
    serializer_class = TestSuiteSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project"]

    @action(detail=True, methods=["post"], url_path="run")
    def run(self, request, pk=None):
        suite = self.get_object()
        case_ids = suite.case_ids or []
        cases = TestCase.objects.filter(id__in=case_ids, project=suite.project)
        results = []
        passed = failed = 0
        for case in cases:
            ok = case.passed is True
            if case.passed is None:
                ok = True
                passed += 1
            elif ok:
                passed += 1
            else:
                failed += 1
            results.append({
                "case_id": case.id,
                "title": case.title,
                "passed": ok if case.passed is not None else None,
                "actual": case.actual or "待执行",
            })

        try:
            ai = AIService()
            analysis = ai.analyze_execution(results)
        except AIServiceError as exc:
            return ai_error_response(exc)
        status_val = "success" if failed == 0 else ("partial" if passed > 0 else "failed")
        run = ExecutionRun.objects.create(
            project=suite.project,
            suite=suite,
            name=f"{suite.name} - 执行",
            status=status_val,
            total=len(results),
            passed=passed,
            failed=failed,
            results=results,
            ai_analysis=analysis,
        )
        return Response(ExecutionRunSerializer(run).data)


class ExecutionRunViewSet(viewsets.ModelViewSet):
    queryset = ExecutionRun.objects.select_related("project", "suite").all()
    serializer_class = ExecutionRunSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["project", "status"]
    ordering_fields = ["created_at"]

    @action(detail=False, methods=["post"], url_path="batch-run")
    def batch_run(self, request):
        project_id = request.data.get("project_id")
        case_ids = request.data.get("case_ids", [])
        name = request.data.get("name", "批量执行")
        cases = TestCase.objects.filter(id__in=case_ids, project_id=project_id)
        results = []
        passed = failed = 0
        for case in cases:
            if case.passed is False:
                failed += 1
                ok = False
            else:
                passed += 1
                ok = True
            results.append({"case_id": case.id, "title": case.title, "passed": ok, "actual": case.actual or ""})

        try:
            ai = AIService()
            analysis = ai.analyze_execution(results)
        except AIServiceError as exc:
            return ai_error_response(exc)
        run = ExecutionRun.objects.create(
            project_id=project_id,
            name=name,
            status="success" if failed == 0 else "partial",
            total=len(results),
            passed=passed,
            failed=failed,
            results=results,
            ai_analysis=analysis,
        )
        return Response(ExecutionRunSerializer(run).data)


class ApiInterfaceViewSet(viewsets.ModelViewSet):
    queryset = ApiInterface.objects.select_related("project", "depends_on", "document").all()
    serializer_class = ApiInterfaceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project", "method", "module", "document"]
    search_fields = ["name", "url"]

    @action(detail=False, methods=["post"], url_path="batch-import")
    def batch_import(self, request):
        project_id = request.data.get("project_id")
        document_id = request.data.get("document_id")
        items = request.data.get("interfaces", [])
        if not project_id:
            return Response({"error": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)
        if not items:
            return Response({"error": "interfaces 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        base_order = ApiInterface.objects.filter(project_id=project_id).count()
        created = []
        created_ids = []
        for idx, item in enumerate(items):
            method = str(item.get("method", "GET")).upper()
            api = ApiInterface.objects.create(
                project_id=project_id,
                document_id=document_id,
                name=item.get("name") or "未命名接口",
                module=item.get("module") or "",
                method=method if method in ("GET", "POST", "PUT", "DELETE", "PATCH") else "GET",
                url=item.get("url") or "",
                headers=item.get("headers") if isinstance(item.get("headers"), dict) else {},
                params=item.get("params") if isinstance(item.get("params"), dict) else {},
                body=item.get("body") if isinstance(item.get("body"), dict) else {},
                response_example=(
                    item.get("response_example")
                    if isinstance(item.get("response_example"), dict)
                    else item.get("response") if isinstance(item.get("response"), dict) else {}
                ),
                description=item.get("description") or "",
                sort_order=base_order + idx,
            )
            created_ids.append(api.id)
            created.append(ApiInterfaceSerializer(api).data)
        auto_deps = {}
        if request.data.get("auto_configure_deps", True):
            from .services.api_dependency_service import auto_configure_after_import

            auto_deps = auto_configure_after_import(project_id, created_ids)
        return Response({"interfaces": created, "count": len(created), "auto_deps": auto_deps})

    @action(detail=False, methods=["post"], url_path="sort-order")
    def sort_order(self, request):
        serializer = ApiInterfaceReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        with transaction.atomic():
            for order, api_id in enumerate(ids):
                ApiInterface.objects.filter(id=api_id).update(sort_order=order)
        apis = ApiInterface.objects.filter(id__in=ids).order_by("sort_order")
        return Response(ApiInterfaceSerializer(apis, many=True).data)

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        serializer = ApiInterfaceBatchDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        deleted, _ = ApiInterface.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="batch-configure-deps")
    def batch_configure_deps(self, request):
        from .services.api_dependency_service import bulk_configure_auth_dependencies, detect_login_api

        project_id = request.data.get("project_id")
        if not project_id:
            return Response({"error": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)

        auth_api_id = request.data.get("auth_api_id")
        if not auth_api_id:
            apis = list(ApiInterface.objects.filter(project_id=project_id))
            login = detect_login_api(apis)
            if not login:
                return Response(
                    {"error": "未找到登录接口，请手动选择"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            auth_api_id = login.id

        try:
            result = bulk_configure_auth_dependencies(
                project_id,
                auth_api_id,
                overwrite=bool(request.data.get("overwrite", False)),
                only_unconfigured=bool(request.data.get("only_unconfigured", True)),
                interface_ids=request.data.get("interface_ids"),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="run-automation")
    def run_automation(self, request):
        from .services.api_automation_service import run_automation

        interface_ids = request.data.get("interface_ids", [])
        variables = request.data.get("variables", {})
        if not interface_ids:
            return Response({"error": "interface_ids 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        result = run_automation(interface_ids, variables)
        return Response(result)

    @action(detail=False, methods=["post"], url_path="generate-python")
    def generate_python(self, request):
        from .services.api_automation_service import generate_python_script

        interface_ids = request.data.get("interface_ids", [])
        variables = request.data.get("variables", {})
        if not interface_ids:
            return Response({"error": "interface_ids 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        code = generate_python_script(interface_ids, variables)
        return Response({"code": code})

    @action(detail=True, methods=["post"])
    def ai_generate_cases(self, request, pk=None):
        api = self.get_object()
        full = request.data.get("full", True)
        try:
            ai = AIService()
            cases = ai.generate_api_cases(
                {"name": api.name, "method": api.method, "url": api.url, "params": api.params},
                full=full,
            )
        except AIServiceError as exc:
            return ai_error_response(exc)
        created = []
        max_order = ApiTestCase.objects.filter(api=api).count()
        for idx, item in enumerate(cases):
            tc = ApiTestCase.objects.create(
                api=api,
                title=item.get("title", f"接口用例{idx+1}"),
                params=item.get("params", {}),
                validate_content=item.get("validate_content", ""),
                sort_order=max_order + idx,
            )
            created.append(ApiTestCaseSerializer(tc).data)
        return Response({"test_cases": created})

    @action(detail=True, methods=["post"])
    def debug(self, request, pk=None):
        from .services.api_automation_service import run_single_interface

        api = self.get_object()
        variables = request.data.get("variables", {})
        result = run_single_interface(api, variables, None)
        if result.get("error"):
            return Response(
                {
                    "error": result["error"],
                    "url": result.get("url"),
                    "status_code": 0,
                    "body": "",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "status_code": result["status_code"],
                "headers": result["headers"],
                "body": result["body"],
                "url": result["url"],
            }
        )


class StressTestTargetViewSet(viewsets.ModelViewSet):
    queryset = StressTestTarget.objects.select_related("project", "depends_on").all()
    serializer_class = StressTestTargetSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project", "method", "module"]
    search_fields = ["name", "url"]

    @action(detail=False, methods=["post"], url_path="import-from-interfaces")
    def import_from_interfaces(self, request):
        from .services.stress_target_service import import_targets_from_interfaces

        serializer = StressTestTargetImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = import_targets_from_interfaces(
                data["project_id"],
                data["interface_ids"],
                replace=data.get("replace", True),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        targets = StressTestTargetSerializer(result["targets"], many=True).data
        return Response({
            "targets": targets,
            "count": result["count"],
            "replace": result["replace"],
            "before_count": result["before_count"],
            "after_count": result["after_count"],
            "created_count": result["created_count"],
            "updated_count": result["updated_count"],
            "removed_count": result["removed_count"],
        })

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        serializer = StressTestTargetBatchDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        deleted, _ = StressTestTarget.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted})

    @action(detail=False, methods=["post"], url_path="batch-configure-deps")
    def batch_configure_deps(self, request):
        from .services.stress_target_service import bulk_configure_auth_dependencies, detect_login_target

        project_id = request.data.get("project_id")
        if not project_id:
            return Response({"error": "缺少 project_id"}, status=status.HTTP_400_BAD_REQUEST)

        auth_target_id = request.data.get("auth_target_id")
        if not auth_target_id:
            targets = list(StressTestTarget.objects.filter(project_id=project_id))
            login = detect_login_target(targets)
            if not login:
                return Response(
                    {"error": "未找到登录接口，请手动选择或先新增登录压测目标"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            auth_target_id = login.id

        try:
            result = bulk_configure_auth_dependencies(
                project_id,
                auth_target_id,
                overwrite=bool(request.data.get("overwrite", False)),
                only_unconfigured=bool(request.data.get("only_unconfigured", True)),
                target_ids=request.data.get("target_ids"),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)

    @action(detail=True, methods=["post"])
    def debug(self, request, pk=None):
        from .services.stress_test_service import debug_stress_target

        target = self.get_object()
        variables = request.data.get("variables", {})
        result = debug_stress_target(target, variables)
        if result.get("error") and not result.get("status_code"):
            return Response(result, status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class StressTestRunViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StressTestRun.objects.select_related("project").all()
    serializer_class = StressTestRunSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project", "status"]

    @action(detail=False, methods=["post"], url_path="start")
    def start(self, request):
        serializer = StressTestRunCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        from .services.stress_test_service import start_stress_run

        try:
            run = start_stress_run(
                data["project_id"],
                data["target_ids"],
                data.get("variables") or {},
                users=data["users"],
                spawn_rate=data["spawn_rate"],
                duration_sec=data["duration_sec"],
                think_time_ms=data["think_time_ms"],
                token_refresh_sec=data.get("token_refresh_sec", 60),
                name=data.get("name") or "",
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(StressTestRunSerializer(run).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="stop")
    def stop(self, request, pk=None):
        from .services.stress_test_service import stop_stress_run

        run = self.get_object()
        if run.status not in ("pending", "running"):
            return Response({"error": "任务已结束"}, status=status.HTTP_400_BAD_REQUEST)
        stop_stress_run(run.id)
        return Response({"stopped": True})

    @action(detail=True, methods=["get"], url_path="analysis")
    def analysis(self, request, pk=None):
        from apps.testing.services.stress_analysis_service import analyze_stress_run

        run = self.get_object()
        if run.status not in ("completed", "stopped"):
            return Response({"error": "压测尚未结束"}, status=status.HTTP_400_BAD_REQUEST)
        data = run.analysis or analyze_stress_run(run)
        if not run.analysis:
            run.analysis = data
            run.save(update_fields=["analysis"])
        return Response(data)

    @action(detail=True, methods=["post"], url_path="generate-report")
    def generate_report(self, request, pk=None):
        from apps.ai_features.services.allure_report_service import generate_stress_report
        from apps.testing.services.stress_analysis_service import analyze_stress_run

        run = self.get_object()
        if run.status not in ("completed", "stopped"):
            return Response({"error": "压测尚未结束"}, status=status.HTTP_400_BAD_REQUEST)
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
        from apps.ai_features.serializers import TestReportSerializer

        return Response(TestReportSerializer(report).data, status=status.HTTP_201_CREATED)


class SecurityScanTargetViewSet(viewsets.ModelViewSet):
    queryset = SecurityScanTarget.objects.select_related("project", "depends_on").all()
    serializer_class = SecurityScanTargetSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["project", "method", "module"]
    search_fields = ["name", "url"]

    @action(detail=False, methods=["get"], url_path="security-meta")
    def security_meta(self, request):
        from .services.api_security_service import get_security_meta

        return Response(get_security_meta())

    @action(detail=False, methods=["post"], url_path="import-from-interfaces")
    def import_from_interfaces(self, request):
        from .services.security_target_service import import_targets_from_interfaces

        serializer = SecurityScanTargetImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = import_targets_from_interfaces(
                data["project_id"],
                data["interface_ids"],
                replace=data.get("replace", True),
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        targets = SecurityScanTargetSerializer(result["targets"], many=True).data
        return Response({
            "targets": targets,
            "count": result["count"],
            "replace": result["replace"],
            "before_count": result["before_count"],
            "after_count": result["after_count"],
            "created_count": result["created_count"],
            "updated_count": result["updated_count"],
            "removed_count": result["removed_count"],
        })

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        serializer = SecurityScanTargetBatchDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        deleted, _ = SecurityScanTarget.objects.filter(id__in=ids).delete()
        return Response({"deleted": deleted})

    @action(detail=False, methods=["post"], url_path="run-scan")
    def run_scan(self, request):
        from .services.api_security_service import run_security_scan_for_targets

        target_ids = request.data.get("target_ids", [])
        variables = request.data.get("variables", {})
        strategies = request.data.get("strategies")
        if not target_ids:
            return Response({"error": "target_ids 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
        result = run_security_scan_for_targets(target_ids, variables, strategies)
        return Response(result)


class ApiTestCaseViewSet(viewsets.ModelViewSet):
    queryset = ApiTestCase.objects.select_related("api").all()
    serializer_class = ApiTestCaseSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["api", "should_run"]

    @action(detail=False, methods=["post"], url_path="reorder")
    def reorder(self, request):
        ids = request.data.get("ids", [])
        with transaction.atomic():
            for order, case_id in enumerate(ids):
                ApiTestCase.objects.filter(id=case_id).update(sort_order=order)
        cases = ApiTestCase.objects.filter(id__in=ids).order_by("sort_order")
        return Response(ApiTestCaseSerializer(cases, many=True).data)


class AsyncTaskViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AsyncTask.objects.all()
    serializer_class = AsyncTaskSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "task_type", "project"]
    search_fields = ["task_name"]

    @action(detail=False, methods=["get"], url_path="active")
    def active(self, request):
        qs = AsyncTask.objects.filter(
            task_type="case_generation",
            status__in=["pending", "running"],
        ).order_by("-created_at")
        project_id = request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        task = qs.first()
        if not task:
            return Response({"active": False})
        data = AsyncTaskSerializer(task).data
        data["active"] = True
        return Response(data)
