import hashlib
import uuid
import logging
from datetime import datetime, timedelta
import time
from datetime import datetime as dt
import jwt
from django.conf import settings
from jwt import InvalidTokenError
from rest_framework import status
from rest_framework.authentication import get_authorization_header
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken
from  Services.api_response import ApiResponse, ErrorResponse, ForbiddenResponse, UnauthorizedResponse
from  Services.response_messages import ErrorMessage
from ..models import AgriUser
from django.http import JsonResponse

# logger
logger = logging.getLogger(__name__)

def generate_tokens(user):
    """
    Generate access and refresh tokens for a user
    """
    try:
        refresh = RefreshToken.for_user(user)
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }
    except Exception as e:
        logger.exception("Unable to generate tokens")
        raise Exception("Token generation failed")

#validate access Token
def validate_access_token(token):
    """
    Validate JWT access token with better error handling
    """
    try:
        # Decode the token
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.SIMPLE_JWT['ALGORITHM']],
            options={
                'verify_exp': True,  # Verify expiration
                'require': ['exp', 'iat', 'user_id', 'token_type']
            }
        )

        # Additional validations
        if payload.get('token_type') != 'access':
            raise InvalidTokenError("Invalid token type")

        if is_token_blacklisted(token):
            raise InvalidTokenError(ErrorMessage.TOKEN_BLACKLISTED.value)

        return payload

    except jwt.ExpiredSignatureError:
        raise InvalidTokenError(ErrorMessage.TOKEN_EXPIRED.value)
    except jwt.InvalidTokenError as e:
        raise InvalidTokenError(ErrorMessage.INVALID_TOKEN.value)
    except Exception as e:
        logger.error(f"Token validation failed: {str(e)}")
        raise InvalidTokenError(ErrorMessage.INVALID_TOKEN.value)

