"""Dependencies: get_current_user, get_current_admin, get_tenant_token_for_request."""
from fastapi import Request, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader, APIKeyCookie, HTTPBearer, HTTPAuthorizationCredentials
from app.auth.session import decode_session
from app.db import get_tenant_by_user_id, get_user_accounts, ensure_user_exists
from config import get_settings

settings = get_settings()

# Session cookie: documented in OpenAPI so Swagger shows wallet/user routes as secured
SessionCookie = APIKeyCookie(
    name=settings.session_cookie_name,
    auto_error=False,
    description="Session cookie (set after Discord/Twitch login or passkey). Required for /api/me and /api/wallet/*.",
)

# Admin API key: documented in OpenAPI so Swagger shows "Authorize" for admin routes
AdminApiKeyHeader = APIKeyHeader(name="X-Admin-API-Key", auto_error=False, description="Admin API key (optional; or use session)")
AdminBearer = HTTPBearer(auto_error=False, description="Admin API key as Bearer token (optional)")


def _admin_discord_ids() -> set[str]:
    return {s.strip() for s in (settings.admin_discord_ids or "").split(",") if s.strip()}


def _admin_twitch_ids() -> set[str]:
    return {s.strip() for s in (settings.admin_twitch_ids or "").split(",") if s.strip()}


async def get_current_user(request: Request, session_value: str | None = Security(SessionCookie)) -> dict:
    """Require valid session cookie (set after login). Used by wallet and other authenticated routes."""
    cookie = session_value or (request.cookies.get(settings.session_cookie_name) if request else None)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = decode_session(cookie)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid session")
    # Ensure users row exists (e.g. after DB reset with stale session) so public profile and other lookups succeed
    user_id = data.get("user_id")
    if user_id:
        await ensure_user_exists(user_id)
    return data


async def is_admin(user: dict) -> bool:
    """Check if user is admin via any linked account (Discord or Twitch)."""
    user_id = (user.get("user_id") or "").strip()
    if not user_id:
        return False
    accounts = await get_user_accounts(user_id)
    for a in accounts:
        if a["provider"] == "discord" and a["provider_user_id"] in _admin_discord_ids():
            return True
        if a["provider"] == "twitch" and a["provider_user_id"] in _admin_twitch_ids():
            return True
    return False


async def get_current_admin(
    request: Request,
    api_key_header: str | None = Security(AdminApiKeyHeader),
    bearer: HTTPAuthorizationCredentials | None = Security(AdminBearer),
) -> dict:
    """Require session-based admin (Discord/Twitch in admin list) or valid ADMIN_API_KEY."""
    api_key = (api_key_header or "").strip()
    if not api_key and bearer:
        api_key = (bearer.credentials or "").strip()
    if not api_key:
        api_key = (request.headers.get("X-Admin-API-Key") or "").strip()
    if not api_key and request.headers.get("Authorization"):
        auth = (request.headers.get("Authorization") or "").strip()
        if auth.lower().startswith("bearer "):
            api_key = auth[7:].strip()
    if (settings.admin_api_key or "").strip() and api_key and api_key == (settings.admin_api_key or "").strip():
        return {"user_id": "__admin_api_key__", "username": "admin", "admin_api_key": True}
    user = await get_current_user(request)
    if not await is_admin(user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_tenant_token_for_request(user: dict = Depends(get_current_user)) -> str | None:
    """Get ACA-Py tenant token for the current user (for wallet API calls)."""
    from app.services.acapy import get_tenant_token
    tenant = await get_tenant_by_user_id(user["user_id"])
    if not tenant:
        return None
    if tenant.get("tenant_token"):
        return tenant["tenant_token"]
    return await get_tenant_token(tenant["wallet_id"], tenant.get("wallet_key") or None)
