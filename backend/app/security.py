"""Security: headers middleware, optional rate limiting."""
import re
import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from config import get_settings

# Match localhost with optional port for CORS fallback (optional trailing slash)
_LOCALHOST_ORIGIN_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?/?$", re.IGNORECASE)


class PreflightCORSForLocalhostMiddleware(BaseHTTPMiddleware):
    """Handle OPTIONS preflight for localhost origins so the response always has valid CORS headers (avoids 'Missing Header' on preflight)."""

    async def dispatch(self, request: Request, call_next):
        if request.method != "OPTIONS":
            return await call_next(request)
        origin = (request.headers.get("origin") or "").strip()
        if not origin or not _LOCALHOST_ORIGIN_RE.fullmatch(origin):
            return await call_next(request)
        # Preflight for localhost: return 200 with full CORS headers so browser allows the actual request
        return Response(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Admin-API-Key",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            },
        )


class EnsureCORSForLocalhostMiddleware(BaseHTTPMiddleware):
    """Fallback: set Access-Control-Allow-Origin for localhost origins if missing (avoids CORS errors when main CORS does not run)."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        origin = request.headers.get("origin")
        origin_normalized = (origin or "").strip().rstrip("/") or None
        if origin_normalized and _LOCALHOST_ORIGIN_RE.fullmatch(origin_normalized) and "access-control-allow-origin" not in response.headers:
            response.headers["Access-Control-Allow-Origin"] = origin  # use original Origin value
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers.setdefault("Vary", "Origin")
        return response


# ---- Security headers ----

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "SAMEORIGIN",  # Allow same-origin framing (e.g. profile preview iframe on /wallet/profile)
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
