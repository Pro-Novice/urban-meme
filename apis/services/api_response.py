from django.http import JsonResponse
from rest_framework import status

class ApiResponse(JsonResponse):
    """
    Standardized API response format
    """
    def __init__(self, data=None, message=None, err=None, status_code=status.HTTP_200_OK, **kwargs):
        response_data = {
            'status': 'error' if err else 'success',
            'message': str(err) if err else (message or 'Success'),
            'data': data if data is not None else {}
        }
        kwargs.pop('status', None)

        super().__init__(response_data, status=status_code, **kwargs)

class SuccessResponse(ApiResponse):
    """
    Predefined success response
    """
    def __init__(self, data=None, message="Operation successful", **kwargs):
        super().__init__(data=data, message=message, **kwargs)

class ErrorResponse(ApiResponse):
    """
    Predefined error response
    """
    def __init__(self, message="An error occurred", status_code=status.HTTP_400_BAD_REQUEST, data=None, **kwargs):
        super().__init__(data=data, err=message, status_code=status_code, **kwargs)

class ValidationErrorResponse(ErrorResponse):
    """
    Predefined validation error response
    """
    def __init__(self, message="Validation error", data=None, **kwargs):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            data=data,
            **kwargs
        )

class UnauthorizedResponse(ErrorResponse):
    """
    Predefined unauthorized error response
    """
    def __init__(self, message="Unauthorized", **kwargs):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            **kwargs
        )

class ForbiddenResponse(ErrorResponse):
    """
    Predefined forbidden error response
    """
    def __init__(self, message="Forbidden", **kwargs):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            **kwargs
        )