from rest_framework import status
from rest_framework.response import Response

from .ai_service import AIServiceError


def ai_error_response(exc: AIServiceError) -> Response:
    return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
