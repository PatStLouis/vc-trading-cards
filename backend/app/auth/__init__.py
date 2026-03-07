"""Auth module: OAuth (Discord/Twitch), WebAuthn (passkeys), session. Exposes a single router for main app."""
from fastapi import APIRouter

_router = None


def get_router() -> APIRouter:
    """Build auth router on first use to avoid circular import with app.dependencies."""
    global _router
    if _router is None:
        from .routes import router as auth_routes
        _router = APIRouter(prefix="/auth", tags=["Auth"])
        _router.include_router(auth_routes)
    return _router


__all__ = ["get_router"]
