from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import logging
import requests
from django.contrib.auth.models import AnonymousUser
import base64
from django.contrib.auth.backends import BaseBackend
from django.conf import settings

logger = logging.getLogger(__name__)

class APIKeyAuthentication(BaseAuthentication):
    """
    Simple API key based authentication.
    
    Clients should pass the API key in the header "X-API-Key".
    
    Example:
        X-API-Key: yourapikey12345
    """
    def authenticate(self, request):
        # Get the API key from the request headers
        api_key = request.headers.get('X-API-Key')
        
        if not api_key:
            # No API key provided
            logger.warning("API request without X-API-Key header")
            raise AuthenticationFailed('API key is missing')
        
        # Get the valid API keys from settings
        valid_api_keys = getattr(settings, 'API_KEYS', {})
        
        if not valid_api_keys:
            # No API keys configured
            logger.error("No API_KEYS configured in settings")
            raise AuthenticationFailed('API keys not configured on server')
        
        # Check if the provided API key is valid
        if api_key in valid_api_keys:
            client_name = valid_api_keys[api_key]
            logger.info(f"API request authenticated for client: {client_name}")
            # Return None for user as we don't have user authentication
            return (None, client_name)
        
        # API key is invalid
        logger.warning(f"Invalid API key used: {api_key[:5]}...")
        raise AuthenticationFailed('Invalid API key')

    def authenticate_header(self, request):
        return 'X-API-Key'

class RajSSOUser(AnonymousUser):
    def __init__(self, ssoid, roles, user_type, profile):
        super().__init__()
        self.username = ssoid
        self.roles = roles
        self.user_type = user_type
        self.profile = profile

    def is_authenticated(self):
        return True

    def has_role(self, role):
        return role in self.roles

    def get_full_name(self):
        return self.profile.get("displayName", self.username)

class RajSSOAuthBackend(BaseBackend):
    def authenticate(self, request, sso_token=None):
        if not sso_token:
            return None

        token_detail_url = f"{settings.SSO_BASE_URL}/SSORESTNEW/TokenDetail"
        headers = {
            "SSO-TOKEN": sso_token,
            "Authorization": "Basic " + base64.b64encode(
                f"{settings.SSO_USERNAME}:{settings.SSO_PASSWORD}".encode()
            ).decode()
        }

        try:
            response = requests.get(token_detail_url, headers=headers, timeout=5)
            if response.status_code != 200:
                logger.warning("SSO token invalid or expired")
                return None

            token_data = response.json()
            ssoid = token_data.get("sAMAccountName")
            roles = token_data.get("Roles", [])
            user_type = token_data.get("UserType")

            profile_url = f"{settings.SSO_BASE_URL}/SSORESTNEW/Profile/{ssoid}"
            profile_resp = requests.get(profile_url, headers=headers, timeout=5)
            profile = profile_resp.json() if profile_resp.status_code == 200 else {}

            return RajSSOUser(ssoid, roles, user_type, profile)

        except Exception as e:
            logger.exception("RajSSO authentication failed: %s", str(e))
            return None
        except requests.exceptions.ConnectionError:
            logger.error("RajSSO service unavailable")
            raise AuthenticationFailed("Authentication service temporarily unavailable")
        except requests.exceptions.Timeout:
            logger.warning("RajSSO service timeout")
            raise AuthenticationFailed("Authentication service timeout")
        except Exception as e:
            logger.exception("RajSSO authentication failed")
            raise AuthenticationFailed("Authentication failed")

    def get_user(self, user_id):
        return None


class RajSSOAuthentication(BaseAuthentication):
    def authenticate(self, request):
        sso_token = request.headers.get("SSO-TOKEN")
        if not sso_token:
            raise AuthenticationFailed("SSO-TOKEN header missing")

        user = RajSSOAuthBackend().authenticate(request, sso_token=sso_token)
        if not user:
            raise AuthenticationFailed("Invalid or expired SSO token")

        return (user, None)

