"""Async PostgreSQL store: users, user_accounts (multi-provider auth), user_tenant (wallet), cards, collection."""
import os
import re
import uuid
import asyncpg
from datetime import timezone
from urllib.parse import urlparse, parse_qs
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


def _card_back_path_if_exists(rel_path: str | None) -> str:
    """Return rel_path only if the file exists under upload_dir; else ''. Avoids 404s for missing set backs."""
    if not (rel_path or "").strip():
        return ""
    base = os.path.abspath(_settings.upload_dir)
    full = os.path.normpath(os.path.join(base, rel_path))
    if not full.startswith(base):
        return ""
    return rel_path if os.path.isfile(full) else ""


async def init_db():
    """Create connection pool and tables. Call once at startup. Creates tables only if they don't exist; adds new columns with ALTER. Does not drop or truncate any tables."""
    global _pool
    url = _settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    _pool = await asyncpg.create_pool(url, min_size=1, max_size=10, command_timeout=60)

    async with _pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                poser_username TEXT UNIQUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS featured_card_ids UUID[] DEFAULT '{}'")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_headline TEXT")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_bio TEXT")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_song_url TEXT")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_song_upload_path TEXT")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_accent_color TEXT")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_spotify_url TEXT")
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_issued_seen_at TIMESTAMPTZ")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_accounts (
                user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                provider TEXT NOT NULL,
                provider_user_id TEXT NOT NULL,
                provider_username TEXT,
                provider_avatar TEXT,
                provider_discriminator TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(provider, provider_user_id)
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_accounts_user_id ON user_accounts(user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_accounts_provider ON user_accounts(provider, provider_user_id)")
        await conn.execute("ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS provider_avatar TEXT")
        await conn.execute("ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS provider_discriminator TEXT")
        await conn.execute("ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS provider_banner TEXT")
        await conn.execute("ALTER TABLE user_accounts ADD COLUMN IF NOT EXISTS provider_accent_color TEXT")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_tenant (
                user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
                wallet_id TEXT NOT NULL,
                wallet_key TEXT,
                tenant_token TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
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
        await conn.execute("ALTER TABLE cards ADD COLUMN IF NOT EXISTS card_id TEXT UNIQUE")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS card_image_data (
                card_id UUID PRIMARY KEY REFERENCES cards(id) ON DELETE CASCADE,
                content_type TEXT NOT NULL DEFAULT 'image/png',
                data BYTEA NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_collection (
                user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                credential_id TEXT,
                synced_at TIMESTAMPTZ DEFAULT NOW(),
                PRIMARY KEY (user_id, card_id)
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_collection_card_id ON user_collection(card_id)"
        )
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS webauthn_credentials (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                credential_id BYTEA NOT NULL UNIQUE,
                public_key BYTEA NOT NULL,
                sign_count INTEGER NOT NULL DEFAULT 0,
                credential_device_type TEXT,
                credential_backed_up BOOLEAN,
                aaguid TEXT,
                attestation_format TEXT,
                registered_name TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_webauthn_credentials_user_id ON webauthn_credentials(user_id)"
        )
        await conn.execute("ALTER TABLE webauthn_credentials ADD COLUMN IF NOT EXISTS registered_name TEXT")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_issued_cards (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                issued_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_issued_cards_user_id ON admin_issued_cards(user_id)"
        )
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_admin_issued_cards_card_id ON admin_issued_cards(card_id)"
        )
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS card_ledger (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                event_type TEXT NOT NULL,
                card_id UUID NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                to_user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                from_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
                actor_user_id UUID REFERENCES users(user_id) ON DELETE SET NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                metadata JSONB
            )
        """)
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_card_ledger_card_id ON card_ledger(card_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_card_ledger_to_user_id ON card_ledger(to_user_id)")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_card_ledger_created_at ON card_ledger(created_at DESC)")
        # Backfill ledger from existing admin_issued_cards (one event per issuance, actor unknown)
        await conn.execute("""
            INSERT INTO card_ledger (event_type, card_id, to_user_id, from_user_id, actor_user_id, metadata)
            SELECT 'card.issued', a.card_id, a.user_id, NULL, NULL, jsonb_build_object('card_id', a.card_id, 'to_user_id', a.user_id)
            FROM admin_issued_cards a
            WHERE NOT EXISTS (
                SELECT 1 FROM card_ledger l
                WHERE l.card_id = a.card_id AND l.to_user_id = a.user_id AND l.event_type = 'card.issued'
            )
        """)
        # Backfill user_collection from admin_issued_cards so public Explore is ledger-based
        await conn.execute("""
            INSERT INTO user_collection (user_id, card_id, credential_id, synced_at)
            SELECT a.user_id, a.card_id, '', NOW()
            FROM admin_issued_cards a
            WHERE NOT EXISTS (
                SELECT 1 FROM user_collection uc
                WHERE uc.user_id = a.user_id AND uc.card_id = a.card_id
            )
        """)


async def close_db():
    """Close the connection pool. Call on app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# ---- Multi-provider auth (users, user_accounts) ----

async def user_exists(user_id: str) -> bool:
    """Return True if user_id exists in users table."""
    if not user_id or not str(user_id).strip():
        return False
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM users WHERE user_id = $1::uuid",
            user_id,
        )
    return row is not None


async def ensure_user_exists(user_id: str) -> None:
    """Ensure a row exists in users for user_id (e.g. after DB reset with stale session). Idempotent."""
    if not user_id or not str(user_id).strip():
        return
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id) VALUES ($1::uuid) ON CONFLICT (user_id) DO NOTHING",
            user_id,
        )


async def get_user_created_at(user_id: str) -> str | None:
    """Return users.created_at (formatted), or None."""
    if not user_id or not str(user_id).strip():
        return None
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT created_at FROM users WHERE user_id = $1::uuid",
            user_id,
        )
    return _format_date(row["created_at"]) if row and row.get("created_at") else None


