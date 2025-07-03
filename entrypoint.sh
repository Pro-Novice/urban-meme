sudo tee entrypoint.sh <<EOF
#!/bin/sh

# Wait for database to be ready (if using PostgreSQL)
while ! nc -z \$DB_HOST \$DB_PORT; do
  echo "Waiting for DB..."
  sleep 1
done

# Run Django migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Start the main process
exec "\$@"
EOF