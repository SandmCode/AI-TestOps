from django.urls import path

from . import views

urlpatterns = [
    path("tools/parse-curl/", views.parse_curl),
    path("tools/api-test/", views.api_test),
    path("tools/mock-data/", views.mock_data),
    path("tools/json/", views.json_tool),
    path("tools/encode/", views.encode_convert),
    path("tools/stress-script/", views.stress_test_script),
]
