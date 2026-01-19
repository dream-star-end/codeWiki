from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

import faiss
import numpy as np

from app.services.chunking import Chunk
from app.services.citations import Citation
from app.services.embeddings import embed_texts


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float


def _index_dir(repo_id: str) -> Path:
    root = Path(__file__).resolve().parents[2] / "workspace" / "indexes" / repo_id
    root.mkdir(parents=True, exist_ok=True)
    return root


def _load_metadata_vectors(repo_id: str) -> dict:
    index_dir = _index_dir(repo_id)
    meta_path = index_dir / "metadata.jsonl"
    if not meta_path.exists():
        return {}
    items: dict = {}
    with meta_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except Exception:
                continue
            chunk_id = record.get("id")
            text = record.get("text")
            vector = record.get("vector")
            if chunk_id and text and isinstance(vector, list):
                items[chunk_id] = {"text": text, "vector": vector}
    return items


def build_index(repo_id: str, chunks: List[Chunk]) -> None:
    if not chunks:
        return
    prev = _load_metadata_vectors(repo_id)
    vectors: List[List[float]] = []
    to_embed_texts: List[str] = []
    to_embed_indices: List[int] = []

    for idx, chunk in enumerate(chunks):
        cached = prev.get(chunk.id)
        if cached and cached.get("text") == chunk.text:
            vectors.append(cached["vector"])
        else:
            to_embed_indices.append(idx)
            to_embed_texts.append(chunk.text)
            vectors.append([])  # placeholder

    if to_embed_texts:
        new_vectors = embed_texts(to_embed_texts, repo_id=repo_id)
        for i, vec in enumerate(new_vectors):
            vectors[to_embed_indices[i]] = vec

    arr = np.array(vectors, dtype="float32")
    faiss.normalize_L2(arr)

    index = faiss.IndexFlatIP(arr.shape[1])
    index.add(arr)

    index_dir = _index_dir(repo_id)
    faiss.write_index(index, str(index_dir / "index.faiss"))

    meta_path = index_dir / "metadata.jsonl"
    with meta_path.open("w", encoding="utf-8") as handle:
        for chunk, vec in zip(chunks, vectors):
            record = {
                "id": chunk.id,
                "text": chunk.text,
                "citations": [asdict(c) for c in chunk.citations],
                "vector": vec,
            }
            handle.write(json.dumps(record) + "\n")


def search_index(repo_id: str, query: str, top_k: int = 8) -> List[SearchHit]:
    index_dir = _index_dir(repo_id)
    index_path = index_dir / "index.faiss"
    meta_path = index_dir / "metadata.jsonl"
    if not index_path.exists() or not meta_path.exists():
        return []

    index = faiss.read_index(str(index_path))
    query_vec = np.array(embed_texts([query], repo_id=repo_id), dtype="float32")
    faiss.normalize_L2(query_vec)

    scores, ids = index.search(query_vec, top_k)

    metadata: List[dict] = []
    with meta_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            metadata.append(json.loads(line))

    hits: List[SearchHit] = []
    for rank, idx in enumerate(ids[0].tolist()):
        if idx < 0 or idx >= len(metadata):
            continue
        record = metadata[idx]
        citations = record.get("citations", [])
        chunk = Chunk(
            id=record.get("id", ""),
            text=record.get("text", ""),
            citations=[Citation(**c) for c in citations],
        )
        hits.append(SearchHit(chunk=chunk, score=float(scores[0][rank])))

    return hits


def keyword_search(repo_id: str, query: str, top_k: int = 8) -> List[SearchHit]:
    """
    关键词搜索 - 基于简单的字符串匹配
    
    Args:
        repo_id: 仓库ID
        query: 查询字符串
        top_k: 返回结果数
        
    Returns:
        List[SearchHit]: 搜索结果
    """
    index_dir = _index_dir(repo_id)
    meta_path = index_dir / "metadata.jsonl"
    if not meta_path.exists():
        return []
    
    query_lower = query.lower()
    query_terms = query_lower.split()
    
    metadata: List[dict] = []
    with meta_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                metadata.append(json.loads(line))
            except Exception:
                continue
    
    # 计算每个文档的关键词匹配分数
    scored_items = []
    for record in metadata:
        text = record.get("text", "").lower()
        
        # 计算匹配分数
        score = 0.0
        for term in query_terms:
            if term in text:
                # 精确匹配加分
                count = text.count(term)
                score += count * 1.0
                
                # 标题/开头匹配额外加分
                if text.startswith(term) or f"\n{term}" in text:
                    score += 0.5
        
        if score > 0:
            citations = record.get("citations", [])
            chunk = Chunk(
                id=record.get("id", ""),
                text=record.get("text", ""),
                citations=[Citation(**c) for c in citations],
            )
            scored_items.append((chunk, score))
    
    # 按分数排序
    scored_items.sort(key=lambda x: x[1], reverse=True)
    
    hits = [SearchHit(chunk=item[0], score=item[1]) for item in scored_items[:top_k]]
    return hits


def hybrid_search(
    repo_id: str, 
    query: str, 
    top_k: int = 8,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> List[SearchHit]:
    """
    混合搜索 - 结合语义搜索和关键词搜索
    
    Args:
        repo_id: 仓库ID
        query: 查询字符串
        top_k: 返回结果数
        semantic_weight: 语义搜索权重
        keyword_weight: 关键词搜索权重
        
    Returns:
        List[SearchHit]: 搜索结果
    """
    # 执行两种搜索
    semantic_hits = search_index(repo_id, query, top_k * 2)
    keyword_hits = keyword_search(repo_id, query, top_k * 2)
    
    # 构建分数字典（按 chunk id）
    scores: dict = {}
    chunks: dict = {}
    
    # 语义搜索结果
    for i, hit in enumerate(semantic_hits):
        chunk_id = hit.chunk.id
        # 归一化分数（rank-based）
        normalized_score = 1.0 / (i + 1)
        scores[chunk_id] = scores.get(chunk_id, 0) + normalized_score * semantic_weight
        chunks[chunk_id] = hit.chunk
    
    # 关键词搜索结果
    for i, hit in enumerate(keyword_hits):
        chunk_id = hit.chunk.id
        normalized_score = 1.0 / (i + 1)
        scores[chunk_id] = scores.get(chunk_id, 0) + normalized_score * keyword_weight
        chunks[chunk_id] = hit.chunk
    
    # 按综合分数排序
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    
    hits = [
        SearchHit(chunk=chunks[chunk_id], score=scores[chunk_id])
        for chunk_id in sorted_ids[:top_k]
    ]
    
    return hits
