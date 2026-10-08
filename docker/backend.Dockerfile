FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system libraries required for OpenCV and PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency requirements
COPY backend/requirements.txt /app/backend_requirements.txt
COPY ml/requirements.txt /app/ml_requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend_requirements.txt && \
    pip install --no-cache-dir -r /app/ml_requirements.txt

# Copy application code
COPY backend/ /app/backend/
COPY ml/ /app/ml/
COPY config/ /app/config/
COPY .env.example /app/.env

ENV PYTHONPATH="/app:/app/backend"

EXPOSE 8000

# Run Alembic migrations and start FastAPI server
CMD ["sh", "-c", "cd /app && alembic upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
