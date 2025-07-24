# Use official Python base image
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

# Create a non-root user
RUN useradd -m appuser

WORKDIR /app

# Copy requirements and install as root
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the project
COPY --chown=appuser:appuser . .

# Copy entrypoint script and make executable
COPY --chown=appuser:appuser entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV DJANGO_SETTINGS_MODULE=agri_backend.settings
ENV WEB_CONCURRENCY=3

EXPOSE 8000

USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "agri_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