async def get_user_created_at_raw(user_id: str):
    """Return users.created_at as timezone-aware datetime (UTC), or None. Used for is_first_login."""
    if not user_id or not str(user_id).strip():
        return None
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT created_at FROM users WHERE user_id = $1::uuid",
            user_id,
        )
    if not row or not row.get("created_at"):
        return None
    dt = row["created_at"]
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def get_user_by_provider(provider: str, provider_user_id: str) -> str | None:
    """Return user_id if (provider, provider_user_id) exists, else None."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM user_accounts WHERE provider = $1 AND provider_user_id = $2",
            provider,
            provider_user_id.strip(),
        )
    return str(row["user_id"]) if row else None


async def get_or_create_user_by_provider(
    provider: str,
    provider_user_id: str,
    provider_username: str = "",
    provider_avatar: str | None = None,
    provider_discriminator: str | None = None,
    provider_banner: str | None = None,
    provider_accent_color: str | None = None,
) -> str:
    """Get or create user for (provider, provider_user_id). Returns user_id."""
    pool = _get_pool()
    existing = await get_user_by_provider(provider, provider_user_id)
    if existing:
        await ensure_poser_username(existing)
        return existing
    async with pool.acquire() as conn:
        user_id = await conn.fetchval(
            "INSERT INTO users DEFAULT VALUES RETURNING user_id"
        )
        await conn.execute(
            """
            INSERT INTO user_accounts (user_id, provider, provider_user_id, provider_username, provider_avatar, provider_discriminator, provider_banner, provider_accent_color)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            user_id,
            provider,
            provider_user_id.strip(),
            (provider_username or "").strip(),
            (provider_avatar or "").strip() or None,
            (provider_discriminator or "").strip() or None,
            (provider_banner or "").strip() or None,
            (provider_accent_color or "").strip() or None,
        )
    await ensure_poser_username(str(user_id))
    return str(user_id)


async def add_account_binding(
    user_id: str,
    provider: str,
    provider_user_id: str,
    provider_username: str = "",
    provider_avatar: str | None = None,
    provider_discriminator: str | None = None,
    provider_banner: str | None = None,
    provider_accent_color: str | None = None,
) -> str | None:
    """
    Add provider account to user. Returns None if success.
    Returns 'conflict' if (provider, provider_user_id) already linked to another user (merge needed).
    Returns 'duplicate' if already linked to this user (profile updated with latest username/avatar/discriminator/banner/accent).
    """
    pool = _get_pool()
    provider_user_id = provider_user_id.strip()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id FROM user_accounts WHERE provider = $1 AND provider_user_id = $2",
            provider,
            provider_user_id,
        )
        if row:
            existing_user = str(row["user_id"])
            if existing_user == user_id:
                await conn.execute(
                    """
                    UPDATE user_accounts SET provider_username = $1, provider_avatar = $2, provider_discriminator = $3, provider_banner = $4, provider_accent_color = $5
                    WHERE provider = $6 AND provider_user_id = $7
                    """,
                    (provider_username or "").strip(),
                    (provider_avatar or "").strip() or None,
                    (provider_discriminator or "").strip() or None,
                    (provider_banner or "").strip() or None,
                    (provider_accent_color or "").strip() or None,
                    provider,
                    provider_user_id,
                )
                return "duplicate"
            return "conflict"
        await conn.execute(
            """
            INSERT INTO user_accounts (user_id, provider, provider_user_id, provider_username, provider_avatar, provider_discriminator, provider_banner, provider_accent_color)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8)
            """,
            user_id,
            provider,
            provider_user_id,
            (provider_username or "").strip(),
            (provider_avatar or "").strip() or None,
            (provider_discriminator or "").strip() or None,
            (provider_banner or "").strip() or None,
            (provider_accent_color or "").strip() or None,
        )
    await ensure_poser_username(user_id)
    return None


async def merge_users(keep_user_id: str, drop_user_id: str) -> None:
    """Merge drop_user into keep_user: move all data, update bindings, delete drop_user."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        # Move user_tenant (drop loses tenant; keep keeps)
        await conn.execute(
            "DELETE FROM user_tenant WHERE user_id = $1::uuid", drop_user_id
        )
        # Move user_collection
        await conn.execute(
            """
            UPDATE user_collection SET user_id = $1::uuid
            WHERE user_id = $2::uuid
            """,
            keep_user_id,
            drop_user_id,
        )
        # Move admin_issued_cards
        await conn.execute(
            """
            UPDATE admin_issued_cards SET user_id = $1::uuid
            WHERE user_id = $2::uuid
            """,
            keep_user_id,
            drop_user_id,
        )
        # Move webauthn_credentials
        await conn.execute(
            """
            UPDATE webauthn_credentials SET user_id = $1::uuid
            WHERE user_id = $2::uuid
            """,
            keep_user_id,
            drop_user_id,
        )
        # Move user_accounts from drop to keep (repoint provider accounts)
        await conn.execute(
            """
            UPDATE user_accounts SET user_id = $1::uuid
            WHERE user_id = $2::uuid
            """,
            keep_user_id,
            drop_user_id,
        )
        # Delete drop user
        await conn.execute("DELETE FROM users WHERE user_id = $1::uuid", drop_user_id)


async def get_user_accounts(user_id: str) -> list[dict]:
    """List linked accounts for user."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT provider, provider_user_id, provider_username, provider_avatar, provider_discriminator, provider_banner, provider_accent_color
            FROM user_accounts WHERE user_id = $1::uuid ORDER BY provider
            """,
            user_id,
        )
    return [
        {
            "provider": r["provider"],
            "provider_user_id": r["provider_user_id"],
            "provider_username": r["provider_username"] or r["provider_user_id"],
            "provider_avatar": r["provider_avatar"] if r.get("provider_avatar") else None,
            "provider_discriminator": r["provider_discriminator"] if r.get("provider_discriminator") else None,
            "provider_banner": r["provider_banner"] if r.get("provider_banner") else None,
            "provider_accent_color": r["provider_accent_color"] if r.get("provider_accent_color") else None,
        }
        for r in rows
    ]


async def update_discord_profile_for_user(
    user_id: str,
    provider_username: str,
    provider_avatar: str | None = None,
    provider_discriminator: str | None = None,
    provider_banner: str | None = None,
    provider_accent_color: str | None = None,
) -> bool:
    """Update Discord account profile (username, avatar, discriminator, banner, accent_color) for the given user. Returns True if a row was updated."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE user_accounts
            SET provider_username = $1, provider_avatar = $2, provider_discriminator = $3, provider_banner = $4, provider_accent_color = $5
            WHERE user_id = $6::uuid AND provider = 'discord'
            """,
            (provider_username or "").strip(),
            (provider_avatar or "").strip() or None,
            (provider_discriminator or "").strip() or None,
            (provider_banner or "").strip() or None,
            (provider_accent_color or "").strip() or None,
            user_id,
        )
    return result and "UPDATE 1" in result


async def update_twitch_profile_for_user(
    user_id: str,
    provider_username: str,
    provider_avatar: str | None = None,
) -> bool:
    """Update Twitch account profile (username, profile_image_url stored in provider_avatar). Returns True if a row was updated."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE user_accounts
            SET provider_username = $1, provider_avatar = $2
            WHERE user_id = $3::uuid AND provider = 'twitch'
            """,
            (provider_username or "").strip(),
            (provider_avatar or "").strip() or None,
            user_id,
        )
    return result and "UPDATE 1" in result


async def get_tenant_by_user_id(user_id: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT wallet_id, wallet_key, tenant_token FROM user_tenant WHERE user_id = $1::uuid",
            user_id,
        )
    if not row:
        return None
    return {
        "wallet_id": row["wallet_id"],
        "wallet_key": row["wallet_key"],
        "tenant_token": row["tenant_token"],
    }


async def set_tenant_for_user(
    user_id: str,
    wallet_id: str,
    tenant_token: str | None = None,
    wallet_key: str | None = None,
):
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_tenant (user_id, wallet_id, wallet_key, tenant_token, updated_at)
            VALUES ($1::uuid, $2, $3, $4, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                wallet_id = EXCLUDED.wallet_id,
                wallet_key = COALESCE(EXCLUDED.wallet_key, user_tenant.wallet_key),
                tenant_token = EXCLUDED.tenant_token,
                updated_at = NOW()
            """,
            user_id,
            wallet_id,
            wallet_key or "",
            tenant_token or "",
        )


