"""Global LLM configuration helpers (admin-managed)."""
from __future__ import annotations

from fastapi import HTTPException

from app.models.schemas import ModelConfig
from app.services.auth import get_llm_config


def get_effective_llm_config(_user_provided: ModelConfig | None = None) -> ModelConfig:
    """Get effective LLM config: global admin config only."""
    global_config = get_llm_config()
    if global_config:
        return ModelConfig(**global_config)

    raise HTTPException(status_code=400, detail="管理员尚未配置 LLM，请联系管理员")
