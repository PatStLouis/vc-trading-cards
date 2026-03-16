from contextlib import asynccontextmanager
import base64
import hashlib
import io
import json
import logging
import os

import qrcode
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response

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
# Allow /_app/* (SPA assets) to be loaded from opaque origin (e.g. sandboxed iframe with allow-scripts but no same-origin)
@app.middleware("http")
async def _cors_app_assets(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/_app/"):
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
    return response


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
                or "discordbot" in ua  # Discord link preview: Discordbot/2.0
                or "facebookexternalhit" in ua
                or "twitterbot" in ua
                or "telegrambot" in ua
                or "slackbot" in ua
                or "whatsapp" in ua
                or "linkedinbot" in ua
            )

        def _build_embed_image(user_id: str, profile: dict, featured_cards: list, base_url: str) -> bytes | None:
            """Build a single PNG with up to 3 featured card thumbnails side-by-side for og:image."""
            try:
                from PIL import Image
            except ImportError:
                return None
            upload_base = os.path.abspath(settings.upload_dir)
            thumb_w, thumb_h = 100, 140
            padding = 8
            n = min(3, len(featured_cards))
            if n == 0:
                return None
            out_w = n * thumb_w + (n + 1) * padding
            out_h = thumb_h + 2 * padding
            canvas = Image.new("RGB", (out_w, out_h), (18, 18, 18))
            for i, c in enumerate(featured_cards[:3]):
                path = (c.get("image_path") or c.get("artwork") or "").strip()
                if not path or ".." in path or path.startswith("http"):
                    continue
                local = os.path.join(upload_base, path if not path.startswith("/") else path.lstrip("/"))
                if not os.path.isfile(local) or not os.path.normpath(local).startswith(upload_base):
                    continue
                try:
                    img = Image.open(local).convert("RGB")
                    img.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                    # Right-align: rightmost card ends at out_w - padding
                    x = out_w - (n - i) * (thumb_w + padding)
                    y = padding
                    canvas.paste(img, (x, y))
                except Exception:
                    continue
            buf = io.BytesIO()
            canvas.save(buf, format="PNG", optimize=True)
            return buf.getvalue()  # return canvas even if no images pasted (dark bar), so route doesn't 404

        @app.get("/u/{user_id}/embed.png", response_class=Response)
        async def _profile_embed_image(request: Request, user_id: str):
            """Single composite image of featured cards for Discord/social og:image."""
            from fastapi import HTTPException
            profile = await get_user_public(user_id)
            if not profile:
                raise HTTPException(status_code=404, detail="User not found")
            featured_ids = profile.get("featured_card_ids") or []
            cards = await list_collection_for_user(profile["user_id"])
            card_by_id = {str(c["id"]): c for c in cards}
            featured_cards = [card_by_id[cid] for cid in featured_ids if cid in card_by_id][:3]
            base = str(request.base_url).rstrip("/") if request.base_url else ""
            png = _build_embed_image(user_id, profile, featured_cards, base)
            if not png:
                raise HTTPException(status_code=404, detail="No embed image")
            return Response(content=png, media_type="image/png", headers={"Cache-Control": "public, max-age=300"})

        @app.get("/u/{user_id}/did.json", response_class=JSONResponse)
        async def _user_did_in_spa(user_id: str):
            """Serve DID document at /u/{user_id}/did.json when serving SPA (before static mount)."""
            from fastapi import HTTPException
            from app.db import get_user_accounts
            profile = await get_user_public(user_id)
            if not profile:
                raise HTTPException(status_code=404, detail="User not found")
            did_id = _did_web_id_for_user(settings.backend_url, user_id)
            accounts = await get_user_accounts(profile["user_id"])
            doc = _build_user_did_document(profile["user_id"], did_id, accounts)
            return JSONResponse(
                content=doc,
                media_type="application/did+ld+json",
                headers={"Cache-Control": "max-age=300"},
            )

        @app.get("/u/{user_id}", response_class=HTMLResponse)
        async def _profile_embed(request: Request, user_id: str):
            if _is_embed_crawler(request.headers.get("user-agent", "")):
                profile = await get_user_public(user_id)
                if not profile:
                    from fastapi import HTTPException
                    raise HTTPException(status_code=404, detail="User not found")
                base = str(request.base_url).rstrip("/") if request.base_url else ""
                api_base = settings.backend_url.rstrip("/")
                title = profile.get("profile_headline") or profile.get("username") or profile.get("poser_username") or "Brutality Cards"
                desc_parts = []
                if profile.get("username") or profile.get("poser_username"):
                    desc_parts.append(f"@{profile.get('username') or profile.get('poser_username')}")
                if profile.get("profile_headline") and profile.get("profile_headline") != title:
                    desc_parts.append((profile["profile_headline"] or "").strip())
                if profile.get("profile_bio"):
                    bio = (profile["profile_bio"] or "")[:200].strip().replace("\n", " ")
                    if len((profile["profile_bio"] or "")) > 200:
                        bio += "…"
                    desc_parts.append(bio)
                desc_parts.append(f"{profile.get('collection_count') or 0} cards in collection")
                description = "\n".join(p for p in desc_parts if p) if desc_parts else "Brutality Cards collector"
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
                # Cache-bust og:image so Discord/social re-fetch when profile changes (they cache by URL)
                embed_version = hashlib.sha256(
                    json.dumps(
                        [
                            profile.get("featured_card_ids") or [],
                            (profile.get("profile_headline") or "")[:200],
                            (profile.get("profile_bio") or "")[:500],
                            profile.get("collection_count"),
                        ],
                        sort_keys=True,
                    ).encode()
                ).hexdigest()[:12]
                if featured_cards:
                    og_image = f"{base}/u/{user_id}/embed.png?v={embed_version}"
                else:
                    og_image = avatar_url or (card_images[0] if card_images else "")
                meta_image_tag = f'<meta property="og:image" content="{_html_esc(og_image)}">' if og_image else ""
                qr_buf = io.BytesIO()
                qrcode.make(profile_url, version=1, box_size=4, border=2).save(qr_buf, format="PNG")
                qr_b64 = base64.b64encode(qr_buf.getvalue()).decode("ascii")
                qr_data_url = f"data:image/png;base64,{qr_b64}"
                deck_url = f"{base}/catalogue?user={user_id}"
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
{meta_image_tag}
<style>
  body {{ font-family: system-ui, sans-serif; padding: 1rem; max-width: 360px; margin: 0 auto; text-align: center; }}
  .embed-actions {{ display: flex; flex-direction: column; gap: 0.75rem; margin: 1rem 0; }}
  .embed-actions a {{ display: block; padding: 0.6rem 1rem; border-radius: 8px; text-decoration: none; font-weight: 500; }}
  .btn-profile {{ background: #333; color: #fff; border: 2px solid #333; }}
  .btn-profile:hover {{ background: #555; }}
  .btn-deck {{ background: transparent; color: #333; border: 2px solid #333; }}
  .btn-deck:hover {{ background: #eee; }}
</style>
</head>
<body>
<div class="embed-actions">
  <a class="btn-profile" href="{_html_esc(profile_url)}">View profile</a>
  <a class="btn-deck" href="{_html_esc(deck_url)}">Explore deck</a>
</div>
<p><img src="{qr_data_url}" alt="QR code: {_html_esc(profile_url)}" width="128" height="128"></p>
</body>
</html>"""
                return HTMLResponse(
                    html,
                    headers={
                        "Cache-Control": "no-cache, no-store, must-revalidate",
                        "Pragma": "no-cache",
                    },
                )
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


def _did_web_id_for_user(backend_url: str, user_id: str) -> str:
    """Build did:web identifier for a user's DID at /u/{user_id}/did.json (path segments u, user_id)."""
    from urllib.parse import urlparse
    p = urlparse(backend_url)
    host = (p.hostname or "localhost").lower()
    port = p.port
    if port and port not in (80, 443):
        return f"did:web:{host}:{port}:u:{user_id}"
    return f"did:web:{host}:u:{user_id}"


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


def _build_user_did_document(user_id: str, did_id: str, accounts: list) -> dict:
    """Build DID document with Discord/Twitch services from user accounts."""
    services = []
    for acc in accounts:
        if acc["provider"] == "discord":
            pid = acc["provider_user_id"] or ""
            services.append({
                "id": f"{did_id}#discord",
                "type": "Discord",
                "serviceEndpoint": f"https://discord.com/users/{pid}" if pid else pid,
            })
        elif acc["provider"] == "twitch":
            login = (acc.get("provider_username") or acc.get("provider_user_id") or "").strip()
            services.append({
                "id": f"{did_id}#twitch",
                "type": "Twitch",
                "serviceEndpoint": f"https://www.twitch.tv/{login}" if login else acc["provider_user_id"],
            })
    doc = {
        "@context": ["https://www.w3.org/ns/did/v1"],
        "id": did_id,
    }
    if services:
        doc["service"] = services
    return doc


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
    doc = _build_user_did_document(user["user_id"], did_id, accounts)
    return JSONResponse(
        content=doc,
        media_type="application/did+ld+json",
        headers={"Cache-Control": "max-age=300"},
    )


@app.get("/u/{user_id}/did.json", response_class=JSONResponse)
async def user_did(user_id: str):
    """Serve the DID document for a user by UUID at /u/{user_id}/did.json (Discord/Twitch services)."""
    from fastapi import HTTPException
    from app.db import get_user_accounts
    profile = await get_user_public(user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")
    did_id = _did_web_id_for_user(settings.backend_url, user_id)
    accounts = await get_user_accounts(profile["user_id"])
    doc = _build_user_did_document(profile["user_id"], did_id, accounts)
    return JSONResponse(
        content=doc,
        media_type="application/did+ld+json",
        headers={"Cache-Control": "max-age=300"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
