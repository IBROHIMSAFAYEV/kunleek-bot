#!/usr/bin/env bash
# Serverda ishga tushirish: admin panel (gunicorn) va telegram bot bitta xizmatda.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py ensure_admin

python manage.py runbot &
gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120 &

# biri to'xtasa, butun xizmat qayta ishga tushsin
wait -n
exit 1
