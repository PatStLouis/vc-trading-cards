"""WebAuthn (passkey) registration and authentication. Requires webauthn package."""
import base64
import json
import secrets
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse, JSONResponse

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

from app.auth.session import encode_session
from app.auth.webauthn_store import store_challenge, get_and_consume_challenge
from app.db import (
    get_tenant_by_discord_sub,
    webauthn_save_credential,
    webauthn_get_credential_by_id,
    webauthn_update_sign_count,
    webauthn_list_credentials_for_user,
)
from app.dependencies import get_current_user
from config import get_settings

router = APIRouter(tags=["Auth"], prefix="/auth/webauthn")
settings = get_settings()


def _b64_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    if pad != 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s)


def _challenge_from_credential_response(credential: dict) -> str | None:
    """Extract base64url challenge from credential response (registration or auth)."""
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


def _frontend_redirect(path: str = "", query: str = "") -> RedirectResponse:
    url = f"{settings.frontend_url.rstrip('/')}{path}"
    if query:
        url += "?" + query
    return RedirectResponse(url=url, status_code=302)


@router.get("/register/options")
async def webauthn_register_options(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Return PublicKeyCredentialCreationOptions for the current user. Requires Discord session."""
    rp_id = settings.webauthn_rp_id_resolved
    origin = settings.webauthn_origin_resolved
    user_id = user["sub"].encode("utf-8") if isinstance(user["sub"], str) else user["sub"]
    user_name = user.get("username") or user["sub"]
    challenge = secrets.token_bytes(32)
    exclude_creds = []
    existing = await webauthn_list_credentials_for_user(user["sub"])
    for c in existing:
        exclude_creds.append(PublicKeyCredentialDescriptor(credential_id=c["credential_id"]))
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_id,
        user_name=user_name,
        user_display_name=user_name,
        challenge=challenge,
        exclude_credentials=exclude_creds or None,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    store_challenge(challenge, "reg", user["sub"])
    return JSONResponse(content=json.loads(options_to_json(options)))


@router.post("/register/verify")
async def webauthn_register_verify(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Verify registration response and store credential. Requires Discord session."""
    body = await request.json()
    challenge_b64 = _challenge_from_credential_response(body)
    if not challenge_b64:
        raise HTTPException(status_code=400, detail="Invalid credential response")
    payload = get_and_consume_challenge(challenge_b64)
    if not payload or payload.get("kind") != "reg" or payload.get("discord_sub") != user["sub"]:
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
    await webauthn_save_credential(
        discord_sub=user["sub"],
        credential_id=verified.credential_id,
        public_key=verified.credential_public_key,
        sign_count=verified.sign_count,
    )
    return {"ok": True, "message": "Passkey added. You can sign in with it next time."}


@router.get("/login/options")
async def webauthn_login_options(request: Request):
    """Return PublicKeyCredentialRequestOptions for usernameless login (no allow_credentials)."""
    rp_id = settings.webauthn_rp_id_resolved
    challenge = secrets.token_bytes(32)
    options = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge,
    )
    store_challenge(challenge, "auth", None)
    return JSONResponse(content=json.loads(options_to_json(options)))


@router.post("/login/verify")
async def webauthn_login_verify(request: Request, response: Response):
    """Verify authentication response, create session, set cookie, redirect to /wallet."""
    body = await request.json()
    challenge_b64 = _challenge_from_credential_response(body)
    if not challenge_b64:
        raise HTTPException(status_code=400, detail="Invalid credential response")
    payload = get_and_consume_challenge(challenge_b64)
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
        if isinstance(cred_id_raw, str):
            credential_id = _b64_decode(cred_id_raw)
        else:
            credential_id = cred_id_raw
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
    tenant = await get_tenant_by_discord_sub(stored["discord_sub"])
    if not tenant:
        raise HTTPException(status_code=500, detail="User tenant not found")
    session_data = {
        "sub": stored["discord_sub"],
        "username": tenant.get("discord_username") or stored["discord_sub"],
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
