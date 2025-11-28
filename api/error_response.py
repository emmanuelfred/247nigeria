from rest_framework.response import Response
from rest_framework import status

def error_response(message, code=status.HTTP_400_BAD_REQUEST, details=None):
    return Response(
        {
            "success": False,
            "message": message,
            "details": details,
        },
        status=code
    )
