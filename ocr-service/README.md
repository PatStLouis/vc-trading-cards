# OCR microservice

Runs EasyOCR for card image analysis. The main backend calls it when `OCR_SERVICE_URL` is set (e.g. `http://ocr:8001` in Docker).

**Endpoints**

- `GET /health` — liveness
- `POST /ocr` — multipart file upload (image), returns `{ "raw_text": "...", "suggested": { "name": "...", ... } }`

**Optional API key**

Set `OCR_API_KEY` or `ADMIN_API_KEY` in the OCR service environment. The backend sends its admin API key (`ADMIN_API_KEY`) as the header `X-OCR-API-Key` when calling the OCR service, so use the **same key** for both: set `ADMIN_API_KEY` in the backend `.env` and give the OCR service the same env (e.g. in Docker use `env_file: ./backend/.env`). If neither var is set, no auth is required.

**Run locally**

```bash
cd ocr-service
pip install -r requirements.txt
# Optional: export OCR_API_KEY=your-secret-key
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

Then set `OCR_SERVICE_URL=http://localhost:8001` in the backend `.env`. If you set `ADMIN_API_KEY` in the backend, set the same value as `OCR_API_KEY` or `ADMIN_API_KEY` when running the OCR service locally so the backend can authenticate.

**Docker**

```bash
docker compose up -d ocr
# Optional: pass OCR_API_KEY and OCR_SERVICE_API_KEY via env or .env
```

Backend is configured with `OCR_SERVICE_URL=http://ocr:8001` when using docker-compose. With `env_file: ./backend/.env`, the OCR service gets `ADMIN_API_KEY` and validates the same key the backend sends.
