# Backend: FastAPI + Discord OIDC + ACA-Py client
# Build from repo root: docker build -f backend/Dockerfile backend/
# Or from backend: docker build -t tritone-cards-backend .

FROM python:3.12-slim

WORKDIR /app

# Install uv and deps (and app as package)
COPY uv.lock pyproject.toml ./
COPY config.py main.py ./
COPY app ./app
RUN pip install --no-cache-dir uv \
    && uv sync --no-dev

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
