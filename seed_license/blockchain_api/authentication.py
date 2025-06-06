from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import logging
import base64
import requests


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
    


class SSOAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.headers.get('SSO-TOKEN')
        if not token:
            raise AuthenticationFailed("SSO token missing")

        auth_header = base64.b64encode(
            f"{settings.SSO_WS_USERNAME}:{settings.SSO_WS_PASSWORD}".encode()
        ).decode()

        headers = {
            "SSO-TOKEN": token,
            "Authorization": f"Basic {auth_header}"
        }

        try:
            
            token_resp = requests.get(
                f"{settings.SSO_BASE_URL}/SSORESTNEW/TokenDetail",
                headers=headers
            )
            if token_resp.status_code != 200:
                raise AuthenticationFailed("Invalid SSO token")

            token_data = token_resp.json()
            sso_id = token_data.get("sAMAccountName")
            roles = token_data.get("Roles", [])

           
            profile_resp = requests.get(
                f"{settings.SSO_BASE_URL}/SSORESTNEW/Profile/{sso_id}",
                headers=headers
            )
            if profile_resp.status_code != 200:
                raise AuthenticationFailed("Failed to fetch profile")

            profile = profile_resp.json()
            profile["roles"] = roles  

            return (None, profile)

        except Exception as e:
            logger.exception("SSO Auth failed")
            raise AuthenticationFailed("SSO Auth failed")
