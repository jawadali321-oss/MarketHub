import uuid
import time
import hmac
import hashlib
from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings


class RequestSigningMiddleware:
    """HMAC-SHA256 signature validation. Headers: X-Timestamp + X-Signature. Drift < 5min."""
    DRIFT_SECONDS = 300

    def __init__(self, get_response):
        self.get_response = get_response
        self.enforce = getattr(settings, "ENFORCE_REQUEST_SIGNING", False)
        self.secret = getattr(settings, "REQUEST_SIGNING_SECRET", "").encode()

    def __call__(self, request):
        if self.enforce and self.secret:
            ts = request.META.get("HTTP_X_TIMESTAMP", "")
            sig = request.META.get("HTTP_X_SIGNATURE", "")
            if not ts or not sig:
                return JsonResponse({"success": False, "data": None,
                    "error": {"detail": "Missing X-Timestamp or X-Signature."}, "pagination": None}, status=400)
            try:
                ts_int = int(ts)
            except ValueError:
                return JsonResponse({"success": False, "data": None,
                    "error": {"detail": "Invalid X-Timestamp."}, "pagination": None}, status=400)
            if abs(time.time() - ts_int) > self.DRIFT_SECONDS:
                return JsonResponse({"success": False, "data": None,
                    "error": {"detail": "Request timestamp expired."}, "pagination": None}, status=400)
            body = request.body
            expected = hmac.new(self.secret, f"{ts}{request.path}".encode() + body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, sig):
                return JsonResponse({"success": False, "data": None,
                    "error": {"detail": "Invalid request signature."}, "pagination": None}, status=400)
        return self.get_response(request)


class GuestSessionMiddleware:
    COOKIE_NAME = "session_key"
    COOKIE_MAX_AGE = 30 * 24 * 60 * 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session_key = request.COOKIES.get(self.COOKIE_NAME)
        if not session_key:
            session_key = str(uuid.uuid4())
        request.guest_session_key = session_key
        response = self.get_response(request)
        if self.COOKIE_NAME not in request.COOKIES:
            response.set_cookie(self.COOKIE_NAME, session_key, max_age=self.COOKIE_MAX_AGE, httponly=True, samesite="Lax")
        return response


class RateLimitMiddleware:
    AUTH_ENDPOINTS = ["/api/v1/auth/login/", "/api/v1/auth/password/reset/"]
    ALWAYS_COUNT_ENDPOINTS = ["/api/v1/auth/password/reset/"]

    def __init__(self, get_response):
        self.get_response = get_response

    @property
    def MAX_ATTEMPTS(self):
        return getattr(settings, "RATE_LIMIT_AUTH_ATTEMPTS", 5)

    @property
    def WINDOW(self):
        return getattr(settings, "RATE_LIMIT_AUTH_WINDOW", 60)

    def __call__(self, request):
        if request.path in self.AUTH_ENDPOINTS and request.method == "POST":
            ip = self._get_client_ip(request)
            cache_key = f"rate_limit:auth:{ip}:{request.path}"
            attempts = cache.get(cache_key, 0)
            if attempts >= self.MAX_ATTEMPTS:
                try:
                    remaining = cache.ttl(cache_key)
                    if not remaining or remaining < 0:
                        remaining = self.WINDOW
                except Exception:
                    remaining = self.WINDOW
                return JsonResponse({
                    "success": False, "data": None,
                    "error": {"detail": f"Too many attempts. Try again in {remaining} seconds.", "retry_after": remaining},
                    "pagination": None
                }, status=429)
            if request.path in self.ALWAYS_COUNT_ENDPOINTS:
                cache.set(cache_key, attempts + 1, self.WINDOW)

        response = self.get_response(request)

        if request.path == "/api/v1/auth/login/" and request.method == "POST":
            if response.status_code in (400, 401):
                ip = self._get_client_ip(request)
                cache_key = f"rate_limit:auth:{ip}:{request.path}"
                current = cache.get(cache_key, 0)
                cache.set(cache_key, current + 1, self.WINDOW)
        return response

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")
