import django_filters

from .models import Document, Project


class ProjectFilter(django_filters.FilterSet):
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    owner = django_filters.CharFilter(field_name="owner", lookup_expr="icontains")

    class Meta:
        model = Project
        fields = ["owner", "created_after", "created_before"]


class DocumentFilter(django_filters.FilterSet):
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    file_ext = django_filters.CharFilter(field_name="file_ext", lookup_expr="iexact")

    class Meta:
        model = Document
        fields = ["project", "doc_type", "file_ext", "created_after", "created_before"]
