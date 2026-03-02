# ACA-Py Agent (multitenancy)

This directory runs an [ACA-Py](https://aca-py.org/) agent in **multitenancy** mode so the VC Trading Cards backend can create one wallet per Discord user and list their credentials. Config follows the same pattern as [digicred-crms](https://github.com/digicred/digicred-crms) (`plugins/docker/default.yml`): **multitenant_provider** plugin with `AskarMultitokenMultitenantManager`, token expiry (1 day), and wallet create/token routes overridden by the plugin.

## Quick run with Docker

**Option A: Quick test without building**  
Uses the stock image with built-in multitenancy only (no multitenant_provider plugin). For production or parity with digicred, use Option B.

```bash
docker run --rm -d --name vc-cards-acapy -p 8031:8031 -p 8032:8032 \
  -e ACAPY_JWT_SECRET=your-jwt-secret-min-32-chars \
  ghcr.io/openwallet-foundation/acapy-agent:latest \
  start -it http 0.0.0.0 8032 -ot http \
  --admin 0.0.0.0 8031 --admin-insecure-mode \
  --multitenant --multitenant-admin --jwt-secret your-jwt-secret-min-32-chars \
  --wallet-type askar --wallet-name vc-cards-base-wallet --wallet-key change-me \
  --no-ledger --auto-provision
```

**Option B: Build and run with config file (recommended)**

```bash
# From repo root
docker build -f agent/Dockerfile -t vc-cards-acapy agent/

# Run (override JWT secret via env)
docker run --rm -d \
  --name vc-cards-acapy \
  -p 8031:8031 \
  -p 8032:8032 \
  -e ACAPY_JWT_SECRET=your-jwt-secret-min-32-chars \
  vc-cards-acapy
```

Then in the **backend** `.env`:

```env
ACAPY_ADMIN_URL=http://localhost:8031
# ACAPY_ADMIN_API_KEY=   # leave unset when using admin-insecure-mode
```

For production, do **not** use `admin-insecure-mode`. Set `admin-insecure-mode: false`, set `admin-api-key` (or `ACAPY_ADMIN_API_KEY`), and use a strong `jwt-secret` / `ACAPY_JWT_SECRET`.

## Files

| File | Purpose |
|------|--------|
| `argfile.yml` | ACA-Py startup config: admin 8031, inbound http 8032, multitenant + multitenant_provider plugin, JWT secret, wallet, no-ledger, auto-provision |
| `Dockerfile` | Image installs multitenant_provider plugin, copies argfile, runs `aca-py start --arg-file /app/argfile.yml` |
| `.env.example` | Optional env for the container (e.g. `ACAPY_JWT_SECRET`) |

## Ports

- **8031** – Admin API (create tenant, get token, list credentials). Backend talks to this.
- **8032** – Inbound HTTP transport (required by ACA-Py; can be unused if you only use the admin API).
