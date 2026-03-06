"""In-memory WebAuthn challenge store with TTL. Single-instance only; use Redis in production for multi-instance."""
import base64
import time
from typing import Any

_CHALLENGES: dict[str, dict[str, Any]] = {}
_TTL_SECONDS = 300  # 5 minutes


def _b64_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def _clean_old():
    now = time.time()
    for key in list(_CHALLENGES):
        if now - _CHALLENGES[key].get("created_at", 0) > _TTL_SECONDS:
            del _CHALLENGES[key]


def store_challenge(challenge: bytes, kind: str, discord_sub: str | None = None) -> str:
    """Store challenge, return base64url-encoded challenge (for client to echo back)."""
    _clean_old()
    key = _b64_encode(challenge)
    _CHALLENGES[key] = {
        "kind": kind,
        "discord_sub": discord_sub,
        "created_at": time.time(),
    }
    return key


def get_and_consume_challenge(challenge_b64: str) -> dict[str, Any] | None:
    """Get challenge payload by base64 challenge; remove from store. Returns None if missing or expired."""
    _clean_old()
    key = challenge_b64
    if key not in _CHALLENGES:
        return None
    payload = _CHALLENGES.pop(key)
    if time.time() - payload["created_at"] > _TTL_SECONDS:
        return None
    return payload


def get_challenge_bytes(challenge_b64: str) -> bytes | None:
    """Decode base64url challenge to bytes. Does not consume."""
    try:
        return _b64_decode(challenge_b64)
    except Exception:
        return None
