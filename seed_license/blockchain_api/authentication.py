from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
import logging

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