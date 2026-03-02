from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from config import get_settings
from app.db import init_db, close_db
from app.routers import auth, wallet, admin, discord_bot

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.upload_dir, exist_ok=True)
    try:
        yield
    finally:
        await close_db()


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url.rstrip("/"), "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(wallet.router)
app.include_router(admin.router)
app.include_router(discord_bot.router)

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
