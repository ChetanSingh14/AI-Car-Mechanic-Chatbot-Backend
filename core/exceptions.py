import logging
from django.conf import settings
from django.http import JsonResponse
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

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
        message = "An error occurred while processing your request."
        
        if isinstance(detail, dict):
            if 'detail' in detail:
                message = str(detail['detail'])
            elif 'message' in detail:
                message = str(detail['message'])
            else:
                first_key = next(iter(detail))
                first_val = detail[first_key]
                if isinstance(first_val, list) and len(first_val) > 0:
                    message = f"{first_key}: {first_val[0]}"
                else:
                    message = "Validation or data payload error."
        elif isinstance(detail, list):
            message = "; ".join([str(item) for item in detail])

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
