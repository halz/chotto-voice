"""JWT token handling."""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt

from server.config import get_settings
from server.db import get_user_by_id
from server.db.models import User


ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer()


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    settings = get_settings()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[str]:
    """Verify JWT token and return user_id."""
    settings = get_settings()
    
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    user_id = verify_token(token)
    
    if user_id is None:
        raise credentials_exception
    
    user = await get_user_by_id(user_id)
    if user is None:
        raise credentials_exception
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    )
) -> Optional[User]:
    """Get current user if authenticated, None otherwise."""
    if credentials is None:
        return None
    
    token = credentials.credentials
    user_id = verify_token(token)
    
    if user_id is None:
        return None
    
    return await get_user_by_id(user_id)
