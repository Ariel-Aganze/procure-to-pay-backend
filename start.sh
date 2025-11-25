#!/usr/bin/env bash
# Render start script

set -o errexit  # exit on error

# Start Gunicorn server
exec gunicorn --bind=0.0.0.0:${PORT:-8000} --workers=3 --worker-class=gevent config.wsgi:application