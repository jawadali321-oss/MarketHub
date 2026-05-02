from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        error_detail = response.data
        if isinstance(error_detail, dict):
            errors = {}
            for field, messages in error_detail.items():
                if isinstance(messages, list):
                    errors[field] = [str(m) for m in messages]
                else:
                    errors[field] = str(messages)
        elif isinstance(error_detail, list):
            errors = {"non_field_errors": [str(m) for m in error_detail]}
        else:
            errors = {"detail": str(error_detail)}

        response.data = {
            "success": False,
            "data": None,
            "error": errors,
            "pagination": None,
        }

    return response


class ServiceUnavailableError(Exception):
    pass


class BusinessRuleViolation(Exception):
    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(message)
