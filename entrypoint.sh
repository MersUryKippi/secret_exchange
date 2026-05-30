#!/bin/sh
set -e

# Wait for DB to be ready
python - <<'PY'
import os
import time
import psycopg2

host = os.environ.get('DB_HOST', 'db')
port = os.environ.get('DB_PORT', '5432')
name = os.environ.get('DB_NAME', 'secret_exchange_db')
user = os.environ.get('DB_USER', 'postgres')
password = os.environ.get('DB_PASSWORD', '')

deadline = time.time() + 60
while True:
	try:
		conn = psycopg2.connect(
			host=host,
			port=port,
			dbname=name,
			user=user,
			password=password,
		)
		conn.close()
		break
	except Exception:
		if time.time() > deadline:
			raise
		time.sleep(2)
PY

# Apply database migrations
python manage.py migrate --noinput

# Collect static files
python manage.py collectstatic --noinput

# Start Gunicorn
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