async def get_tenant_by_discord_sub(discord_sub: str) -> dict | None:
    """Compatibility: resolve discord_sub -> user_id, return tenant. For Discord bot."""
    user_id = await get_user_by_provider("discord", discord_sub)
    if not user_id:
        return None
    return await get_tenant_by_user_id(user_id)


async def list_users(limit: int = 500) -> list[dict]:
    """List all users for admin dashboard (user_id, accounts, wallet_id, created_at)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT u.user_id, u.created_at,
                   t.wallet_id, t.created_at AS tenant_created
            FROM users u
            LEFT JOIN user_tenant t ON t.user_id = u.user_id
            ORDER BY u.created_at DESC
            LIMIT $1
            """,
            limit,
        )
    out = []
    for r in rows:
        accounts = await get_user_accounts(str(r["user_id"]))
        discord = next((a for a in accounts if a["provider"] == "discord"), None)
        out.append({
            "user_id": str(r["user_id"]),
            "discord_sub": discord["provider_user_id"] if discord else "",
            "discord_username": discord["provider_username"] if discord else "",
            "wallet_id": r["wallet_id"] or "",
            "created_at": _format_date(r["created_at"]),
            "updated_at": _format_date(r["tenant_created"]),
        })
    return out


async def count_users() -> int:
    """Total number of registered users."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        return (await conn.fetchval("SELECT COUNT(*) FROM users")) or 0


async def get_registered_discord_ids(discord_ids: list[str]) -> set[str]:
    """Return set of discord provider_user_ids that exist in user_accounts (i.e. registered app users)."""
    if not discord_ids:
        return set()
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT provider_user_id FROM user_accounts
            WHERE provider = 'discord' AND provider_user_id = ANY($1)
            """,
            discord_ids,
        )
        return {r["provider_user_id"] for r in rows}


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
            "card_back_path": _card_back_path_if_exists(r.get("card_back_path")),
            "created_at": _format_date(r["created_at"]),
            "updated_at": _format_date(r["updated_at"]),
        }
        for r in rows
    ]


async def list_card_set_back_paths() -> list[dict]:
    """Return sets that have a card_back_path set (raw from DB, for sync). Use when pulling from URL to know what to fetch."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, card_back_path FROM card_sets WHERE card_back_path IS NOT NULL AND TRIM(card_back_path) != ''"
        )
    return [{"id": str(r["id"]), "card_back_path": (r["card_back_path"] or "").strip()} for r in rows]


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
        "card_back_path": _card_back_path_if_exists(row.get("card_back_path")),
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
            SELECT id, set_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, created_at, updated_at, card_id
            FROM cards WHERE set_id = $1 ORDER BY number, name
            """,
            set_id,
        )
    return [_row_to_card(r) for r in rows]


async def list_cards_with_image_paths() -> list[dict]:
    """Return all cards that have a non-empty image_path (for sync/cache)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, set_id, name, image_path
            FROM cards
            WHERE image_path IS NOT NULL AND TRIM(image_path) != ''
            ORDER BY set_id, number, name
            """
        )
    return [
        {
            "id": str(r["id"]),
            "set_id": str(r["set_id"]),
            "name": r["name"] or "",
            "image_path": (r["image_path"] or "").strip(),
        }
        for r in rows
    ]


async def set_card_image_data(card_id: str, data: bytes, content_type: str = "image/png") -> bool:
    """Upsert image bytes for a card. Used by Push to DB."""
    if not data:
        return False
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO card_image_data (card_id, content_type, data)
            VALUES ($1::uuid, $2, $3)
            ON CONFLICT (card_id) DO UPDATE SET content_type = $2, data = $3
            """,
            card_id,
            content_type or "image/png",
            data,
        )
    return True


async def get_card_image_data(card_id: str) -> tuple[bytes | None, str | None]:
    """Return (data, content_type) for a card's stored image, or (None, None)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT data, content_type FROM card_image_data WHERE card_id = $1::uuid",
            card_id,
        )
    if not row:
        return None, None
    return bytes(row["data"]), (row["content_type"] or "image/png")


async def list_card_ids_with_image_data() -> list[str]:
    """Return card IDs that have blob data in card_image_data (for Pull from DB)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT card_id FROM card_image_data")
    return [str(r["card_id"]) for r in rows]


async def list_cards_with_image_data_and_path() -> list[dict]:
    """Return cards that have both image blob in card_image_data and image_path set (for Pull from DB)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.id, c.image_path
            FROM cards c
            INNER JOIN card_image_data d ON d.card_id = c.id
            WHERE c.image_path IS NOT NULL AND TRIM(c.image_path) != ''
            ORDER BY c.set_id, c.number
            """
        )
    return [{"id": str(r["id"]), "image_path": (r["image_path"] or "").strip()} for r in rows]


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
        "card_id": row.get("card_id") or str(row["id"]),
    }
    if row.get("card_back_path") is not None:
        out["card_back_path"] = _card_back_path_if_exists(row.get("card_back_path"))
    return out


async def create_card(
    set_id: str,
    card_id: str,
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
    name: str = "",
) -> dict | None:
    """Create card. card_id is a unique identifier (e.g. UUID or hash). name defaults to card_id if omitted."""
    pool = _get_pool()
    types_arr = types or ["TradingCard"]
    cid = (card_id or "").strip()
    if not cid:
        return None
    display_name = (name or "").strip() or cid
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO cards (set_id, card_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW())
            RETURNING id, set_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, created_at, updated_at, card_id
            """,
            set_id,
            cid,
            display_name,
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


