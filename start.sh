#!/usr/bin/env bash

# Start Celery worker in background (for document processing)
celery -A config worker --loglevel=info --detach

# Start the Django application with Gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 3