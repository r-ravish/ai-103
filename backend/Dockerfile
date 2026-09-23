# --------------------------------------------------------------------------- #
# Enterprise Knowledge Agent — Backend                                        #
# Docker image for Azure Container Apps deployment                            #
# --------------------------------------------------------------------------- #
FROM python:3.12-slim

# System deps for psycopg2-binary + asyncpg
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (separate layer = faster rebuilds)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Non-root user for security
RUN useradd -m appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# startup.sh runs migrations then starts uvicorn
CMD ["bash", "startup.sh"]
