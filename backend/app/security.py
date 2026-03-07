"""Security: headers middleware, optional rate limiting."""
import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from config import get_settings


# ---- Security headers ----

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "1; mode=block",
    "Permissions-Policy": "accelerometer=(), camera=(), geolocation=(), microphone=(), payment=(), usb=()",
}


def add_security_headers(response: Response, use_hsts: bool = False) -> None:
    """Add security headers to the response."""
    for key, value in SECURITY_HEADERS.items():
        response.headers[key] = value
    if use_hsts:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses. HSTS only when backend URL is HTTPS (non-localhost)."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        settings = get_settings()
        self._use_hsts = (
            (settings.backend_url or "").strip().lower().startswith("https")
            and "localhost" not in (settings.backend_url or "").lower()
            and "127.0.0.1" not in (settings.backend_url or "")
        )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        add_security_headers(response, use_hsts=self._use_hsts)
        return response


# ---- Rate limiting (in-memory, per IP) ----

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Optional per-IP rate limit. Returns 429 when exceeded.
    Config: RATE_LIMIT_ENABLED, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        settings = get_settings()
        self._enabled = getattr(settings, "rate_limit_enabled", False)
        self._max_requests = getattr(settings, "rate_limit_requests", 100)
        self._window_sec = getattr(settings, "rate_limit_window_seconds", 60)
        self._counts: dict[str, list[float]] = defaultdict(list)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.scope.get("client"):
            host, _ = request.scope["client"]
            return host or "unknown"
        return "unknown"

    async def dispatch(self, request: Request, call_next):
        if not self._enabled:
            return await call_next(request)
        key = self._client_key(request)
        now = time.monotonic()
        # Prune old entries
        cutoff = now - self._window_sec
        self._counts[key] = [t for t in self._counts[key] if t > cutoff]
        if len(self._counts[key]) >= self._max_requests:
            return Response(
                content='{"detail":"Too many requests"}',
                status_code=429,
                media_type="application/json",
            )
        self._counts[key].append(now)
        response = await call_next(request)
        return response
