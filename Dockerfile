# ---------------------------
# Base Image
# ---------------------------
FROM python:3.11-slim

# ---------------------------
# Environment Variables
# ---------------------------
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/app/.venv/bin:$PATH"

# environment variables for build process
ENV DEBUG=False
ENV SECRET_KEY=build-time-secret-key-will-be-replaced
ENV DATABASE_URL=sqlite:///build.sqlite3
ENV ALLOWED_HOSTS="localhost,127.0.0.1,https://procure-to-pay-backend-y65j.onrender.com"

# ---------------------------
# Working Directory
# ---------------------------
WORKDIR /app

# ---------------------------
# Install System Dependencies
# ---------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        postgresql-client \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        curl \
        git \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------
# Copy Requirements & Install Python Dependencies
# ---------------------------
COPY requirements.txt /app/
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install dj-database-url

# ---------------------------
# Copy Project Files
# ---------------------------
COPY . /app/

# ---------------------------
# Create Non-root User
# ---------------------------
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app

# ---------------------------
# Ensure Directories Exist (as root before switching user)
# ---------------------------
RUN mkdir -p /app/media /app/staticfiles \
    && chmod -R 755 /app/media /app/staticfiles \
    && chown -R appuser:appuser /app/media /app/staticfiles

# ---------------------------
# Switch to non-root user
# ---------------------------
USER appuser

# FIXED: Create a minimal .env file for collectstatic
RUN echo "DEBUG=False" > /app/.env.build \
    && echo "SECRET_KEY=build-time-secret" >> /app/.env.build \
    && echo "DATABASE_URL=sqlite:///build.sqlite3" >> /app/.env.build \
    && echo "ALLOWED_HOSTS=localhost" >> /app/.env.build

# ---------------------------
# Collect Static Files with build environment
# ---------------------------
RUN DJANGO_SETTINGS_MODULE=config.settings \
    DATABASE_URL=sqlite:///build.sqlite3 \
    SECRET_KEY=build-time-secret \
    DEBUG=False \
    python manage.py collectstatic --noinput

# ---------------------------
# Clean up build environment file
# ---------------------------
RUN rm -f /app/.env.build

# ---------------------------
# Expose Port
# ---------------------------
EXPOSE 8000

# ---------------------------
# Health Check
# ---------------------------
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/auth/users/ || exit 1

# ---------------------------
# Run the Application
# ---------------------------
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "config.wsgi:application"]