async def get_card_by_card_id(set_id: str, card_id: str) -> dict | None:
    """Get a card by set_id and logical card_id (e.g. 001_OGSET_NICKARTHUR)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, set_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, created_at, updated_at, card_id
            FROM cards WHERE set_id = $1 AND card_id = $2
            """,
            set_id,
            card_id,
        )
    if not row:
        return None
    return _row_to_card(row)


async def get_card(card_id: str) -> dict | None:
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, set_id, name, number, rarity, set_name, quote, artwork, image_path, photograph, artist, band, types, subtypes, supertype, created_at, updated_at, card_id
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

async def admin_issue_card_to_user(card_id: str, user_id: str) -> dict | None:
    """Record that an admin issued a card to a user. Returns the issuance row { id, card_id, user_id, issued_at } or None."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO admin_issued_cards (card_id, user_id)
            VALUES ($1::uuid, $2::uuid)
            RETURNING id, card_id, user_id, issued_at
            """,
            card_id,
            user_id.strip(),
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "card_id": str(row["card_id"]),
        "user_id": str(row["user_id"]),
        "issued_at": _format_date(row["issued_at"]),
    }


async def list_admin_issued_for_user(user_id: str) -> list[dict]:
    """List admin-issued cards for a user. Returns list of card-like dicts for wallet merge."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT a.id AS issued_id, c.id AS card_id, c.set_id, c.name, c.number, c.rarity, c.set_name,
                   c.quote, c.artwork, c.image_path, c.types, c.subtypes, c.supertype
            FROM admin_issued_cards a
            JOIN cards c ON c.id = a.card_id
            WHERE a.user_id = $1::uuid
            ORDER BY a.issued_at DESC
            """,
            user_id,
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


async def get_admin_issued_card_ids(user_id: str) -> list[str]:
    """Return list of card_id (UUID strings) for admin-issued cards for this user."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT card_id FROM admin_issued_cards WHERE user_id = $1::uuid",
            user_id,
        )
    return [str(r["card_id"]) for r in rows]


async def get_pending_issued_count(user_id: str) -> int:
    """Count of admin-issued cards for this user that are newer than last_issued_seen_at (not yet 'checked out')."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        n = await conn.fetchval(
            """
            SELECT COUNT(*)::int FROM admin_issued_cards a
            JOIN users u ON u.user_id = a.user_id
            WHERE a.user_id = $1::uuid
              AND (u.last_issued_seen_at IS NULL OR a.issued_at > u.last_issued_seen_at)
            """,
            user_id,
        )
    return n or 0


async def set_last_issued_seen_at(user_id: str) -> None:
    """Mark the user as having seen their issued cards (e.g. after visiting wallet). Sets last_issued_seen_at = NOW()."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET last_issued_seen_at = NOW() WHERE user_id = $1::uuid",
            user_id,
        )


# ---- Card ledger (event-driven: append events, then apply to read models) ----

# Event type constants (event stream is source of truth)
EVENT_CARD_ISSUED = "card.issued"
EVENT_CARD_TRADED = "card.traded"


def _normalize_event_type_for_filter(event_type: str | None) -> str | None:
    """Map legacy or display names to stored event_type."""
    if not event_type or not event_type.strip():
        return None
    t = event_type.strip().lower()
    if t in ("issuance", "issued", "card.issued"):
        return EVENT_CARD_ISSUED
    if t in ("trade", "traded", "card.traded"):
        return EVENT_CARD_TRADED
    return event_type.strip()


async def append_card_event(
    event_type: str,
    payload: dict,
    actor_user_id: str | None = None,
) -> dict | None:
    """
    Append an immutable event to the ledger. Payload must include card_id, to_user_id;
    for trades include from_user_id. Returns the created event row.
    """
    import json
    card_id = (payload.get("card_id") or "").strip()
    to_user_id = (payload.get("to_user_id") or "").strip()
    from_user_id = (payload.get("from_user_id") or "").strip() or None
    if not card_id or not to_user_id:
        return None
    pool = _get_pool()
    meta_json = json.dumps(payload)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO card_ledger (event_type, card_id, to_user_id, from_user_id, actor_user_id, metadata)
            VALUES ($1, $2::uuid, $3::uuid, $4::uuid, $5::uuid, $6::jsonb)
            RETURNING id, event_type, card_id, to_user_id, from_user_id, actor_user_id, created_at, metadata
            """,
            event_type.strip(),
            card_id,
            to_user_id,
            from_user_id,
            actor_user_id.strip() if actor_user_id else None,
            meta_json,
        )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "event_type": row["event_type"],
        "card_id": str(row["card_id"]),
        "to_user_id": str(row["to_user_id"]),
        "from_user_id": str(row["from_user_id"]) if row.get("from_user_id") else None,
        "actor_user_id": str(row["actor_user_id"]) if row.get("actor_user_id") else None,
        "created_at": _format_date(row["created_at"]),
        "payload": row.get("metadata"),
    }


async def apply_card_issued_event(card_id: str, to_user_id: str, actor_user_id: str | None) -> dict | None:
    """
    Event-driven issuance: append card.issued event then apply to admin_issued_cards in one transaction.
    Stores issued_card_id in ledger metadata for public ledger display. Returns the issuance row or None.
    """
    import json
    pool = _get_pool()
    payload = {"card_id": card_id, "to_user_id": to_user_id, "actor_user_id": actor_user_id}
    meta_json = json.dumps(payload)
    async with pool.acquire() as conn:
        ledger_row = await conn.fetchrow(
            """
            INSERT INTO card_ledger (event_type, card_id, to_user_id, from_user_id, actor_user_id, metadata)
            VALUES ($1, $2::uuid, $3::uuid, NULL, $4::uuid, $5::jsonb)
            RETURNING id
            """,
            EVENT_CARD_ISSUED,
            card_id,
            to_user_id.strip(),
            actor_user_id if actor_user_id else None,
            meta_json,
        )
        row = await conn.fetchrow(
            """
            INSERT INTO admin_issued_cards (card_id, user_id)
            VALUES ($1::uuid, $2::uuid)
            RETURNING id, card_id, user_id, issued_at
            """,
            card_id,
            to_user_id.strip(),
        )
        if row and ledger_row:
            await conn.execute(
                """
                UPDATE card_ledger SET metadata = metadata || $1::jsonb WHERE id = $2::uuid
                """,
                json.dumps({"issued_card_id": str(row["id"])}),
                ledger_row["id"],
            )
        if row:
            await conn.execute(
                """
                INSERT INTO user_collection (user_id, card_id, credential_id, synced_at)
                VALUES ($1::uuid, $2::uuid, '', NOW())
                ON CONFLICT (user_id, card_id) DO UPDATE SET synced_at = NOW()
                """,
                to_user_id.strip(),
                card_id,
            )
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "card_id": str(row["card_id"]),
        "user_id": str(row["user_id"]),
        "issued_at": _format_date(row["issued_at"]),
    }


