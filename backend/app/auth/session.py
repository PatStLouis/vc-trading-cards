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
