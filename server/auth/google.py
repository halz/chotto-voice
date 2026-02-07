"""Google OAuth2 authentication."""
import httpx
from typing import Optional
from urllib.parse import urlencode

from server.config import get_settings


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


def get_google_auth_url(state: Optional[str] = None) -> str:
    """Generate Google OAuth authorization URL."""
    settings = get_settings()
    
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    
    if state:
        params["state"] = state
    
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for tokens."""
    settings = get_settings()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_redirect_uri,
            }
        )
        response.raise_for_status()
        return response.json()


async def get_google_user_info(access_token: str) -> dict:
    """Get user info from Google using access token."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"}
        )
        response.raise_for_status()
        return response.json()


async def verify_google_token(code: str) -> dict:
    """Verify Google OAuth code and return user info.
    
    Returns:
        dict: User info containing:
            - id: Google user ID
            - email: User's email
            - name: User's name
            - picture: Profile picture URL
    """
    # Exchange code for tokens
    tokens = await exchange_code_for_tokens(code)
    
    # Get user info
    user_info = await get_google_user_info(tokens["access_token"])
    
    return {
        "google_id": user_info["id"],
        "email": user_info["email"],
        "name": user_info.get("name"),
        "picture_url": user_info.get("picture"),
        "access_token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token"),
    }
