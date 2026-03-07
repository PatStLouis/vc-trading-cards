"""Auth routes: OAuth (Discord/Twitch), logout. WebAuthn in webauthn.py."""
import logging
from fastapi import APIRouter, Response, Request
from fastapi.responses import RedirectResponse, JSONResponse
import secrets

from . import webauthn
from .providers.discord import get_authorize_url, exchange_code_for_tokens, get_discord_user
from .providers.twitch import (
    get_authorize_url as twitch_authorize_url,
    exchange_code_for_tokens as twitch_exchange_code,
    get_twitch_user,
)
from .session import encode_session, decode_session
from app.db import (
    get_or_create_user_by_provider,
    get_user_by_provider,
    add_account_binding,
    merge_users,
    get_tenant_by_user_id,
    set_tenant_for_user,
    ensure_user_exists,
)
from app.services.acapy import create_tenant, get_tenant_token
from config import get_settings

router = APIRouter()
settings = get_settings()
router.include_router(webauthn.router)

CALLBACK_PATH = "/auth/callback"
STATE_PREFIX_DISCORD = "discord:"
STATE_PREFIX_TWITCH = "twitch:"


def _callback_redirect_uri() -> str:
    return settings.discord_redirect_uri or f"{settings.backend_url.rstrip('/')}{CALLBACK_PATH}"


def _twitch_redirect_uri() -> str:
    return settings.twitch_redirect_uri or f"{settings.backend_url.rstrip('/')}{CALLBACK_PATH}"


def _frontend_redirect(path: str = "", query: str = "") -> RedirectResponse:
    url = f"{settings.frontend_url.rstrip('/')}{path}"
    if query:
        url += "?" + query
    return RedirectResponse(url=url, status_code=302)


async def _ensure_tenant_sync(user_id: str, provider_username: str, provider_user_id: str) -> dict:
    tenant = await get_tenant_by_user_id(user_id)
    if tenant:
        return tenant
    admin_ids = {s.strip() for s in (settings.admin_discord_ids or "").split(",") if s.strip()}
    admin_twitch = {s.strip() for s in (settings.admin_twitch_ids or "").split(",") if s.strip()}
    label = f"tritone-cards-{user_id}"
    if (provider_user_id in admin_ids or provider_user_id in admin_twitch) and settings.innkeeper_id and settings.innkeeper_key:
        token = await get_tenant_token(settings.innkeeper_id, settings.innkeeper_key)
        if token:
            await set_tenant_for_user(user_id, settings.innkeeper_id, token, wallet_key=settings.innkeeper_key)
            return await get_tenant_by_user_id(user_id)
    wallet_key = secrets.token_urlsafe(32)
    created = await create_tenant(label, wallet_key=wallet_key)
    if created and created.get("wallet_id"):
        await set_tenant_for_user(user_id, created["wallet_id"], created.get("token"), wallet_key=wallet_key)
    else:
        await set_tenant_for_user(user_id, f"local-{user_id}", None, wallet_key=None)
    return await get_tenant_by_user_id(user_id) or {"wallet_id": f"local-{user_id}"}


VALID_PROVIDERS = {"discord", "twitch"}


def _login_url(provider: str) -> str | None:
    if provider == "discord":
        state = STATE_PREFIX_DISCORD + secrets.token_urlsafe(32)
        redirect_uri = _callback_redirect_uri()
        return get_authorize_url(state, redirect_uri)
    if provider == "twitch":
        state = STATE_PREFIX_TWITCH + secrets.token_urlsafe(32)
        redirect_uri = _twitch_redirect_uri()
        return twitch_authorize_url(state, redirect_uri)
    return None


@router.get("/login")
async def login_redirect(request: Request, provider: str):
    """Redirect to OAuth2 for the given provider (discord or twitch)."""
    provider = (provider or "").strip().lower()
    if provider not in VALID_PROVIDERS:
        return _frontend_redirect("/", "error=invalid_provider")
    url = _login_url(provider)
    if not url:
        return _frontend_redirect("/", "error=auth_failed")
    return RedirectResponse(url=url, status_code=302)


@router.get("/login/url")
async def login_url(provider: str):
    """Return OAuth2 authorize URL for the given provider (client-side redirect or Android intent)."""
    provider = (provider or "").strip().lower()
    if provider not in VALID_PROVIDERS:
        return JSONResponse(content={"error": "invalid_provider"}, status_code=400)
    url = _login_url(provider)
    if not url:
        return JSONResponse(content={"error": "auth_unavailable"}, status_code=500)
    return JSONResponse(content={"url": url})


