import logging
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework import status
from django.contrib.auth import authenticate, logout
from django.contrib.auth.models import update_last_login

from django.core.exceptions import ValidationError
from .models import AgriUser
from .enums import UserType
from .services.access_token import (
    generate_tokens,
    blacklist_token,
    is_token_blacklisted,
    token_required
)
from .services.api_response import (
    SuccessResponse,
    ErrorResponse,
    ValidationErrorResponse,
    UnauthorizedResponse,
    ForbiddenResponse,
    ApiResponse
)
from .services.error_messages import ErrorMessage

logger = logging.getLogger(__name__)

@api_view(['POST'])
@parser_classes([JSONParser])
def register_user(request):
    try:
        data = request.data
        required_fields = ['username', 'email', 'name', 'phone_no', 'address', 'aadhaar_no', 'password']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return ValidationErrorResponse(
                message="Missing required fields",
                errors={'missing_fields': missing_fields}
            )

        # Check for existing user data
        if AgriUser.objects.filter(username=data['username']).exists():
            return ErrorResponse(
                message=ErrorMessage.USERNAME_EXISTS.value,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if AgriUser.objects.filter(email=data['email']).exists():
            return ErrorResponse(
                message=ErrorMessage.EMAIL_EXISTS.value,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if AgriUser.objects.filter(phone_no=data['phone_no']).exists():
            return ErrorResponse(
                message=ErrorMessage.PHONE_EXISTS.value,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if AgriUser.objects.filter(aadhaar_no=data['aadhaar_no']).exists():
            return ErrorResponse(
                message=ErrorMessage.AADHAAR_EXISTS.value,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        user = AgriUser.objects.create_user(**data)

        return SuccessResponse(
            data={'user': user.to_dict()},
            message="User registered successfully",
            status_code=status.HTTP_201_CREATED
        )

    except ValidationError as e:
       
        return ApiResponse(err=e)

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return ErrorResponse(
            message=ErrorMessage.SERVER_ERROR.value,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@parser_classes([JSONParser])
def login_user(request):
    try:
        data = request.data
        username = data.get('username')
        password = data.get('password')

        # Validate input
        if not username or not password:
            return ErrorResponse(
                message=ErrorMessage.INVALID_CREDENTIALS.value,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        # Authenticate user
        user = authenticate(request, username=username, password=password)
        if user is None:
            return UnauthorizedResponse(message=ErrorMessage.INVALID_CREDENTIALS.value)

        # Check user status
        if not user.is_active:
            return ForbiddenResponse(message=ErrorMessage.ACCOUNT_INACTIVE.value)

        # Check user type
        if user.user_type not in [UserType.USER.value, UserType.ADMIN.value]:
            return ForbiddenResponse(
                message=f"{ErrorMessage.LOGIN_NOT_ALLOWED.value}: {user.user_type}"
            )

        # Generate tokens
        tokens = generate_tokens(user)
        update_last_login(None, user)

        return SuccessResponse(
            data={
                'user': user.to_dict(),
                'tokens': tokens
            },
            message=f"{user.user_type.capitalize()} login successful"
        )

    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message=ErrorMessage.SERVER_ERROR.value,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["POST"])
@parser_classes([JSONParser])
@token_required
def logout_user(request):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return ErrorResponse(
                message=ErrorMessage.AUTH_HEADER_MISSING.value,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = auth_header.split(" ")[1]
        except IndexError:
            return ErrorResponse(
                message=ErrorMessage.INVALID_AUTH_HEADER.value,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        if is_token_blacklisted(token):
            return ErrorResponse(
                message=ErrorMessage.TOKEN_BLACKLISTED.value,
                status_code=status.HTTP_400_BAD_REQUEST
            )

        blacklist_token(token)
        logout(request)

        return SuccessResponse(message="Logout successful. Token blacklisted.")

    except Exception as e:
        logger.error(f"Logout error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message=ErrorMessage.SERVER_ERROR.value,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )