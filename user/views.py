import logging
from jwt import InvalidTokenError
import jwt
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework import status
from django.contrib.auth import authenticate, logout
from django.contrib.auth.models import update_last_login
from rest_framework.authentication import get_authorization_header
from django.core.exceptions import ValidationError
from web3 import Web3

from agri_backend import settings
from agri_backend.enums import UserType
from .models import AgriUser
from dotenv import load_dotenv

load_dotenv()
import random
from django.core.cache import cache
from user.utils.access_token import (
    generate_tokens,
    blacklist_token,
    is_token_blacklisted,
    token_required,
    validate_refresh_token
)
from  Services.api_response import ApiResponse


from Services.response_messages import ErrorMessage
from Services import logger
from user.utils.send_mail import send_otp_email

@api_view(['POST'])
@parser_classes([JSONParser])
def register_user(request):
    try:
        data = request.data
        required_fields = ['username', 'email', 'name', 'phone_no', 'address', 'aadhaar_no', 'password']
        missing_fields = [field for field in required_fields if field not in data]

        if missing_fields:
            return ApiResponse(
                err={ 'missing_fields': missing_fields },
                msg=ErrorMessage.MISSING_FIELDS.value,
                status=status.HTTP_400_BAD_REQUEST
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
            return ApiResponse(
                err=errors,
                msg="Validation failed",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = AgriUser.objects.create_user(**data)
            return ApiResponse(
                data={'user': user.to_dict()},
                msg="User registered successfully",
                status=status.HTTP_201_CREATED
            )
        except ValidationError as e:
            return ApiResponse(
                err=str(e),
                msg="Validation failed",
                status=status.HTTP_400_BAD_REQUEST
            )

    except Exception as e:
        logger.error(f"Registration error: {str(e)}", exc_info=True)
        return ApiResponse(
            err=str(e),
            msg=ErrorMessage.SERVER_ERROR.value,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@parser_classes([JSONParser])
def login_user(request):
    try:
        data = request.data
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return ApiResponse(
                err={'credentials': 'Both username and password are required'},
                msg=ErrorMessage.INVALID_CREDENTIALS.value,
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(request, username=username, password=password)
        if user is None:
            return ApiResponse(
                err=ErrorMessage.INVALID_CREDENTIALS.value,
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_active:
            return ApiResponse(
                err=ErrorMessage.ACCOUNT_INACTIVE.value,
                status=status.HTTP_403_FORBIDDEN
            )

        if user.user_type not in [UserType.USER.value, UserType.ADMIN.value]:
            return ApiResponse(
                err=f"{ErrorMessage.LOGIN_NOT_ALLOWED.value}: {user.user_type}",
                status=status.HTTP_403_FORBIDDEN
            )

        tokens = generate_tokens(user)
        update_last_login(None, user)

        return ApiResponse(
            data={
                'user': user.to_dict(),
                'tokens': tokens
            },
            msg=f"{user.user_type.capitalize()} login successful",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Login error: {str(e)}", exc_info=True)
        return ApiResponse(
            err=str(e),
            msg=ErrorMessage.SERVER_ERROR.value,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@parser_classes([JSONParser])
def refresh_token_view(request):
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return ApiResponse(
                err="Refresh token is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        is_blacklisted, msg = is_token_blacklisted(refresh_token)
        if is_blacklisted:
            logger.warning("Refresh token is blacklisted")
            return ApiResponse(
                err=msg,
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            payload = jwt.decode(
                refresh_token,
                settings.SECRET_KEY,
                algorithms=[settings.SIMPLE_JWT['ALGORITHM']],
                options={
                    'verify_exp': True,
                    'require': ['exp', 'iat', 'user_id', 'token_type']
                }
            )

            if payload.get('token_type') != 'refresh':
                return ApiResponse(
                    err=ErrorMessage.INVALID_TOKEN.value,
                    status=status.HTTP_401_UNAUTHORIZED
                )

        except jwt.ExpiredSignatureError:
            return ApiResponse(
                err=ErrorMessage.TOKEN_EXPIRED.value,
                status=status.HTTP_401_UNAUTHORIZED
            )
        except jwt.InvalidTokenError as e:
            return ApiResponse(
                err=ErrorMessage.INVALID_TOKEN.value,
                status=status.HTTP_401_UNAUTHORIZED
            )

        user_id = payload.get('user_id')
        if not user_id:
            return ApiResponse(
                err="Invalid token payload. User ID is missing",
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = AgriUser.objects.filter(id=user_id).first()
        if not user:
            logger.warning("User not found for token refresh")
            return ApiResponse(
                err="User not found",
                status=status.HTTP_401_UNAUTHORIZED
            )

        tokens = generate_tokens(user)
        return ApiResponse(
            data={'tokens': tokens},
            msg="Token refreshed successfully",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Refresh token error: {str(e)}", exc_info=True)
        return ApiResponse(
            err=str(e),
            msg=ErrorMessage.SERVER_ERROR.value,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["POST"])
@parser_classes([JSONParser])
@token_required
def logout_user(request):
    try:
        auth_header = get_authorization_header(request).split()

        if not auth_header or len(auth_header) != 2:
            return ApiResponse(
                err=ErrorMessage.INVALID_AUTH_HEADER.value,
                status=status.HTTP_401_UNAUTHORIZED
            )

        token = auth_header[1].decode()

        # Check if token is already blacklisted
        is_blacklisted, blacklist_msg = is_token_blacklisted(token)
        if is_blacklisted:
            return ApiResponse(
                err=blacklist_msg,
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Blacklist the access token
        if not blacklist_token(token):
            logger.error("Failed to blacklist access token")
            return ApiResponse(
                err="Failed to blacklist token - cache service may be down",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
        return ApiResponse(
            msg="Logout successful. Token blacklisted.",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Logout error: {str(e)}", exc_info=True)
        return ApiResponse(
            err=str(e),
            msg=ErrorMessage.SERVER_ERROR.value,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@parser_classes([JSONParser])
@token_required
def get_user_profile(request):
    try:
        user = request.user
        return ApiResponse(
            data={'user': user.to_dict()},
            msg="User profile fetched successfully",
            status=status.HTTP_200_OK
        )
    except Exception as e:
        logger.error(f"Get profile error: {str(e)}", exc_info=True)
        return ApiResponse(
            err=str(e),
            msg=ErrorMessage.SERVER_ERROR.value,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['PUT'])
@parser_classes([JSONParser])
@token_required
def update_user_profile(request):
    """
    API endpoint to update the authenticated user's profile
    """
    try:
        user = request.user
        data = request.data
        allowed_fields = ['name', 'phone_no', 'address']

        update_fields = [field for field in allowed_fields if field in data]
        if not update_fields:
            return ApiResponse(
                err={'fields': f"Provide at least one of {', '.join(allowed_fields)}"},
                msg="No valid fields to update",
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update fields
        if 'name' in data:
            try:
                from .models import validate_name
                validate_name(data['name'])
                user.name = data['name']
            except ValidationError as e:
                return ApiResponse(
                    err={'name': str(e)},
                    msg="Invalid name",
                    status=status.HTTP_400_BAD_REQUEST
                )

        if 'phone_no' in data:
            try:
                if AgriUser.objects.filter(phone_no=data['phone_no']).exclude(id=user.id).exists():
                    return ApiResponse(
                        err=ErrorMessage.PHONE_EXISTS.value,
                        status=status.HTTP_400_BAD_REQUEST
                    )
                from .models import validate_mobile
                validate_mobile(data['phone_no'])
                user.phone_no = data['phone_no']
            except ValidationError as e:
                return ApiResponse(
                    err={'phone_no': str(e)},
                    msg="Invalid phone number",
                    status=status.HTTP_400_BAD_REQUEST
                )

        if 'address' in data:
            try:
                from .models import validate_address
                validate_address(data['address'])
                user.address = data['address']
            except ValidationError as e:
                return ApiResponse(
                    err={'address': str(e)},
                    msg="Invalid address",
                    status=status.HTTP_400_BAD_REQUEST
                )

        user.save()

        return ApiResponse(
            data={'user': user.to_dict()},
            msg="Profile updated successfully",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Update profile error: {str(e)}", exc_info=True)
        return ApiResponse(
            err=str(e),
            msg=ErrorMessage.SERVER_ERROR.value,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@parser_classes([JSONParser])
def request_password_reset(request):
    try:
        email = request.data.get('email')
        if not email:
            return ApiResponse(
                err="Email is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = AgriUser.objects.get(email=email)
        except AgriUser.DoesNotExist:
            return ApiResponse(
                err="No user found with this email",
                status=status.HTTP_400_BAD_REQUEST
            )

        otp = str(random.randint(100000, 999999))
        cache.set(f"otp_{email}", otp, timeout=300)  # OTP valid for 5 minutes

        send_otp_email(email, otp)

        return ApiResponse(
            msg="OTP sent to email",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Send OTP error: {str(e)}", exc_info=True)
        return ApiResponse(
            err=str(e),
            msg=ErrorMessage.SERVER_ERROR.value,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@parser_classes([JSONParser])
def reset_password_with_otp(request):
    try:
        email = request.data.get('email')
        otp = request.data.get('otp')
        new_password = request.data.get('new_password')

        if not all([email, otp, new_password]):
            return ApiResponse(
                err="Email, OTP and new password are required",
                status=status.HTTP_400_BAD_REQUEST
            )

        cached_otp = cache.get(f"otp_{email}")
        if cached_otp != otp:
            return ApiResponse(
                err="Invalid or expired OTP",
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = AgriUser.objects.get(email=email)
        except AgriUser.DoesNotExist:
            return ApiResponse(
                err="User not found",
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(new_password)
        user.save()
        cache.delete(f"otp_{email}")

        return ApiResponse(
            msg="Password reset successfully",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Reset password error: {str(e)}", exc_info=True)
        return ApiResponse(
            err=str(e),
            msg=ErrorMessage.SERVER_ERROR.value,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )