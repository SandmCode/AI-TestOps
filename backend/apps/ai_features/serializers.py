from rest_framework import serializers

from .models import AIProviderConfig, AISkill, AISkillsSettings, AnalysisRecord, TestReport


class AnalysisRecordSerializer(serializers.ModelSerializer):
    analysis_type_display = serializers.CharField(source="get_analysis_type_display", read_only=True)

    class Meta:
        model = AnalysisRecord
        fields = [
            "id",
            "analysis_type",
            "analysis_type_display",
            "title",
            "summary",
            "input_preview",
            "input_content",
            "result",
            "created_at",
        ]
        read_only_fields = fields


class AnalysisRecordListSerializer(serializers.ModelSerializer):
    analysis_type_display = serializers.CharField(source="get_analysis_type_display", read_only=True)

    class Meta:
        model = AnalysisRecord
        fields = [
            "id",
            "analysis_type",
            "analysis_type_display",
            "title",
            "summary",
            "input_preview",
            "created_at",
        ]


class TestReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestReport
        fields = "__all__"


class AIProviderConfigSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source="get_provider_display", read_only=True)
    masked_api_key = serializers.CharField(read_only=True)
    api_key = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = AIProviderConfig
        fields = [
            "id",
            "name",
            "provider",
            "provider_display",
            "api_key",
            "masked_api_key",
            "base_url",
            "model",
            "temperature",
            "max_tokens",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at", "is_active"]

    def validate(self, attrs):
        provider = attrs.get("provider") or getattr(self.instance, "provider", None)
        base_url = attrs.get("base_url", getattr(self.instance, "base_url", ""))
        model = attrs.get("model", getattr(self.instance, "model", ""))
        api_key = attrs.get("api_key")

        if self.instance is None and not api_key:
            raise serializers.ValidationError({"api_key": "请填写 API Key"})

        if provider in ("openai", "deepseek", "qwen", "moonshot", "custom") and not base_url:
            defaults = {
                "openai": "https://api.openai.com/v1",
                "deepseek": "https://api.deepseek.com/v1",
                "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "moonshot": "https://api.moonshot.cn/v1",
            }
            if provider in defaults:
                attrs["base_url"] = defaults[provider]
            elif not base_url:
                raise serializers.ValidationError({"base_url": "自定义厂商需填写 Base URL"})

        if not model:
            raise serializers.ValidationError({"model": "请填写模型名称"})

        return attrs

    def create(self, validated_data):
        validated_data["is_active"] = not AIProviderConfig.objects.exists()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "api_key" not in validated_data or not validated_data["api_key"]:
            validated_data.pop("api_key", None)
        return super().update(instance, validated_data)


class AIConfigStatusSerializer(serializers.Serializer):
    configured = serializers.BooleanField()
    source = serializers.CharField()
    provider = serializers.CharField(allow_blank=True, required=False, default="")
    provider_display = serializers.CharField(allow_blank=True, required=False, default="")
    model = serializers.CharField(allow_blank=True, required=False, default="")
    name = serializers.CharField(allow_blank=True, required=False, default="")
    masked_api_key = serializers.CharField(allow_blank=True, required=False, default="")
    skills_enabled = serializers.BooleanField(required=False, default=True)
    skills_count = serializers.IntegerField(required=False, default=0)


class AISkillsSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISkillsSettings
        fields = ["skills_enabled", "updated_at"]


class AISkillSerializer(serializers.ModelSerializer):
    content_preview = serializers.SerializerMethodField()

    class Meta:
        model = AISkill
        fields = [
            "id",
            "name",
            "folder_name",
            "content",
            "content_preview",
            "source_path",
            "source_type",
            "is_enabled",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_content_preview(self, obj) -> str:
        return (obj.content or "")[:200].strip()
