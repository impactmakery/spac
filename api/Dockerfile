# Tomorrow Agent Hub API — also runs the ingestion worker and the cron service.
# All three Railway services share this image and differ only by start command.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first so code changes don't invalidate the install layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway provides $PORT; default keeps `docker run` working locally.
ENV PORT=8000
EXPOSE 8000

# Migrations run on boot so a deploy never serves an out-of-date schema.
# Alembic is idempotent, so a restart or a second instance is harmless.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