@router.get("/callback")
async def oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """OAuth callback: dispatch by state prefix to Discord or Twitch flow."""
    if error or not code or not state:
        return _frontend_redirect("/", "error=auth_failed")

    try:
        if state.startswith(STATE_PREFIX_DISCORD):
            return await _handle_discord_callback(request, code)
        if state.startswith(STATE_PREFIX_TWITCH):
            return await _handle_twitch_callback(request, code)
        return _frontend_redirect("/", "error=auth_failed")
    except Exception as e:
        logging.getLogger("uvicorn.error").exception("OAuth callback failed: %s", e)
        return _frontend_redirect("/", "error=auth_failed")


async def _handle_discord_callback(request: Request, code: str):
    redirect_uri = _callback_redirect_uri()
    tokens = await exchange_code_for_tokens(code, redirect_uri)
    if not tokens:
        return _frontend_redirect("/", "error=token_exchange_failed")
    user_data = await get_discord_user(tokens["access_token"])
    if not user_data:
        return _frontend_redirect("/", "error=user_fetch_failed")
    provider_user_id = str(user_data.get("id", ""))
    provider_username = user_data.get("username") or user_data.get("global_name") or ""
    provider_avatar = (user_data.get("avatar") or "").strip() or None
    provider_discriminator = (user_data.get("discriminator") or "").strip() or None

    cookie = request.cookies.get(settings.session_cookie_name)
    session = decode_session(cookie) if cookie else None
    current_user_id = (session or {}).get("user_id")

    if current_user_id:
        await ensure_user_exists(current_user_id)
        result = await add_account_binding(current_user_id, "discord", provider_user_id, provider_username, provider_avatar, provider_discriminator)
        if result == "duplicate":
            return _frontend_redirect("/wallet/account", "linked=discord")
        if result == "conflict":
            other_user_id = await get_user_by_provider("discord", provider_user_id)
            if other_user_id and other_user_id != current_user_id:
                await merge_users(current_user_id, other_user_id)
        return _frontend_redirect("/wallet", "merged=discord")
    else:
        user_id = await get_or_create_user_by_provider("discord", provider_user_id, provider_username, provider_avatar, provider_discriminator)
        tenant = await _ensure_tenant_sync(user_id, provider_username, provider_user_id)
        if not tenant:
            return _frontend_redirect("/", "error=tenant_failed")
        session_data = {
            "user_id": user_id,
            "sub": provider_user_id,
            "provider": "discord",
            "username": provider_username,
            "wallet_id": tenant["wallet_id"],
        }
        token = encode_session(session_data)
        resp = _frontend_redirect("/wallet")
        resp.set_cookie(
            key=settings.session_cookie_name,
            value=token,
            max_age=settings.session_ttl_seconds,
            httponly=True,
            samesite="lax",
            secure=settings.backend_url.startswith("https"),
        )
        return resp


async def _handle_twitch_callback(request: Request, code: str):
    redirect_uri = _twitch_redirect_uri()
    tokens = await twitch_exchange_code(code, redirect_uri)
    if not tokens:
        return _frontend_redirect("/", "error=token_exchange_failed")
    user_data = await get_twitch_user(tokens["access_token"])
    if not user_data:
        return _frontend_redirect("/", "error=user_fetch_failed")
    provider_user_id = str(user_data.get("id", ""))
    provider_username = user_data.get("login") or user_data.get("display_name") or ""

    cookie = request.cookies.get(settings.session_cookie_name)
    session = decode_session(cookie) if cookie else None
    current_user_id = (session or {}).get("user_id")

    if current_user_id:
        await ensure_user_exists(current_user_id)
        result = await add_account_binding(current_user_id, "twitch", provider_user_id, provider_username)
        if result == "duplicate":
            return _frontend_redirect("/wallet/account", "linked=twitch")
        if result == "conflict":
            other_user_id = await get_user_by_provider("twitch", provider_user_id)
            if other_user_id and other_user_id != current_user_id:
                await merge_users(current_user_id, other_user_id)
        return _frontend_redirect("/wallet", "merged=twitch")
    else:
        user_id = await get_or_create_user_by_provider("twitch", provider_user_id, provider_username)
        tenant = await _ensure_tenant_sync(user_id, provider_username, provider_user_id)
        if not tenant:
            return _frontend_redirect("/", "error=tenant_failed")
        session_data = {
            "user_id": user_id,
            "sub": provider_user_id,
            "provider": "twitch",
            "username": provider_username,
            "wallet_id": tenant["wallet_id"],
        }
        token = encode_session(session_data)
        resp = _frontend_redirect("/wallet")
        resp.set_cookie(
            key=settings.session_cookie_name,
            value=token,
            max_age=settings.session_ttl_seconds,
            httponly=True,
            samesite="lax",
            secure=settings.backend_url.startswith("https"),
        )
        return resp


@router.post("/logout")
async def logout(response: Response):
    """Clear session cookie."""
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}
