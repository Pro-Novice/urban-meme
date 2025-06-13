import logging
import time
import json
import base64
import requests
from django.utils.deprecation import MiddlewareMixin
from django.utils.deprecation import MiddlewareMixin
from .authentication import RajSSOAuthBackend
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.functional import SimpleLazyObject

logger = logging.getLogger(__name__)

class BlockchainAPILoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all requests to blockchain API endpoints for monitoring.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('blockchain_api')
        # Initialize parent class properly
        super().__init__(get_response)
    
    def process_request(self, request):
        # Only log blockchain API endpoints
        if '/api/blockchain/' in request.path:
            request.start_time = time.time()
            # Log the incoming request
            client_ip = self.get_client_ip(request)
            api_key = request.headers.get('X-API-Key', 'none')[:5] + '...' if request.headers.get('X-API-Key') else 'none'
            request_data = None
            
            if request.method == 'POST':
                try:
                    request_data = json.loads(request.body) if request.body else None
                except json.JSONDecodeError:
                    request_data = "Invalid JSON"
                except Exception:
                    request_data = "Error reading request body"
            
            self.logger.info(f"API Request | {request.method} {request.path} | IP: {client_ip} | API Key: {api_key} | Data: {request_data}")
    
    def process_response(self, request, response):
        # Only log blockchain API endpoints
        if '/api/blockchain/' in request.path:
            # Calculate request processing time
            if hasattr(request, 'start_time'):
                processing_time = time.time() - request.start_time
                status_code = response.status_code
                
                # Log the response
                self.logger.info(f"API Response | {request.method} {request.path} | Status: {status_code} | Time: {processing_time:.3f}s")
            
        return response
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', 'unknown')
        return ip
    

def get_sso_user(request):
    sso_token = request.headers.get("SSO-TOKEN")
    return RajSSOAuthBackend().authenticate(request, sso_token=sso_token) or AnonymousUser()

class RajSSOMiddleware(MiddlewareMixin):
    def process_request(self, request):
        sso_token = request.headers.get("SSO-TOKEN")
        if sso_token:
           
            self._extend_sso_session(sso_token)
            request.user = SimpleLazyObject(lambda: get_sso_user(request))
        else:
            request.user = AnonymousUser()

    def _extend_sso_session(self, sso_token):
        try:
            headers = {
                "SSO-TOKEN": sso_token,
                "Authorization": "Basic " + base64.b64encode(
                    f"{settings.SSO_USERNAME}:{settings.SSO_PASSWORD}".encode()
                ).decode()
            }
            requests.get(
                f"{settings.SSO_BASE_URL}/SSORESTNEW/IncreaseSessionTime",
                headers=headers,
                timeout=2
            )
        except Exception as e:
            logger.warning(f"Failed to extend SSO session: {str(e)}")