import hashlib
import uuid

import jwt
from django.conf import settings
from jwt import InvalidTokenError
from rest_framework import status
# signup is relatively unsecure process. it only means to take the aadhaar ekyc details and store it in db. anothing else is done and user is logged out or asked to login

# login is more frequent and relatively secure process.
from rest_framework.authentication import get_authorization_header
import datetime

import string
from django.core.cache import cache

from rest_framework_jwt.utils import jwt_encode_handler, jwt_decode_handler
import logging
from .api_response import ApiResponse
from datetime import datetime as dt
logger = logging.getLogger(__name__)

def gen_access_token(user_id, user_name, user_role, user_type="USER"):
    logger.debug("Inside generate jwt")
    try:
        payload = {
            'type': "ACCESS TOKEN",
            'id': user_id,
            'username': user_name,
            'role': user_role,  # assuming you have a role field in your user model
            'user_type': user_type,
            'exp': dt.utcnow() + datetime.timedelta(seconds=settings.JWT_ACCESS_EXPIRATION_DELTA),
            'iat': dt.utcnow(),
            'token_id': str(uuid.uuid4())
        }
        logger.debug(str(payload))

        access_token = jwt_encode_handler(payload)
        return access_token
    except Exception as e:
        logger.exception("unable to generate access token")
        raise e


# This function should generate refresh the token
def gen_refresh_token(user_id, user_name, user_role, user_type="USER"):
    logger.debug("Inside generate jwt")
    try:
        payload = {
            'type': "REFRESH TOKEN",
            'id': user_id,
            'username': user_name,
            'role': user_role,  # assuming you have a role field in your user model
            'user_type': user_type,
            'exp': dt.utcnow() + datetime.timedelta(seconds=settings.JWT_REFRESH_EXPIRATION_DELTA),
            'iat': dt.utcnow(),
            'token_id': str(uuid.uuid4())
            # 'token_id': str(''.join(random.choices(string.ascii_letters
            #                                        + string.digits, k=32)))
        }
        logger.debug(str(payload))

        refresh_token = jwt_encode_handler(payload)
        return refresh_token
    except Exception as e:
        logger.exception("unable to generate refresh token")
        raise e


def check_refresh_token(token):
    logger.debug("START: CHECK REFRESH TOKEN")
    logger.debug(token)
    try:
        payload = jwt_decode_handler(token)
    except jwt.ExpiredSignature:
        logger.exception("Token expired")
        raise Exception("Token expired")
    except jwt.DecodeError:
        logger.exception("Error in decoding token")
        raise Exception("Error in decoding token")
    except jwt.InvalidTokenError:
        logger.exception("Invalid token")
        raise Exception("Invalid token")
    if payload.get('type') != "REFRESH TOKEN":
        logger.error('JWT is not REFRESH TOKEN')
        raise InvalidTokenError("JWT is not REFRESH TOKEN")
    key = payload.get("token_id")
    logger.debug("token id is %s", key)
    cached_token = cache.get(key)
    if cached_token:
        logger.debug("refresh token with token id %s is already used", key)
        raise Exception(" Used Token")
    value = "expired"
    if is_token_blacklisted(token):
        logger.debug("user already logged out")
        raise Exception("User logged out")
    logger.debug("setting refresh token with id %s expired ", key)
    cache.set(key, value, settings.JWT_REFRESH_EXPIRATION_DELTA)
    return payload


# Define a function to check if a token is blacklisted
def is_token_blacklisted(token):
    # Generate a SHA-256 hash of the token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    # Check if the token hash exists in Redis
    token_data = cache.get(token_hash)
    if token_data:
        return True
    return False


# Define a function to store a blacklisted token's hash in Redis
def blacklist_token(token):
    # Generate a SHA-256 hash of the token
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    # Set the token hash in Redis with a 7 day expiration
    cache.set(token_hash, 'blacklisted', settings.JWT_BLACKLIST_DELTA)


# roles is a list of roles that have permission to run the given function
def get_login_info(func):
        def wrapper(request, *args, **kwargs):
            logger.debug("Checking authentication")
            try:
                jwt_payload = fetch_data_and_validate_access_token(request)
            except InvalidTokenError as e:
                logger.exception("Invalid JWT")
                return ApiResponse(err="User not logged in",
                                   status=status.HTTP_401_UNAUTHORIZED)
            logger.debug(type(request))
            request.user_id = jwt_payload.get('id')
            request.user_name = jwt_payload.get('user_name')
            return func(request)

        return wrapper



def fetch_data_and_validate_access_token(request):
    """
    Validates jwt token, and if validated return the payload as dictionary
    :param request:
    :return:
    """
    try:
        token = request.headers.get('Authorization').split()[1]
        logger.debug("JWT is %s", token)
        logger.debug(settings.JWT_AUTH.get('JWT_ALGORITHM'))
        payload = jwt_decode_handler(token)
        logger.debug(payload)
    except jwt.DecodeError as e:
        logger.exception("decoding error")
        raise e
    except jwt.ExpiredSignatureError as e:
        logger.exception("Expired signature error")
        raise e
    except Exception as e:
        logger.exception(str(e))
        raise InvalidTokenError(str(e))
    if is_token_blacklisted(token):
        logger.error("user already logged out")
        raise InvalidTokenError("user already logged out")
    if not payload.get('id'):
        logger.error('JWT does not have user id')
        raise InvalidTokenError("JWT does not have user ids")
    if payload.get('type') != "ACCESS TOKEN":
        logger.error('JWT is not ACCESS TOKE<<N')
        raise InvalidTokenError("JWT is not ACCESS TOKEN")
    return payload