import logging
from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

def _clean_error_message(data):
    if isinstance(data, dict):
        if 'detail' in data and not isinstance(data['detail'], (dict, list)):
            return str(data['detail'])
        items = []
        for key, val in data.items():
            clean_val = _clean_error_message(val)
            if key in ('non_field_errors', 'detail', 'error'):
                items.append(clean_val)
            else:
                items.append(f"{key}: {clean_val}")
        return "; ".join(items) if items else "Validation error."
    elif isinstance(data, (list, tuple)):
        clean_items = [_clean_error_message(item) for item in data]
        return "; ".join(clean_items) if clean_items else "Validation error."
    elif hasattr(data, 'string'):
        return str(data.string)
    return str(data)


def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler to ensure standard JSON error response format.
    Format:
    {
        "success": False,
        "error": {
            "code": "ERROR_CODE",
            "message": "Human readable summary",
            "details": {...}
        }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        error_code = exc.__class__.__name__.upper()
        if hasattr(exc, 'default_code'):
            error_code = str(exc.default_code).upper()

        detail = response.data
        message = _clean_error_message(detail)

        formatted_data = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "details": detail if settings.DEBUG else None
            }
        }
        response.data = formatted_data
    else:
        logger.error(f"Unhandled Server Exception: {str(exc)}", exc_info=True)
        formatted_data = {
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred."
            }
        }
        if settings.DEBUG:
            formatted_data["error"]["details"] = str(exc)

        response = Response(
            formatted_data,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response


def custom_404_handler(request, exception=None):
    """
    Global Django 404 JSON Handler for unmatched routes.
    """
    return JsonResponse(
        {
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested endpoint or resource was not found."
            }
        },
        status=404
    )


def custom_500_handler(request):
    """
    Global Django 500 JSON Handler.
    """
    return JsonResponse(
        {
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred."
            }
        },
        status=500
    )
