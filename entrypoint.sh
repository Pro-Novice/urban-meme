#!/bin/sh
echo "Waiting for postgres..."
while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done
echo "PostgreSQL started"

if [ "$1" = "gunicorn" ]; then
  echo "Running Django migrations and collectstatic..."
  python manage.py migrate
  python manage.py collectstatic --noinput
fi

exec "$@"
