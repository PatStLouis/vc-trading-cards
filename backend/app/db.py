"""Async PostgreSQL store for discord_sub -> tenant (wallet_id, token) mapping."""
import re
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
        await conn.execute("ALTER TABLE card_sets ADD COLUMN IF NOT EXISTS set_type TEXT")
        await conn.execute("ALTER TABLE card_sets ADD COLUMN IF NOT EXISTS card_back_path TEXT")
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
        await conn.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS photograph TEXT")
        await conn.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS artist TEXT")
        await conn.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS band TEXT")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_collection (
                discord_sub TEXT NOT NULL,
                card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                credential_id TEXT,
                synced_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (discord_sub, card_id)
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_collection_card_id ON user_collection(card_id)"
        )
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS webauthn_credentials (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                discord_sub TEXT NOT NULL REFERENCES user_tenant(discord_sub) ON DELETE CASCADE,
                credential_id BYTEA NOT NULL UNIQUE,
                public_key BYTEA NOT NULL,
                sign_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webauthn_credentials_discord_sub ON webauthn_credentials(discord_sub)"
        )
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_issued_cards (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                discord_sub TEXT NOT NULL,
                issued_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_issued_cards_discord_sub ON admin_issued_cards(discord_sub)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_issued_cards_card_id ON admin_issued_cards(card_id)"
        )


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

async def count_card_sets() -> int:
    """Total number of card sets."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        return (await conn.fetchval("SELECT COUNT(*) FROM card_sets")) or 0


async def count_cards_total() -> int:
    """Total number of cards across all sets."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        return (await conn.fetchval("SELECT COUNT(*) FROM cards")) or 0


async def list_card_sets() -> list[dict]:
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, slug, description, set_type, card_back_path, created_at, updated_at FROM card_sets ORDER BY name"
        )
    return [
        {
            "id": str(r["id"]),
            "name": r["name"] or "",
            "slug": r["slug"] or "",
            "description": r["description"] or "",
            "set_type": r.get("set_type") or "",
            "card_back_path": r.get("card_back_path") or "",
            "created_at": _format_date(r["created_at"]),
            "updated_at": _format_date(r["updated_at"]),
        }
        for r in rows
    ]


def _slug_from_name(name: str) -> str:
    """Derive URL-friendly slug from name: lowercase, spaces to dashes, strip non-alphanumeric."""
    s = (name or "").strip().lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s or "set"


async def create_card_set(
    name: str, slug: str, description: str = "", set_type: str = "", card_back_path: str = ""
) -> dict | None:
    pool = _get_pool()
    effective_slug = (slug or "").strip() or _slug_from_name(name)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO card_sets (name, slug, description, set_type, card_back_path, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING id, name, slug, description, set_type, card_back_path, created_at, updated_at
            """,
            name.strip(),
            effective_slug,
            (description or "").strip(),
            (set_type or "").strip(),
            (card_back_path or "").strip(),
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "slug": row["slug"],
        "description": row["description"] or "",
        "set_type": row.get("set_type") or "",
        "card_back_path": row.get("card_back_path") or "",
        "created_at": _format_date(row["created_at"]),
        "updated_at": _format_date(row["updated_at"]),
    }


async def get_card_set(set_id: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name, slug, description, set_type, card_back_path, created_at, updated_at FROM card_sets WHERE id = $1",
            set_id,
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "slug": row["slug"],
        "description": row["description"] or "",
        "set_type": row.get("set_type") or "",
        "card_back_path": row.get("card_back_path") or "",
        "created_at": _format_date(row["created_at"]),
        "updated_at": _format_date(row["updated_at"]),
    }


async def update_card_set(
    set_id: str,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    set_type: str | None = None,
    card_back_path: str | None = None,
) -> dict | None:
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
    if set_type is not None:
        updates.append(f"set_type = ${i}")
        values.append(set_type.strip())
        i += 1
    if card_back_path is not None:
        updates.append(f"card_back_path = ${i}")
        values.append(card_back_path.strip())
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
            SELECT id, set_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, created_at, updated_at
            FROM cards WHERE set_id = $1 ORDER BY number, name
            """,
            set_id,
        )
    return [_row_to_card(r) for r in rows]


def _row_to_card(row) -> dict:
    """Build card dict from a DB row (supports optional photograph, artist, band, card_back_path from set join)."""
    out = {
        "id": str(row["id"]),
        "set_id": str(row["set_id"]),
        "name": row["name"] or "",
        "number": row["number"] or "",
        "rarity": row["rarity"] or "common",
        "set_name": row["set_name"] or "",
        "quote": row.get("quote") or "",
        "artwork": row.get("artwork") or "",
        "image_path": row["image_path"] or "",
        "photograph": row.get("photograph") or "",
        "artist": row.get("artist") or "",
        "band": row.get("band") or "",
        "types": list(row["types"]) if row.get("types") else ["TradingCard"],
        "subtypes": row.get("subtypes") or "trading-cards",
        "supertype": row.get("supertype") or "trading-card",
        "created_at": _format_date(row["created_at"]),
        "updated_at": _format_date(row["updated_at"]),
    }
    if row.get("card_back_path") is not None:
        out["card_back_path"] = row.get("card_back_path") or ""
    return out


