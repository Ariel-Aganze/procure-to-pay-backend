# Procure-to-Pay System - Complete Setup Guide

## 🚀 Quick Start

### Local Development
```bash
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
```

### Docker Development
```bash
# 1. Build and run with Docker
docker-compose up --build

# 2. Access services
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/api/docs/
# - Admin: http://localhost:8000/admin/
# - PostgreSQL: localhost:5432
# - Redis: localhost:6379
# - Ollama: http://localhost:11434
```

## 🏗️ Production Deployment on Render

### Prerequisites
1. GitHub repository with your code
2. Render account
3. Domain name (optional)

### Step 1: Prepare Repository
```bash
# Copy all generated files to your project
cp Dockerfile docker-compose.yml .dockerignore ./
cp build.sh start.sh ./
cp requirements_production.txt requirements.txt
chmod +x build.sh start.sh

# Commit and push
git add .
git commit -m "Add deployment configuration"
git push origin main
```

### Step 2: Create Render Services

#### A. PostgreSQL Database
1. Go to Render Dashboard
2. Create new PostgreSQL service
3. Note the connection details

#### B. Redis Instance
1. Create new Redis service in Render
2. Note the Redis URL

#### C. Web Service
1. Create new Web Service
2. Connect your GitHub repository
3. Configure:
   - **Build Command**: `./build.sh`
   - **Start Command**: `./start.sh`
   - **Environment**: Python 3.11

#### D. Environment Variables
Add these to your Render web service:

```env
# Django
SECRET_KEY=your-super-secret-production-key-here
DEBUG=False
ALLOWED_HOSTS=*.render.com

# Database (from Render PostgreSQL)
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# Redis (from Render Redis)
REDIS_URL=redis://red-xxx:6379

# CORS (update with your frontend URL)
CORS_ALLOWED_ORIGINS=https://your-frontend.com

# File uploads
MAX_UPLOAD_SIZE=10485760
ALLOWED_FILE_TYPES=pdf,png,jpg,jpeg

# Ollama (you'll need separate service)
OLLAMA_HOST=http://your-ollama-host:11434
OLLAMA_MODEL=llama2

# Email (optional)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Security
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Step 3: Deploy
1. Click "Deploy" in Render
2. Wait for build to complete
3. Access your API at the Render URL

## 🤖 AI Setup (Ollama)

### Option 1: Separate Render Service
```dockerfile
# Create separate Dockerfile.ollama
FROM ollama/ollama

# Expose port
EXPOSE 11434

# Health check
HEALTHCHECK --interval=60s --timeout=30s --start-period=120s --retries=3 \
  CMD curl -f http://localhost:11434/api/tags || exit 1

# Start command
CMD ["ollama", "serve"]
```

### Option 2: External Ollama Service
1. Set up Ollama on a VPS or cloud service
2. Update `OLLAMA_HOST` environment variable
3. Ensure network connectivity

### Option 3: Development Only
For development, you can run without Ollama:
- Document processing will be disabled
- Manual PO creation can still work
- Set `OLLAMA_HOST=disabled` in .env

## 🔧 Configuration Options

### Database Options
```python
# SQLite (development)
USE_POSTGRESQL=False

# PostgreSQL (production)
USE_POSTGRESQL=True
DATABASE_URL=postgresql://...
```

### File Storage Options
```python
# Local storage (development)
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# AWS S3 (production)
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = 'your-key'
AWS_SECRET_ACCESS_KEY = 'your-secret'
AWS_STORAGE_BUCKET_NAME = 'your-bucket'
```

### Email Configuration
```python
# Console (development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# SMTP (production)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
```

## 🧪 Testing

### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-django factory-boy

# Run tests
python -m pytest

# With coverage
python -m pytest --cov=apps
```

### API Testing
```bash
# Test authentication
curl -X POST https://your-app.render.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'

# Test API docs
curl https://your-app.render.com/api/docs/
```

## 🔍 Monitoring and Logs

### Render Logs
```bash
# View logs in Render dashboard
# Or use Render CLI
render logs --service your-service-name
```

### Health Checks
- API Health: `GET /api/docs/`
- Database: Check PostgreSQL connection in Render
- Redis: Check Redis connection in Render
- Ollama: `GET /api/documents/ollama-status/`

## 🚨 Troubleshooting

### Common Issues

#### 1. Build Failures
```bash
# Check build logs in Render
# Common fixes:
pip install --upgrade pip setuptools
```

#### 2. Database Connection
```bash
# Verify DATABASE_URL format
postgresql://user:password@host:5432/database
```

#### 3. Static Files
```bash
# Ensure collectstatic runs in build
python manage.py collectstatic --noinput
```

#### 4. CORS Issues
```bash
# Update CORS_ALLOWED_ORIGINS
CORS_ALLOWED_ORIGINS=https://your-frontend.com,https://your-api.render.com
```

#### 5. File Uploads
```bash
# Check file permissions and storage
# Ensure MEDIA_ROOT is writable
```

### Debug Commands
```bash
# Django shell
python manage.py shell

# Check configuration
python manage.py check

# Run specific migration
python manage.py migrate app_name migration_name

# Create test data
python manage.py loaddata fixtures/test_data.json
```

## 📊 Performance Optimization

### Database
- Add indexes for frequently queried fields
- Use select_related() for ForeignKey queries
- Implement database connection pooling

### Caching
```python
# Add Redis caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://localhost:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

### File Storage
- Use CDN for static files
- Implement image optimization
- Add file compression

## 🔐 Security Checklist

- [ ] Set strong SECRET_KEY in production
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Set secure cookie flags
- [ ] Configure CORS properly
- [ ] Use environment variables for secrets
- [ ] Enable Django security middleware
- [ ] Regular dependency updates
- [ ] Database connection encryption
- [ ] File upload validation
- [ ] Rate limiting for API endpoints

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Run tests and linting
6. Submit pull request

## 📝 API Documentation

- **Swagger UI**: `/api/docs/`
- **ReDoc**: `/api/redoc/`
- **OpenAPI Schema**: `/api/swagger.json`

## 🎉 Congratulations!

Your Procure-to-Pay system is now ready for production! 

### What You've Built:
✅ **Complete Purchase Request Workflow**
✅ **Multi-level Approval System**  
✅ **AI Document Processing**
✅ **Role-based Access Control**
✅ **RESTful APIs with Documentation**
✅ **Docker Containerization**
✅ **Production-ready Deployment**

### Next Steps:
1. Deploy to Render
2. Set up monitoring
3. Create frontend application
4. Add more AI features
5. Scale as needed

Happy coding! 🚀