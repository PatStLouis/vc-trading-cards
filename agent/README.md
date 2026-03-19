# ACA-Py Agent (multitenancy)

This directory runs an [ACA-Py](https://aca-py.org/) agent in **multitenancy** mode so the Brutality Cards backend can create one wallet per Discord user and list their credentials. Config follows the same pattern as [digicred-crms](https://github.com/digicred/digicred-crms) (`plugins/docker/default.yml`): **multitenant_provider** plugin with `AskarMultitokenMultitenantManager`, token expiry (1 day), and wallet create/token routes overridden by the plugin.

## Quick run with Docker

**Option A: Quick test without building**  
Uses the stock image with built-in multitenancy only (no multitenant_provider plugin). For production or parity with digicred, use Option B.

```bash
docker run --rm -d --name tritone-cards-acapy -p 8020:8020 -p 8022:8022 \
  -e ACAPY_JWT_SECRET=your-jwt-secret-min-32-chars \
  ghcr.io/openwallet-foundation/acapy-agent:latest \
  start -it http 0.0.0.0 8022 -ot http \
  --admin 0.0.0.0 8020 --admin-insecure-mode \
  --multitenant --multitenant-admin --jwt-secret your-jwt-secret-min-32-chars \
  --wallet-type askar --wallet-name tritone-cards-base-wallet --wallet-key change-me \
  --no-ledger --auto-provision
```

**Option B: Build and run with config file (recommended)**

```bash
# From repo root
docker build -f agent/Dockerfile -t tritone-cards-acapy agent/

# Run (override JWT secret and Innkeeper wallet key via env)
docker run --rm -d \
  --name tritone-cards-acapy \
  -p 8020:8020 \
  -p 8022:8022 \
  -e ACAPY_JWT_SECRET=your-jwt-secret-min-32-chars \
  -e INNKEEPER_WALLET_KEY=your-innkeeper-wallet-key \
  tritone-cards-acapy
```

Then in the **backend** `.env`:

```env
ACAPY_ADMIN_URL=http://localhost:8020
# ACAPY_ADMIN_API_KEY=   # leave unset when using admin-insecure-mode
```

For production, do **not** use `admin-insecure-mode`. Set `admin-insecure-mode: false`, set `admin-api-key` (or `ACAPY_ADMIN_API_KEY`), and use a strong `jwt-secret` / `ACAPY_JWT_SECRET`.

## Files

| File | Purpose |
|------|--------|
| `argfile.yml` | ACA-Py startup config: admin 8020, DIDComm HTTP inbound 8022, multitenant + multitenant_provider + traction_innkeeper, JWT secret, wallet, no-ledger. Use `${INNKEEPER_WALLET_KEY}` to substitute from env. |
| `entrypoint.py` | Expands `${VAR}` in argfile.yml from environment, then runs aca-py. |
| `Dockerfile` | Image installs plugins, copies argfile and entrypoint, runs via entrypoint so env vars are applied. |
| `.env.example` | Optional env for the container (e.g. `ACAPY_JWT_SECRET`) |

## Ports

- **8020** – Admin API (create tenant, get token, list credentials). Backend talks to this.
- **8022** – DIDComm HTTP inbound transport (required by ACA-Py).
