from rest_framework import serializers

from .models import Document, Project


class ProjectSerializer(serializers.ModelSerializer):
    document_count = serializers.SerializerMethodField()
    testcase_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = "__all__"

    def get_document_count(self, obj):
        return obj.documents.count()

    def get_testcase_count(self, obj):
        return obj.test_cases.count()


class ProjectBatchDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class DocumentBatchDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class DocumentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    file_url = serializers.SerializerMethodField()
    preview_mode = serializers.SerializerMethodField()
    doc_type_display = serializers.CharField(source="get_doc_type_display", read_only=True)

    class Meta:
        model = Document
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "version",
            "doc_type",
            "doc_type_display",
            "file",
            "file_url",
            "original_name",
            "file_ext",
            "file_size",
            "preview_mode",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["file_ext", "file_size", "original_name"]

    def get_file_url(self, obj):
        return obj.file.url if obj.file else ""

    def get_preview_mode(self, obj):
        return obj.preview_mode
