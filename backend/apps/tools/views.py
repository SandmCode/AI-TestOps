import base64
import json
import re

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["POST"])
def parse_curl(request):
    curl_expr = request.data.get("curl", "")
    if not curl_expr.strip():
        return Response({"error": "curl 表达式不能为空"}, status=status.HTTP_400_BAD_REQUEST)

    method = "GET"
    url = ""
    headers = {}
    body = {}

    upper = curl_expr.upper()
    for m in ("POST", "PUT", "DELETE", "PATCH"):
        if f"-X {m}" in upper or f"--request {m}" in upper:
            method = m
            break

    url_match = re.search(r"curl\s+(?:[^'\"]*\s+)?['\"]?(https?://[^\s'\"\\]+)", curl_expr, re.I)
    if url_match:
        url = url_match.group(1).strip("'\"")
    else:
        url_match = re.search(r"['\"]?(https?://[^\s'\"\\]+)", curl_expr)
        if url_match:
            url = url_match.group(1).strip("'\"")

    for hm in re.finditer(r"-H\s+['\"]([^'\"]+)['\"]", curl_expr):
        part = hm.group(1)
        if ":" in part:
            k, v = part.split(":", 1)
            headers[k.strip()] = v.strip()

    data_match = re.search(r"-d\s+['\"](.+?)['\"]", curl_expr, re.S)
    if data_match:
        raw = data_match.group(1)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {"raw": raw}

    return Response({"method": method, "url": url, "headers": headers, "body": body})


@api_view(["POST"])
def api_test(request):
    import requests as http_requests

    method = request.data.get("method", "GET").upper()
    url = request.data.get("url", "")
    headers = request.data.get("headers", {})
    params = request.data.get("params", {})
    body = request.data.get("body", {})
    if not url:
        return Response({"error": "URL 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        resp = http_requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params if method == "GET" else None,
            json=body if method in ("POST", "PUT", "PATCH") else None,
            timeout=15,
        )
        try:
            resp_body = resp.json()
        except Exception:
            resp_body = resp.text[:5000]
        return Response(
            {
                "status_code": resp.status_code,
                "elapsed_ms": int(resp.elapsed.total_seconds() * 1000),
                "headers": dict(resp.headers),
                "body": resp_body,
            }
        )
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


from .mock_data_service import generate_mock_data, get_meta


@api_view(["GET", "POST"])
def mock_data(request):
    if request.method == "GET":
        return Response(get_meta())

    schema = request.data.get("schema", {})
    if not isinstance(schema, dict) or not schema:
        return Response({"error": "schema 不能为空"}, status=status.HTTP_400_BAD_REQUEST)
    count = min(max(int(request.data.get("count", 5)), 1), 500)
    seed_raw = request.data.get("seed")
    seed = int(seed_raw) if seed_raw not in (None, "") else None
    result = generate_mock_data(schema, count, seed=seed)
    return Response({"data": result, "count": len(result), "seed": seed})


@api_view(["POST"])
def json_tool(request):
    action = request.data.get("action", "format")
    text = request.data.get("text", "")
    try:
        if action == "format":
            obj = json.loads(text)
            return Response({"result": json.dumps(obj, ensure_ascii=False, indent=2)})
        if action == "minify":
            obj = json.loads(text)
            return Response({"result": json.dumps(obj, ensure_ascii=False, separators=(",", ":"))})
        if action == "validate":
            json.loads(text)
            return Response({"valid": True, "result": "JSON 格式正确"})
        if action == "to_yaml":
            obj = json.loads(text)
            lines = []
            _json_to_yaml(obj, lines)
            return Response({"result": "\n".join(lines)})
        return Response({"error": "未知操作"}, status=status.HTTP_400_BAD_REQUEST)
    except json.JSONDecodeError as exc:
        return Response({"valid": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _json_to_yaml(obj, lines, indent=0):
    prefix = "  " * indent
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                lines.append(f"{prefix}{k}:")
                _json_to_yaml(v, lines, indent + 1)
            else:
                lines.append(f"{prefix}{k}: {v}")
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                _json_to_yaml(item, lines, indent + 1)
            else:
                lines.append(f"{prefix}- {item}")


@api_view(["GET", "POST"])
def encode_convert(request):
    from .encode_service import encode_convert as do_convert, get_encode_meta

    if request.method == "GET":
        return Response(get_encode_meta())

    action = request.data.get("action", "base64_encode")
    text = request.data.get("text", "")
    extra = {
        "salt": request.data.get("salt", ""),
        "secret": request.data.get("secret", ""),
    }
    try:
        result = do_convert(str(action), str(text), extra)
        return Response({"result": result, "action": action})
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
def stress_test_script(request):
    api_url = request.data.get("url", "http://localhost:8000/api/")
    users = int(request.data.get("users", 10))
    spawn_rate = int(request.data.get("spawn_rate", 2))
    duration = request.data.get("duration", "30s")
    script = f'''from locust import HttpUser, task, between

class QuickTestUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def test_api(self):
        self.client.get("{api_url}")
'''
    return Response(
        {
            "script": script,
            "config": {
                "users": users,
                "spawn_rate": spawn_rate,
                "duration": duration,
                "command": f"locust -f locustfile.py --users {users} --spawn-rate {spawn_rate} --run-time {duration}",
            },
        }
    )
