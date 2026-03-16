from contextlib import asynccontextmanager
import base64
import io
import logging
import os

import qrcode
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse

from config import get_settings
from app.db import init_db, close_db, get_user_public, list_collection_for_user
from app.auth import get_router as get_auth_router
from app.admin import router as admin_router, discord_router as admin_discord_router
from app.wallet import router as wallet_router
from app.public import router as public_router
from app.services import discord_bot_router
from app.security import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    EnsureCORSForLocalhostMiddleware,
    PreflightCORSForLocalhostMiddleware,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    os.makedirs(settings.upload_dir, exist_ok=True)
    # Pull missing card images from DB to disk (non-fatal: log and continue if pull fails)
    try:
        from app.image_sync import pull_images_from_db
        result = await pull_images_from_db(settings.upload_dir, force=False)
        if result["pulled"] > 0 or result["errors"]:
            logging.getLogger("uvicorn.error").info(
                "Startup: pulled %s images from DB, skipped %s%s",
                result["pulled"],
                result["skipped"],
                f", {len(result['errors'])} errors" if result["errors"] else "",
            )
    except Exception as e:
        logging.getLogger("uvicorn.error").warning("Startup: DB image pull skipped: %s", e)
    if (
        (settings.secret_key or "").strip() in ("", "change-me-in-production")
        and settings.backend_url.strip().lower().startswith("https")
        and "localhost" not in settings.backend_url.lower()
    ):
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


