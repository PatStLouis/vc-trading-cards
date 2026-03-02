"""Optional: get fresh ACA-Py tenant token for API calls. Depends on current user."""
from fastapi import Request, HTTPException, Depends
from app.auth.session import decode_session
from app.db import get_tenant_by_discord_sub
from app.services.acapy import get_tenant_token
from config import get_settings

settings = get_settings()


async def get_current_user(request: Request) -> dict:
    cookie = request.cookies.get(settings.session_cookie_name)
    if not cookie:
        raise HTTPException(status_code=401, detail="Not authenticated")
    data = decode_session(cookie)
    if not data:
        raise HTTPException(status_code=401, detail="Invalid session")
    return data


async def get_tenant_token_for_request(user: dict = Depends(get_current_user)) -> str | None:
    """Get ACA-Py tenant token for the current user (for wallet API calls)."""
    tenant = await get_tenant_by_discord_sub(user["sub"])
    if not tenant:
        return None
    if tenant.get("tenant_token"):
        return tenant["tenant_token"]
    return await get_tenant_token(tenant["wallet_id"])
