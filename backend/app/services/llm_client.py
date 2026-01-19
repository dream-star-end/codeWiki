from __future__ import annotations

from dataclasses import dataclass
from typing import List, Generator, Tuple, Dict
import json
import requests

from app.models.schemas import ModelConfig


@dataclass(frozen=True)
class LLMMessage:
    role: str
    content: str


def _to_payload(messages: List[LLMMessage], model: ModelConfig, stream: bool = False, enable_thinking: bool = True) -> dict:
    payload = {
        "model": model.model_name,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "max_tokens": model.max_tokens,
        "stream": stream,
    }
    # Enable deep thinking for supported models (GLM-4.7, GLM-4.6, GLM-4.5, etc.)
    if enable_thinking:
        payload["thinking"] = {"type": "enabled"}
    if stream:
        payload["stream_options"] = {"include_usage": True}
    return payload


def _build_chat_url(base_url: str) -> str:
    """Build chat completions URL, avoiding duplicate version paths."""
    base = base_url.rstrip("/")
    # If base_url already ends with a version path (v1, v2, v3, v4, etc.), just append /chat/completions
    if base.split("/")[-1].startswith("v") and base.split("/")[-1][1:].isdigit():
        return base + "/chat/completions"
    # Otherwise, add /v1/chat/completions for OpenAI-compatible APIs
    return base + "/v1/chat/completions"


def _estimate_tokens(text: str) -> int:
    # Simple heuristic: ~4 chars per token
    if not text:
        return 0
    return max(1, len(text) // 4)


def chat_completion_with_usage(messages: List[LLMMessage], model: ModelConfig) -> Tuple[str, Dict]:
    url = _build_chat_url(model.base_url)
    headers = {
        "Authorization": f"Bearer {model.api_key}",
        "Content-Type": "application/json",
    }
    payload = _to_payload(messages, model)
    response = requests.post(url, headers=headers, json=payload, timeout=model.timeout_s)
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices", [])
    message = choices[0].get("message", {}) if choices else {}
    content = message.get("content", "")
    usage = data.get("usage") or {}
    if usage:
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(usage.get("completion_tokens") or 0)
        total_tokens = int(usage.get("total_tokens") or (prompt_tokens + completion_tokens))
        return content, {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "is_estimated": False,
        }
    return content, {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "is_estimated": False,
    }


def chat_completion(messages: List[LLMMessage], model: ModelConfig) -> str:
    content, _ = chat_completion_with_usage(messages, model)
    return content


def chat_completion_stream(messages: List[LLMMessage], model: ModelConfig, enable_thinking: bool = True) -> Generator[dict, None, None]:
    """Stream chat completion responses with thinking support.
    
    Yields dicts with 'type' ('thinking' or 'content') and 'text' fields.
    See: https://docs.bigmodel.cn/cn/guide/capabilities/thinking
    """
    url = _build_chat_url(model.base_url)
    headers = {
        "Authorization": f"Bearer {model.api_key}",
        "Content-Type": "application/json",
    }
    payload = _to_payload(messages, model, stream=True, enable_thinking=enable_thinking)
    
    with requests.post(url, headers=headers, json=payload, timeout=model.timeout_s, stream=True) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                data_str = line_str[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    usage = data.get("usage")
                    if usage:
                        yield {"type": "usage", "usage": usage}
                        continue
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        # Handle reasoning_content (thinking process) - GLM API format
                        reasoning = delta.get("reasoning_content", "")
                        if reasoning:
                            yield {"type": "thinking", "text": reasoning}
                        # Handle regular content
                        content = delta.get("content", "")
                        if content:
                            yield {"type": "content", "text": content}
                except json.JSONDecodeError:
                    continue
