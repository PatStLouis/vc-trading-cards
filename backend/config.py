import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_title: str = "Tritone Cards API"
    app_version: str = "0.1.0"

    # Server (public URL of this backend – used for redirect URIs and cookie secure flag)
    backend_url: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Discord OIDC
    discord_client_id: str = os.getenv("DISCORD_CLIENT_ID", "")
    discord_client_secret: str = os.getenv("DISCORD_CLIENT_SECRET", "")
    discord_redirect_uri: str = os.getenv("DISCORD_REDIRECT_URI", "")

    # Discord Bot (slash commands via Interactions API)
    discord_bot_token: str = os.getenv("DISCORD_BOT_TOKEN", "")
    discord_public_key: str = os.getenv("DISCORD_PUBLIC_KEY", "")

    # Session / JWT
    secret_key: str = os.getenv("SECRET_KEY", "change-me-in-production")
    session_cookie_name: str = "tritone_cards_session"
    session_ttl_seconds: int = 86400 * 7  # 7 days

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

    # Uploads: directory for card images (relative to cwd or absolute). Served at /uploads.
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")

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
