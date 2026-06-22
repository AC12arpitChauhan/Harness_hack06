FROM python:3.11-slim

WORKDIR /app

# Install deps first so this layer is cached when only code changes.
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

EXPOSE 8000

# Runs DB migrations then starts the server.
# Set DATABASE_URL to a postgres:// URL to use PostgreSQL; defaults to SQLite.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