async def create_card(
    set_id: str,
    name: str,
    number: str = "",
    rarity: str = "common",
    set_name: str = "",
    quote: str = "",
    artwork: str = "",
    image_path: str = "",
    photograph: str = "",
    artist: str = "",
    band: str = "",
    types: list[str] | None = None,
    subtypes: str = "trading-cards",
    supertype: str = "trading-card",
) -> dict | None:
    pool = _get_pool()
    types_arr = types or ["TradingCard"]
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO cards (set_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, NOW())
            RETURNING id, set_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, created_at, updated_at
            """,
            set_id,
            name.strip(),
            number.strip(),
            (rarity or "common").strip(),
            set_name.strip(),
            quote.strip(),
            artwork.strip(),
            image_path.strip(),
            photograph.strip(),
            artist.strip(),
            band.strip(),
            types_arr,
            (subtypes or "trading-cards").strip(),
            (supertype or "trading-card").strip(),
        )
    if not row:
        return None
    return _row_to_card(row)


async def get_card(card_id: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, set_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, created_at, updated_at
            FROM cards WHERE id = $1
            """,
            card_id,
        )
    if not row:
        return None
    return _row_to_card(row)


async def update_card(
    card_id: str,
    name: str | None = None,
    number: str | None = None,
    rarity: str | None = None,
    set_name: str | None = None,
    quote: str | None = None,
    artwork: str | None = None,
    image_path: str | None = None,
    photograph: str | None = None,
    artist: str | None = None,
    band: str | None = None,
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
    if photograph is not None:
        updates.append(f"photograph = ${i}")
        values.append(photograph.strip())
        i += 1
    if artist is not None:
        updates.append(f"artist = ${i}")
        values.append(artist.strip())
        i += 1
    if band is not None:
        updates.append(f"band = ${i}")
        values.append(band.strip())
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


# ---- Admin: issue card to user ----

async def admin_issue_card_to_user(card_id: str, discord_sub: str) -> dict | None:
    """Record that an admin issued a card to a user. Returns the issuance row { id, card_id, discord_sub, issued_at } or None."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO admin_issued_cards (card_id, discord_sub)
            VALUES ($1::uuid, $2)
            RETURNING id, card_id, discord_sub, issued_at
            """,
            card_id,
            discord_sub.strip(),
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "card_id": str(row["card_id"]),
        "discord_sub": row["discord_sub"],
        "issued_at": _format_date(row["issued_at"]),
    }


async def list_admin_issued_for_user(discord_sub: str) -> list[dict]:
    """List admin-issued cards for a user. Returns list of card-like dicts for wallet merge (id = issuance id, plus card fields)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.id AS issued_id, c.id AS card_id, c.set_id, c.name, c.number, c.rarity, c.set_name,
                   c.quote, c.artwork, c.image_path, c.types, c.subtypes, c.supertype
            FROM admin_issued_cards a
            JOIN cards c ON c.id = a.card_id
            WHERE a.discord_sub = $1
            ORDER BY a.issued_at DESC
            """,
            discord_sub,
        )
    out = []
    for r in rows:
        out.append({
            "id": str(r["issued_id"]),
            "name": r["name"] or "Card",
            "rarity": (r["rarity"] or "common").lower().replace(" ", " "),
            "set": r["set_name"] or "",
            "number": r["number"] or "",
            "quote": r.get("quote") or "",
            "artwork": r.get("artwork") or "",
            "types": list(r["types"]) if r.get("types") else ["TradingCard"],
            "subtypes": r.get("subtypes") or "trading-cards",
            "supertype": r.get("supertype") or "trading-card",
            "image_url": r.get("artwork") or r.get("image_path") or "",
        })
    return out


async def get_admin_issued_card_ids(discord_sub: str) -> list[str]:
    """Return list of card_id (UUID strings) for admin-issued cards for this user. For sync to public collection."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT card_id FROM admin_issued_cards WHERE discord_sub = $1",
            discord_sub,
        )
    return [str(r["card_id"]) for r in rows]


# ---- Public catalog & user collection ----

async def get_card_id_by_set_and_name(set_name: str, card_name: str) -> str | None:
    """Find a card id by set name and card name (for matching credentials to catalog)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id FROM cards
            WHERE COALESCE(set_name, '') = $1 AND name = $2
            LIMIT 1
            """,
            (set_name or "").strip(),
            (card_name or "").strip(),
        )
    return str(row["id"]) if row else None


async def sync_user_collection(discord_sub: str, card_credential_pairs: list[tuple[str, str]]) -> None:
    """Replace user's collection with the given list of (card_id, credential_id)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM user_collection WHERE discord_sub = $1", discord_sub)
        for card_id, cred_id in card_credential_pairs:
            await conn.execute(
                """
                INSERT INTO user_collection (discord_sub, card_id, credential_id, synced_at)
                VALUES ($1, $2::uuid, $3, NOW())
                ON CONFLICT (discord_sub, card_id) DO UPDATE SET credential_id = $3, synced_at = NOW()
                """,
                discord_sub,
                card_id,
                cred_id or "",
            )


