"""Async PostgreSQL store for discord_sub -> tenant (wallet_id, token) mapping."""
import asyncpg
from datetime import timezone
from config import get_settings

_settings = get_settings()
_pool: asyncpg.Pool | None = None


def _get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database not initialized: call init_db() first")
    return _pool


def _format_date(dt):
    """Format datetime as YYYY-MM-DD HH:MM:SSZ (UTC, no microseconds)."""
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    utc = dt.astimezone(timezone.utc)
    return utc.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%SZ")


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
                wallet_key TEXT,
                tenant_token TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # Add wallet_key for existing deployments (no-op if already present)
        await conn.execute("""
            ALTER TABLE user_tenant ADD COLUMN IF NOT EXISTS wallet_key TEXT
        """)

    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS card_sets (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                set_id UUID NOT NULL REFERENCES card_sets(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                number TEXT,
                rarity TEXT DEFAULT 'common',
                set_name TEXT,
                quote TEXT,
                artwork TEXT,
                image_path TEXT,
                types TEXT[] DEFAULT ARRAY['TradingCard'],
                subtypes TEXT DEFAULT 'trading-cards',
                supertype TEXT DEFAULT 'trading-card',
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
            "SELECT wallet_id, wallet_key, tenant_token, discord_username FROM user_tenant WHERE discord_sub = $1",
            discord_sub,
        )
    if not row:
        return None
    return {
        "wallet_id": row["wallet_id"],
        "wallet_key": row["wallet_key"],
        "tenant_token": row["tenant_token"],
        "discord_username": row["discord_username"],
    }


async def set_tenant_for_user(
    discord_sub: str,
    discord_username: str | None,
    wallet_id: str,
    tenant_token: str | None = None,
    wallet_key: str | None = None,
):
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_tenant (discord_sub, discord_username, wallet_id, wallet_key, tenant_token, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (discord_sub) DO UPDATE SET
                discord_username = EXCLUDED.discord_username,
                wallet_id = EXCLUDED.wallet_id,
                wallet_key = COALESCE(EXCLUDED.wallet_key, user_tenant.wallet_key),
                tenant_token = EXCLUDED.tenant_token,
                updated_at = NOW()
            """,
            discord_sub,
            discord_username or "",
            wallet_id,
            wallet_key or "",
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
            "created_at": _format_date(r["created_at"]),
            "updated_at": _format_date(r["updated_at"]),
        }
        for r in rows
    ]


async def count_users() -> int:
    """Total number of registered users."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        return (await conn.fetchval("SELECT COUNT(*) FROM user_tenant")) or 0


# ---- Card sets and cards (admin) ----

async def list_card_sets() -> list[dict]:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, slug, description, created_at, updated_at FROM card_sets ORDER BY name"
        )
    return [
        {
            "id": str(r["id"]),
            "name": r["name"] or "",
            "slug": r["slug"] or "",
            "description": r["description"] or "",
            "created_at": _format_date(r["created_at"]),
            "updated_at": _format_date(r["updated_at"]),
        }
        for r in rows
    ]


async def create_card_set(name: str, slug: str, description: str = "") -> dict | None:
    pool = _get_pool()
    effective_slug = (slug or "").strip() or name.strip().lower().replace(" ", "-")
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO card_sets (name, slug, description, updated_at)
            VALUES ($1, $2, $3, NOW())
            RETURNING id, name, slug, description, created_at, updated_at
            """,
            name.strip(),
            effective_slug,
            (description or "").strip(),
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "slug": row["slug"],
        "description": row["description"] or "",
        "created_at": _format_date(row["created_at"]),
        "updated_at": _format_date(row["updated_at"]),
    }


async def get_card_set(set_id: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, slug, description, created_at, updated_at FROM card_sets WHERE id = $1",
            set_id,
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "slug": row["slug"],
        "description": row["description"] or "",
        "created_at": _format_date(row["created_at"]),
        "updated_at": _format_date(row["updated_at"]),
    }


async def update_card_set(set_id: str, name: str | None = None, slug: str | None = None, description: str | None = None) -> dict | None:
    pool = _get_pool()
    updates = []
    values = []
    i = 1
    if name is not None:
        updates.append(f"name = ${i}")
        values.append(name.strip())
        i += 1
    if slug is not None:
        updates.append(f"slug = ${i}")
        values.append(slug.strip())
        i += 1
    if description is not None:
        updates.append(f"description = ${i}")
        values.append(description.strip())
        i += 1
    if not updates:
        return await get_card_set(set_id)
    updates.append("updated_at = NOW()")
    values.append(set_id)
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE card_sets SET {', '.join(updates)} WHERE id = ${i}",
            *values,
        )
    return await get_card_set(set_id)


async def delete_card_set(set_id: str) -> bool:
    pool = _get_pool()
    async with pool.acquire() as conn:
        n = await conn.execute("DELETE FROM card_sets WHERE id = $1", set_id)
    return n and "DELETE 1" in n


async def list_cards(set_id: str) -> list[dict]:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, set_id, name, number, rarity, set_name, quote, artwork, image_path, types, subtypes, supertype, created_at, updated_at
            FROM cards WHERE set_id = $1 ORDER BY number, name
            """,
            set_id,
        )
    return [
        {
            "id": str(r["id"]),
            "set_id": str(r["set_id"]),
            "name": r["name"] or "",
            "number": r["number"] or "",
            "rarity": r["rarity"] or "common",
            "set_name": r["set_name"] or "",
            "quote": r["quote"] or "",
            "artwork": r["artwork"] or "",
            "image_path": r["image_path"] or "",
            "types": list(r["types"]) if r["types"] else ["TradingCard"],
            "subtypes": r["subtypes"] or "trading-cards",
            "supertype": r["supertype"] or "trading-card",
            "created_at": _format_date(r["created_at"]),
            "updated_at": _format_date(r["updated_at"]),
        }
        for r in rows
    ]


