import hashlib
import uuid
import logging
from datetime import datetime, timedelta
import time
import jwt
from django.conf import settings
from jwt import InvalidTokenError
from rest_framework import status
from rest_framework.authentication import get_authorization_header
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken

from .api_response import ApiResponse
from .error_messages import ErrorMessage
from ..models import AgriUser
from ..enums import UserType

#logger
logger = logging.getLogger(__name__)

#generate Token
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
    
#check for if token is blacklisted
def is_token_blacklisted(token):
    """
    Check if token is blacklisted in cache
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return cache.get(token_hash) is not None

def blacklist_token(token, expiry_seconds=None):
    """
    Add token to blacklist cache
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    if not expiry_seconds:
        expiry_seconds = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds()
    cache.set(token_hash, {'status': 'blacklisted', 'timestamp': time.time()}, timeout=expiry_seconds)


#token required
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

#admin required decorator
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