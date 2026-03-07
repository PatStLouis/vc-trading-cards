"""Admin module: dashboard API (stats, users, sets, cards, Discord bot). Requires admin role."""
from .routes import router, discord_router

__all__ = ["router", "discord_router"]
