"""
LLM service factory for creating configured LLM clients.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import threading

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModelSettings
from pydantic_ai.models.fallback import FallbackModel
from openai import OpenAI

from codewiki.src.config import Config

logger = logging.getLogger(__name__)


_usage_lock = threading.Lock()
_token_usage: Dict[str, int] = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}


def reset_token_usage() -> None:
    with _usage_lock:
        _token_usage["prompt_tokens"] = 0
        _token_usage["completion_tokens"] = 0
        _token_usage["total_tokens"] = 0


def get_token_usage() -> Dict[str, int]:
    with _usage_lock:
        return dict(_token_usage)


def _normalize_usage(usage: Any) -> Optional[Dict[str, int]]:
    if usage is None:
        return None
    if hasattr(usage, "model_dump"):
        usage = usage.model_dump()
    elif hasattr(usage, "dict"):
        usage = usage.dict()
    if isinstance(usage, dict):
        # Support both OpenAI style (prompt_tokens) and pydantic_ai style (request_tokens)
        prompt_tokens = int(usage.get("prompt_tokens") or usage.get("request_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or usage.get("response_tokens") or 0)
        total_tokens = usage.get("total_tokens")
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens
        return {
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(total_tokens),
        }
    # Support both OpenAI style and pydantic_ai style attribute names
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or getattr(usage, "request_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or getattr(usage, "response_tokens", 0) or 0)
    total_tokens = getattr(usage, "total_tokens", None)
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(total_tokens),
    }


def record_token_usage(usage: Any) -> None:
    normalized = _normalize_usage(usage)
    if not normalized:
        logger.debug(f"[token_usage] no usage to record, raw={usage}")
        return
    with _usage_lock:
        _token_usage["prompt_tokens"] += normalized["prompt_tokens"]
        _token_usage["completion_tokens"] += normalized["completion_tokens"]
        _token_usage["total_tokens"] += normalized["total_tokens"]
        logger.debug(f"[token_usage] recorded: {normalized}, total now: {dict(_token_usage)}")


def _extract_usage_from_result(result: Any) -> Optional[Any]:
    if result is None:
        return None
    if isinstance(result, dict):
        return result.get("usage") or result.get("token_usage") or result.get("llm_usage")
    # pydantic_ai RunResult has usage() method
    if hasattr(result, "usage") and callable(result.usage):
        try:
            return result.usage()
        except Exception:
            pass
    for attr in ("usage", "token_usage", "llm_usage", "_usage"):
        usage = getattr(result, attr, None)
        if usage:
            return usage
    for attr in ("model_response", "response", "raw_response", "raw", "all_messages_json"):
        sub = getattr(result, attr, None)
        if sub is None:
            continue
        if isinstance(sub, dict):
            usage = sub.get("usage")
            if usage:
                return usage
        usage = getattr(sub, "usage", None)
        if usage:
            return usage
    return None


def record_usage_from_result(result: Any) -> None:
    usage = _extract_usage_from_result(result)
    logger.debug(f"[token_usage] from_result: extracted={usage}, result_type={type(result).__name__}")
    if usage:
        record_token_usage(usage)
    else:
        # Debug: show what attributes are available on result
        attrs = [a for a in dir(result) if not a.startswith("_")]
        logger.debug(f"[token_usage] result has attrs: {attrs[:20]}")


def create_main_model(config: Config) -> OpenAIModel:
    """Create the main LLM model from configuration."""
    return OpenAIModel(
        model_name=config.main_model,
        provider=OpenAIProvider(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key
        ),
        settings=OpenAIModelSettings(
            temperature=0.0,
            max_tokens=config.max_tokens
        )
    )


def create_fallback_model(config: Config) -> OpenAIModel:
    """Create the fallback LLM model from configuration."""
    return OpenAIModel(
        model_name=config.fallback_model,
        provider=OpenAIProvider(
            base_url=config.llm_base_url,
            api_key=config.llm_api_key
        ),
        settings=OpenAIModelSettings(
            temperature=0.0,
            max_tokens=config.max_tokens
        )
    )


def create_fallback_models(config: Config) -> FallbackModel:
    """Create fallback models chain from configuration."""
    main = create_main_model(config)
    fallback = create_fallback_model(config)
    return FallbackModel(main, fallback)


def create_openai_client(config: Config) -> OpenAI:
    """Create OpenAI client from configuration."""
    return OpenAI(
        base_url=config.llm_base_url,
        api_key=config.llm_api_key
    )


def call_llm(
    prompt: str,
    config: Config,
    model: str = None,
    temperature: float = 0.0
) -> str:
    """
    Call LLM with the given prompt.
    
    Args:
        prompt: The prompt to send
        config: Configuration containing LLM settings
        model: Model name (defaults to config.main_model)
        temperature: Temperature setting
        
    Returns:
        LLM response text
    """
    if model is None:
        model = config.main_model
    
    client = create_openai_client(config)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=config.max_tokens
    )
    usage = getattr(response, "usage", None)
    logger.debug(f"[token_usage] call_llm response.usage={usage}")
    record_token_usage(usage)
    return response.choices[0].message.content