async def list_owners_for_card(card_id: str) -> list[dict]:
    """List users who have this card in their (synced) collection. Public."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.discord_sub, u.discord_username
            FROM user_collection c
            JOIN user_tenant u ON u.discord_sub = c.discord_sub
            WHERE c.card_id = $1::uuid
            ORDER BY u.discord_username
            """,
            card_id,
        )
    return [
        {"discord_sub": r["discord_sub"], "username": r["discord_username"] or r["discord_sub"]}
        for r in rows
    ]


async def list_collection_for_user(discord_sub: str) -> list[dict]:
    """List cards in a user's (synced) collection. Returns card dicts with card_back_path from set. Public."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.id, c.set_id, c.name, c.number, c.rarity, c.set_name, c.quote, c.artwork,
                   c.image_path, c.photograph, c.artist, c.band, c.types, c.subtypes, c.supertype,
                   c.created_at, c.updated_at, s.card_back_path
            FROM user_collection uc
            JOIN cards c ON c.id = uc.card_id
            LEFT JOIN card_sets s ON s.id = c.set_id
            WHERE uc.discord_sub = $1
            ORDER BY c.set_name, c.number, c.name
            """,
            discord_sub,
        )
    return [_row_to_card(r) for r in rows]


async def search_users(q: str, limit: int = 50) -> list[dict]:
    """Search users by username (case-insensitive). Public. Returns minimal profile + card count."""
    pool = _get_pool()
    pattern = f"%{(q or '').strip()}%" if (q or '').strip() else "%"
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.discord_sub, u.discord_username,
                   (SELECT COUNT(*) FROM user_collection c WHERE c.discord_sub = u.discord_sub) AS collection_count
            FROM user_tenant u
            WHERE u.discord_username ILIKE $1
            ORDER BY u.discord_username
            LIMIT $2
            """,
            pattern,
            limit,
        )
    return [
        {
            "discord_sub": r["discord_sub"],
            "username": r["discord_username"] or r["discord_sub"],
            "collection_count": r["collection_count"] or 0,
        }
        for r in rows
    ]


async def get_user_public(discord_sub: str) -> dict | None:
    """Get public user profile by discord_sub. Returns username and collection count."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.discord_sub, u.discord_username,
                   (SELECT COUNT(*) FROM user_collection c WHERE c.discord_sub = u.discord_sub) AS collection_count
            FROM user_tenant u
            WHERE u.discord_sub = $1
            """,
            discord_sub,
        )
    if not row:
        return None
    return {
        "discord_sub": row["discord_sub"],
        "username": row["discord_username"] or row["discord_sub"],
        "collection_count": row["collection_count"] or 0,
    }


# ---- WebAuthn credentials ----

async def webauthn_save_credential(
    discord_sub: str,
    credential_id: bytes,
    public_key: bytes,
    sign_count: int = 0,
) -> None:
    """Store a WebAuthn credential after successful registration."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO webauthn_credentials (discord_sub, credential_id, public_key, sign_count)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (credential_id) DO UPDATE SET public_key = $3, sign_count = $4
            """,
            discord_sub,
            credential_id,
            public_key,
            sign_count,
        )


async def webauthn_get_credential_by_id(credential_id: bytes) -> dict | None:
    """Look up a credential by credential_id (raw bytes). Returns discord_sub, public_key, sign_count."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT discord_sub, public_key, sign_count FROM webauthn_credentials WHERE credential_id = $1",
            credential_id,
        )
    if not row:
        return None
    return {
        "discord_sub": row["discord_sub"],
        "public_key": bytes(row["public_key"]),
        "sign_count": row["sign_count"] or 0,
    }


async def webauthn_update_sign_count(credential_id: bytes, new_sign_count: int) -> None:
    """Update sign_count after successful authentication."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE webauthn_credentials SET sign_count = $1 WHERE credential_id = $2",
            new_sign_count,
            credential_id,
        )


async def webauthn_list_credentials_for_user(discord_sub: str) -> list[dict]:
    """List credential ids for a user (for exclude_credentials in registration)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT credential_id, created_at FROM webauthn_credentials WHERE discord_sub = $1",
            discord_sub,
        )
    return [
        {"credential_id": bytes(r["credential_id"]), "created_at": _format_date(r["created_at"])}
        for r in rows
    ]
