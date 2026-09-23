#!/bin/bash
# backend/startup.sh
# Runs Alembic DB migrations then starts the production server.
# Called by the Docker CMD in both local and Azure Container Apps.

echo "[startup] Checking environment variables..."
python -c "import os; u=os.getenv('SYNC_DATABASE_URL',''); print('SYNC_DATABASE_URL length:', len(u)); print('SYNC_DATABASE_URL (masked):', u[:30]+'...' if len(u)>30 else u)"

# Strip any invisible whitespace/newlines from DB URLs
export DATABASE_URL=$(echo -n "$DATABASE_URL" | tr -d '\r\n ')
export SYNC_DATABASE_URL=$(echo -n "$SYNC_DATABASE_URL" | tr -d '\r\n ')

echo "[startup] Running database migrations..."
alembic upgrade head || echo "[startup] WARNING: migrations failed, continuing anyway (DB may already be at head)"

echo "[startup] Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
