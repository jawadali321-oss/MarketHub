from rest_framework.response import Response
from rest_framework import status


def success_response(data=None, message=None, status_code=status.HTTP_200_OK, pagination=None):
    payload = {
        "success": True,
        "data": data,
        "error": None,
        "pagination": pagination,
    }
    if message:
        payload["message"] = message
    return Response(payload, status=status_code)


def error_response(errors, status_code=status.HTTP_400_BAD_REQUEST):
    if isinstance(errors, str):
        errors = {"detail": errors}
    return Response(
        {
            "success": False,
            "data": None,
            "error": errors,
            "pagination": None,
        },
        status=status_code,
    )


def created_response(data=None, message=None):
    return success_response(data=data, message=message, status_code=status.HTTP_201_CREATED)


def no_content_response():
    return Response(status=status.HTTP_204_NO_CONTENT)
