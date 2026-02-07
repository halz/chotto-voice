"""Turso database connection and operations."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

import libsql_experimental as libsql

from server.config import get_settings
from .models import User, UserCreate, UsageRecord, CreditTransaction


# Global connection
_conn = None


def get_db():
    """Get database connection."""
    global _conn
    if _conn is None:
        settings = get_settings()
        _conn = libsql.connect(
            database=settings.turso_db_url,
            auth_token=settings.turso_auth_token
        )
    return _conn


async def init_db():
    """Initialize database schema."""
    conn = get_db()
    
    # Users table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            picture_url TEXT,
            google_id TEXT UNIQUE NOT NULL,
            credits INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Usage records table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usage_records (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            credits_used INTEGER NOT NULL,
            duration_seconds REAL NOT NULL,
            metadata TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Credit transactions table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            stripe_payment_id TEXT,
            description TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    # Indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage_records(user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON credit_transactions(user_id)")
    
    conn.commit()


# User operations
async def get_user_by_google_id(google_id: str) -> Optional[User]:
    """Get user by Google ID."""
    conn = get_db()
    result = conn.execute(
        "SELECT * FROM users WHERE google_id = ?",
        (google_id,)
    ).fetchone()
    
    if result:
        return User(
            id=result[0],
            email=result[1],
            name=result[2],
            picture_url=result[3],
            google_id=result[4],
            credits=result[5],
            created_at=datetime.fromisoformat(result[6]),
            updated_at=datetime.fromisoformat(result[7])
        )
    return None


async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get user by ID."""
    conn = get_db()
    result = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    
    if result:
        return User(
            id=result[0],
            email=result[1],
            name=result[2],
            picture_url=result[3],
            google_id=result[4],
            credits=result[5],
            created_at=datetime.fromisoformat(result[6]),
            updated_at=datetime.fromisoformat(result[7])
        )
    return None


async def create_user(user_data: UserCreate, free_credits: int = 100) -> User:
    """Create a new user with signup bonus credits."""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    
    conn.execute(
        """
        INSERT INTO users (id, email, name, picture_url, google_id, credits, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, user_data.email, user_data.name, user_data.picture_url, 
         user_data.google_id, free_credits, now, now)
    )
    
    # Record signup bonus transaction
    await add_credit_transaction(
        user_id=user_id,
        amount=free_credits,
        transaction_type="signup_bonus",
        description="Welcome bonus credits"
    )
    
    conn.commit()
    
    return await get_user_by_id(user_id)


async def update_user_credits(user_id: str, delta: int) -> int:
    """Update user credits and return new balance."""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    conn.execute(
        "UPDATE users SET credits = credits + ?, updated_at = ? WHERE id = ?",
        (delta, now, user_id)
    )
    conn.commit()
    
    result = conn.execute("SELECT credits FROM users WHERE id = ?", (user_id,)).fetchone()
    return result[0] if result else 0


# Usage operations
async def record_usage(
    user_id: str, 
    action: str, 
    credits_used: int, 
    duration_seconds: float,
    metadata: Optional[dict] = None
) -> UsageRecord:
    """Record API usage and deduct credits."""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())
    
    import json
    metadata_str = json.dumps(metadata) if metadata else None
    
    conn.execute(
        """
        INSERT INTO usage_records (id, user_id, action, credits_used, duration_seconds, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (record_id, user_id, action, credits_used, duration_seconds, metadata_str, now)
    )
    
    # Deduct credits
    await update_user_credits(user_id, -credits_used)
    
    # Record transaction
    await add_credit_transaction(
        user_id=user_id,
        amount=-credits_used,
        transaction_type="usage",
        description=f"{action}: {duration_seconds:.1f}s"
    )
    
    conn.commit()
    
    return UsageRecord(
        id=record_id,
        user_id=user_id,
        action=action,
        credits_used=credits_used,
        duration_seconds=duration_seconds,
        metadata=metadata,
        created_at=datetime.fromisoformat(now)
    )


async def add_credit_transaction(
    user_id: str,
    amount: int,
    transaction_type: str,
    stripe_payment_id: Optional[str] = None,
    description: Optional[str] = None
) -> CreditTransaction:
    """Add a credit transaction record."""
    conn = get_db()
    now = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid.uuid4())
    
    conn.execute(
        """
        INSERT INTO credit_transactions (id, user_id, amount, transaction_type, stripe_payment_id, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (transaction_id, user_id, amount, transaction_type, stripe_payment_id, description, now)
    )
    
    return CreditTransaction(
        id=transaction_id,
        user_id=user_id,
        amount=amount,
        transaction_type=transaction_type,
        stripe_payment_id=stripe_payment_id,
        description=description,
        created_at=datetime.fromisoformat(now)
    )


async def get_user_usage_stats(user_id: str, days: int = 30) -> dict:
    """Get user's usage statistics for the past N days."""
    conn = get_db()
    from datetime import timedelta
    
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    result = conn.execute(
        """
        SELECT 
            COUNT(*) as total_requests,
            COALESCE(SUM(credits_used), 0) as total_credits_used,
            COALESCE(SUM(duration_seconds), 0) as total_duration
        FROM usage_records 
        WHERE user_id = ? AND created_at >= ?
        """,
        (user_id, cutoff)
    ).fetchone()
    
    return {
        "total_requests": result[0],
        "total_credits_used": result[1],
        "total_duration_seconds": result[2],
        "period_days": days
    }
