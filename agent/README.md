# ACA-Py Agent (multitenancy)

This directory runs an [ACA-Py](https://aca-py.org/) agent in **multitenancy** mode so the VC Trading Cards backend can create one wallet per Discord user and list their credentials.

## Quick run with Docker

**Option A: Use the official image and pass args (no build)**

```bash
docker run --rm -d \
  --name vc-cards-acapy \
  -p 8031:8031 \
  -e ACAPY_JWT_SECRET=your-jwt-secret-min-32-chars \
  -e ACAPY_ADMIN_INSECURE_MODE=1 \
  ghcr.io/openwallet-foundation/acapy-agent:latest \
  aca-start \
  --multitenant \
  --multitenant-admin \
  --jwt-secret your-jwt-secret-min-32-chars \
  --admin 0.0.0.0 8031 \
  --admin-insecure-mode \
  --wallet-type askar \
  --wallet-local-did
```

**Option B: Build and run with config file**

```bash
# Build (uses argfile.yml in this directory)
docker build -t vc-cards-acapy .

# Run (override JWT secret via env)
docker run --rm -d \
  --name vc-cards-acapy \
  -p 8031:8031 \
  -e ACAPY_JWT_SECRET=your-jwt-secret-min-32-chars \
  vc-cards-acapy
```

Then in the **backend** `.env`:

```env
ACAPY_ADMIN_URL=http://localhost:8031
# ACAPY_ADMIN_API_KEY=   # leave unset when using admin-insecure-mode
```

For production, do **not** use `--admin-insecure-mode`. Build with an `argfile.yml` that omits `admin-insecure-mode` and set `ACAPY_ADMIN_API_KEY` in the backend.

## Files

| File | Purpose |
|------|--------|
| `argfile.yml` | ACA-Py startup config: admin port 8031, multitenant, admin API, JWT secret placeholder |
| `Dockerfile` | Image that copies `argfile.yml` and runs `aca-start --arg-file /app/argfile.yml` |
| `.env.example` | Optional env for the container (e.g. `ACAPY_JWT_SECRET`) |

## Ports

- **8031** – Admin API (create tenant, get token, list credentials). Backend talks to this.
