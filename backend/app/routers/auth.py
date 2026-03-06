from fastapi import APIRouter, Depends, HTTPException, Response, Request
from fastapi.responses import RedirectResponse, JSONResponse
import secrets

from app.auth.discord import get_authorize_url, exchange_code_for_tokens, get_discord_user
from app.auth.session import encode_session, decode_session
from app.db import get_tenant_by_discord_sub, set_tenant_for_user, init_db
from app.services.acapy import create_tenant, get_tenant_token
from config import get_settings

router = APIRouter(tags=["Auth"], prefix="/auth")
settings = get_settings()


def _frontend_redirect(path: str = "", query: str = "") -> RedirectResponse:
    url = f"{settings.frontend_url.rstrip('/')}{path}"
    if query:
        url += "?" + query
    return RedirectResponse(url=url, status_code=302)


@router.get("/discord")
async def discord_login(request: Request):
    """Redirect to Discord OAuth2 authorize."""
    state = secrets.token_urlsafe(32)
    # In production store state in cache/redis and validate in callback
    url = get_authorize_url(state)
    return RedirectResponse(url=url, status_code=302)


@router.get("/discord/url")
async def discord_authorize_url():
    """Return the Discord OAuth2 authorize URL for client-side redirect or mobile intent."""
    state = secrets.token_urlsafe(32)
    url = get_authorize_url(state)
    return JSONResponse(content={"url": url})


@router.get("/redirect-uri")
async def auth_redirect_uri():
    """Return the redirect_uri this backend sends to Discord (for verification). Must match Discord Developer Portal → OAuth2 → Redirects."""
    redirect_uri = settings.discord_redirect_uri or f"{settings.backend_url.rstrip('/')}/auth/callback"
    return {"redirect_uri": redirect_uri}


@router.get("/callback")
async def discord_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    """Exchange code for tokens, ensure tenant exists, set session cookie, redirect to frontend."""
    if error or not code:
        return _frontend_redirect("/", "error=auth_failed")

    tokens = await exchange_code_for_tokens(code)
    if not tokens:
        return _frontend_redirect("/", "error=token_exchange_failed")

    user = await get_discord_user(tokens["access_token"])
    if not user:
        return _frontend_redirect("/", "error=user_fetch_failed")

    discord_sub = str(user.get("id", ""))
    discord_username = user.get("username") or user.get("global_name") or ""

    tenant = None
    # Admins with Innkeeper config use the shared Innkeeper tenant instead of creating a new one
    admin_ids = {s.strip() for s in (settings.admin_discord_ids or "").split(",") if s.strip()}
    is_admin_user = discord_sub in admin_ids
    if is_admin_user and settings.innkeeper_id and settings.innkeeper_key:
        token = await get_tenant_token(settings.innkeeper_id, settings.innkeeper_key)
        if token:
            await set_tenant_for_user(
                discord_sub,
                discord_username,
                settings.innkeeper_id,
                token,
                wallet_key=settings.innkeeper_key,
            )
            tenant = await get_tenant_by_discord_sub(discord_sub)
    if not tenant:
        # Get or create ACA-Py tenant for this user (non-admins, or admin when no Innkeeper / token failed)
        tenant = await get_tenant_by_discord_sub(discord_sub)
        if not tenant:
            # Create new subwallet on first login: generate key, create tenant, store wallet_id + wallet_key + token
            label = f"tritone-cards-{discord_sub}"
            wallet_key = secrets.token_urlsafe(32)
            created = await create_tenant(label, wallet_key=wallet_key)
            if created and created.get("wallet_id"):
                await set_tenant_for_user(
                    discord_sub,
                    discord_username,
                    created["wallet_id"],
                    created.get("token"),
                    wallet_key=wallet_key,
                )
                tenant = await get_tenant_by_discord_sub(discord_sub)
            else:
                # No ACA-Py: use a placeholder wallet_id so app still works (no wallet_key)
                wallet_id = f"local-{discord_sub}"
                await set_tenant_for_user(discord_sub, discord_username, wallet_id, None, wallet_key=None)
                tenant = await get_tenant_by_discord_sub(discord_sub)

    if not tenant:
        return _frontend_redirect("/", "error=tenant_failed")

    session_data = {
        "sub": discord_sub,
        "username": discord_username,
        "wallet_id": tenant["wallet_id"],
    }
    token = encode_session(session_data)

    response = _frontend_redirect("/wallet")
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.backend_url.startswith("https"),
    )
    return response


@router.post("/logout")
async def logout(response: Response):
    """Clear session cookie."""
    response.delete_cookie(settings.session_cookie_name)
    return {"ok": True}
