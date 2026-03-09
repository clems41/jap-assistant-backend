"""
Custom DRF exception handler — standardized error responses across all endpoints.

Every error response follows this shape:
{
    "message":   "Message lisible par l'utilisateur (fr)",   # always
    "code":      "machine_readable_code",                    # always
    "fields":    {"field_name": ["error msg"]},              # 400 field errors only
    "detail":    "ExcType: exc message",                     # only when DEBUG=True
    "traceback": "Traceback (most recent call last):\n ...", # only when DEBUG=True
}

500s from unhandled exceptions are caught here, logged, and returned in the same shape.
"""

import logging
import sys
import traceback as tb
from typing import Any

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)

_USER_MESSAGES: dict[int, str] = {
    400: "Les données envoyées sont invalides.",
    401: "Authentification requise.",
    403: "Vous n'avez pas la permission d'effectuer cette action.",
    404: "La ressource demandée est introuvable.",
    405: "Méthode HTTP non autorisée.",
    429: "Trop de requêtes. Veuillez réessayer plus tard.",
    500: "Une erreur interne est survenue. Veuillez réessayer plus tard.",
}


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    """
    DRF EXCEPTION_HANDLER — replaces the default handler globally.

    Normalizes all error responses to a consistent shape.
    Unhandled exceptions (would normally become 500s) are caught, logged, and
    returned in the same format so the frontend always deals with one contract.
    """
    # Capture traceback while we are still inside the except block
    exc_info = sys.exc_info()
    traceback_str: str | None = (
        "".join(tb.format_exception(*exc_info)) if exc_info[0] is not None else None
    )

    # Let DRF handle DRF-level exceptions first (auth, permissions, validation…)
    response = exception_handler(exc, context)

    request = context.get("request")
    method: str = request.method if request else "UNKNOWN"
    path: str = request.path if request else "unknown"

    if response is None:
        # Unhandled exception → would normally bubble up as a Django 500.
        # We catch it here so the response stays JSON and consistent.
        logger.exception("Unhandled exception on %s %s", method, path)
        return _build_response(
            exc=exc,
            code="internal_server_error",
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message=_USER_MESSAGES[500],
            fields=None,
            traceback_str=traceback_str,
        )

    if response.status_code >= 500:
        logger.error("Server error %s on %s %s: %s", response.status_code, method, path, exc)

    http_status: int = response.status_code
    message: str = _USER_MESSAGES.get(http_status, "Une erreur est survenue.")
    fields: dict[str, Any] | None = None

    if http_status == 400:
        data = response.data
        if isinstance(data, dict):
            non_field = data.get("non_field_errors")
            if non_field:
                message = str(non_field[0])
            elif "detail" in data:
                message = str(data["detail"])
            # Everything except meta-keys goes into `fields`
            excluded = {"non_field_errors", "detail"}
            field_errors = {k: v for k, v in data.items() if k not in excluded}
            fields = field_errors or None
        elif isinstance(data, list) and data:
            message = str(data[0])

    code: str = getattr(exc, "default_code", None) or "error"

    return _build_response(
        exc=exc,
        code=code,
        http_status=http_status,
        message=message,
        fields=fields,
        traceback_str=traceback_str,
    )


def _build_response(
    exc: Exception,
    code: str,
    http_status: int,
    message: str,
    fields: dict[str, Any] | None,
    traceback_str: str | None,
) -> Response:
    body: dict[str, Any] = {
        "message": message,
        "code": code,
    }
    if fields:
        body["fields"] = fields
    if settings.DEBUG:
        body["detail"] = f"{type(exc).__name__}: {exc}"
        if traceback_str:
            body["traceback"] = traceback_str

    return Response(body, status=http_status)
