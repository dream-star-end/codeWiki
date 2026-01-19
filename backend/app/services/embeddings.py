from __future__ import annotations

import hashlib
import json
import os
from typing import List, Optional
import requests
import numpy as np


def _hash_embedding(text: str, dim: int = 384) -> List[float]:
    """Fallback: generate pseudo-random vector from text hash.
    
    Warning: This does NOT provide semantic similarity!
    Same text -> same vector, but similar text -> NOT similar vector.
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:8], "big")
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim)
    vec = vec / np.linalg.norm(vec)
    return vec.astype("float32").tolist()


def _get_embedding_config() -> Optional[dict]:
    """Get embedding config from database, fallback to env vars."""
    # Try database config first
    try:
        from app.services.auth import get_embedding_config
        config = get_embedding_config()
        if config:
            return config
    except Exception:
        pass
    
    # Fallback to environment variables
    base_url = os.getenv("EMBEDDING_BASE_URL")
    api_key = os.getenv("EMBEDDING_API_KEY")
    model = os.getenv("EMBEDDING_MODEL")
    
    if base_url and api_key and model:
        return {
            "base_url": base_url,
            "api_key": api_key,
            "model_name": model,
        }
    
    return None


def _build_embeddings_url(base_url: str) -> str:
    """Build embeddings URL, avoiding duplicate version paths."""
    base = base_url.rstrip("/")
    last = base.split("/")[-1]
    if last.startswith("v") and last[1:].isdigit():
        return base + "/embeddings"
    # BigModel default (api/paas) uses v4 for embeddings
    if "open.bigmodel.cn/api/paas" in base:
        return base + "/v4/embeddings"
    return base + "/v1/embeddings"


def embed_texts(texts: List[str], repo_id: Optional[str] = None) -> List[List[float]]:
    """Generate embeddings for texts.
    
    Uses configured embedding model if available, otherwise falls back to hash-based pseudo-vectors.
    """
    config = _get_embedding_config()
    
    if not config:
        # No embedding model configured, use fallback
        return [_hash_embedding(text) for text in texts]

    base_url = config.get("base_url", "")
    api_key = config.get("api_key", "")
    model = config.get("model_name", "")

    if not base_url or not api_key or not model:
        return [_hash_embedding(text) for text in texts]

    url = _build_embeddings_url(base_url)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "input": texts}
    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # Token usage tracking
    try:
        from app.services.db import record_token_usage
        usage = data.get("usage") or {}
        if usage:
            prompt_tokens = int(usage.get("prompt_tokens") or 0)
            total_tokens = int(usage.get("total_tokens") or prompt_tokens)
            record_token_usage(
                repo_id,
                kind="embedding",
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                total_tokens=total_tokens,
                is_estimated=False,
                source="embedding",
            )
    except Exception:
        pass
    return [item["embedding"] for item in data.get("data", [])]