def _cors_headers_for_request(request: Request) -> dict:
    """Add CORS headers for localhost origin so error responses allow the frontend to read the body."""
    origin = request.headers.get("origin", "").strip()
    if not origin:
        return {}
    if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
        }
    return {}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return JSON with a friendly message for any unhandled exception (avoids raw 'Internal Server Error' HTML)."""
    logger = logging.getLogger("uvicorn.error")
    logger.exception("Unhandled exception: %s", exc)
    headers = dict(_cors_headers_for_request(request))
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
        headers=headers,
    )


# CORS: frontend URL + localhost ports. Fallback middleware ensures localhost gets the header even when main CORS does not run (e.g. error path).
_app_origins = [
    o for o in [
        settings.frontend_url.rstrip("/"),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ] if o
]
# Innermost first: preflight handler for localhost (so OPTIONS always gets CORS headers), then fallback for other responses
app.add_middleware(PreflightCORSForLocalhostMiddleware)
app.add_middleware(EnsureCORSForLocalhostMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_app_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
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

# Optional: serve SPA from this directory (used by Dockerfile.combined). Mount /_app first so JS/CSS get correct MIME types.
_frontend_build_dir = (settings.frontend_build_dir or "").strip()
_serving_spa = False
if _frontend_build_dir and os.path.isdir(_frontend_build_dir):
    _index_path = os.path.join(_frontend_build_dir, "index.html")
    _app_dir = os.path.join(_frontend_build_dir, "_app")
    if os.path.isfile(_index_path) and os.path.isdir(_app_dir):
        _no_cache_headers = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}

        @app.get("/")
        async def _serve_index():
            return FileResponse(_index_path, media_type="text/html", headers=_no_cache_headers)

        # Serve SW and Workbox with no-cache so deploy updates are picked up immediately
        _no_cache_headers_sw = {"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"}
        _frontend_root = _frontend_build_dir

        @app.get("/sw.js")
        async def _serve_sw():
            p = os.path.join(_frontend_root, "sw.js")
            if os.path.isfile(p):
                return FileResponse(p, media_type="application/javascript", headers=_no_cache_headers_sw)
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        @app.get("/workbox-{rest:path}")
        async def _serve_workbox(rest: str):
            p = os.path.join(_frontend_root, f"workbox-{rest}")
            if os.path.isfile(p) and os.path.normpath(p).startswith(os.path.normpath(_frontend_root)):
                return FileResponse(p, media_type="application/javascript", headers=_no_cache_headers_sw)
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        def _html_esc(s: str) -> str:
            if not s:
                return ""
            return (
                str(s)
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )

        def _is_embed_crawler(user_agent: str) -> bool:
            ua = (user_agent or "").lower()
            return (
                "discord" in ua
                or "facebookexternalhit" in ua
                or "twitterbot" in ua
                or "telegrambot" in ua
                or "slackbot" in ua
                or "whatsapp" in ua
                or "linkedinbot" in ua
            )

        @app.get("/u/{user_id}", response_class=HTMLResponse)
        async def _profile_embed(request: Request, user_id: str):
            if _is_embed_crawler(request.headers.get("user-agent", "")):
                profile = await get_user_public(user_id)
                if not profile:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=404, detail="User not found")
                base = (request.base_url or "").rstrip("/")
                api_base = settings.backend_url.rstrip("/")
                title = profile.get("profile_headline") or profile.get("username") or profile.get("poser_username") or "Brutality Cards"
                desc_parts = []
                if profile.get("username") or profile.get("poser_username"):
                    desc_parts.append(f"@{profile.get('username') or profile.get('poser_username')}")
                if profile.get("profile_headline") and profile.get("profile_headline") != title:
                    desc_parts.append(profile["profile_headline"])
                if profile.get("profile_bio"):
                    bio = (profile["profile_bio"] or "")[:200].strip().replace("\n", " ")
                    if len((profile["profile_bio"] or "")) > 200:
                        bio += "…"
                    desc_parts.append(bio)
                desc_parts.append(f"{profile.get('collection_count') or 0} cards in collection")
                description = " · ".join(desc_parts) if desc_parts else "Brutality Cards collector"
                description = description.replace("\n", " ").strip()
                profile_url = f"{base}/u/{user_id}"
                avatar_url = profile.get("avatar_url") or ""
                featured_ids = profile.get("featured_card_ids") or []
                cards = await list_collection_for_user(profile["user_id"])
                card_by_id = {str(c["id"]): c for c in cards}
                featured_cards = [card_by_id[cid] for cid in featured_ids if cid in card_by_id][:3]
                def card_image_url(c):
                    path = (c.get("artwork") or c.get("image_path") or "").strip()
                    if not path:
                        return ""
                    if path.startswith("http"):
                        return path
                    return f"{api_base}/uploads/{path}" if not path.startswith("/") else f"{api_base}{path}"
                card_images = [card_image_url(c) for c in featured_cards if card_image_url(c)]
                og_image = avatar_url or (card_images[0] if card_images else "")
                meta_images = [og_image] + [u for u in card_images if u != og_image][:3]
                meta_image_tags = "".join(
                    f'<meta property="og:image" content="{_html_esc(u)}">' for u in meta_images if u
                )
                qr_buf = io.BytesIO()
                qrcode.make(profile_url, version=1, box_size=4, border=2).save(qr_buf, format="PNG")
                qr_b64 = base64.b64encode(qr_buf.getvalue()).decode("ascii")
                qr_data_url = f"data:image/png;base64,{qr_b64}"
                html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta property="og:title" content="{_html_esc(title)}">
<meta property="og:description" content="{_html_esc(description)}">
<meta property="og:url" content="{_html_esc(profile_url)}">
<meta property="og:type" content="profile">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{_html_esc(title)}">
<meta name="twitter:description" content="{_html_esc(description)}">
<meta name="twitter:image" content="{_html_esc(og_image) if og_image else ''}">
{meta_image_tags}
</head>
<body>
<p><a href="{_html_esc(profile_url)}">View profile</a></p>
<p><img src="{qr_data_url}" alt="QR code: {_html_esc(profile_url)}" width="128" height="128"></p>
</body>
</html>"""
                return HTMLResponse(html)
            return FileResponse(_index_path, media_type="text/html", headers=_no_cache_headers)

        app.mount("/_app", StaticFiles(directory=_app_dir, html=False), name="frontend_app")
        app.mount("/", StaticFiles(directory=_frontend_build_dir, html=True), name="frontend")
        _serving_spa = True

        @app.exception_handler(404)
        async def _spa_fallback(request: Request, _exc):
            if request.method != "GET":
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            path = request.url.path
            if path.startswith(("/api", "/auth", "/uploads", "/_app", "/.well-known", "/docs", "/openapi.json", "/redoc")):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            return FileResponse(_index_path, media_type="text/html", headers=_no_cache_headers)
    else:
        logging.getLogger("uvicorn.error").warning(
            "FRONTEND_BUILD_DIR=%r missing index.html or _app/; not serving SPA", _frontend_build_dir,
        )

if not _serving_spa:
    @app.get("/")
    async def root():
        return {"service": "Brutality Cards API", "docs": "/docs"}


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
