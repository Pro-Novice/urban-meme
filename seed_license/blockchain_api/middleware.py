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
        super().__init__(get_response)
        self.logger = logging.getLogger('blockchain_api')
        super().__init__(get_response)  # Add this line
    
    def process_request(self, request):
        # Only log blockchain API endpoints
        if '/api/blockchain/' in request.path or '/blockchain/' in request.path:
            request.start_time = time.time()
            # Log the incoming request
            client_ip = self.get_client_ip(request)
            api_key = request.headers.get('X-API-Key', 'none')
            if api_key != 'none' and len(api_key) > 5:
                api_key = api_key[:5] + '...'
            
            request_data = None
            
            if request.method in ['POST', 'PUT', 'PATCH']:
                try:
                    # Store the original body for later use
                    if hasattr(request, '_body'):
                        body = request._body
                    else:
                        body = request.body
                    
                    if body:
                        request_data = json.loads(body.decode('utf-8'))
                        # Sanitize sensitive data
                        request_data = self.sanitize_request_data(request_data)
                except json.JSONDecodeError:
                    request_data = "Invalid JSON"
                except UnicodeDecodeError:
                    request_data = "Binary data"
                except Exception as e:
                    request_data = f"Error reading request body: {str(e)}"
            
            self.logger.info(
                f"API Request | {request.method} {request.path} | "
                f"IP: {client_ip} | API Key: {api_key} | Data: {request_data}"
            )
    
    def process_response(self, request, response):
        # Only log blockchain API endpoints
        if '/api/blockchain/' in request.path or '/blockchain/' in request.path:
            # Calculate request processing time
            if hasattr(request, 'start_time'):
                processing_time = time.time() - request.start_time
                status_code = response.status_code
                
                # Log response details
                response_info = {
                    'method': request.method,
                    'path': request.path,
                    'status': status_code,
                    'time': f"{processing_time:.3f}s"
                }
                
                # Add error details for failed requests
                if status_code >= 400:
                    try:
                        if hasattr(response, 'content'):
                            content = response.content.decode('utf-8')
                            if content and len(content) < 500:  # Only log short error messages
                                response_info['error'] = content
                    except Exception:
                        pass
                
                # Log the response
                self.logger.info(
                    f"API Response | {request.method} {request.path} | "
                    f"Status: {status_code} | Time: {processing_time:.3f}s"
                )
                
                # Log errors and slow requests separately
                if status_code >= 400:
                    self.logger.error(
                        f"API Error | {request.method} {request.path} | "
                        f"Status: {status_code} | Time: {processing_time:.3f}s"
                    )
                elif processing_time > 5.0:  # Log slow requests (>5 seconds)
                    self.logger.warning(
                        f"Slow API Request | {request.method} {request.path} | "
                        f"Time: {processing_time:.3f}s"
                    )
            
        return response
    
    def process_exception(self, request, exception):
        """Log exceptions that occur during request processing"""
        if '/api/blockchain/' in request.path or '/blockchain/' in request.path:
            processing_time = 'unknown'
            if hasattr(request, 'start_time'):
                processing_time = f"{time.time() - request.start_time:.3f}s"
            
            self.logger.error(
                f"API Exception | {request.method} {request.path} | "
                f"Exception: {str(exception)} | Time: {processing_time}",
                exc_info=True
            )
    
    def get_client_ip(self, request):
        """Extract the real client IP address"""
        # Check for IP in various headers (for proxy/load balancer scenarios)
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Take the first IP in the list (original client)
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            # Check other common headers
            ip = (request.META.get('HTTP_X_REAL_IP') or 
                  request.META.get('HTTP_CF_CONNECTING_IP') or 
                  request.META.get('REMOTE_ADDR', 'unknown'))
        return ip
    
    def sanitize_request_data(self, data):
        """Remove sensitive information from request data before logging"""
        if not isinstance(data, dict):
            return data
        
        # List of sensitive keys to sanitize
        sensitive_keys = [
            'password', 'token', 'api_key', 'secret', 'private_key',
            'auth', 'authorization', 'credit_card', 'ssn', 'social_security'
        ]
        
        sanitized = data.copy()
        for key in sanitized:
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = "***HIDDEN***"
            elif isinstance(sanitized[key], dict):
                sanitized[key] = self.sanitize_request_data(sanitized[key])
        
        return sanitized