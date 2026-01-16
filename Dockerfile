# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# System-Dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python-Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source code
COPY src/ /app/src/
COPY .env.example /app/

# Create empty .env if it doesn't exist (for development/testing)
RUN test -f /app/.env || echo "# Configuration - see .env.example" > /app/.env

# Logs und Downloads als Volumes
VOLUME ["/app/downloads", "/app/logs"]

# Run
CMD ["python3", "-m", "src.main"]
