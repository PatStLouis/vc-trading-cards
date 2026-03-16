import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_title: str = "Brutality Cards API"
    app_version: str = "0.1.0"

    # Server (public URL of this backend – used for redirect URIs and cookie secure flag)
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Discord OIDC
    discord_client_id: str = os.getenv("DISCORD_CLIENT_ID", "")
    discord_client_secret: str = os.getenv("DISCORD_CLIENT_SECRET", "")
    # Optional. Defaults to BACKEND_URL + /auth/callback. Set only if your public callback URL differs.
    discord_redirect_uri: str = os.getenv("DISCORD_REDIRECT_URI", "")

    # Discord Bot (slash commands via Interactions API)
    discord_bot_token: str = os.getenv("DISCORD_BOT_TOKEN", "")
    discord_public_key: str = os.getenv("DISCORD_PUBLIC_KEY", "")

    # Twitch OAuth (login + bind)
    twitch_client_id: str = os.getenv("TWITCH_CLIENT_ID", "")
    twitch_client_secret: str = os.getenv("TWITCH_CLIENT_SECRET", "")
    # Optional. Defaults to BACKEND_URL + /auth/callback. Set only if your public callback URL differs.
    twitch_redirect_uri: str = os.getenv("TWITCH_REDIRECT_URI", "")

    # Session / JWT
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    session_cookie_name: str = "tritone_cards_session"
    session_ttl_seconds: int = 86400 * 7  # 7 days
    # Optional: explicit cookie domain (e.g. .tritone.cards for www+apex). When unset, production uses backend_url host so cookie works behind proxies.
    cookie_domain: str = os.getenv("COOKIE_DOMAIN", "")

    # ACA-Py multitenancy
    acapy_admin_url: str = os.getenv("ACAPY_ADMIN_URL", "http://localhost:8020")
    acapy_admin_api_key: str = os.getenv("ACAPY_ADMIN_API_KEY", "")

    # Traction Innkeeper: admin tenant credentials (tenant_id + tenant_api_key) for reservation/check-in etc.
    innkeeper_id: str = os.getenv("INNKEEPER_ID", "")
    innkeeper_key: str = os.getenv("INNKEEPER_KEY", "")

    # DB for user -> tenant mapping (PostgreSQL)
    database_url: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/tritone_cards")

    # Admin: comma-separated Discord user IDs allowed to access /admin
    admin_discord_ids: str = os.getenv("ADMIN_DISCORD_IDS", "")
    admin_twitch_ids: str = os.getenv("ADMIN_TWITCH_IDS", "")
    # Optional: API key for admin access (header X-Admin-API-Key or Authorization: Bearer <key>)
    admin_api_key: str = os.getenv("ADMIN_API_KEY", "")

    # Uploads: directory for card images (relative to cwd or absolute). Served at /uploads.
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")

    # Optional: serve the SPA from this directory (frontend build). When set, GET / returns index.html
    # and /_app/* are served as static files; API/auth/uploads unchanged. Use for single-origin deploy.
    frontend_build_dir: str = os.getenv("FRONTEND_BUILD_DIR", "")

    # Optional: OCR microservice URL for card image analysis (e.g. http://ocr:8001). If set, OCR via HTTP.

    # Optional: default source URL for admin "Sync images" (e.g. http://localhost:8000). Can be overridden per request.
    sync_source_url: str = os.getenv("SYNC_SOURCE_URL", "")

    # WebAuthn (passkeys)
    webauthn_rp_id: str = os.getenv("WEBAUTHN_RP_ID", "")  # e.g. localhost or app.example.com
    webauthn_rp_name: str = os.getenv("WEBAUTHN_RP_NAME", "Brutality Cards")
    webauthn_origin: str = os.getenv("WEBAUTHN_ORIGIN", "")  # e.g. http://localhost:5175

    # Optional: YouTube Data API key. When set, profile song URLs (YouTube) are validated as Music category (categoryId 10).
    youtube_api_key: str = os.getenv("YOUTUBE_API_KEY", "")

    # Security: rate limiting (per IP). Set RATE_LIMIT_ENABLED=1 to enable.
    rate_limit_enabled: bool = os.getenv("RATE_LIMIT_ENABLED", "0").strip().lower() in ("1", "true", "yes")
    rate_limit_requests: int = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
    rate_limit_window_seconds: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

    @property
    def cookie_domain_resolved(self) -> str | None:
        """Cookie domain for Set-Cookie. Explicit COOKIE_DOMAIN, or backend_url host in production (so cookie works behind proxies)."""
        if (self.cookie_domain or "").strip():
            return self.cookie_domain.strip()
        from urllib.parse import urlparse
        b = urlparse(self.backend_url)
        host = (b.hostname or "").strip().lower()
        if host and self.backend_url.strip().lower().startswith("https") and host not in ("localhost", "127.0.0.1"):
            return host
        return None

    @property
    def cross_origin_deploy(self) -> bool:
        """True when frontend and backend are on different origins (cookie must use SameSite=None)."""
        from urllib.parse import urlparse
        b = urlparse(self.backend_url)
        f = urlparse(self.frontend_url)
        return (b.hostname or "").lower() != (f.hostname or "").lower()

    @property
    def webauthn_rp_id_resolved(self) -> str:
        """Resolve rp_id from env or frontend_url host."""
        if self.webauthn_rp_id:
            return self.webauthn_rp_id
        from urllib.parse import urlparse
        p = urlparse(self.frontend_url)
        return (p.hostname or "localhost").lower() or "localhost"

    @property
    def webauthn_origin_resolved(self) -> str:
        """Resolve origin from env or frontend_url (no trailing slash)."""
        if self.webauthn_origin:
            return self.webauthn_origin.rstrip("/")
        return self.frontend_url.rstrip("/")

    # OAuth callback URL for Discord and Twitch. Override with DISCORD_REDIRECT_URI / TWITCH_REDIRECT_URI if needed.
    @property
    def oauth_redirect_uri(self) -> str:
        return f"{self.backend_url.rstrip('/')}/auth/callback"

    @property
    def discord_authorize_url(self) -> str:
        return "https://discord.com/api/oauth2/authorize"

    @property
    def discord_token_url(self) -> str:
        return "https://discord.com/api/oauth2/token"

    @property
    def discord_user_url(self) -> str:
        return "https://discord.com/api/users/@me"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
