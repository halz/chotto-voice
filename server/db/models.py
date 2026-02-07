"""Database models (Pydantic schemas for Turso/LibSQL)."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class User(BaseModel):
    """User model."""
    id: str  # UUID
    email: EmailStr
    name: Optional[str] = None
    picture_url: Optional[str] = None
    google_id: str
    credits: int = 0
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    """User creation payload."""
    email: EmailStr
    name: Optional[str] = None
    picture_url: Optional[str] = None
    google_id: str


class UsageRecord(BaseModel):
    """Usage record for tracking API consumption."""
    id: str  # UUID
    user_id: str
    action: str  # 'transcribe', 'ai_process', etc.
    credits_used: int
    duration_seconds: float  # Audio duration
    metadata: Optional[dict] = None
    created_at: datetime


class CreditTransaction(BaseModel):
    """Credit transaction record."""
    id: str
    user_id: str
    amount: int  # Positive = add, negative = use
    transaction_type: str  # 'signup_bonus', 'purchase', 'usage'
    stripe_payment_id: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
