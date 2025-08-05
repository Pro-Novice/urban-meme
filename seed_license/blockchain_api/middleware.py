import logging
import time
import json
from django.utils.deprecation import MiddlewareMixin

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