async def insert_ledger_entry(
    event_type: str,
    card_id: str,
    to_user_id: str,
    from_user_id: str | None = None,
    actor_user_id: str | None = None,
    metadata: dict | None = None,
) -> dict | None:
    """Append a ledger entry (legacy helper). Prefer append_card_event for new code."""
    t = event_type.strip().lower()
    if t == "issuance":
        event_type = EVENT_CARD_ISSUED
    elif t == "trade":
        event_type = EVENT_CARD_TRADED
    payload = {"card_id": card_id, "to_user_id": to_user_id, "from_user_id": from_user_id, "actor_user_id": actor_user_id}
    if metadata:
        payload.update(metadata)
    return await append_card_event(event_type, payload, actor_user_id)


async def list_ledger(
    limit: int = 100,
    card_id: str | None = None,
    user_id: str | None = None,
    event_type: str | None = None,
) -> list[dict]:
    """List ledger entries with card and user display info. Admin only."""
    pool = _get_pool()
    if limit < 1 or limit > 500:
        limit = 100
    conditions = []
    values = []
    i = 0
    if card_id and card_id.strip():
        i += 1
        conditions.append(f"l.card_id = ${i}::uuid")
        values.append(card_id.strip())
    if user_id and user_id.strip():
        i += 1
        conditions.append(f"(l.to_user_id = ${i}::uuid OR l.from_user_id = ${i}::uuid)")
        values.append(user_id.strip())
    if event_type and event_type.strip():
        i += 1
        norm = _normalize_event_type_for_filter(event_type)
        conditions.append(f"l.event_type = ${i}")
        values.append(norm or event_type.strip())
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    i += 1
    values.append(limit)
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT l.id, l.event_type, l.card_id, l.to_user_id, l.from_user_id, l.actor_user_id, l.created_at, l.metadata,
                   c.name AS card_name, c.number AS card_number, c.set_name AS card_set_name, c.image_path AS card_image_path,
                   to_ua.provider_username AS to_username,
                   from_ua.provider_username AS from_username,
                   COALESCE(actor_d.provider_username, actor_t.provider_username) AS actor_username
            FROM card_ledger l
            JOIN cards c ON c.id = l.card_id
            LEFT JOIN user_accounts to_ua ON to_ua.user_id = l.to_user_id AND to_ua.provider = 'discord'
            LEFT JOIN user_accounts from_ua ON from_ua.user_id = l.from_user_id AND from_ua.provider = 'discord'
            LEFT JOIN user_accounts actor_d ON actor_d.user_id = l.actor_user_id AND actor_d.provider = 'discord'
            LEFT JOIN user_accounts actor_t ON actor_t.user_id = l.actor_user_id AND actor_t.provider = 'twitch'
            {where}
            ORDER BY l.created_at DESC
            LIMIT ${i}
            """,
            *values,
        )
    out = []
    for r in rows:
        actor_uid = str(r["actor_user_id"]) if r.get("actor_user_id") else None
        actor_name = (r["actor_username"] or actor_uid) if actor_uid else "API key"
        from_uid = str(r["from_user_id"]) if r.get("from_user_id") else None
        from_name = r["from_username"] if from_uid else None
        # For issuances, show issuer in From column (who issued the card)
        if r["event_type"] == EVENT_CARD_ISSUED:
            from_name = actor_name
        meta = r.get("metadata") or {}
        issued_card_id = meta.get("issued_card_id") if isinstance(meta, dict) else None
        out.append({
            "id": str(r["id"]),
            "event_type": r["event_type"],
            "card_id": str(r["card_id"]),
            "card_name": r["card_name"] or "",
            "card_number": r["card_number"] or "",
            "card_set_name": r["card_set_name"] or "",
            "card_image_path": r.get("card_image_path") or "",
            "to_user_id": str(r["to_user_id"]),
            "to_username": r["to_username"] or str(r["to_user_id"]),
            "from_user_id": from_uid,
            "from_username": from_name,
            "actor_user_id": actor_uid,
            "actor_username": actor_name,
            "created_at": _format_date(r["created_at"]),
            "issued_card_id": issued_card_id,
            "payload": meta,
        })
    return out


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


async def sync_user_collection(user_id: str, card_credential_pairs: list[tuple[str, str]]) -> None:
    """Replace user's collection with the given list of (card_id, credential_id)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM user_collection WHERE user_id = $1::uuid", user_id)
        for card_id, cred_id in card_credential_pairs:
            await conn.execute(
                """
                INSERT INTO user_collection (user_id, card_id, credential_id, synced_at)
                VALUES ($1::uuid, $2::uuid, $3, NOW())
                ON CONFLICT (user_id, card_id) DO UPDATE SET credential_id = $3, synced_at = NOW()
                """,
                user_id,
                card_id,
                cred_id or "",
            )


async def list_owners_for_card(card_id: str) -> list[dict]:
    """List users who have this card (from ledger / admin_issued_cards). Public."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT u.user_id, ua.provider_username
            FROM admin_issued_cards a
            JOIN users u ON u.user_id = a.user_id
            LEFT JOIN user_accounts ua ON ua.user_id = u.user_id AND ua.provider = 'discord'
            WHERE a.card_id = $1::uuid
            ORDER BY ua.provider_username
            """,
            card_id,
        )
    return [
        {"user_id": str(r["user_id"]), "username": r["provider_username"] or str(r["user_id"])}
        for r in rows
    ]


async def list_collection_for_user(user_id: str) -> list[dict]:
    """List cards in user's collection from ledger (admin_issued_cards). Returns card dicts with copy_count and card_back_path. Public."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT c.id, c.set_id, c.name, c.number, c.rarity, c.set_name, c.quote, c.artwork,
                   c.image_path, c.photograph, c.artist, c.band, c.types, c.subtypes, c.supertype,
                   c.created_at, c.updated_at, c.card_id, s.card_back_path,
                   COUNT(a.id)::int AS copy_count
            FROM admin_issued_cards a
            JOIN cards c ON c.id = a.card_id
            LEFT JOIN card_sets s ON s.id = c.set_id
            WHERE a.user_id = $1::uuid
            GROUP BY c.id, c.set_id, c.name, c.number, c.rarity, c.set_name, c.quote, c.artwork,
                     c.image_path, c.photograph, c.artist, c.band, c.types, c.subtypes, c.supertype,
                     c.created_at, c.updated_at, c.card_id, s.card_back_path
            ORDER BY c.set_name, c.number, c.name
            """,
            user_id,
        )
    out = []
    for r in rows:
        card = _row_to_card(dict(r))
        card["copy_count"] = int(r.get("copy_count") or 1)
        out.append(card)
    return out


