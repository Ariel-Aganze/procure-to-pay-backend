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
ENV POETRY_VIRTUALENVS_CREATE=false
ENV PATH="/app/.venv/bin:$PATH"

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
    && rm -rf /var/lib/apt/lists/*

# ---------------------------
# Copy Requirements & Install Python Dependencies
# ---------------------------
COPY requirements.txt /app/
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ---------------------------
# Copy Project Files
# ---------------------------
COPY . /app/

# ---------------------------
# Create Non-root User
# ---------------------------
RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app
USER appuser

# ---------------------------
# Ensure Directories Exist
# ---------------------------
RUN mkdir -p /app/media /app/staticfiles \
    && chmod -R 755 /app/media /app/staticfiles


# ---------------------------
# Collect Static Files
# ---------------------------
RUN python manage.py collectstatic --noinput

# ---------------------------
# Expose Port
# ---------------------------
EXPOSE 8000


# ---------------------------
# Run the Application
# ---------------------------
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "config.wsgi:application"]
