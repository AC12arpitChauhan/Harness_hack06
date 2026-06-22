# PR Health Analytics — FastAPI service image.
# Build for linux/amd64 (cluster nodes). The app auto-creates its schema on
# startup (init_db), so it boots zero-setup on SQLite; point DATABASE_URL at
# Postgres for persistence.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install the package + dependencies (incl. anthropic[bedrock]/boto3).
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install . && useradd -m appuser && chown -R appuser /app

USER appuser
EXPOSE 8000

# init_db() in the lifespan creates tables on startup; no migration step needed
# for a fresh DB (works for SQLite and Postgres alike).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
