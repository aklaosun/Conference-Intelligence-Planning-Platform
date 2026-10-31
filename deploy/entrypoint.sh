#!/bin/sh
set -eu
python manage.py migrate --noinput
python manage.py setup_platform
python manage.py collectstatic --noinput
exec gunicorn ccse_platform.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --threads 4 --timeout 180 --access-logfile - --error-logfile -
