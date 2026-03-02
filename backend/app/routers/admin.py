"""Admin dashboard API: stats and user list. Requires user to be in ADMIN_DISCORD_IDS."""
from fastapi import APIRouter, Depends
from app.dependencies import get_current_admin
from app.db import list_users, count_users

router = APIRouter(tags=["Admin"], prefix="/api/admin")


@router.get("/stats")
async def admin_stats(_admin: dict = Depends(get_current_admin)):
    """Return counts for the admin dashboard."""
    total_users = await count_users()
    return {"total_users": total_users}


@router.get("/users")
async def admin_users(_admin: dict = Depends(get_current_admin), limit: int = 500):
    """List registered users (discord_sub, username, wallet_id, created_at)."""
    if limit < 1 or limit > 1000:
        limit = 500
    users = await list_users(limit=limit)
    return {"users": users}
