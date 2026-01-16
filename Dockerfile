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

# Quellcode
COPY src/ /app/src/
COPY .env .env.example /app/
COPY src/main.py /app/

# Logs und Downloads als Volumes
VOLUME ["/app/downloads", "/app/logs"]

# Run
CMD ["python3", "-m", "src.main"]
