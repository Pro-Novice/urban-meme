import re
import json
import time
import logging
import functools

from django.http import JsonResponse

logger = logging.getLogger('django.request')

_GENERIC_API_ERROR = "Resource not found."
_LEAK_PATTERN = re.compile(
    r"(?i)traceback|file \"|line \d+|exception|errno|execution reverted|web3|rpc|"
    r"https?://|connection|timeout|psycopg|django|sql|relation |column |"
    r"out of range|site-packages|/home/|/usr/|/app/|object has no attribute|"
    r"not subscriptable|unexpected keyword|int too large|overflow"
)


def _generic_error():
    return JsonResponse({"success": False, "data": {}, "error": _GENERIC_API_ERROR}, status=404)


def _is_leaky(response) -> bool:
    if response.status_code >= 500:
        return True
    ctype = (response.get("Content-Type") or "").lower()
    if "text/html" in ctype:
        return True
    if "json" not in ctype:
        return False
    try:
        error = json.loads(response.content).get("error")
    except Exception:
        return False
    return isinstance(error, str) and bool(_LEAK_PATTERN.search(error))


def sensitive_view(view_func):
    
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        request._is_sensitive_view = True
        return view_func(request, *args, **kwargs)
    
    wrapper._is_sensitive_view = True
    return wrapper


class SecurityHeadersMiddleware:
    # Strict CSP for all responses, with no unsafe allowances. Adjust as needed for specific endpoints.
    _CSP = (
        "default-src 'self'; "
        "script-src 'none'; "
        "object-src 'none'; "
        "style-src 'none'; "
        "img-src 'none'; "
        "font-src 'none'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'none'; "
        "base-uri 'self';"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except Exception:
            logger.exception("Unhandled exception path=%s", request.path)
            response = _generic_error()

        # Error responses must never carry debug pages or exception text.
        if response.status_code >= 400 and not response.streaming and _is_leaky(response):
            logger.error("Sanitized error response path=%s status=%s", request.path, response.status_code)
            response = _generic_error()

        if "Server" in response:
            del response["Server"]
        self._apply(request, response)
        return response

    # ------------------------------------------------------------------
    # Determine if the request is for a sensitive view by checking the request attribute and resolver match.
    @staticmethod
    def _is_sensitive(request) -> bool:
        
        
        if getattr(request, "_is_sensitive_view", False):
            return True

        view_func = getattr(request, "resolver_match", None)
        if view_func:
            func = getattr(view_func, "func", None)
            if getattr(func, "_is_sensitive_view", False):
                return True
          
            inner = getattr(func, "initkwargs", {}).get("actions") or getattr(func, "cls", None)
            if getattr(inner, "_is_sensitive_view", False):
                return True

        return False
    
    def _apply(self, request, response):
       
        if self._is_sensitive(request):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Pragma"] = "no-cache"

        response["Content-Security-Policy"] = self._CSP

        response["X-XSS-Protection"] = "1; mode=block"


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        ms = round((time.monotonic() - start) * 1000)
        logger.info('%s %s %s %dms', request.method, request.get_full_path(), response.status_code, ms)
        return response
