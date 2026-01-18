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

# Create non-root user with specific UID/GID for consistent permissions across containers
# Using 1000:1000 as default (common first user on Linux systems)
ARG UID=1000
ARG GID=1000
RUN groupadd -g ${GID} hermine && \
    useradd -u ${UID} -g ${GID} -m -s /bin/bash hermine && \
    mkdir -p /app/downloads /app/data /app/logs && \
    chown -R hermine:hermine /app

USER hermine

# Downloads, Data and Logs als Volumes
VOLUME ["/app/downloads", "/app/data", "/app/logs"]

# Default environment variables
ENV DATA_DIR=/app/data \
    DOWNLOAD_DIR=/app/downloads \
    PYTHONUNBUFFERED=1

# Run
CMD ["python3", "-m", "src.main"]
