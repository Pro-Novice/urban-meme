#!/bin/sh

echo "📡 Waiting for PostgreSQL to be ready..."
while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
  sleep 0.5
done
echo "✅ PostgreSQL is up - continuing..."

echo "🛠️ Running database migrations..."
python manage.py makemigrations --noinput
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting application..."
exec "$@"
