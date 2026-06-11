import django_filters
from django.db.models import Q

from .models import TestCase


class TestCaseFilter(django_filters.FilterSet):
    passed_status = django_filters.CharFilter(method="filter_passed_status")
    created_after = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_before = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    executor = django_filters.CharFilter(field_name="executor", lookup_expr="icontains")
    case_no = django_filters.CharFilter(field_name="case_no", lookup_expr="icontains")
    module = django_filters.CharFilter(field_name="module", lookup_expr="icontains")
    field_search = django_filters.CharFilter(method="filter_field_search")

    class Meta:
        model = TestCase
        fields = [
            "project",
            "priority",
            "executor",
            "passed_status",
            "created_after",
            "created_before",
            "case_no",
            "module",
            "field_search",
        ]

    def filter_passed_status(self, queryset, name, value):
        if value == "passed":
            return queryset.filter(passed=True)
        if value == "failed":
            return queryset.filter(passed=False)
        if value == "pending":
            return queryset.filter(passed__isnull=True)
        return queryset

    def filter_field_search(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value)
            | Q(case_no__icontains=value)
            | Q(module__icontains=value)
            | Q(steps__icontains=value)
            | Q(expected__icontains=value)
            | Q(precondition__icontains=value)
        )
