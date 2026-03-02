"""Async PostgreSQL store for discord_sub -> tenant (wallet_id, token) mapping."""
import asyncpg
from config import get_settings

_settings = get_settings()
_pool: asyncpg.Pool | None = None


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not initialized: call init_db() first")
    return _pool


async def init_db():
    """Create connection pool and table. Call once at startup."""
    global _pool
    url = _settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    _pool = await asyncpg.create_pool(url, min_size=1, max_size=10, command_timeout=60)
    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_tenant (
                discord_sub TEXT PRIMARY KEY,
                discord_username TEXT,
                wallet_id TEXT NOT NULL,
                tenant_token TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)


async def close_db():
    """Close the connection pool. Call on app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_tenant_by_discord_sub(discord_sub: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT wallet_id, tenant_token, discord_username FROM user_tenant WHERE discord_sub = $1",
            discord_sub,
        )
    if not row:
        return None
    return {
        "wallet_id": row["wallet_id"],
        "tenant_token": row["tenant_token"],
        "discord_username": row["discord_username"],
    }


async def set_tenant_for_user(
    discord_sub: str,
    discord_username: str | None,
    wallet_id: str,
    tenant_token: str | None = None,
):
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_tenant (discord_sub, discord_username, wallet_id, tenant_token, updated_at)
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (discord_sub) DO UPDATE SET
                discord_username = EXCLUDED.discord_username,
                wallet_id = EXCLUDED.wallet_id,
                tenant_token = EXCLUDED.tenant_token,
                updated_at = NOW()
            """,
            discord_sub,
            discord_username or "",
            wallet_id,
            tenant_token or "",
        )


async def list_users(limit: int = 500) -> list[dict]:
    """List all user_tenant rows for admin dashboard."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT discord_sub, discord_username, wallet_id, created_at, updated_at
            FROM user_tenant
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit,
        )
    return [
        {
            "discord_sub": r["discord_sub"],
            "discord_username": r["discord_username"] or "",
            "wallet_id": r["wallet_id"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
        }
        for r in rows
    ]


async def count_users() -> int:
    """Total number of registered users."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        return (await conn.fetchval("SELECT COUNT(*) FROM user_tenant")) or 0
