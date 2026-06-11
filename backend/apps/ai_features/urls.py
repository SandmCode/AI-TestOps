from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("analysis-records", views.AnalysisRecordViewSet, basename="analysis-records")
router.register("test-reports", views.TestReportViewSet)
router.register("ai-config", views.AIProviderConfigViewSet, basename="ai-config")
router.register("ai-skills", views.AISkillViewSet, basename="ai-skills")

urlpatterns = [
    path("", include(router.urls)),
    path("ai/config-status/", views.ai_config_status),
    path("ai/contract-test/", views.contract_test),
    path("ai/contract-test/fix/", views.contract_test_fix),
    path("ai/coverage-analysis/", views.coverage_analysis),
    path("ai/log-analysis/", views.log_analysis),
    path("system/info/", views.system_info),
    path("system/maintain/", views.system_maintain),
]
