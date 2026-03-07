"""WebAuthn (passkey) routes and challenge store. Single file."""
import base64
import json
import secrets
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import JSONResponse

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .session import encode_session
from app.db import (
    get_tenant_by_user_id,
    webauthn_save_credential,
    webauthn_get_credential_by_id,
    webauthn_update_sign_count,
    webauthn_list_credentials_for_user,
    get_user_accounts,
    ensure_user_exists,
)
from app.dependencies import get_current_user
from config import get_settings

router = APIRouter(prefix="/webauthn")
settings = get_settings()

# ---- Challenge store (in-memory, 5 min TTL; use Redis in production for multi-instance) ----

_CHALLENGES: dict[str, dict[str, Any]] = {}
_CHALLENGE_TTL = 300


def _b64_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def _clean_old_challenges():
    now = time.time()
    for key in list(_CHALLENGES):
        if now - _CHALLENGES[key].get("created_at", 0) > _CHALLENGE_TTL:
            del _CHALLENGES[key]


def _store_challenge(challenge: bytes, kind: str, user_id: str | None = None) -> None:
    _clean_old_challenges()
    key = _b64_encode(challenge)
    _CHALLENGES[key] = {"kind": kind, "user_id": user_id, "created_at": time.time()}


def _get_and_consume_challenge(challenge_b64: str) -> dict[str, Any] | None:
    _clean_old_challenges()
    if challenge_b64 not in _CHALLENGES:
        return None
    payload = _CHALLENGES.pop(challenge_b64)
    if time.time() - payload["created_at"] > _CHALLENGE_TTL:
        return None
    return payload


def _challenge_from_response(credential: dict) -> str | None:
    try:
        res = credential.get("response") or {}
        client_data = res.get("clientDataJSON")
        if isinstance(client_data, str):
            raw = _b64_decode(client_data)
        else:
            return None
        data = json.loads(raw)
        return data.get("challenge")
    except Exception:
        return None


@router.get("/register/options")
async def register_options(request: Request, user: dict = Depends(get_current_user)):
    """Return PublicKeyCredentialCreationOptions for the current user. Requires session."""
    rp_id = settings.webauthn_rp_id_resolved
    user_id = user["user_id"]
    user_id_bytes = user_id.encode("utf-8") if isinstance(user_id, str) else user_id
    user_name = user.get("username") or user.get("sub") or user_id
    challenge = secrets.token_bytes(32)
    exclude_creds = []
    existing = await webauthn_list_credentials_for_user(user["user_id"])
    for c in existing:
        exclude_creds.append(PublicKeyCredentialDescriptor(id=c["credential_id"]))
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_id_bytes,
        user_name=user_name,
        user_display_name=user_name,
        challenge=challenge,
        exclude_credentials=exclude_creds or None,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    _store_challenge(challenge, "reg", user["user_id"])
    return JSONResponse(content=json.loads(options_to_json(options)))


@router.post("/register/verify")
async def register_verify(request: Request, user: dict = Depends(get_current_user)):
    """Verify registration response and store credential. Requires session."""
    body = await request.json()
    challenge_b64 = _challenge_from_response(body)
    if not challenge_b64:
        raise HTTPException(status_code=400, detail="Invalid credential response")
    payload = _get_and_consume_challenge(challenge_b64)
    if not payload or payload.get("kind") != "reg" or payload.get("user_id") != user["user_id"]:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")
    try:
        challenge_bytes = _b64_decode(challenge_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid challenge encoding")
    rp_id = settings.webauthn_rp_id_resolved
    origin = settings.webauthn_origin_resolved
    try:
        verified = verify_registration_response(
            credential=body,
            expected_challenge=challenge_bytes,
            expected_rp_id=rp_id,
            expected_origin=origin,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")
    await ensure_user_exists(user["user_id"])
    registered_name = user.get("username") or user.get("sub") or user["user_id"]
    await webauthn_save_credential(
        user_id=user["user_id"],
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
        credential_device_type=getattr(verified.credential_device_type, "value", str(verified.credential_device_type)) if verified.credential_device_type else None,
        credential_backed_up=verified.credential_backed_up,
        aaguid=verified.aaguid or None,
        attestation_format=getattr(verified.fmt, "value", str(verified.fmt)) if verified.fmt else None,
        registered_name=registered_name,
    )
    return {"ok": True, "message": "Passkey added. You can sign in with it next time."}


@router.get("/login/options")
async def login_options(request: Request):
    """Return PublicKeyCredentialRequestOptions for usernameless login."""
    rp_id = settings.webauthn_rp_id_resolved
    challenge = secrets.token_bytes(32)
    options = generate_authentication_options(rp_id=rp_id, challenge=challenge)
    _store_challenge(challenge, "auth", None)
    return JSONResponse(content=json.loads(options_to_json(options)))


@router.post("/login/verify")
async def login_verify(request: Request, response: Response):
    """Verify authentication response, create session, set cookie."""
    body = await request.json()
    challenge_b64 = _challenge_from_response(body)
    if not challenge_b64:
        raise HTTPException(status_code=400, detail="Invalid credential response")
    payload = _get_and_consume_challenge(challenge_b64)
    if not payload or payload.get("kind") != "auth":
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")
    try:
        challenge_bytes = _b64_decode(challenge_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid challenge encoding")
    cred_id_raw = body.get("rawId") or body.get("id")
    if not cred_id_raw:
        raise HTTPException(status_code=400, detail="Missing credential id")
    try:
        credential_id = _b64_decode(cred_id_raw) if isinstance(cred_id_raw, str) else cred_id_raw
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid credential id")
    stored = await webauthn_get_credential_by_id(credential_id)
    if not stored:
        raise HTTPException(status_code=401, detail="Unknown passkey")
    rp_id = settings.webauthn_rp_id_resolved
    origin = settings.webauthn_origin_resolved
    try:
        verified = verify_authentication_response(
            credential=body,
            expected_challenge=challenge_bytes,
            expected_rp_id=rp_id,
            expected_origin=origin,
            credential_public_key=stored["public_key"],
            credential_current_sign_count=stored["sign_count"],
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Verification failed: {e}")
    await webauthn_update_sign_count(credential_id, verified.new_sign_count)
    user_id = stored["user_id"]
    tenant = await get_tenant_by_user_id(user_id)
    if not tenant:
        raise HTTPException(status_code=500, detail="User tenant not found")
    accounts = await get_user_accounts(user_id)
    discord_account = next((a for a in accounts if a["provider"] == "discord"), None)
    session_data = {
        "user_id": user_id,
        "sub": discord_account["provider_user_id"] if discord_account else user_id,
        "provider": discord_account["provider"] if discord_account else "passkey",
        "username": discord_account["provider_username"] if discord_account else user_id,
        "wallet_id": tenant["wallet_id"],
    }
    token = encode_session(session_data)
    res = JSONResponse(content={"ok": True, "redirect": "/wallet"})
    res.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.backend_url.startswith("https"),
    )
    return res
