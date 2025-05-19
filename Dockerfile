# Use official Python base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
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

# Set working directory
WORKDIR /app

# Copy dependency file first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project into the container
COPY . .

# Environment variables
ENV DJANGO_SETTINGS_MODULE=agri_backend.settings
ENV WEB_CONCURRENCY=3

# Create a non-root user
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Create entrypoint script
RUN echo '#!/bin/sh\n\
echo "Waiting for postgres..."\n\
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do\n\
  sleep 0.1\n\
done\n\
echo "PostgreSQL started"\n\
\n\
python manage.py migrate\n\
python manage.py collectstatic --noinput\n\
\n\
exec "$@"' > /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run with gunicorn
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "agri_backend.wsgi:application", "--bind", "0.0.0.0:8000"]
