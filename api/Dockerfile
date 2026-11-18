# Multi-stage or slim Python image for FastAPI
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/root/.local/bin:/usr/local/bin:$PATH" \
    OUTPUT_DIR=/data/output \
    LATEST_DIR=/data/latest \
    CONFIG_FILE=/data/config.yaml \
    COLORS_DIR=/data/colors

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . /app/api

# Create mock data dirs if not mounted
RUN mkdir -p /data/output /data/latest /data/colors

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