async def search_users(q: str, limit: int = 50) -> list[dict]:
    """Search users by username (from linked accounts). Public. One row per user; display name prefers Discord then Twitch."""
    pool = _get_pool()
    pattern = f"%{(q or '').strip()}%" if (q or '').strip() else "%"
    async with pool.acquire() as conn:
        # One row per user: prefer Discord username, then Twitch, then any other provider
        rows = await conn.fetch(
            """
            SELECT DISTINCT ON (u.user_id)
                   u.user_id, u.poser_username, ua.provider_username,
                   (SELECT COUNT(*) FROM admin_issued_cards a WHERE a.user_id = u.user_id) AS collection_count
            FROM user_accounts ua
            JOIN users u ON u.user_id = ua.user_id
            WHERE ua.provider_username ILIKE $1
            ORDER BY u.user_id,
                     CASE ua.provider WHEN 'discord' THEN 0 WHEN 'twitch' THEN 1 ELSE 2 END,
                     ua.provider_username
            LIMIT $2
            """,
            pattern,
            limit,
        )
    return [
        {
            "user_id": str(r["user_id"]),
            "username": r["provider_username"] or r["poser_username"] or str(r["user_id"]),
            "poser_username": r["poser_username"],
            "collection_count": r["collection_count"] or 0,
        }
        for r in rows
    ]


def _sanitize_poser_username(s: str) -> str:
    """Sanitize to a safe poser_username: lowercase, alphanumeric and underscore only."""
    if not s or not s.strip():
        return ""
    t = re.sub(r"[^a-z0-9_]", "_", (s or "").strip().lower())
    return re.sub(r"_+", "_", t).strip("_") or "user"


async def get_user_poser_username(user_id: str) -> str | None:
    """Get poser_username for a user. Returns None if not set."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT poser_username FROM users WHERE user_id = $1::uuid",
            user_id,
        )
    return (row["poser_username"] or None) if row else None


async def set_poser_username(user_id: str, raw_value: str) -> str | None:
    """Set poser_username for user. Sanitizes and ensures uniqueness. Returns new value or None on conflict."""
    if not raw_value or not str(raw_value).strip():
        return None
    candidate = _sanitize_poser_username(str(raw_value).strip())
    if not candidate or len(candidate) < 2:
        return None
    if len(candidate) > 64:
        candidate = candidate[:64].rstrip("_")
    pool = _get_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "UPDATE users SET poser_username = $1 WHERE user_id = $2::uuid",
                candidate,
                user_id,
            )
            return candidate
        except asyncpg.UniqueViolationError:
            return None


async def ensure_poser_username(user_id: str) -> None:
    """Set poser_username for user from Discord (or first) provider_username if null. Ensures uniqueness."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.poser_username,
                   (SELECT ua.provider_username FROM user_accounts ua WHERE ua.user_id = u.user_id AND ua.provider = 'discord' LIMIT 1)
                   AS discord_username,
                   (SELECT ua.provider_username FROM user_accounts ua WHERE ua.user_id = u.user_id ORDER BY ua.provider LIMIT 1)
                   AS first_username
            FROM users u WHERE u.user_id = $1::uuid
            """,
            user_id,
        )
        if not row or row["poser_username"]:
            return
        base = _sanitize_poser_username(
            (row["discord_username"] or row["first_username"] or str(user_id)) or "user"
        )
        if not base:
            base = "user"
        candidate = base
        for attempt in range(100):
            try:
                await conn.execute(
                    "UPDATE users SET poser_username = $1 WHERE user_id = $2::uuid",
                    candidate,
                    user_id,
                )
                return
            except asyncpg.UniqueViolationError:
                candidate = f"{base}_{str(uuid.uuid4())[:8]}"
    return


async def get_user_by_poser_username(poser_username: str) -> dict | None:
    """Get public user profile by unique poser_username. Returns user_id, username, collection_count or None."""
    if not poser_username or not poser_username.strip():
        return None
    key = (poser_username or "").strip().lower()
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.user_id,
                   u.poser_username,
                   (SELECT ua.provider_username FROM user_accounts ua WHERE ua.user_id = u.user_id AND ua.provider = 'discord' LIMIT 1) AS display_username,
                   (SELECT COUNT(*) FROM admin_issued_cards a WHERE a.user_id = u.user_id) AS collection_count
            FROM users u
            WHERE LOWER(u.poser_username) = $1
            """,
            key,
        )
    if not row:
        return None
    return {
        "user_id": str(row["user_id"]),
        "username": row["display_username"] or row["poser_username"] or str(row["user_id"]),
        "poser_username": row["poser_username"],
        "collection_count": row["collection_count"] or 0,
    }


async def resolve_user_id(identifier: str) -> str | None:
    """Resolve identifier to user_id. identifier can be user_id (UUID) or discord_sub (from user_accounts)."""
    if not identifier or not identifier.strip():
        return None
    s = identifier.strip()
    try:
        uuid.UUID(s)
        return s  # Already a valid user_id
    except (ValueError, TypeError):
        pass
    return await get_user_by_provider("discord", s)


