"""
LLM service factory for creating configured LLM clients.
"""
from __future__ import annotations

import logging
import time
import random
from typing import Any, Dict, Optional, Callable, TypeVar
import threading
from functools import wraps

from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModelSettings
from pydantic_ai.models.fallback import FallbackModel
from openai import OpenAI

from codewiki.src.config import Config

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ------------------------------------------------------------
# ---------------------- Retry Utilities ---------------------
# ------------------------------------------------------------

class RetryConfig:
    """重试配置"""
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


# 可重试的异常类型
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    # OpenAI specific
)

# 可重试的错误消息关键词
RETRYABLE_ERROR_KEYWORDS = [
    'rate limit',
    'timeout',
    'connection',
    'server error',
    '503',
    '502',
    '500',
    '429',
    'overloaded',
    'capacity',
]


def is_retryable_error(exception: Exception) -> bool:
    """
    判断异常是否值得重试。
    
    Args:
        exception: 异常对象
        
    Returns:
        是否应该重试
    """
    # 检查异常类型
    if isinstance(exception, RETRYABLE_EXCEPTIONS):
        return True
    
    # 检查错误消息
    error_msg = str(exception).lower()
    for keyword in RETRYABLE_ERROR_KEYWORDS:
        if keyword in error_msg:
            return True
    
    return False


def calculate_retry_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    计算重试延迟时间（指数退避 + 抖动）。
    
    Args:
        attempt: 当前尝试次数（从0开始）
        config: 重试配置
        
    Returns:
        延迟秒数
    """
    delay = config.initial_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)
    
    if config.jitter:
        # 添加 ±25% 的抖动
        jitter_range = delay * 0.25
        delay = delay + random.uniform(-jitter_range, jitter_range)
    
    return max(0, delay)


def retry_with_backoff(
    func: Callable[..., T],
    config: RetryConfig = None,
    on_retry: Callable[[int, Exception], None] = None
) -> Callable[..., T]:
    """
    带指数退避的重试装饰器。
    
    Args:
        func: 要重试的函数
        config: 重试配置
        on_retry: 重试时的回调函数
        
    Returns:
        包装后的函数
    """
    if config is None:
        config = RetryConfig()
    
    @wraps(func)
    def wrapper(*args, **kwargs) -> T:
        last_exception = None
        
        for attempt in range(config.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                # 检查是否值得重试
                if not is_retryable_error(e):
                    logger.warning(f"Non-retryable error: {type(e).__name__}: {e}")
                    raise
                
                # 检查是否还有重试次数
                if attempt >= config.max_retries:
                    logger.error(f"All {config.max_retries + 1} attempts failed")
                    raise
                
                # 计算延迟
                delay = calculate_retry_delay(attempt, config)
                
                # 调用回调
                if on_retry:
                    on_retry(attempt + 1, e)
                
                logger.warning(
                    f"Attempt {attempt + 1}/{config.max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )
                
                time.sleep(delay)
        
        # 不应该到达这里
        raise last_exception
    
    return wrapper


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
    temperature: float = 0.0,
    max_retries: int = 3,
    retry_delay: float = 1.0
) -> str:
    """
    Call LLM with the given prompt (with automatic retry).
    
    Args:
        prompt: The prompt to send
        config: Configuration containing LLM settings
        model: Model name (defaults to config.main_model)
        temperature: Temperature setting
        max_retries: Maximum number of retries
        retry_delay: Initial delay between retries (exponential backoff)
        
    Returns:
        LLM response text
    """
    if model is None:
        model = config.main_model
    
    retry_config = RetryConfig(
        max_retries=max_retries,
        initial_delay=retry_delay,
        max_delay=60.0
    )
    
    def _make_request():
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
    
    def _on_retry(attempt: int, error: Exception):
        logger.warning(f"LLM call attempt {attempt} failed: {error}")
    
    wrapped_request = retry_with_backoff(
        _make_request,
        config=retry_config,
        on_retry=_on_retry
    )
    
    return wrapped_request()


def call_llm_with_fallback(
    prompt: str,
    config: Config,
    primary_model: str = None,
    fallback_model: str = None,
    temperature: float = 0.0,
    max_retries: int = 2
) -> str:
    """
    调用LLM，如果主模型失败则尝试备用模型。
    
    Args:
        prompt: 提示
        config: 配置
        primary_model: 主模型（默认使用config.main_model）
        fallback_model: 备用模型（默认使用config.fallback_model）
        temperature: 温度参数
        max_retries: 每个模型的最大重试次数
        
    Returns:
        LLM响应文本
    """
    primary = primary_model or config.main_model
    fallback = fallback_model or config.fallback_model
    
    # 尝试主模型
    try:
        return call_llm(
            prompt=prompt,
            config=config,
            model=primary,
            temperature=temperature,
            max_retries=max_retries
        )
    except Exception as e:
        logger.warning(f"Primary model '{primary}' failed: {e}. Trying fallback model '{fallback}'...")
    
    # 尝试备用模型
    try:
        return call_llm(
            prompt=prompt,
            config=config,
            model=fallback,
            temperature=temperature,
            max_retries=max_retries
        )
    except Exception as e:
        logger.error(f"Fallback model '{fallback}' also failed: {e}")
        raise


async def call_llm_async(
    prompt: str,
    config: Config,
    model: str = None,
    temperature: float = 0.0,
    max_retries: int = 3
) -> str:
    """
    异步版本的LLM调用（带重试）。
    
    Args:
        prompt: 提示
        config: 配置
        model: 模型名称
        temperature: 温度参数
        max_retries: 最大重试次数
        
    Returns:
        LLM响应文本
    """
    import asyncio
    
    if model is None:
        model = config.main_model
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            # 在线程池中运行同步调用
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: call_llm(
                    prompt=prompt,
                    config=config,
                    model=model,
                    temperature=temperature,
                    max_retries=0  # 禁用内部重试，由外层处理
                )
            )
            return result
        except Exception as e:
            last_exception = e
            
            if not is_retryable_error(e):
                raise
            
            if attempt >= max_retries:
                raise
            
            delay = calculate_retry_delay(attempt, RetryConfig())
            logger.warning(
                f"Async LLM call attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                f"Retrying in {delay:.2f}s..."
            )
            await asyncio.sleep(delay)
    
    raise last_exception