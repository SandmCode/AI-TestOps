from rest_framework import serializers

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


class RequirementSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    document_name = serializers.CharField(source="document.name", read_only=True, default="")
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Requirement
        fields = "__all__"

    def get_children_count(self, obj):
        return obj.children.count()


class RequirementBatchCreateSerializer(serializers.Serializer):
    document_id = serializers.IntegerField()
    project_id = serializers.IntegerField()
    items = serializers.ListField(child=serializers.DictField(), min_length=1)
    replace = serializers.BooleanField(default=True, required=False)


class TestPointSerializer(serializers.ModelSerializer):
    requirement_name = serializers.CharField(source="requirement.name", read_only=True)
    module = serializers.CharField(source="requirement.module", read_only=True)
    project = serializers.IntegerField(source="requirement.project_id", read_only=True)

    class Meta:
        model = TestPoint
        fields = "__all__"


class TestPointBatchCreateSerializer(serializers.Serializer):
    document_id = serializers.IntegerField()
    project_id = serializers.IntegerField()
    items = serializers.ListField(child=serializers.DictField(), min_length=1)
    replace = serializers.BooleanField(default=True, required=False)


class TestPointBatchGenerateCasesSerializer(serializers.Serializer):
    test_point_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    strategies = serializers.ListField(
        child=serializers.ChoiceField(choices=["default", "equivalence", "boundary", "scenario", "state"]),
        min_length=1,
    )
    use_rag = serializers.BooleanField(default=False, required=False)


class KnowledgeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeItem
        fields = "__all__"


class CaseTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CaseTemplate
        fields = "__all__"


class TestCaseFieldDefinitionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestCaseFieldDefinition
        fields = "__all__"
        read_only_fields = ["created_at"]


class TestCaseFieldDefinitionReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class TestCaseSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    test_point_name = serializers.CharField(source="test_point.name", read_only=True, default="")
    depends_on_title = serializers.CharField(source="depends_on.title", read_only=True, default="")

    class Meta:
        model = TestCase
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        extra = instance.extra_data or {}
        for key, value in extra.items():
            data[key] = value
        if instance.created_at:
            data["created_at"] = instance.created_at.isoformat()
        return data

    def to_internal_value(self, data):
        self._dynamic_input = {k: v for k, v in data.items() if k not in self.fields}
        return super().to_internal_value(data)

    def _split_payload(self, validated_data: dict) -> tuple[dict, dict]:
        extra = dict(validated_data.pop("extra_data", {}) or {})
        extra.update(getattr(self, "_dynamic_input", {}))
        return validated_data, extra

    def validate(self, attrs):
        if not str(attrs.get("title") or "").strip():
            attrs["title"] = "未命名用例"
        if not str(attrs.get("priority") or "").strip():
            attrs["priority"] = "P2"
        return attrs

    def create(self, validated_data):
        base, extra = self._split_payload(validated_data)
        base["extra_data"] = extra
        return super().create(base)

    def update(self, instance, validated_data):
        base, extra = self._split_payload(validated_data)
        if extra:
            merged = dict(instance.extra_data or {})
            merged.update(extra)
            base["extra_data"] = merged
        return super().update(instance, base)


class TestCaseBatchDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class TestCaseBatchUpdateStatusSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    passed = serializers.BooleanField(required=True, allow_null=True)


class TestCaseReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class TestCaseConvertSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    format = serializers.ChoiceField(choices=["pytest", "postman", "jmeter"])


class TestCaseApplyTemplateSerializer(serializers.Serializer):
    template_id = serializers.IntegerField()
    project_id = serializers.IntegerField()
    title = serializers.CharField(max_length=300)


class ApiInterfaceBatchDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class ApiInterfaceReorderSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class ApiInterfaceSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    depends_on_name = serializers.CharField(source="depends_on.name", read_only=True, allow_null=True)
    document_name = serializers.CharField(source="document.name", read_only=True, allow_null=True)

    class Meta:
        model = ApiInterface
        fields = "__all__"


class StressTestTargetSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    depends_on_name = serializers.CharField(source="depends_on.name", read_only=True, allow_null=True)

    class Meta:
        model = StressTestTarget
        fields = "__all__"


class StressTestTargetBatchDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class StressTestTargetImportSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    interface_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    replace = serializers.BooleanField(default=True, required=False)


class StressTestRunSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = StressTestRun
        fields = "__all__"


class StressTestRunCreateSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    target_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    variables = serializers.DictField(required=False, default=dict)
    users = serializers.IntegerField(default=10, min_value=1, max_value=500)
    spawn_rate = serializers.IntegerField(default=2, min_value=1, max_value=100)
    duration_sec = serializers.IntegerField(default=30, min_value=1, max_value=3600)
    think_time_ms = serializers.IntegerField(default=0, min_value=0, max_value=60000)
    token_refresh_sec = serializers.IntegerField(default=60, min_value=0, max_value=3600)
    name = serializers.CharField(required=False, allow_blank=True, default="")


class SecurityScanTargetSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    depends_on_name = serializers.CharField(source="depends_on.name", read_only=True, allow_null=True)

    class Meta:
        model = SecurityScanTarget
        fields = "__all__"


class SecurityScanTargetBatchDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class SecurityScanTargetImportSerializer(serializers.Serializer):
    project_id = serializers.IntegerField()
    interface_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    replace = serializers.BooleanField(default=True, required=False)


class ApiTestCaseSerializer(serializers.ModelSerializer):
    api_name = serializers.CharField(source="api.name", read_only=True)

    class Meta:
        model = ApiTestCase
        fields = "__all__"


class TestSuiteSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = TestSuite
        fields = "__all__"


class ExecutionRunSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ExecutionRun
        fields = "__all__"


class AsyncTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = AsyncTask
        fields = "__all__"