async def get_featured_card_ids(user_id: str) -> list[str]:
    """Return the user's featured card IDs (up to 3) for profile display."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT featured_card_ids FROM users WHERE user_id = $1::uuid",
            user_id,
        )
    if not row or not row.get("featured_card_ids"):
        return []
    ids = row["featured_card_ids"]
    return [str(x) for x in (ids or [])[:3]]


def _validate_song_url(url: str | None) -> str | None:
    """Return trimmed URL if it looks like a safe http(s) URL, else None."""
    if not url or not (u := str(url).strip()):
        return None
    u = u[:2000]
    if u.startswith("http://") or u.startswith("https://"):
        return u
    return None


def _youtube_video_id(url: str) -> str | None:
    """Extract YouTube video ID from common URL forms, or return None."""
    if not url or not url.strip():
        return None
    try:
        parsed = urlparse(url.strip())
        netloc = (parsed.netloc or "").lower()
        if "youtu.be" in netloc:
            path = (parsed.path or "").strip("/")
            if path and "/" not in path:
                return path
        if "youtube.com" in netloc or "www.youtube.com" in netloc:
            if "/embed/" in parsed.path:
                # .../embed/VIDEO_ID
                parts = parsed.path.split("/embed/")
                if len(parts) >= 2 and parts[1]:
                    return parts[1].split("/")[0].split("?")[0]
            qs = parse_qs(parsed.query)
            v = qs.get("v", [])
            if v and v[0]:
                return v[0]
    except Exception:
        pass
    return None


async def _youtube_is_music(video_id: str) -> bool:
    """
    Return True if the video is in YouTube's Music category (categoryId 10), or if we cannot check
    (no API key or API error). Return False only when API says category is not Music.
    """
    api_key = (get_settings().youtube_api_key or "").strip()
    if not api_key:
        return True  # Skip check when no key configured
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "snippet", "id": video_id, "key": api_key},
            )
        r.raise_for_status()
        data = r.json()
        items = data.get("items") or []
        if not items:
            return False  # Video not found or private
        category_id = (items[0].get("snippet") or {}).get("categoryId")
        # Category 10 = Music (US; commonly used)
        return category_id == "10"
    except Exception:
        return True  # On error, allow the URL so we don't block users


def _validate_spotify_url(url: str | None) -> str | None:
    """Return trimmed URL if it is a valid Spotify link (open.spotify.com or spotify.com), else None."""
    if not url or not (u := str(url).strip()):
        return None
    u = u[:500]
    if not u.startswith("https://"):
        return None
    try:
        parsed = urlparse(u)
        host = (parsed.netloc or "").lower()
        if "open.spotify.com" in host or host == "spotify.com":
            return u
    except Exception:
        pass
    return None


def _discord_avatar_url(provider_user_id: str | None, provider_avatar: str | None, size: int = 128) -> str | None:
    """Build Discord CDN avatar URL. Returns None if missing hash or user id."""
    if not provider_avatar or not provider_user_id:
        return None
    ext = "gif" if (provider_avatar or "").startswith("a_") else "png"
    return f"https://cdn.discordapp.com/avatars/{provider_user_id}/{provider_avatar}.{ext}?size={size}"


def _discord_banner_url(provider_user_id: str | None, provider_banner: str | None, size: int = 600) -> str | None:
    """Build Discord CDN banner URL. Returns None if missing hash or user id."""
    if not provider_banner or not provider_user_id:
        return None
    ext = "gif" if (provider_banner or "").startswith("a_") else "png"
    return f"https://cdn.discordapp.com/banners/{provider_user_id}/{provider_banner}.{ext}?size={size}"


def _profile_song_upload_url(relative_path: str | None) -> str | None:
    """Return full URL for profile song upload, or None."""
    if not relative_path or not (p := str(relative_path).strip()):
        return None
    base = (_settings.backend_url or "").rstrip("/")
    return f"{base}/uploads/{p}" if base else None


async def get_profile_customization(user_id: str) -> dict:
    """Return profile_headline, profile_bio, profile_song_url, profile_song_upload_url, profile_accent_color."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT profile_headline, profile_bio, profile_song_url, profile_song_upload_path, profile_accent_color FROM users WHERE user_id = $1::uuid""",
            user_id,
        )
    if not row:
        return {
            "profile_headline": None,
            "profile_bio": None,
            "profile_song_url": None,
            "profile_song_upload_url": None,
            "profile_accent_color": None,
        }
    upload_path = (row.get("profile_song_upload_path") or "").strip() or None
    return {
        "profile_headline": (row.get("profile_headline") or "").strip() or None,
        "profile_bio": (row.get("profile_bio") or "").strip() or None,
        "profile_song_url": _validate_song_url(row.get("profile_song_url")) if not upload_path else None,
        "profile_song_upload_url": _profile_song_upload_url(upload_path),
        "profile_accent_color": (row.get("profile_accent_color") or "").strip()[:20] or None,
    }


async def set_profile_customization(
    user_id: str,
    profile_headline: str | None = None,
    profile_bio: str | None = None,
    profile_song_url: str | None = None,
    profile_accent_color: str | None = None,
) -> dict:
    """Update profile customization fields. Max lengths: headline 200, bio 5000. Returns current state."""
    pool = _get_pool()
    # Only update if explicitly provided (use sentinel or separate endpoint); here we allow empty string to clear
    updates = []
    params = []
    n = 1
    if profile_headline is not None:
        h = (profile_headline or "")[:200].strip() or None
        updates.append(f"profile_headline = ${n}")
        params.append(h)
        n += 1
    if profile_bio is not None:
        b = (profile_bio or "")[:5000].strip() or None
        updates.append(f"profile_bio = ${n}")
        params.append(b)
        n += 1
    if profile_song_url is not None:
        raw = (profile_song_url or "").strip()
        if not raw:
            u = None
        else:
            u = _validate_song_url(profile_song_url or "")
            if not u:
                raise ValueError("Profile song must be a valid URL.")
            video_id = _youtube_video_id(u)
            if video_id:
                if not await _youtube_is_music(video_id):
                    raise ValueError(
                        "Only music videos are allowed for the profile song. This video is not in the Music category."
                    )
            elif _validate_spotify_url(u):
                pass  # Spotify URL allowed
            # else: direct audio URL (any https), allowed
        updates.append(f"profile_song_url = ${n}")
        params.append(u)
        n += 1
        updates.append(f"profile_song_upload_path = ${n}")
        params.append(None)
        n += 1
    if profile_accent_color is not None:
        c = (profile_accent_color or "").strip()[:20] or None
        if c and not re.match(r"^#[0-9A-Fa-f]{3,6}$", c) and not re.match(r"^[a-zA-Z]+$", c):
            c = None  # allow hex or CSS color names
        updates.append(f"profile_accent_color = ${n}")
        params.append(c)
        n += 1
    if updates:
        params.append(user_id)
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE user_id = ${n}::uuid",
                *params,
            )
    return await get_profile_customization(user_id)


async def set_profile_song_upload(user_id: str, relative_path: str | None) -> dict:
    """Set or clear profile_song_upload_path. Clears profile_song_url when setting upload. Returns current profile customization."""
    pool = _get_pool()
    p = (relative_path or "").strip() or None
    if p and not p.startswith("profile-songs/"):
        raise ValueError("Invalid profile song upload path.")
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET profile_song_upload_path = $1, profile_song_url = NULL WHERE user_id = $2::uuid",
            p,
            user_id,
        )
    return await get_profile_customization(user_id)


