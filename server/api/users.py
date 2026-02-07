"""Users API - profile and usage info."""
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from server.auth.jwt import get_current_user
from server.db import get_user_usage_stats
from server.db.models import User


router = APIRouter(prefix="/api/users", tags=["users"])


class UserProfile(BaseModel):
    """User profile response."""
    id: str
    email: str
    name: Optional[str]
    picture_url: Optional[str]
    credits: int


class UsageStats(BaseModel):
    """Usage statistics response."""
    total_requests: int
    total_credits_used: int
    total_duration_seconds: float
    period_days: int


class UserProfileWithStats(UserProfile):
    """User profile with usage stats."""
    usage_stats: UsageStats


@router.get("/me", response_model=UserProfile)
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile."""
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        picture_url=current_user.picture_url,
        credits=current_user.credits,
    )


@router.get("/me/stats", response_model=UserProfileWithStats)
async def get_my_profile_with_stats(
    days: int = 30,
    current_user: User = Depends(get_current_user)
):
    """Get current user's profile with usage statistics."""
    stats = await get_user_usage_stats(current_user.id, days=days)
    
    return UserProfileWithStats(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        picture_url=current_user.picture_url,
        credits=current_user.credits,
        usage_stats=UsageStats(**stats),
    )


@router.get("/me/credits", response_model=dict)
async def get_my_credits(current_user: User = Depends(get_current_user)):
    """Get current user's credit balance."""
    return {
        "credits": current_user.credits,
        "user_id": current_user.id,
    }
