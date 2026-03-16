# Brutality Cards API

FastAPI backend: Discord/Twitch OAuth, ACA-Py multitenancy, admin (cards, ledger), wallet, image analysis (OCR).

## Testing

Tests use **pytest** and **pytest-asyncio**. The DB is patched so **no Postgres is required**.

**Run all tests:**

```bash
cd backend
uv sync --extra dev
uv run pytest tests/ -v
```

**Run a single file or test:**

```bash
uv run pytest tests/test_session.py -v
uv run pytest tests/test_api.py::test_root -v
```

**Options:**

- `-v` — verbose
- `-x` — stop on first failure
- `--tb=short` — shorter tracebacks

Tests hit the app via ASGI (no real HTTP server). Session and API tests use a fake tenant; no ACA-Py or Discord is required.
