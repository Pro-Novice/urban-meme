from django.http import JsonResponse
from rest_framework import status

class ApiResponse(JsonResponse):
    """
    Standardized API response format
    """
    def __init__(self, data=None, message=None, errors=None, status_code=status.HTTP_200_OK, **kwargs):
        response_data = {
           'status': 'error' if errors else 'success',
            'message': str(errors) if errors else (message or 'Success'),
            'data': data if data is not None else {}
        }
        kwargs.pop('status', None)  # Remove status if it was passed in kwargs
        super().__init__(response_data, status=status_code, **kwargs)

class SuccessResponse(ApiResponse):
    """
    Predefined success response
    """
    def __init__(self, data=None, message="Operation successful", status_code=status.HTTP_200_OK, **kwargs):
        super().__init__(data=data, message=message, status_code=status_code, **kwargs)

class ErrorResponse(ApiResponse):
    """
    Predefined error response
    """
    def __init__(self, message="An error occurred", status_code=status.HTTP_400_BAD_REQUEST, errors=None, **kwargs):
        super().__init__(message=message, errors=errors, status_code=status_code, **kwargs)

class ValidationErrorResponse(ErrorResponse):
    """
    Predefined validation error response
    """
    def __init__(self, message="Validation error", errors=None, **kwargs):
        if errors is None:
            errors = {}
        super().__init__(
            message=message,
            errors=errors,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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