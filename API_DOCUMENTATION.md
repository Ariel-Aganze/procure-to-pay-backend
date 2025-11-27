# Procure-to-Pay API Documentation

## Authentication
All API endpoints (except registration/login) require JWT authentication.

### Headers

Authorization: Bearer <your_jwt_access_token>
Content-Type: application/json


## Endpoints Overview

### Authentication Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register/` | Register new user |
| POST | `/api/auth/login/` | Login user |
| POST | `/api/auth/logout/` | Logout user |
| POST | `/api/auth/token/refresh/` | Refresh JWT token |
| GET | `/api/auth/profile/` | Get user profile |
| PATCH | `/api/auth/profile/` | Update user profile |
| POST | `/api/auth/change-password/` | Change password |
| GET | `/api/auth/users/` | List users (approvers/admin only) |
| GET | `/api/auth/dashboard-stats/` | Get dashboard stats |

### Purchase Request Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/requests/` | List purchase requests |
| POST | `/api/requests/` | Create purchase request |
| GET | `/api/requests/{id}/` | Get request details |
| PATCH | `/api/requests/{id}/` | Update request |
| DELETE | `/api/requests/{id}/` | Delete request |
| POST | `/api/requests/{id}/approve/` | Approve/reject request |
| POST | `/api/requests/{id}/receipt/` | Upload receipt |
| GET | `/api/requests/{id}/workflow/` | Get workflow info |
| GET | `/api/my-requests/` | Get current user's requests |
| GET | `/api/pending-approvals/` | Get pending approvals |
| GET | `/api/finance-requests/` | Get approved requests (finance) |
| GET | `/api/dashboard-stats/` | Get dashboard statistics |

### Document Processing Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/documents/status/{id}/` | Get processing status |
| POST | `/api/documents/upload-proforma/{id}/` | Upload proforma |
| POST | `/api/documents/trigger/{id}/` | Trigger processing |
| GET | `/api/documents/jobs/` | List processing jobs |
| GET | `/api/documents/jobs/{id}/` | Get job details |
| GET | `/api/documents/extracted-data/` | List extracted data |
| GET | `/api/documents/validation-results/` | List validation results |
| GET | `/api/documents/ollama-status/` | Check AI service status |
| GET | `/api/documents/processing-stats/` | Get processing statistics |

### API Documentation
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/docs/` | Swagger UI documentation |
| GET | `/api/redoc/` | ReDoc documentation |
| GET | `/api/swagger.json` | OpenAPI schema |

## User Roles and Permissions

### Staff
- Create, update, delete own purchase requests
- Upload proforma and receipts for own requests
- View own request status and workflow

### Approver Level 1
- All staff permissions
- View and approve/reject requests (Level 1)
- View all purchase requests

### Approver Level 2  
- All Level 1 permissions
- Approve/reject requests requiring Level 2 approval

### Finance
- View all approved requests
- Access financial reports and statistics
- Trigger PO generation
- Upload receipts for any request

### Admin
- All permissions
- Manage users
- System administration

## Request Workflow

1. **Staff** creates purchase request with proforma
2. **AI** extracts data from proforma automatically
3. **Approver(s)** review and approve based on amount:
   - ≤ $1,000: Level 1 approval only
   - > $1,000: Level 1 + Level 2 approval
4. **System** generates Purchase Order automatically
5. **Staff/Finance** uploads receipt after purchase
6. **AI** validates receipt against PO
7. **Finance** reviews final documentation

## File Upload Formats

### Supported Formats
- **PDF**: `.pdf`
- **Images**: `.jpg`, `.jpeg`, `.png`

### Size Limits
- Maximum file size: 10MB

### File Types
- **Proforma**: Quotations, estimates, proforma invoices
- **Receipts**: Purchase receipts, invoices

## Error Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 500 | Internal Server Error |

## Example Usage

### 1. Register and Login
bash
# Register
curl -X POST http://localhost:8000/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "email": "john@company.com",
    "password": "securepass123",
    "password_confirm": "securepass123",
    "first_name": "John",
    "last_name": "Doe",
    "role": "staff"
  }'

# Login
curl -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "john_doe",
    "password": "securepass123"
  }'


### 2. Create Purchase Request
bash
curl -X POST http://localhost:8000/api/requests/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Office Supplies",
    "description": "Monthly office supplies order",
    "amount": "500.00",
    "priority": "medium",
    "vendor_name": "Office Depot",
    "vendor_email": "sales@officedepot.com"
  }'


### 3. Upload Proforma
bash
curl -X POST http://localhost:8000/api/documents/upload-proforma/REQUEST_ID/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "proforma=@/path/to/proforma.pdf"


### 4. Approve Request
bash
curl -X POST http://localhost:8000/api/requests/REQUEST_ID/approve/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "approved": true,
    "comments": "Approved for purchase"
  }'


## AI Features

### Automatic Data Extraction
- Extracts vendor information from proforma documents
- Parses line items, pricing, and terms
- Confidence scoring for data quality

### Purchase Order Generation
- Creates formatted PO from approved requests
- Includes all necessary business terms
- Professional document formatting

### Receipt Validation
- Compares receipts against purchase orders
- Identifies discrepancies in vendor, amount, items
- Provides validation scores and recommendations

## Development Setup

1. Clone repository
2. Create virtual environment
3. Install dependencies: `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and configure
5. Run migrations: `python manage.py migrate`
6. Create superuser: `python manage.py createsuperuser`
7. Start server: `python manage.py runserver`

## Production Deployment

### Render Deployment
1. Connect GitHub repository to Render
2. Configure environment variables from `.env.production`
3. Set build command: `./build.sh`
4. Set start command: `./start.sh`
5. Deploy!

### Required Services
- **PostgreSQL**: Database
- **Redis**: Background task queue
- **Ollama**: AI processing (separate service)

For detailed deployment instructions, see the deployment guide.