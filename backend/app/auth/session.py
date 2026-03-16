"""Session: sign/verify a simple payload (discord_sub, wallet_id) in a cookie."""
import json
import base64
import hmac
import hashlib
import secrets
from typing import Any
from config import get_settings

_settings = get_settings()


def _sign(payload_b64: str) -> str:
    return hmac.new(
        _settings.secret_key.encode(),
        payload_b64.encode(),
        hashlib.sha256,
    ).hexdigest()


def encode_session(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True)
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = _sign(payload_b64)
    return f"{payload_b64}.{sig}"


def decode_session(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        if hmac.compare_digest(_sign(payload_b64), sig) is False:
            return None
        pad = 4 - len(payload_b64) % 4
        if pad != 4:
            payload_b64 += "=" * pad
        payload = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload)
    except Exception:
        return None


def session_cookie_kwargs(token: str) -> dict[str, Any]:
    """Kwargs for Response.set_cookie(). Use SameSite=None when frontend and backend are on different origins.
    Sets explicit domain in production (from COOKIE_DOMAIN or backend_url host) so the cookie is sent on the
    public host even behind a proxy, and so www/apex share a cookie when COOKIE_DOMAIN=.example.com."""
    s = get_settings()
    kwargs = {
        "key": s.session_cookie_name,
        "value": token,
        "max_age": s.session_ttl_seconds,
        "httponly": True,
        "path": "/",
    }
    domain = s.cookie_domain_resolved
    if domain:
        kwargs["domain"] = domain
    if s.cross_origin_deploy and s.backend_url.strip().lower().startswith("https"):
        kwargs["samesite"] = "none"
        kwargs["secure"] = True
    else:
        kwargs["samesite"] = "lax"
        kwargs["secure"] = s.backend_url.strip().lower().startswith("https")
    return kwargs
