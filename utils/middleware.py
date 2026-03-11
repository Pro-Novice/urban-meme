import time
import logging

logger = logging.getLogger('django.request')

class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        ms = round((time.monotonic() - start) * 1000)
        logger.info('%s %s %s %dms', request.method, request.get_full_path(), response.status_code, ms)
        return response