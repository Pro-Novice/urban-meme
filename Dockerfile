FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    netcat-openbsd \
    iputils-ping \
    curl \
    gnupg \
    apt-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m appuser

WORKDIR /app

COPY --chown=appuser:appuser requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser . .

# ✅ Ensure log directory exists and is writable
RUN mkdir -p /app/logs && chown -R appuser:appuser /app/logs

# ✅ Ensure .env is included if needed
COPY --chown=appuser:appuser .env .env

COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh

ENV DJANGO_SETTINGS_MODULE=agri_backend.settings
ENV WEB_CONCURRENCY=3

EXPOSE 8000

USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "agri_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
