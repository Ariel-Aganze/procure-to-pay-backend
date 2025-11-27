# Procure-to-Pay System – Complete Setup Guide

 Quick Start

# Local Development

bash
# 1. Clone and setup
git clone <your-repo>
cd procure-to-pay-backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your settings

# 4. Setup database
python manage.py migrate
python manage.py createsuperuser

# 5. Start server
python manage.py runserver


# Docker Development

bash
# 1. Build and run with Docker
docker-compose up --build

# 2. Access services
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/api/docs/
# - Admin: http://localhost:8000/admin/
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
# - Ollama: http://localhost:11434


 Production Deployment on Render

# Prerequisites

1. GitHub repository with your code
2. Render account
3. Domain name (optional)

# Step 1: Prepare Repository

bash
cp Dockerfile docker-compose.yml .dockerignore ./
cp build.sh start.sh ./
cp requirements_production.txt requirements.txt
chmod +x build.sh start.sh

git add .
git commit -m "Add deployment configuration"
git push origin main


# Step 2: Create Render Services

 A. PostgreSQL Database

1. Open Render Dashboard
2. Create a new PostgreSQL service
3. Save the connection credentials

 B. Redis Instance

1. Create a new Redis service
2. Save the Redis URL

 C. Web Service

1. Create a new Web Service
2. Connect to the GitHub repository
3. Configure:

   * Build Command: `./build.sh`
   * Start Command: `./start.sh`
   * Environment: Python 3.11

 D. Environment Variables

Add the following:

env
SECRET_KEY=your-production-secret-key
DEBUG=False
ALLOWED_HOSTS=*.render.com

DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://red-xxx:6379

CORS_ALLOWED_ORIGINS=https://your-frontend.com

MAX_UPLOAD_SIZE=10485760
ALLOWED_FILE_TYPES=pdf,png,jpg,jpeg

OLLAMA_HOST=http://your-ollama-host:11434
OLLAMA_MODEL=llama2

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True


# Step 3: Deploy

1. Click "Deploy"
2. Wait for build to complete
3. Access the API via Render URL



 AI Setup (Ollama)

# Option 1: Separate Render Service

dockerfile
FROM ollama/ollama
EXPOSE 11434

HEALTHCHECK --interval=60s --timeout=30s --start-period=120s --retries=3 \
  CMD curl -f http://localhost:11434/api/tags || exit 1

CMD ["ollama", "serve"]


# Option 2: External Ollama Service

* Host Ollama on VPS/cloud
* Set `OLLAMA_HOST` accordingly
* Ensure network access

# Option 3: Development Only

Set:


OLLAMA_HOST=disabled




 Configuration Options

# Database Settings


USE_POSTGRESQL=False  # Development (SQLite)
USE_POSTGRESQL=True   # Production


# File Storage Settings


# Development
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Production (AWS S3)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_STORAGE_BUCKET_NAME=your-bucket


# Email Settings


# Development
EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'

# Production
EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST='smtp.gmail.com'
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER='your-email@gmail.com'
EMAIL_HOST_PASSWORD='your-app-password'




 Testing

# Run Django Tests

bash
pip install pytest pytest-django factory-boy
pytest
pytest --cov=apps


# API Testing Examples

bash
curl -X POST https://your-app.render.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'

curl https://your-app.render.com/api/docs/




 Monitoring and Logs

# Render Logs

bash
render logs --service your-service-name


# Health Checks

* API: `/api/docs/`
* Database: Render dashboard
* Redis: Render dashboard
* Ollama: `/api/documents/ollama-status/`



 Troubleshooting

# 1. Build Failures

bash
pip install --upgrade pip setuptools


# 2. Database Connection

Check format:


postgresql://user:password@host:5432/database


# 3. Static Files

Run:

bash
python manage.py collectstatic --noinput


# 4. CORS Issues

Update:


CORS_ALLOWED_ORIGINS=https://your-frontend.com


# 5. File Upload Errors

* Verify MEDIA_ROOT
* Check file permissions



 Debug Commands

bash
python manage.py shell
python manage.py check
python manage.py migrate app_name migration_name
python manage.py loaddata fixtures/test_data.json




 Performance Optimization

# Database

* Add indexes
* Use `select_related()`
* Enable pooling

# Caching with Redis


CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}


# File Storage

* Enable CDN
* Compress images
* Minimize static assets



 Security Checklist

* Strong SECRET_KEY
* HTTPS enabled
* Secure cookies enabled
* CORS correctly configured
* Secrets stored in environment variables
* Security middleware enabled
* Dependencies updated
* File upload validation enforced
* API rate limiting applied



 Contributing

1. Fork repository
2. Create a feature branch
3. Implement changes
4. Add tests
5. Run validations
6. Submit pull request



 API Documentation

* Swagger UI: `/api/docs/`
* ReDoc: `/api/redoc/`


