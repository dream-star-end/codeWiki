from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict

from app.services.citations import Citation


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    citations: List[Citation]


def chunk_text(text: str, max_chars: int = 1200) -> List[str]:
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        start = end
    return chunks


def chunk_file(path: str, max_chars: int = 1200) -> List[str]:
    content = Path(path).read_text(encoding="utf-8", errors="replace")
    return chunk_text(content, max_chars=max_chars)


def build_chunks(paths: Iterable[str], max_chars: int = 1200) -> List[Chunk]:
    chunks: List[Chunk] = []
    for path in paths:
        parts = chunk_file(path, max_chars=max_chars)
        for idx, part in enumerate(parts):
            chunk_id = f"{path}::chunk:{idx}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=part,
                    citations=[Citation(file_path=path, symbol=None, line_start=None, line_end=None)],
                )
            )
    return chunks


def build_chunks_from_docs(docs: Iterable[Dict], max_chars: int = 1200) -> List[Chunk]:
    chunks: List[Chunk] = []
    for doc in docs:
        text = doc.get("markdown") or doc.get("content") or ""
        if not text:
            continue
        module_id = doc.get("module_id") or "overview"
        for idx, part in enumerate(chunk_text(text, max_chars=max_chars)):
            chunk_id = f"{module_id}::doc_chunk:{idx}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=part,
                    citations=[
                        Citation(
                            file_path=doc.get("doc_path") or f"docs/{module_id}.md",
                            symbol=None,
                            line_start=None,
                            line_end=None,
                        )
                    ],
                )
            )
    return chunks
