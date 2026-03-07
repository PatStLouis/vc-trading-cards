from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from config import get_settings
from app.db import init_db, close_db
from app.auth import get_router as get_auth_router
from app.admin import router as admin_router, discord_router as admin_discord_router
from app.wallet import router as wallet_router
from app.public import router as public_router
from app.services import discord_bot_router
from app.security import SecurityHeadersMiddleware, RateLimitMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.upload_dir, exist_ok=True)
    if (
        (settings.secret_key or "").strip() in ("", "change-me-in-production")
        and settings.backend_url.strip().lower().startswith("https")
        and "localhost" not in settings.backend_url.lower()
    ):
        import logging
        logging.getLogger("uvicorn.error").warning(
            "SECRET_KEY is default or empty and BACKEND_URL is HTTPS. Set SECRET_KEY in production."
        )
    try:
        yield
    finally:
        await close_db()


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return JSON with a friendly message for any unhandled exception (avoids raw 'Internal Server Error' HTML)."""
    logger = logging.getLogger("uvicorn.error")
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url.rstrip("/"), "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:5175", "http://127.0.0.1:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

app.include_router(get_auth_router())
app.include_router(wallet_router)
app.include_router(admin_router)
app.include_router(admin_discord_router, prefix="/api/admin")
app.include_router(discord_bot_router)
app.include_router(public_router)

os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


def _did_web_id_from_url(url: str) -> str:
    """Build did:web identifier from backend URL (e.g. https://api.example.com -> did:web:api.example.com)."""
    from urllib.parse import urlparse
    p = urlparse(url)
    host = (p.hostname or "localhost").lower()
    port = p.port
    if port and port not in (80, 443):
        return f"did:web:{host}:{port}"
    return f"did:web:{host}"


def _did_web_id_for_poser(backend_url: str, username: str) -> str:
    """Build did:web identifier for a user's DID at /poser/{username}/did.json."""
    from urllib.parse import urlparse
    p = urlparse(backend_url)
    host = (p.hostname or "localhost").lower()
    port = p.port
    if port and port not in (80, 443):
        return f"did:web:{host}:{port}:poser:{username}"
    return f"did:web:{host}:poser:{username}"


@app.get("/.well-known/did.json", response_class=JSONResponse)
async def well_known_did():
    """Serve the DID document at the root domain (did:web)."""
    did_id = _did_web_id_from_url(settings.backend_url)
    doc = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did_id,
    }
    return JSONResponse(
        content=doc,
        media_type="application/did+ld+json",
        headers={"Cache-Control": "max-age=300"},
    )


@app.get("/")
async def root():
    return {"service": "Tritone Cards API", "docs": "/docs"}


@app.get("/poser/{username}/did.json", response_class=JSONResponse)
async def poser_did(username: str):
    """Serve the DID document for a registered user (unique poser_username)."""
    from fastapi import HTTPException
    from app.db import get_user_by_poser_username, get_user_accounts
    user = await get_user_by_poser_username(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    did_id = _did_web_id_for_poser(settings.backend_url, user["poser_username"])
    accounts = await get_user_accounts(user["user_id"])
    services = []
    for acc in accounts:
        if acc["provider"] == "discord":
            user_id = acc["provider_user_id"] or ""
            services.append({
                "id": f"{did_id}#discord",
                "type": "Discord",
                "serviceEndpoint": f"https://discord.com/users/{user_id}" if user_id else user_id,
            })
        elif acc["provider"] == "twitch":
            username = (acc.get("provider_username") or acc.get("provider_user_id") or "").strip()
            services.append({
                "id": f"{did_id}#twitch",
                "type": "Twitch",
                "serviceEndpoint": f"https://www.twitch.tv/{username}" if username else acc["provider_user_id"],
            })
    doc = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did_id,
    }
    if services:
        doc["service"] = services
    return JSONResponse(
        content=doc,
        media_type="application/did+ld+json",
        headers={"Cache-Control": "max-age=300"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
