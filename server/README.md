# Chotto Voice Server

Backend API server for Chotto Voice production deployment.

## Architecture

```
Client (PyQt6)  →  FastAPI Server  →  OpenAI Whisper API
                        ↓
                  Turso Database
                        ↓
                     Stripe
```

## Features

- **Google OAuth**: Login with Google account
- **Turso Database**: User management, usage tracking
- **Stripe Billing**: Credit purchases
- **OpenAI Whisper Proxy**: Server-side API key management

## Setup

### 1. Create Turso Database

```bash
# Install Turso CLI
curl -sSfL https://get.tur.so/install.sh | bash

# Login
turso auth login

# Create database
turso db create chotto-voice

# Get connection URL
turso db show chotto-voice --url

# Create auth token
turso db tokens create chotto-voice
```

### 2. Setup Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Go to **APIs & Services > Credentials**
5. Create **OAuth 2.0 Client ID**
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/auth/google/callback`
6. Copy Client ID and Client Secret

### 3. Setup Stripe

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Get API keys from **Developers > API keys**
3. Create webhook endpoint for `/api/billing/webhook`
4. Copy Webhook signing secret

### 4. Configure Environment

Copy `.env.example` to `.env` and fill in:

```bash
cp .env.example .env
# Edit .env with your values
```

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Run Server

```bash
# Development
uvicorn server.main:app --reload

# Production
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Authentication

- `GET /auth/google/url` - Get Google OAuth URL
- `GET /auth/google/callback` - OAuth callback
- `POST /auth/google/token` - Exchange code for JWT

### Transcription

- `POST /api/transcribe` - Transcribe audio (requires auth)
- `GET /api/transcribe/estimate` - Estimate credits needed

### Users

- `GET /api/users/me` - Get current user profile
- `GET /api/users/me/stats` - Get usage statistics
- `GET /api/users/me/credits` - Get credit balance

### Billing

- `GET /api/billing/packages` - List credit packages
- `GET /api/billing/balance` - Get credit balance
- `POST /api/billing/checkout/{package_id}` - Create checkout session
- `POST /api/billing/webhook` - Stripe webhook
- `GET /api/billing/verify/{session_id}` - Verify payment

## Database Schema

### Users
- id, email, name, picture_url, google_id, credits, created_at, updated_at

### Usage Records
- id, user_id, action, credits_used, duration_seconds, metadata, created_at

### Credit Transactions
- id, user_id, amount, transaction_type, stripe_payment_id, description, created_at

## Credit System

- **Signup Bonus**: 100 free credits
- **Pricing**: 1 credit per 15 seconds of audio
- **Packages**:
  - Starter: 500 credits ($4.99)
  - Pro: 2000 credits ($14.99)
  - Team: 10000 credits ($49.99)

## Deployment

### Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Railway / Render / Fly.io

Set environment variables and deploy.

## Security Notes

- OpenAI API key is **never** sent to client
- JWT tokens expire after 30 days
- All API endpoints require authentication except `/health` and `/auth/*`
