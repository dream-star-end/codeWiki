"""User authentication and JWT token management."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

import jwt

from app.services.db import get_conn, init_db

# JWT Configuration
JWT_SECRET = "codewiki_secret_key_change_in_production"  # Should be from env in production
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash password with salt using SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def _verify_password(password: str, password_hash: str) -> bool:
    """Verify password against hash."""
    try:
        salt, stored_hash = password_hash.split(":")
        new_hash = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return new_hash == stored_hash
    except ValueError:
        return False


def create_user(username: str, email: str, password: str, role: str = "user") -> dict:
    """Create a new user."""
    init_db()
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    password_hash = _hash_password(password)
    now = _now()
    
    with get_conn() as conn:
        # Check if username or email exists
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        ).fetchone()
        if existing:
            raise ValueError("用户名或邮箱已存在")
        
        conn.execute(
            """
            INSERT INTO users (id, username, email, password_hash, role, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (user_id, username, email, password_hash, role, now, now)
        )
    
    return {
        "id": user_id,
        "username": username,
        "email": email,
        "role": role,
        "is_active": True,
        "created_at": now,
    }


def authenticate_user(username_or_email: str, password: str) -> Optional[dict]:
    """Authenticate user by username/email and password."""
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, username, email, password_hash, role, is_active
            FROM users 
            WHERE (username = ? OR email = ?) AND is_active = 1
            """,
            (username_or_email, username_or_email)
        ).fetchone()
        
        if not row:
            return None
        
        if not _verify_password(password, row["password_hash"]):
            return None
        
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
        }


def create_token(user: dict) -> str:
    """Create JWT token for user."""
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and return user info."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "id": payload["sub"],
            "username": payload["username"],
            "email": payload["email"],
            "role": payload["role"],
        }
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Get user by ID."""
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, role, is_active, created_at FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "created_at": row["created_at"],
        }


def update_password(user_id: str, new_password: str) -> bool:
    """Update user password."""
    init_db()
    password_hash = _hash_password(new_password)
    with get_conn() as conn:
        result = conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (password_hash, _now(), user_id)
        )
        return result.rowcount > 0


def list_users() -> list:
    """List all users (admin only)."""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, email, role, is_active, created_at FROM users ORDER BY created_at DESC"
        ).fetchall()
        return [
            {
                "id": row["id"],
                "username": row["username"],
                "email": row["email"],
                "role": row["role"],
                "is_active": bool(row["is_active"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]


def update_user_role(user_id: str, role: str) -> bool:
    """Update user role (admin only)."""
    init_db()
    with get_conn() as conn:
        result = conn.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            (role, _now(), user_id)
        )
        return result.rowcount > 0


def toggle_user_active(user_id: str, is_active: bool) -> bool:
    """Enable/disable user (admin only)."""
    init_db()
    with get_conn() as conn:
        result = conn.execute(
            "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
            (1 if is_active else 0, _now(), user_id)
        )
        return result.rowcount > 0


def delete_user(user_id: str) -> bool:
    """Delete user (admin only)."""
    init_db()
    with get_conn() as conn:
        result = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        return result.rowcount > 0


# System settings (LLM config)
def get_system_setting(key: str) -> Optional[str]:
    """Get system setting by key."""
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM system_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def set_system_setting(key: str, value: str, updated_by: str) -> None:
    """Set system setting (admin only)."""
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO system_settings (key, value, updated_at, updated_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?, updated_by = ?
            """,
            (key, value, _now(), updated_by, value, _now(), updated_by)
        )


def get_llm_config() -> Optional[dict]:
    """Get global LLM configuration."""
    import json
    config_str = get_system_setting("llm_config")
    if config_str:
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            return None
    return None


def set_llm_config(config: dict, updated_by: str) -> None:
    """Set global LLM configuration (admin only)."""
    import json
    set_system_setting("llm_config", json.dumps(config), updated_by)


def get_embedding_config() -> Optional[dict]:
    """Get global Embedding model configuration."""
    import json
    config_str = get_system_setting("embedding_config")
    if config_str:
        try:
            return json.loads(config_str)
        except json.JSONDecodeError:
            return None
    return None


def set_embedding_config(config: dict, updated_by: str) -> None:
    """Set global Embedding model configuration (admin only)."""
    import json
    set_system_setting("embedding_config", json.dumps(config), updated_by)


def ensure_admin_exists() -> None:
    """Ensure at least one admin user exists. Create default if not."""
    init_db()
    with get_conn() as conn:
        admin = conn.execute(
            "SELECT id FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
        if not admin:
            # Create default admin
            create_user(
                username="admin",
                email="admin@codewiki.local",
                password="admin123",  # Should be changed immediately!
                role="admin"
            )
            print("默认管理员已创建: admin / admin123 (请立即修改密码!)")
