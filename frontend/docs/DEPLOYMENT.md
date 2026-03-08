# Deploying the frontend (tritone.cards)

## Normal deploy: frontend served by nginx, backend is API only

The frontend is a static SPA served by nginx (or any static host). The backend serves only the API; it does not serve the SPA.

**With Docker Compose** (from repo root):

```bash
# In backend/.env set BACKEND_URL, FRONTEND_URL, Discord/Twitch, SECRET_KEY, ADMIN_DISCORD_IDS, etc.
# For two domains: BACKEND_URL=https://api.tritone.cards, FRONTEND_URL=https://tritone.cards
# For single domain behind one proxy: set both to your single URL.

docker compose up -d postgres backend frontend
# Optional: docker compose up -d ocr
```

- **Frontend (SPA)** is served by the `frontend` container on **port 80** (nginx; serves `/_app/*` correctly).
- **Backend (API)** is on **port 8000**.

Build the frontend with the API URL so the SPA calls the right backend:

```bash
VITE_API_URL=https://api.tritone.cards docker compose up -d --build postgres backend frontend
```

(Use your real backend URL. For single domain with a reverse proxy, use that URL.)

**Two domains:** Point tritone.cards at the host for port 80 (frontend), api.tritone.cards at the host for port 8000 (backend). Set Discord/Twitch redirect to `https://api.tritone.cards/auth/callback`.

**Single domain:** Put a reverse proxy in front: route `/`, `/_app`, `/favicon`, etc. to frontend:80, and `/auth`, `/api`, `/uploads`, `/docs`, etc. to backend:8000.

---

## Two domains: tritone.cards (frontend) + api.tritone.cards (backend)

**1. Backend at api.tritone.cards**

Run the API (and Postgres, optional OCR) where api.tritone.cards points (e.g. one server or PaaS).

- **With Docker Compose** (from repo root):

  ```bash
  # In backend/.env set:
  # BACKEND_URL=https://api.tritone.cards
  # FRONTEND_URL=https://tritone.cards
  # DATABASE_URL=... (or let compose override for postgres service)
  # DISCORD_*, SECRET_KEY, ADMIN_DISCORD_IDS, etc.

  docker compose up -d postgres backend
  # Optional (card image “Analyze” suggestions): docker compose up -d ocr
  ```

  Expose port 8000 as api.tritone.cards (reverse proxy with TLS). Do **not** expose the frontend container on the same host as the API unless you want to serve the SPA from the backend (see “One container” below).

- **Without Docker**: run the backend (e.g. `uvicorn main:app`) and Postgres elsewhere; set `BACKEND_URL=https://api.tritone.cards`, `FRONTEND_URL=https://tritone.cards`, and the rest in `backend/.env`.

**2. Frontend at tritone.cards**

The frontend must be built with the API base URL, then the **entire** `build/` output must be served (so `/_app/*` are real files, not HTML).

- **Build** (from repo root):

  ```bash
  cd frontend
  npm ci
  VITE_API_URL=https://api.tritone.cards npm run build
  ```

- **Deploy the `build/` folder** to whatever serves tritone.cards:
  - **Static host** (Vercel, Netlify, Cloudflare Pages): set build command to `npm run build`, env `VITE_API_URL=https://api.tritone.cards`, and **publish/output directory to `build`** (see repo `vercel.json` / `netlify.toml`).
  - **Your own server**: copy the contents of `frontend/build/` to the document root and use **try_files** (Nginx) or equivalent so `/_app/*` are served as static files and only non-file routes fall back to `index.html` (see Nginx/Apache section below).

- **Or use the frontend Docker image** on the host that serves tritone.cards:

  ```bash
  docker build -f frontend/Dockerfile --build-arg VITE_API_URL=https://api.tritone.cards -t tritone-frontend ./frontend
  docker run -p 80:80 tritone-frontend
  ```

  Point tritone.cards at this host (with a reverse proxy for TLS). The image already serves `/_app/*` correctly.

**Checklist**

| Where            | What to set / do |
|------------------|------------------|
| backend/.env     | `BACKEND_URL=https://api.tritone.cards`, `FRONTEND_URL=https://tritone.cards`, Discord/Twitch, `SECRET_KEY`, `ADMIN_DISCORD_IDS`, `DATABASE_URL`, optional `ADMIN_API_KEY`, `OCR_SERVICE_URL` if you run ocr |
| Frontend build   | `VITE_API_URL=https://api.tritone.cards` |
| Discord/Twitch   | Redirect/callback URL = `https://api.tritone.cards/auth/callback` |
| tritone.cards    | Serve full `build/` (including `_app/`); SPA fallback only for non-file routes |

---

## Build

```bash
npm ci
npm run build
```

Output is in **`build/`**: `index.html`, `_app/` (JS/CSS), `favicon.png`, `manifest.webmanifest`, etc.

## Why you get a white screen / "MIME type text/html" for .js

If the browser requests `/_app/immutable/entry/start.XXXX.js` and the server returns **HTML** (your SPA `index.html`) instead of the real JavaScript file, you see:

- **"Expected a JavaScript-or-Wasm module script but the server responded with a MIME type of text/html"**
- Blank white screen

That means the server is sending the SPA fallback for **every** request instead of serving static files first.

## Fix: serve static files first, then fallback to index.html

The server must:

1. **Use the full `build/` output as the document root** (so that `/_app/` exists as a directory).
2. **Serve existing files with correct MIME types** (e.g. `.js` → `application/javascript`).
3. **Only** serve `index.html` for requests that do **not** match a file or directory.

**If you use the frontend Docker image:** Rebuild the image after pulling the latest Dockerfile. The Dockerfile now checks that `build/_app/` exists after `npm run build` and configures nginx so `/_app/*` never returns `index.html`. If the image builds successfully, the container has the right files; redeploy that image.

### Nginx

```nginx
root /path/to/build;
index index.html;
location / {
    try_files $uri $uri/ /index.html;
}
# Optional: ensure .js MIME type
location ~* \.js$ {
    add_header Content-Type "application/javascript; charset=utf-8";
}
```

### Apache

```apache
DocumentRoot /path/to/build
<Directory /path/to/build>
    Options -Indexes +FollowSymLinks
    AllowOverride None
    Require all granted
    RewriteEngine On
    RewriteBase /
    RewriteRule ^index\.html$ - [L]
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule . /index.html [L]
</Directory>
```

### Node / Express (e.g. serve or custom server)

- Serve the `build/` directory as static first (e.g. `express.static('build')`).
- Then add a catch-all that sends `index.html` only for GET requests that didn’t match a file.

### Vercel / Netlify

- Use the repo’s `vercel.json` / `netlify.toml` so the app is built with `npm run build` and the **publish directory is `build`**.
- Both platforms serve static files first; the SPA fallback only applies when no file is found.

## AdGuard / extension errors

`GET https://local.adguard.org/... net::ERR_CONNECTION_REFUSED` is from the AdGuard browser extension. It does not affect your app. Users can disable AdGuard for your site or ignore the error.
