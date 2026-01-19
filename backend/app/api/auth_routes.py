"""Authentication and user management routes."""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional, List
import time

from app.models.schemas import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    PasswordReset,
    AdminUserUpdate,
    LLMConfigUpdate,
    EmbeddingConfigUpdate,
    ModelConfig,
)
from app.services.auth import (
    create_user,
    authenticate_user,
    create_token,
    verify_token,
    get_user_by_id,
    update_password,
    list_users,
    update_user_role,
    toggle_user_active,
    delete_user,
    ensure_admin_exists,
)
from app.services.llm_settings import get_effective_llm_config
from app.services.llm_client import chat_completion_with_usage, LLMMessage
from app.services.embeddings import embed_texts
from app.services.db import record_token_usage, get_token_usage_summary
from app.services.auth import get_llm_config, set_llm_config, get_embedding_config, set_embedding_config

router = APIRouter(prefix="/auth", tags=["Authentication"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Extract and verify user from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录")
    
    # Support "Bearer <token>" format
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    
    user = verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="无效或过期的令牌")
    
    return user


def get_admin_user(authorization: Optional[str] = Header(None)) -> dict:
    """Verify user is admin."""
    user = get_current_user(authorization)
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


def get_optional_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    """Get current user if logged in, None otherwise."""
    if not authorization:
        return None
    
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]
    
    return verify_token(token)


# ==================== Public Auth Routes ====================

@router.post("/register", response_model=TokenResponse)
def register(data: UserRegister):
    """Register a new user."""
    try:
        user = create_user(data.username, data.email, data.password)
        token = create_token(user)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": user,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin):
    """Login with username/email and password."""
    user = authenticate_user(data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    token = create_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserResponse)
def get_me(user: dict = Depends(get_current_user)):
    """Get current user info."""
    full_user = get_user_by_id(user["id"])
    if not full_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return full_user


@router.post("/password/reset")
def reset_password(data: PasswordReset, user: dict = Depends(get_current_user)):
    """Reset current user's password."""
    # Verify old password
    auth_user = authenticate_user(user["username"], data.old_password)
    if not auth_user:
        raise HTTPException(status_code=400, detail="当前密码错误")
    
    success = update_password(user["id"], data.new_password)
    if not success:
        raise HTTPException(status_code=500, detail="密码更新失败")
    
    return {"message": "密码已更新"}


# ==================== Admin Routes ====================

@admin_router.get("/users", response_model=List[UserResponse])
def admin_list_users(admin: dict = Depends(get_admin_user)):
    """List all users (admin only)."""
    return list_users()


@admin_router.put("/users/{user_id}")
def admin_update_user(user_id: str, data: AdminUserUpdate, admin: dict = Depends(get_admin_user)):
    """Update user role or status (admin only)."""
    if data.role is not None:
        if data.role not in ["admin", "user"]:
            raise HTTPException(status_code=400, detail="无效的角色")
        update_user_role(user_id, data.role)
    
    if data.is_active is not None:
        toggle_user_active(user_id, data.is_active)
    
    return {"message": "用户已更新"}


@admin_router.delete("/users/{user_id}")
def admin_delete_user(user_id: str, admin: dict = Depends(get_admin_user)):
    """Delete a user (admin only)."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    success = delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return {"message": "用户已删除"}


@admin_router.get("/llm-config")
def admin_get_llm_config(admin: dict = Depends(get_admin_user)):
    """Get global LLM configuration (admin only)."""
    config = get_llm_config()
    if not config:
        return {"configured": False}
    
    # Mask API key for security
    masked_config = config.copy()
    if "api_key" in masked_config:
        key = masked_config["api_key"]
        masked_config["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    
    return {"configured": True, "config": masked_config}


@admin_router.put("/llm-config")
def admin_set_llm_config(data: LLMConfigUpdate, admin: dict = Depends(get_admin_user)):
    """Set global LLM configuration (admin only)."""
    config = {
        "base_url": data.base_url,
        "api_key": data.api_key,
        "model_name": data.model_name,
        "timeout_s": data.timeout_s,
        "max_tokens": data.max_tokens,
    }
    set_llm_config(config, admin["id"])
    return {"message": "LLM 配置已更新"}


@admin_router.post("/llm-config/test")
def admin_test_llm_config(admin: dict = Depends(get_admin_user)):
    """Test global LLM configuration connectivity (admin only)."""
    model = get_effective_llm_config(None)
    test_model = ModelConfig(
        base_url=model.base_url,
        api_key=model.api_key,
        model_name=model.model_name,
        timeout_s=model.timeout_s,
        max_tokens=min(32, model.max_tokens),
    )
    start = time.time()
    try:
        reply, usage = chat_completion_with_usage(
            [LLMMessage(role="user", content="请只回答：OK")],
            test_model,
        )
        record_token_usage(
            repo_id=None,
            kind="llm",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            is_estimated=usage.get("is_estimated", True),
            source="admin_llm_test",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"LLM 连接失败：{exc}")
    latency_ms = int((time.time() - start) * 1000)
    return {
        "ok": True,
        "latency_ms": latency_ms,
        "model_name": test_model.model_name,
        "base_url": test_model.base_url,
        "reply_preview": (reply or "").strip()[:50],
    }


@admin_router.get("/embedding-config")
def admin_get_embedding_config(admin: dict = Depends(get_admin_user)):
    """Get global Embedding model configuration (admin only)."""
    config = get_embedding_config()
    if not config:
        return {"configured": False}
    
    # Mask API key for security
    masked_config = config.copy()
    if "api_key" in masked_config:
        key = masked_config["api_key"]
        masked_config["api_key"] = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
    
    return {"configured": True, "config": masked_config}


@admin_router.put("/embedding-config")
def admin_set_embedding_config(data: EmbeddingConfigUpdate, admin: dict = Depends(get_admin_user)):
    """Set global Embedding model configuration (admin only)."""
    config = {
        "base_url": data.base_url,
        "api_key": data.api_key,
        "model_name": data.model_name,
    }
    set_embedding_config(config, admin["id"])
    return {"message": "Embedding 配置已更新"}


@admin_router.post("/embedding-config/test")
def admin_test_embedding_config(admin: dict = Depends(get_admin_user)):
    """Test Embedding configuration connectivity (admin only)."""
    config = get_embedding_config()
    if not config:
        raise HTTPException(status_code=400, detail="Embedding 未配置")
    start = time.time()
    try:
        vectors = embed_texts(["ping"], repo_id=None)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Embedding 连接失败：{exc}")
    latency_ms = int((time.time() - start) * 1000)
    dim = len(vectors[0]) if vectors else 0
    return {
        "ok": True,
        "latency_ms": latency_ms,
        "model_name": config.get("model_name", ""),
        "base_url": config.get("base_url", ""),
        "dim": dim,
    }


@admin_router.get("/token-usage")
def admin_get_token_usage(admin: dict = Depends(get_admin_user)):
    """Get total token usage (admin only)."""
    return get_token_usage_summary()


@admin_router.get("/stats")
def admin_get_stats(admin: dict = Depends(get_admin_user)):
    """Get system statistics (admin only)."""
    from app.services.db import get_conn, init_db
    
    init_db()
    with get_conn() as conn:
        users_count = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
        repos_count = conn.execute("SELECT COUNT(*) as cnt FROM repos").fetchone()["cnt"]
        active_users = conn.execute(
            "SELECT COUNT(*) as cnt FROM users WHERE is_active = 1"
        ).fetchone()["cnt"]
    
    return {
        "users_total": users_count,
        "users_active": active_users,
        "projects_total": repos_count,
    }