#validate token
def validate_refresh_token(token):
    """
    Validate JWT refresh token
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
        )

        if payload.get('token_type') != 'refresh':
            raise InvalidTokenError("Invalid token type")

        if is_token_blacklisted(token):
            raise InvalidTokenError("Token is blacklisted")

        return payload

    except jwt.ExpiredSignatureError:
        raise InvalidTokenError("Token has expired")
    except jwt.InvalidTokenError:
        raise InvalidTokenError("Invalid token")
        raise InvalidTokenError("Invalid token")

#check for if token is blacklisted

def is_token_blacklisted(token):
    """
    Check if token is blacklisted in cache with proper error handling
    Returns tuple: (is_blacklisted: bool, error_message: str or None)
    """
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        blacklisted = cache.get(token_hash)
        if blacklisted is None:
            return False, None
        return True, ErrorMessage.TOKEN_BLACKLISTED.value
    except Exception as e:
        logger.error(f"Cache connection error while checking token blacklist: {str(e)}")

        return False, None


# token required
def token_required(func):
    """
    Decorator to validate access token for protected views
    """

    def wrapper(request, *args, **kwargs):
        try:
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return ApiResponse(
                    err="Authorization header with Bearer token is required",
                    status=status.HTTP_401_UNAUTHORIZED
                )

            token = auth_header.split()[1]
            payload = validate_access_token(token)

            try:
                user = AgriUser.objects.get(id=payload['user_id'])
                request.user = user
            except AgriUser.DoesNotExist:
                return ApiResponse(
                    err="User not found",
                    status=status.HTTP_401_UNAUTHORIZED
                )

            return func(request, *args, **kwargs)

        except InvalidTokenError as e:
            return ApiResponse(
                err=str(e),
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            logger.exception("Token validation error")
            return ApiResponse(
                err="Authentication failed",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return wrapper


# admin required decorator
def admin_required(func):
    """
    Decorator to restrict access to admin users only
    """

    def wrapper(request, *args, **kwargs):
        if not hasattr(request, 'user'):
            return ApiResponse(
                err="Authentication required",
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not request.user.is_admin:
            return ApiResponse(
                err="Admin access required",
                status=status.HTTP_403_FORBIDDEN
            )

        return func(request, *args, **kwargs)

    return wrapper


def is_token_blacklisted(token):
    """
    Check if token is blacklisted in cache with proper error handling
    Returns tuple: (is_blacklisted: bool, error_message: str or None)
    """
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        blacklisted = cache.get(token_hash)
        if blacklisted is None:
            return False, None
        return True, ErrorMessage.TOKEN_BLACKLISTED.value
    except Exception as e:
        logger.error(f"Cache connection error while checking token blacklist: {str(e)}")

        return False, None


def blacklist_token(token, expiry_seconds=None):
    """
    Add token to blacklist cache with robust error handling
    Returns bool: True if successfully blacklisted, False otherwise
    """
    try:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        if not expiry_seconds:
            expiry_seconds = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
        cache.set(token_hash, True, timeout=expiry_seconds)
        return True
    except Exception as e:
        logger.error(f"Failed to blacklist token: {str(e)}")
        return False



# roles is a list of roles that have permission to run the given function
def authenticate(roles=None, user_account_needed=True, user_type_required=None):
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            logger.debug("Checking authentication")
            try:
                jwt_payload = fetch_data_and_validate_access_token(request)#call rajasthan api for fetching and validtaing access token and get details.
            except InvalidTokenError as e:
                logger.exception("Invalid JWT")
                return ApiResponse(err="User not logged in",
                                   status=status.HTTP_401_UNAUTHORIZED)
            request.user_id = jwt_payload.get('id')
            request.role = jwt_payload.get('role')  # currently assuming just one role per user
            request.user_name = jwt_payload.get('username')
            request.user_type = jwt_payload.get("user_type")
            # if user_account_needed:
            #     user = User.objects(userId=request.user_id).first()
            #     if not user:
            #         return ApiResponse(err=" unknown user", status=status.HTTP_401_UNAUTHORIZED)
            #     if not user.has_account:
            #         return ApiResponse(err=" user account not created", status=status.HTTP_404_NOT_FOUND)
            #     else:
            #         request.address = user.account
            # if user_type_required:
            #     if not user_type_required.upper() == request.user_type.upper():
            #         return ApiResponse(err="PERMISSION DENIED", status=status.HTTP_401_UNAUTHORIZED)
            if roles is None:
                logger.debug("no permissions required")
                return func(request)
            # if roles is required
            if not request.role:
                # case of first time login
                logger.debug("User has no roles")
                return ApiResponse(err="PERMISSION DENIED. Please logout and login again",
                                   status=status.HTTP_401_UNAUTHORIZED)
            if not has_common_element(request.role, roles):
                logger.debug("PERMISSION DENIED: user role is '%s', while the permissions needed is %s ", request.role,
                             str(roles))

                return ApiResponse(err="User does not have required permissions",
                                   status=status.HTTP_401_UNAUTHORIZED)
            return func(request)

        return wrapper

    return decorator



def api_key_required(func):
    def wrapper(request, *args, **kwargs):
        logger.debug("Checking api key requirements")
        api_key = request.META.get('HTTP_API_KEY')
        if not api_key:
            return ApiResponse(err="Api key not found", status=status.HTTP_403_FORBIDDEN)
        # if api key exists, check validity
        hash_key = hashlib.sha256(api_key.encode()).hexdigest()

        client = ApiKeyClient.objects(hash_key=hash_key).first()
        if not client:
            return ApiResponse(err="Unauthorized", status=status.HTTP_401_UNAUTHORIZED)
        else:
            logger.debug("client %s authorized for request %s", client, request)
            return func(request)

    return wrapper


def has_common_element(list1, list2):
    if isinstance(list1, (int, float, str)):  # Convert a single element to a list of length 1
        list1 = [list1]
    if isinstance(list2, (int, float, str)):  # Convert a single element to a list of length 1
        list2 = [list2]
    set1 = set([x.upper() for x in list1])
    set2 = set([x.upper() for x in list2])
    return bool(set1 & set2)