# Tritone Cards — The Devil's Interval Collectible Cards

Full-stack app: **landing page**, **Discord OIDC login**, **ACA-Py multitenancy** (one wallet per user), and **wallet browser** with holographic-style collectible cards (Svelte + CSS from pokemon-cards-css / brutality-cards). Theme: **Tritone Cards**, the Devil's Interval Collectible Cards.

## How to run (full stack)

Run these in order (each in its own terminal, or run Postgres and ACA-Py in the background):

1. **PostgreSQL** (backend DB)
   ```bash
   docker run -d --name tritone-cards-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=tritone_cards -p 5432:5432 postgres:16-alpine
   ```

2. **ACA-Py agent** (multitenancy; backend will create one wallet per user)
   ```bash
   cd agent && docker build -t tritone-cards-acapy . && docker run --rm -d --name tritone-cards-acapy -p 8020:8020 -p 8022:8022 -e ACAPY_JWT_SECRET=your-jwt-secret-min-32-chars tritone-cards-acapy
   ```
   Or use the [no-build option](agent/README.md#quick-run-with-docker) in `agent/README.md`.

3. **Backend**
   ```bash
   cd backend && cp .env.example .env
   # Edit .env: DISCORD_*, DATABASE_URL, ACAPY_ADMIN_URL=http://localhost:8020
   uv sync && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Frontend**
   ```bash
   cd frontend && npm install && npm run dev
   ```

Then open **http://localhost:5173**, click “Log in with Discord”, and after auth you’ll be on `/wallet` (empty until credentials are in the wallet).

## Stack

- **Backend**: FastAPI (Discord OIDC, session cookie, **Discord bot** slash commands, ACA-Py multitenancy client, PostgreSQL user→tenant mapping)
- **Frontend**: SvelteKit (landing, login redirect, `/wallet` with card grid), PWA-ready (vite-plugin-pwa). UI: [shadcn-svelte](https://www.shadcn-svelte.com/) (Tailwind) for layout and chrome; holographic cards are a separate module.
- **PWA**: Web app manifest is in `frontend/vite.config.js` (name, short_name, icons, theme_color, display, start_url, scope). For full installability (e.g. Chrome “Add to Home Screen”), add `frontend/static/pwa-192.png` (192×192) and `frontend/static/pwa-512.png` (512×512) and reference them in the manifest `icons` array.
- **Cards**: Holographic collectible cards (`Card.svelte` + `cards.css` from pokemon-cards-css / brutality-cards); layout uses shadcn Card/Button/Skeleton.

## Quick start

### Backend

Ensure PostgreSQL is running and create a database (e.g. `tritone_cards`). Then:

```bash
cd backend
uv sync   # or: pip install -e .
cp .env.example .env
# Set DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET
# Set DATABASE_URL, e.g. postgresql://postgres:postgres@localhost:5432/tritone_cards
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**PostgreSQL via Docker (optional):**
```bash
docker run -d --name tritone-cards-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=tritone_cards -p 5432:5432 postgres:16-alpine
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tritone_cards
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Log in with Discord (redirects to backend `/auth/discord` → Discord → backend `/auth/callback` → sets cookie → redirects to `/wallet`). Wallet page loads `/api/me` and `/api/wallet/credentials` (proxied to backend in dev).

**Frontend env (optional):** Copy `frontend/.env.example` to `frontend/.env`. Set `VITE_API_URL` only when the API is on a different origin (e.g. production with a separate API host). For local dev with the Vite proxy, leave it unset.

### Environment (backend)

- `DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET` – Discord OAuth2 app
- `DISCORD_REDIRECT_URI` – optional; defaults to `{BACKEND_URL}/auth/callback`. Set this explicitly (e.g. `https://your-backend.railway.app/auth/callback`) to avoid using the wrong URL when `BACKEND_URL` is misconfigured. You can verify what the backend sends by opening `GET {BACKEND_URL}/auth/redirect-uri` (returns `{"redirect_uri": "..."}`).
- `BACKEND_URL` – **Backend’s own** public URL (e.g. `https://vc-trading-cards-production.up.railway.app`). Used for the Discord OAuth2 redirect URI and cookie `secure` flag. Do **not** set this to the frontend URL or Discord will get the wrong redirect_uri and auth will fail.
- `FRONTEND_URL` – frontend origin (e.g. `http://localhost:5173` or your frontend Railway URL) for CORS and post-login redirect to `/wallet`.
- `SECRET_KEY` – used to sign session cookie
- `DATABASE_URL` – PostgreSQL URL (e.g. `postgresql://user:password@localhost:5432/tritone_cards`). Table `user_tenant` is created on startup.
- `ACAPY_ADMIN_URL`, `ACAPY_ADMIN_API_KEY` – optional; if set, backend creates a tenant per user and lists credentials from ACA-Py. If not set, wallet still works with an empty card list.
- `INNKEEPER_ID`, `INNKEEPER_KEY` – optional; Traction Innkeeper admin tenant ID and API key (for reservation/check-in flows). Leave unset if not using Innkeeper APIs.
- `ADMIN_DISCORD_IDS` – optional; comma-separated Discord user IDs (same as `sub` after login). Those users can open `/admin` and call `/api/admin/*` (stats, user list).

### Discord bot (slash commands)

The app can act as a **Discord bot** so users can run `/wallet` and `/collection` in Discord. Optional; if not configured, the interactions endpoint returns 501.

1. In the [Discord Developer Portal](https://discord.com/developers/applications), open your application (same one used for OAuth2).
2. **Bot** → Add Bot if needed, then **Reset Token** and copy the token → `DISCORD_BOT_TOKEN`.
3. **General Information** → **Application ID** is your `DISCORD_CLIENT_ID`. **Public Key** → `DISCORD_PUBLIC_KEY`.
4. **Interactions Endpoint URL** → set to `https://your-backend.example.com/discord/interactions` (must be HTTPS in production).
5. Register the slash commands once (from backend directory with `.env` set):
   ```bash
   uv run python scripts/register_discord_commands.py
   ```
6. Invite the bot to a server (OAuth2 → URL Generator → scopes: `bot`, `applications.commands`).

Commands: **/wallet** — link to open your deck (and card count if logged in); **/collection** — same.

### Admin dashboard

Admins log in with the same Discord OAuth as everyone else. Set `ADMIN_DISCORD_IDS` to your Discord user ID(s), e.g. `ADMIN_DISCORD_IDS=123456789,987654321`. After login, admins see an **Admin** button on the wallet page and can open **/admin** to view total users and a table of registered users (Discord username, ID, wallet ID, created date). Non-admins get 403 on `/api/admin/*` and are redirected from `/admin` to `/wallet`.

## Project layout

- `agent/` – ACA-Py Dockerfile and `argfile.yml` for multitenancy (see [agent/README.md](agent/README.md))
- `backend/` – FastAPI app, auth, **Discord bot** (POST `/discord/interactions`), ACA-Py client, PostgreSQL user→tenant store
- `frontend/` – SvelteKit app, landing, `/wallet`, `/admin` (admin dashboard), Card component and card CSS

## Docker

Build all images from the repo root:

```bash
docker build -f backend/Dockerfile -t tritone-cards-backend backend/
docker build -f frontend/Dockerfile -t tritone-cards-frontend frontend/
docker build -f agent/Dockerfile -t tritone-cards-acapy agent/
```

**Backend container and PostgreSQL:**  
The backend needs a reachable `DATABASE_URL`. If you run the backend **in Docker**:

- **Recommended:** Use docker-compose so the backend and Postgres share a network:
  ```bash
  docker compose up -d postgres backend
  ```
  The compose file sets `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/tritone_cards` so the backend connects to the `postgres` service.

- **Standalone backend container** with Postgres on the host: use a hostname that resolves to the host from inside the container, e.g.  
  `DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/tritone_cards`  
  On Linux you may need: `docker run --add-host=host.docker.internal:host-gateway ...`

**If you see `ConnectionRefusedError` when starting the backend:**  
The backend is trying to connect to the host in `DATABASE_URL` and nothing is reachable. Fix: (1) Use **docker compose** and run `docker compose up -d postgres backend` so `DATABASE_URL` is set to `postgres:5432` and Postgres is on the same network. (2) Or, if you run the backend container alone, ensure Postgres is running (e.g. on the host or another container) and set `DATABASE_URL` to that host (e.g. `host.docker.internal:5432` from inside the container, not `localhost`).

- **Backend image** expects `DATABASE_URL`, `SECRET_KEY`, `BACKEND_URL`, `FRONTEND_URL`, Discord env vars; expose port 8000.
- **Frontend** image: static build served with nginx on port 80. When the backend is on a **different origin** (e.g. backend on :8000, frontend on :80), build with `--build-arg VITE_API_URL=http://localhost:8000` so "Log in with Discord" and API calls use the backend URL; otherwise you get "Not found: /auth/discord".
- **Agent**: see [agent/README.md](agent/README.md); override `ACAPY_JWT_SECRET` at run time.

### Card images (uploads) in production

**Images are not stored in the database.** The DB only stores paths (e.g. `cards/{set_id}/{card_id}.png`). The actual files are written to the backend’s **upload directory** (`UPLOAD_DIR`, default `uploads/`) and served at `/uploads/...`.

- **After deploy, images disappear?** The uploads directory is on the server’s disk. If the backend runs in a new container/VM on each deploy with no persistent volume, that directory is empty. **Fix:** Use a persistent volume (or bind mount) for `UPLOAD_DIR` so the same directory is used across restarts. Example (Docker): `-v ./uploads:/app/uploads` or a named volume.
- **Images 404 or broken?** The frontend builds image URLs as `VITE_API_URL + '/uploads/' + path`. If the frontend is on a different host than the API (e.g. Vercel + Railway), you **must** set `VITE_API_URL` to your backend’s public URL (e.g. `https://your-api.railway.app`) at **build time** so image requests go to the API. If you use a reverse proxy that serves both the app and the API under one domain and proxy `/api` and `/uploads` to the backend, you can leave `VITE_API_URL` unset (same-origin).

## Testing

- **Backend** (pytest; no DB/ACA-Py required, tests use mocks):
  ```bash
  cd backend && uv sync --extra dev && uv run pytest tests/ -v
  ```
- **Frontend** (Vitest; unit tests only, e.g. stores):
  ```bash
  cd frontend && npm run test:run
  ```

## License

Same as the original projects you derived from (e.g. GPL for the card CSS from pokemon-cards-css).
