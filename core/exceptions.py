from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

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
            else:
                message = "Validation or data payload error."
        elif isinstance(detail, list):
            message = "; ".join([str(item) for item in detail])

        formatted_data = {
            "success": False,
            "error": {
                "code": error_code,
                "message": message,
                "details": detail
            }
        }
        response.data = formatted_data
    else:
        logger.error(f"Unhandled Exception: {str(exc)}", exc_info=True)
        response = Response(
            {
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "details": str(exc)
                }
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    return response
