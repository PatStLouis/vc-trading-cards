# VC Trading Cards App

Full-stack app: **landing page**, **Discord OIDC login**, **ACA-Py multitenancy** (one wallet per user), and **wallet browser** with holographic-style trading cards (Svelte + CSS from pokemon-cards-css / brutality-cards).

## How to run (full stack)

Run these in order (each in its own terminal, or run Postgres and ACA-Py in the background):

1. **PostgreSQL** (backend DB)
   ```bash
   docker run -d --name vc-cards-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=vc_cards -p 5432:5432 postgres:16-alpine
   ```

2. **ACA-Py agent** (multitenancy; backend will create one wallet per user)
   ```bash
   cd agent && docker build -t vc-cards-acapy . && docker run --rm -d --name vc-cards-acapy -p 8031:8031 -e ACAPY_JWT_SECRET=your-jwt-secret-min-32-chars vc-cards-acapy
   ```
   Or use the [no-build option](agent/README.md#quick-run-with-docker) in `agent/README.md`.

3. **Backend**
   ```bash
   cd backend && cp .env.example .env
   # Edit .env: DISCORD_*, DATABASE_URL, ACAPY_ADMIN_URL=http://localhost:8031
   uv sync && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Frontend**
   ```bash
   cd frontend && npm install && npm run dev
   ```

Then open **http://localhost:5173**, click “Log in with Discord”, and after auth you’ll be on `/wallet` (empty until credentials are in the wallet).

## Stack

- **Backend**: FastAPI (Discord OIDC, session cookie, ACA-Py multitenancy client, **PostgreSQL** for user→tenant mapping)
- **Frontend**: SvelteKit (landing, login redirect, `/wallet` with card grid), PWA-ready (vite-plugin-pwa). UI: [shadcn-svelte](https://www.shadcn-svelte.com/) (Tailwind) for layout and chrome; holographic cards are a separate module.
- **Cards**: Holographic trading cards (`Card.svelte` + `cards.css` from pokemon-cards-css / brutality-cards); layout uses shadcn Card/Button/Skeleton.

## Quick start

### Backend

Ensure PostgreSQL is running and create a database (e.g. `vc_cards`). Then:

```bash
cd backend
uv sync   # or: pip install -e .
cp .env.example .env
# Set DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET
# Set DATABASE_URL, e.g. postgresql://postgres:postgres@localhost:5432/vc_cards
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**PostgreSQL via Docker (optional):**
```bash
docker run -d --name vc-cards-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=vc_cards -p 5432:5432 postgres:16-alpine
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vc_cards
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
- `DISCORD_REDIRECT_URI` – optional; defaults to `{BACKEND_URL}/auth/callback`
- `BACKEND_URL` – public URL of the backend (e.g. `http://localhost:8000`), used for Discord redirect URI and cookie `secure` flag
- `FRONTEND_URL` – frontend origin (e.g. `http://localhost:5173`) for CORS and post-login redirect
- `SECRET_KEY` – used to sign session cookie
- `DATABASE_URL` – PostgreSQL URL (e.g. `postgresql://user:password@localhost:5432/vc_cards`). Table `user_tenant` is created on startup.
- `ACAPY_ADMIN_URL`, `ACAPY_ADMIN_API_KEY` – optional; if set, backend creates a tenant per user and lists credentials from ACA-Py. If not set, wallet still works with an empty card list.
- `ADMIN_DISCORD_IDS` – optional; comma-separated Discord user IDs (same as `sub` after login). Those users can open `/admin` and call `/api/admin/*` (stats, user list).

### Admin dashboard

Admins log in with the same Discord OAuth as everyone else. Set `ADMIN_DISCORD_IDS` to your Discord user ID(s), e.g. `ADMIN_DISCORD_IDS=123456789,987654321`. After login, admins see an **Admin** button on the wallet page and can open **/admin** to view total users and a table of registered users (Discord username, ID, wallet ID, created date). Non-admins get 403 on `/api/admin/*` and are redirected from `/admin` to `/wallet`.

## Project layout

- `agent/` – ACA-Py Dockerfile and `argfile.yml` for multitenancy (see [agent/README.md](agent/README.md))
- `backend/` – FastAPI app, auth, ACA-Py client, PostgreSQL user→tenant store
- `frontend/` – SvelteKit app, landing, `/wallet`, `/admin` (admin dashboard), Card component and card CSS

## Docker

Build all images from the repo root:

```bash
docker build -f backend/Dockerfile -t vc-cards-backend backend/
docker build -f frontend/Dockerfile -t vc-cards-frontend frontend/
docker build -f agent/Dockerfile -t vc-cards-acapy agent/
```

**Backend container and PostgreSQL:**  
The backend needs a reachable `DATABASE_URL`. If you run the backend **in Docker**:

- **Recommended:** Use docker-compose so the backend and Postgres share a network:
  ```bash
  docker compose up -d postgres backend
  ```
  The compose file sets `DATABASE_URL=postgresql://postgres:postgres@postgres:5432/vc_cards` so the backend connects to the `postgres` service.

- **Standalone backend container** with Postgres on the host: use a hostname that resolves to the host from inside the container, e.g.  
  `DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/vc_cards`  
  On Linux you may need: `docker run --add-host=host.docker.internal:host-gateway ...`

- **Backend image** expects `DATABASE_URL`, `SECRET_KEY`, `BACKEND_URL`, `FRONTEND_URL`, Discord env vars; expose port 8000.
- **Frontend** image: static build served with nginx on port 80. Set `VITE_API_URL` at build time if the API is on another origin.
- **Agent**: see [agent/README.md](agent/README.md); override `ACAPY_JWT_SECRET` at run time.

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
