"""Chotto Voice Server - FastAPI application."""
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.config import get_settings
from server.db import init_db, get_user_by_google_id, create_user
from server.db.models import UserCreate
from server.auth.google import get_google_auth_url, verify_google_token
from server.auth.jwt import create_access_token
from server.api import transcribe_router, users_router, billing_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize database on startup."""
    await init_db()
    yield


app = FastAPI(
    title="Chotto Voice API",
    description="Voice transcription API with usage tracking and billing",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(transcribe_router)
app.include_router(users_router)
app.include_router(billing_router)


# ============= Auth Endpoints =============

class AuthUrlResponse(BaseModel):
    """Auth URL response."""
    auth_url: str
    state: str


class TokenResponse(BaseModel):
    """Token response after successful auth."""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    name: str | None
    credits: int
    is_new_user: bool


@app.get("/auth/google/url", response_model=AuthUrlResponse)
async def get_auth_url():
    """Get Google OAuth authorization URL.
    
    The client should redirect the user to this URL to initiate OAuth flow.
    After successful auth, Google will redirect to the callback URL with a code.
    """
    state = secrets.token_urlsafe(32)
    auth_url = get_google_auth_url(state=state)
    
    return AuthUrlResponse(auth_url=auth_url, state=state)


@app.get("/auth/google/callback")
async def google_callback(code: str, state: str | None = None):
    """Handle Google OAuth callback.
    
    This endpoint receives the authorization code from Google,
    verifies it, and returns a JWT token for the user.
    """
    try:
        # Verify Google token and get user info
        google_user = await verify_google_token(code)
        
        # Check if user exists
        user = await get_user_by_google_id(google_user["google_id"])
        is_new_user = False
        
        if not user:
            # Create new user with free credits
            settings = get_settings()
            user = await create_user(
                UserCreate(
                    email=google_user["email"],
                    name=google_user["name"],
                    picture_url=google_user["picture_url"],
                    google_id=google_user["google_id"],
                ),
                free_credits=settings.free_credits
            )
            is_new_user = True
        
        # Create JWT token
        access_token = create_access_token(user.id)
        
        return TokenResponse(
            access_token=access_token,
            user_id=user.id,
            email=user.email,
            name=user.name,
            credits=user.credits,
            is_new_user=is_new_user,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Authentication failed: {str(e)}"
        )


@app.post("/auth/google/token", response_model=TokenResponse)
async def google_token_auth(code: str):
    """Authenticate using Google OAuth code (for desktop app flow).
    
    The desktop app handles the OAuth redirect and sends the code here.
    """
    return await google_callback(code=code)


# ============= Health Endpoints =============

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "chotto-voice-api"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Chotto Voice API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
