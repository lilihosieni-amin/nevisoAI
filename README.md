# Neviso - Speech-to-Text Platform for Students

Neviso is a specialized speech-to-text platform designed for students. Users can upload audio/image files from lectures, which are processed by the Gemini AI model to produce structured, editable digital notes.

## Features

- 🎤 **Audio/Image to Text**: Convert lecture recordings and images to structured notes using Gemini AI
- 📚 **Notebook Organization**: Organize notes into subject-based notebooks
- ✏️ **Rich Text Editor**: Edit AI-generated content with a visual editor
- 📄 **PDF Export**: Export individual notes or entire notebooks as PDF files
- 💳 **Subscription Plans**: Multiple subscription tiers with different feature sets
- 🔐 **OTP Authentication**: Secure phone-based authentication
- 🌙 **Dark Mode**: Full dark mode support

## Technology Stack

### Backend
- **FastAPI**: Modern, fast Python web framework
- **SQLAlchemy**: Async ORM for database operations
- **MySQL**: Primary database
- **Celery**: Asynchronous task processing
- **Redis**: Message broker for Celery
- **Gemini AI**: Google's Generative AI for transcription
- **Alembic**: Database migrations

### Frontend
- **Jinja2**: Template engine
- **Vanilla JavaScript**: No framework dependencies
- **Responsive Design**: Mobile-first approach

## Project Structure

```
neviso-backend/
├── app/
│   ├── api/v1/           # API endpoints
│   ├── core/             # Core utilities (config, security, dependencies)
│   ├── crud/             # Database CRUD operations
│   ├── db/               # Database models and session
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic (AI, PDF, SMS)
│   ├── worker/           # Celery tasks
│   ├── templates/        # Jinja2 templates
│   ├── static/           # Static files (CSS, JS)
│   └── main.py           # FastAPI application
├── alembic/              # Database migrations
├── uploads/              # Uploaded files storage
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variables template
└── README.md            # This file
```

## Prerequisites

- Python 3.10+
- MySQL 8.0+
- Redis 6.0+
- Gemini API Key (from Google AI Studio)

## Installation

### 1. Clone the repository

```bash
cd neviso-backend
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` and configure your settings:

```env
# Database
DATABASE_URL=mysql+asyncmy://root:your_password@localhost:3306/neviso_db

# Security
SECRET_KEY=your-very-secret-key-change-this
ALGORITHM=HS256

# Gemini AI
GEMINI_API_KEY=your-gemini-api-key-here

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Application
UPLOAD_DIR=./uploads
```

### 5. Create MySQL database

```bash
mysql -u root -p
```

```sql
CREATE DATABASE neviso_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

### 6. Run database migrations

```bash
alembic upgrade head
```

This will create all tables and insert sample subscription plans.

### 7. Create uploads directory

```bash
mkdir -p uploads
```

## Running the Application

### 1. Start Redis (in a separate terminal)

```bash
redis-server
```

### 2. Start Celery worker (in a separate terminal)

```bash
celery -A app.worker.celery_app worker --loglevel=info
```

### 3. Start FastAPI application

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The application will be available at: [http://localhost:8000](http://localhost:8000)

## API Documentation

Once the application is running, you can access:

- **Interactive API docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative API docs (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

## API Endpoints

### Authentication
- `POST /api/v1/auth/request-otp` - Request OTP for phone number
- `POST /api/v1/auth/verify-otp` - Verify OTP and get JWT tokens

### Plans
- `GET /api/v1/plans/` - Get all active subscription plans

### Payments & Subscriptions
- `POST /api/v1/payments/create-checkout` - Create payment checkout
- `GET /api/v1/payments/callback` - Payment gateway callback (mock)

### Notebooks
- `POST /api/v1/notebooks/` - Create notebook
- `GET /api/v1/notebooks/` - Get all notebooks
- `GET /api/v1/notebooks/{id}` - Get notebook by ID
- `PUT /api/v1/notebooks/{id}` - Update notebook
- `DELETE /api/v1/notebooks/{id}` - Delete notebook

### Notes
- `POST /api/v1/notes/` - Create note with file upload
- `GET /api/v1/notes/` - Get all notes (optional: filter by notebook_id)
- `GET /api/v1/notes/{id}` - Get note by ID
- `PUT /api/v1/notes/{id}` - Update note
- `DELETE /api/v1/notes/{id}` - Delete note
- `GET /api/v1/notes/{id}/export/pdf` - Export note as PDF

### Export
- `GET /api/v1/export/notebooks/{id}/pdf` - Export entire notebook as PDF

### Users
- `GET /api/v1/users/me` - Get current user profile
- `PUT /api/v1/users/me` - Update current user profile
- `GET /api/v1/users/me/subscription` - Get current subscription

## Frontend Pages

- `/` - Landing page
- `/login` - Login/Signup with OTP
- `/notebooks` - Notebooks dashboard (protected)
- `/notes?notebook_id={id}` - Notes in a notebook (protected)
- `/all-notes` - All notes (protected)
- `/editor?note_id={id}` - Note editor (protected)
- `/upload` - Upload new file (protected)
- `/profile` - User profile (protected)
- `/plans` - Subscription plans

## User Flow

1. **Registration/Login**: User enters phone number and receives OTP via SMS
2. **Verify OTP**: User enters OTP and gets authenticated
3. **Create Notebooks**: User creates notebooks for different subjects
4. **Upload Files**: User uploads audio/image files
5. **AI Processing**: Celery worker processes file with Gemini AI in background
6. **View & Edit**: User views and edits the structured AI-generated content
7. **Export**: User exports notes or notebooks as PDF

## Gemini AI Integration

The application uses Google's Gemini 1.5 Flash model for transcription. The AI processes files and returns structured JSON:

```json
[
  {
    "title": "Introduction to Calculus",
    "content": "<h1>Intro</h1><p>Calculus is the study of change...</p>"
  },
  {
    "title": "Derivatives",
    "content": "<h2>Definition</h2><p>The derivative measures...</p>"
  }
]
```

## Database Schema

The application uses the following main tables:

- `users` - User accounts
- `user_otps` - OTP verification codes
- `plans` - Subscription plans
- `user_subscriptions` - User subscriptions
- `payments` - Payment records
- `notebooks` - Note collections
- `notes` - Individual notes with JSON content
- `uploads` - Uploaded file records
- `activity_logs` - User activity tracking

## Development

### Running tests

```bash
pytest
```

### Creating a new migration

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Code formatting

```bash
black app/
isort app/
```

## Production Deployment

1. Set `DEBUG=False` in production
2. Use a production WSGI server (e.g., Gunicorn)
3. Set up proper SSL/TLS certificates
4. Use a production-grade database setup
5. Configure proper backup strategies
6. Set up monitoring and logging
7. Use environment-specific `.env` files
8. Implement rate limiting
9. Set up CDN for static files

Example production command:

```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Security Notes

- All API endpoints that manage user data are protected with JWT authentication
- OTP codes expire after 5 minutes
- Passwords are hashed using bcrypt
- File uploads are validated and stored securely
- CORS is configured (update in production)

## License

This project is proprietary software. All rights reserved.

## Support

For support, please contact the development team.

---

**Built with ❤️ for students**
