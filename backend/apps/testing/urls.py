from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApiInterfaceViewSet,
    ApiTestCaseViewSet,
    AsyncTaskViewSet,
    CaseTemplateViewSet,
    ExecutionRunViewSet,
    KnowledgeItemViewSet,
    RequirementViewSet,
    SecurityScanTargetViewSet,
    StressTestRunViewSet,
    StressTestTargetViewSet,
    TestCaseFieldDefinitionViewSet,
    TestCaseViewSet,
    TestPointViewSet,
    TestSuiteViewSet,
)

router = DefaultRouter()
router.register("requirements", RequirementViewSet)
router.register("test-points", TestPointViewSet)
router.register("test-cases", TestCaseViewSet)
router.register("case-field-definitions", TestCaseFieldDefinitionViewSet)
router.register("knowledge-items", KnowledgeItemViewSet)
router.register("case-templates", CaseTemplateViewSet)
router.register("test-suites", TestSuiteViewSet)
router.register("execution-runs", ExecutionRunViewSet)
router.register("api-interfaces", ApiInterfaceViewSet)
router.register("security-scan-targets", SecurityScanTargetViewSet)
router.register("stress-test-targets", StressTestTargetViewSet)
router.register("stress-test-runs", StressTestRunViewSet)
router.register("api-test-cases", ApiTestCaseViewSet)
router.register("async-tasks", AsyncTaskViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
