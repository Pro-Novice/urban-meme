import logging
from jwt import InvalidTokenError
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework import status
from django.contrib.auth import authenticate, logout
from django.contrib.auth.models import update_last_login
from rest_framework.authentication import get_authorization_header
from django.core.exceptions import ValidationError
from .models import AgriUser
from .enums import UserType
from .services.access_token import (
    generate_tokens,
    blacklist_token,
    is_token_blacklisted,
    token_required,
    validate_refresh_token
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
                message=ErrorMessage.MISSING_FIELDS.value,
                errors={'missing_fields': missing_fields}
            )

        errors = {}
        if AgriUser.objects.filter(username=data['username']).exists():
            errors['username'] = ErrorMessage.USERNAME_EXISTS.value
        if AgriUser.objects.filter(email=data['email']).exists():
            errors['email'] = ErrorMessage.EMAIL_EXISTS.value
        if AgriUser.objects.filter(phone_no=data['phone_no']).exists():
            errors['phone_no'] = ErrorMessage.PHONE_EXISTS.value
        if AgriUser.objects.filter(aadhaar_no=data['aadhaar_no']).exists():
            errors['aadhaar_no'] = ErrorMessage.AADHAAR_EXISTS.value
            
        if errors:
            return ValidationErrorResponse(
                message="Validation failed",
                errors=errors
            )

        try:
            user = AgriUser.objects.create_user(**data)
            return SuccessResponse(
                data={'user': user.to_dict()},
                message="User registered successfully",
                status_code=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return ValidationErrorResponse(
                message="Validation failed",
                errors=str(e)
            )

    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
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

        if not username or not password:
            return ValidationErrorResponse(
                message=ErrorMessage.INVALID_CREDENTIALS.value,
                errors={'credentials': 'Both username and password are required'}
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return UnauthorizedResponse(message=ErrorMessage.INVALID_CREDENTIALS.value)

        if not user.is_active:
            return ForbiddenResponse(message=ErrorMessage.ACCOUNT_INACTIVE.value)

        if user.user_type not in [UserType.USER.value, UserType.ADMIN.value]:
            return ForbiddenResponse(
                message=f"{ErrorMessage.LOGIN_NOT_ALLOWED.value}: {user.user_type}"
            )

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
        auth_header = get_authorization_header(request).split()
        
        if not auth_header or len(auth_header) != 2:
            return UnauthorizedResponse(message=ErrorMessage.INVALID_AUTH_HEADER.value)

        token = auth_header[1].decode()
        
        # Check if token is already blacklisted
        is_blacklisted, blacklist_msg = is_token_blacklisted(token)
        if is_blacklisted:
            return UnauthorizedResponse(message=blacklist_msg)

        # Blacklist the access token
        if not blacklist_token(token):
            logger.error("Failed to blacklist access token")
            return ErrorResponse(
                message="Failed to blacklist token - cache service may be down",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Blacklist refresh token if provided
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            try:
                payload = validate_refresh_token(refresh_token)
                if payload.get('user_id') != request.user.id:
                    logger.warning("Refresh token user mismatch during logout")
                if not blacklist_token(refresh_token):
                    logger.error("Failed to blacklist refresh token")
            except InvalidTokenError as e:
                logger.warning(f"Invalid refresh token during logout: {str(e)}")

        logout(request)
        return SuccessResponse(message="Logout successful. Tokens blacklisted.")

    except Exception as e:
        logger.error(f"Logout error: {str(e)}", exc_info=True)
        return ErrorResponse(
            message=ErrorMessage.SERVER_ERROR.value,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )