"""Turso database connection and operations using HTTP API."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Any
import json

import httpx

from server.config import get_settings
from .models import User, UserCreate, UsageRecord, CreditTransaction


def execute_sql(sql: str, args: list = None) -> dict:
    """Execute SQL via Turso HTTP API."""
    settings = get_settings()
    base_url = settings.turso_db_url.replace("libsql://", "https://")
    
    # Turso HTTP API format (v2 pipeline)
    # Convert args to named params format
    params = {}
    if args:
        for i, arg in enumerate(args):
            params[f"p{i}"] = arg
        # Replace ? with :p0, :p1, etc.
        for i in range(len(args)):
            sql = sql.replace("?", f":p{i}", 1)
    
    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql, "named_args": [{"name": k, "value": {"type": "text" if isinstance(v, str) else "integer" if isinstance(v, int) else "float" if isinstance(v, float) else "null", "value": str(v) if v is not None else None}} for k, v in params.items()] if params else []}},
            {"type": "close"}
        ]
    }
    
    response = httpx.post(
        f"{base_url}/v2/pipeline",
        headers={
            "Authorization": f"Bearer {settings.turso_auth_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


def execute_batch(statements: list) -> dict:
    """Execute multiple SQL statements."""
    settings = get_settings()
    base_url = settings.turso_db_url.replace("libsql://", "https://")
    
    requests = []
    for sql, args in statements:
        params = {}
        if args:
            for i, arg in enumerate(args):
                params[f"p{i}"] = arg
            for i in range(len(args)):
                sql = sql.replace("?", f":p{i}", 1)
        
        requests.append({
            "type": "execute",
            "stmt": {
                "sql": sql,
                "named_args": [{"name": k, "value": {"type": "text" if isinstance(v, str) else "integer" if isinstance(v, int) else "float" if isinstance(v, float) else "null", "value": str(v) if v is not None else None}} for k, v in params.items()] if params else []
            }
        })
    
    requests.append({"type": "close"})
    
    response = httpx.post(
        f"{base_url}/v2/pipeline",
        headers={
            "Authorization": f"Bearer {settings.turso_auth_token}",
            "Content-Type": "application/json",
        },
        json={"requests": requests},
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


async def init_db():
    """Initialize database schema."""
    statements = [
        # Users table
        ("""
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
        """, []),
        
        # Usage records table
        ("""
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
        """, []),
        
        # Credit transactions table
        ("""
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
        """, []),
        
        # Indexes
        ("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)", []),
        ("CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id)", []),
        ("CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage_records(user_id)", []),
        ("CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON credit_transactions(user_id)", []),
    ]
    
    execute_batch(statements)


def _extract_rows(result: dict) -> list:
    """Extract rows from Turso response."""
    rows = []
    if "results" in result:
        for res in result["results"]:
            if res.get("type") == "ok" and res.get("response", {}).get("type") == "execute":
                exec_result = res["response"]["result"]
                cols = [c["name"] for c in exec_result.get("cols", [])]
                for row in exec_result.get("rows", []):
                    row_dict = {}
                    for i, val in enumerate(row):
                        if isinstance(val, dict) and "value" in val:
                            row_dict[cols[i]] = val["value"]
                        else:
                            row_dict[cols[i]] = val
                    rows.append(row_dict)
    return rows


def _row_to_user(row: dict) -> User:
    """Convert row dict to User model."""
    return User(
        id=row["id"],
        email=row["email"],
        name=row.get("name"),
        picture_url=row.get("picture_url"),
        google_id=row["google_id"],
        credits=int(row.get("credits", 0)) if row.get("credits") else 0,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"])
    )


# User operations
async def get_user_by_google_id(google_id: str) -> Optional[User]:
    """Get user by Google ID."""
    result = execute_sql(
        "SELECT * FROM users WHERE google_id = ?",
        [google_id]
    )
    
    rows = _extract_rows(result)
    if rows:
        return _row_to_user(rows[0])
    return None


async def get_user_by_id(user_id: str) -> Optional[User]:
    """Get user by ID."""
    result = execute_sql(
        "SELECT * FROM users WHERE id = ?",
        [user_id]
    )
    
    rows = _extract_rows(result)
    if rows:
        return _row_to_user(rows[0])
    return None


async def create_user(user_data: UserCreate, free_credits: int = 100) -> User:
    """Create a new user with signup bonus credits."""
    now = datetime.now(timezone.utc).isoformat()
    user_id = str(uuid.uuid4())
    
    execute_sql(
        """
        INSERT INTO users (id, email, name, picture_url, google_id, credits, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [user_id, user_data.email, user_data.name, user_data.picture_url, 
         user_data.google_id, free_credits, now, now]
    )
    
    # Record signup bonus transaction
    await add_credit_transaction(
        user_id=user_id,
        amount=free_credits,
        transaction_type="signup_bonus",
        description="Welcome bonus credits"
    )
    
    return await get_user_by_id(user_id)


async def update_user_credits(user_id: str, delta: int) -> int:
    """Update user credits and return new balance."""
    now = datetime.now(timezone.utc).isoformat()
    
    execute_sql(
        "UPDATE users SET credits = credits + ?, updated_at = ? WHERE id = ?",
        [delta, now, user_id]
    )
    
    result = execute_sql("SELECT credits FROM users WHERE id = ?", [user_id])
    rows = _extract_rows(result)
    if rows:
        return int(rows[0].get("credits", 0))
    return 0


# Usage operations
async def record_usage(
    user_id: str, 
    action: str, 
    credits_used: int, 
    duration_seconds: float,
    metadata: Optional[dict] = None
) -> UsageRecord:
    """Record API usage and deduct credits."""
    now = datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())
    
    metadata_str = json.dumps(metadata) if metadata else None
    
    execute_sql(
        """
        INSERT INTO usage_records (id, user_id, action, credits_used, duration_seconds, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [record_id, user_id, action, credits_used, duration_seconds, metadata_str, now]
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
    now = datetime.now(timezone.utc).isoformat()
    transaction_id = str(uuid.uuid4())
    
    execute_sql(
        """
        INSERT INTO credit_transactions (id, user_id, amount, transaction_type, stripe_payment_id, description, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [transaction_id, user_id, amount, transaction_type, stripe_payment_id, description, now]
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
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    
    result = execute_sql(
        """
        SELECT 
            COUNT(*) as total_requests,
            COALESCE(SUM(credits_used), 0) as total_credits_used,
            COALESCE(SUM(duration_seconds), 0) as total_duration
        FROM usage_records 
        WHERE user_id = ? AND created_at >= ?
        """,
        [user_id, cutoff]
    )
    
    rows = _extract_rows(result)
    if rows:
        row = rows[0]
        return {
            "total_requests": int(row.get("total_requests", 0)),
            "total_credits_used": int(row.get("total_credits_used", 0)),
            "total_duration_seconds": float(row.get("total_duration", 0)),
            "period_days": days
        }
    
    return {
        "total_requests": 0,
        "total_credits_used": 0,
        "total_duration_seconds": 0,
        "period_days": days
    }


# Keep get_db for compatibility
def get_db():
    """Placeholder for compatibility."""
    return None