async def get_profile_song_upload_path(user_id: str) -> str | None:
    """Return profile_song_upload_path for user, or None."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT profile_song_upload_path FROM users WHERE user_id = $1::uuid",
            user_id,
        )
    if not row:
        return None
    return (row.get("profile_song_upload_path") or "").strip() or None


async def set_featured_card_ids(user_id: str, card_ids: list[str]) -> list[str]:
    """Set featured card IDs for profile (max 3). Validates each card is in the user's collection. Returns the saved list."""
    card_ids = [c.strip() for c in (card_ids or []) if c and str(c).strip()][:3]
    pool = _get_pool()
    async with pool.acquire() as conn:
        # Ensure all card_ids belong to this user's collection
        if card_ids:
            owned = await conn.fetch(
                "SELECT card_id FROM user_collection WHERE user_id = $1::uuid AND card_id = ANY($2::uuid[])",
                user_id,
                card_ids,
            )
            owned_ids = {str(r["card_id"]) for r in owned}
            card_ids = [c for c in card_ids if c in owned_ids]
        await conn.execute(
            "UPDATE users SET featured_card_ids = $1::uuid[] WHERE user_id = $2::uuid",
            card_ids,
            user_id,
        )
    return card_ids


async def get_user_public(identifier: str) -> dict | None:
    """Get public user profile by user_id or discord_sub. Returns user_id, username, poser_username, collection_count, featured_card_ids."""
    user_id = await resolve_user_id(identifier)
    if not user_id:
        return None
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.user_id, u.poser_username, u.featured_card_ids,
                   u.profile_headline, u.profile_bio, u.profile_song_url, u.profile_song_upload_path, u.profile_accent_color,
                   (SELECT ua.provider_username FROM user_accounts ua WHERE ua.user_id = u.user_id AND ua.provider = 'discord' LIMIT 1) AS username,
                   (SELECT ua.provider_user_id FROM user_accounts ua WHERE ua.user_id = u.user_id AND ua.provider = 'discord' LIMIT 1) AS discord_provider_user_id,
                   (SELECT ua.provider_avatar FROM user_accounts ua WHERE ua.user_id = u.user_id AND ua.provider = 'discord' LIMIT 1) AS discord_provider_avatar,
                   (SELECT ua.provider_banner FROM user_accounts ua WHERE ua.user_id = u.user_id AND ua.provider = 'discord' LIMIT 1) AS discord_provider_banner,
                   (SELECT ua.provider_accent_color FROM user_accounts ua WHERE ua.user_id = u.user_id AND ua.provider = 'discord' LIMIT 1) AS discord_provider_accent_color,
                   (SELECT COUNT(*) FROM admin_issued_cards a WHERE a.user_id = u.user_id) AS collection_count
            FROM users u WHERE u.user_id = $1::uuid
            """,
            user_id,
        )
    if not row:
        return None
    featured = row.get("featured_card_ids") or []
    upload_path = (row.get("profile_song_upload_path") or "").strip() or None
    avatar_url = _discord_avatar_url(
        row.get("discord_provider_user_id"),
        row.get("discord_provider_avatar"),
        256,
    )
    discord_accent = (row.get("discord_provider_accent_color") or "").strip() or None
    custom_accent = (row.get("profile_accent_color") or "").strip() or None
    profile_accent_color = discord_accent or custom_accent
    banner_url = _discord_banner_url(
        row.get("discord_provider_user_id"),
        row.get("discord_provider_banner"),
        600,
    )
    return {
        "user_id": str(row["user_id"]),
        "discord_sub": None,
        "username": row["username"] or row["poser_username"] or str(row["user_id"]),
        "poser_username": row["poser_username"],
        "avatar_url": avatar_url,
        "collection_count": row["collection_count"] or 0,
        "featured_card_ids": [str(x) for x in featured[:3]],
        "profile_headline": (row.get("profile_headline") or "").strip() or None,
        "profile_bio": (row.get("profile_bio") or "").strip() or None,
        "profile_song_url": None if upload_path else ((row.get("profile_song_url") or "").strip() or None),
        "profile_song_upload_url": _profile_song_upload_url(upload_path),
        "profile_accent_color": profile_accent_color,
        "banner_url": banner_url,
    }


# ---- WebAuthn credentials ----

async def webauthn_save_credential(
    user_id: str,
    credential_id: bytes,
    public_key: bytes,
    sign_count: int = 0,
    credential_device_type: str | None = None,
    credential_backed_up: bool | None = None,
    aaguid: str | None = None,
    attestation_format: str | None = None,
    registered_name: str | None = None,
) -> None:
    """Store a WebAuthn credential after successful registration."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO webauthn_credentials (
                user_id, credential_id, public_key, sign_count,
                credential_device_type, credential_backed_up, aaguid, attestation_format, registered_name
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (credential_id) DO UPDATE SET
                public_key = $3, sign_count = $4,
                credential_device_type = $5, credential_backed_up = $6, aaguid = $7, attestation_format = $8,
                registered_name = $9
            """,
            user_id,
            credential_id,
            public_key,
            sign_count,
            credential_device_type,
            credential_backed_up,
            aaguid,
            attestation_format,
            registered_name,
        )


async def webauthn_get_credential_by_id(credential_id: bytes) -> dict | None:
    """Look up a credential by credential_id (raw bytes). Returns user_id, public_key, sign_count."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_id, public_key, sign_count FROM webauthn_credentials WHERE credential_id = $1",
            credential_id,
        )
    if not row:
        return None
    return {
        "user_id": str(row["user_id"]),
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


async def webauthn_remove_credential(user_id: str, credential_id: bytes) -> bool:
    """Remove a passkey for the user. Returns True if a row was deleted."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM webauthn_credentials WHERE user_id = $1::uuid AND credential_id = $2",
            user_id,
            credential_id,
        )
    return result == "DELETE 1"


async def webauthn_list_credentials_for_user(user_id: str) -> list[dict]:
    """List credentials for a user with metadata (for exclude_credentials and profile display)."""
    pool = _get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT credential_id, created_at, credential_device_type, credential_backed_up, aaguid, attestation_format, registered_name
            FROM webauthn_credentials WHERE user_id = $1::uuid ORDER BY created_at DESC
            """,
            user_id,
        )
    return [
        {
            "credential_id": bytes(r["credential_id"]),
            "created_at": _format_date(r["created_at"]),
            "credential_device_type": r["credential_device_type"],
            "credential_backed_up": r["credential_backed_up"],
            "aaguid": r["aaguid"],
            "attestation_format": r["attestation_format"],
            "registered_name": r["registered_name"],
        }
        for r in rows
    ]