async def create_card(
    set_id: str,
    name: str,
    number: str = "",
    rarity: str = "common",
    set_name: str = "",
    quote: str = "",
    artwork: str = "",
    image_path: str = "",
    types: list[str] | None = None,
    subtypes: str = "trading-cards",
    supertype: str = "trading-card",
) -> dict | None:
    pool = _get_pool()
    types_arr = types or ["TradingCard"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO cards (set_id, name, number, rarity, set_name, quote, artwork, image_path, types, subtypes, supertype, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
            RETURNING id, set_id, name, number, rarity, set_name, quote, artwork, image_path, types, subtypes, supertype, created_at, updated_at
            """,
            set_id,
            name.strip(),
            number.strip(),
            (rarity or "common").strip(),
            set_name.strip(),
            quote.strip(),
            artwork.strip(),
            image_path.strip(),
            types_arr,
            (subtypes or "trading-cards").strip(),
            (supertype or "trading-card").strip(),
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "set_id": str(row["set_id"]),
        "name": row["name"],
        "number": row["number"] or "",
        "rarity": row["rarity"] or "common",
        "set_name": row["set_name"] or "",
        "quote": row["quote"] or "",
        "artwork": row["artwork"] or "",
        "image_path": row["image_path"] or "",
        "types": list(row["types"]) if row["types"] else ["TradingCard"],
        "subtypes": row["subtypes"] or "trading-cards",
        "supertype": row["supertype"] or "trading-card",
        "created_at": _format_date(row["created_at"]),
        "updated_at": _format_date(row["updated_at"]),
    }


async def get_card(card_id: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, set_id, name, number, rarity, set_name, quote, artwork, image_path, types, subtypes, supertype, created_at, updated_at
            FROM cards WHERE id = $1
            """,
            card_id,
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "set_id": str(row["set_id"]),
        "name": row["name"] or "",
        "number": row["number"] or "",
        "rarity": row["rarity"] or "common",
        "set_name": row["set_name"] or "",
        "quote": row["quote"] or "",
        "artwork": row["artwork"] or "",
        "image_path": row["image_path"] or "",
        "types": list(row["types"]) if row["types"] else ["TradingCard"],
        "subtypes": row["subtypes"] or "trading-cards",
        "supertype": row["supertype"] or "trading-card",
        "created_at": _format_date(row["created_at"]),
        "updated_at": _format_date(row["updated_at"]),
    }


async def update_card(
    card_id: str,
    name: str | None = None,
    number: str | None = None,
    rarity: str | None = None,
    set_name: str | None = None,
    quote: str | None = None,
    artwork: str | None = None,
    image_path: str | None = None,
    types: list[str] | None = None,
    subtypes: str | None = None,
    supertype: str | None = None,
) -> dict | None:
    pool = _get_pool()
    updates = []
    values = []
    i = 1
    if name is not None:
        updates.append(f"name = ${i}")
        values.append(name.strip())
        i += 1
    if number is not None:
        updates.append(f"number = ${i}")
        values.append(number.strip())
        i += 1
    if rarity is not None:
        updates.append(f"rarity = ${i}")
        values.append(rarity.strip())
        i += 1
    if set_name is not None:
        updates.append(f"set_name = ${i}")
        values.append(set_name.strip())
        i += 1
    if quote is not None:
        updates.append(f"quote = ${i}")
        values.append(quote.strip())
        i += 1
    if artwork is not None:
        updates.append(f"artwork = ${i}")
        values.append(artwork.strip())
        i += 1
    if image_path is not None:
        updates.append(f"image_path = ${i}")
        values.append(image_path.strip())
        i += 1
    if types is not None:
        updates.append(f"types = ${i}")
        values.append(types)
        i += 1
    if subtypes is not None:
        updates.append(f"subtypes = ${i}")
        values.append(subtypes.strip())
        i += 1
    if supertype is not None:
        updates.append(f"supertype = ${i}")
        values.append(supertype.strip())
        i += 1
    if not updates:
        return await get_card(card_id)
    updates.append("updated_at = NOW()")
    values.append(card_id)
    async with pool.acquire() as conn:
        await conn.execute(
            f"UPDATE cards SET {', '.join(updates)} WHERE id = ${i}",
            *values,
        )
    return await get_card(card_id)


async def delete_card(card_id: str) -> bool:
    pool = _get_pool()
    async with pool.acquire() as conn:
        n = await conn.execute("DELETE FROM cards WHERE id = $1", card_id)
    return n and "DELETE 1" in n
