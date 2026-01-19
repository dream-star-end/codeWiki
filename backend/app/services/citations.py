from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.services.parsers import Symbol
from app.services.doc_builder import ModuleDoc


@dataclass(frozen=True)
class Citation:
    file_path: str
    symbol: str | None
    line_start: int | None
    line_end: int | None


def build_citation_map(module_docs: List[ModuleDoc], symbols: List[Tuple[str, Symbol]]) -> Dict[str, List[Citation]]:
    symbol_map = {sym_id: sym for sym_id, sym in symbols}
    citations: Dict[str, List[Citation]] = {}

    for doc in module_docs:
        module_id = doc.module_id
        entries: List[Citation] = []
        for item in doc.overview.get("key_symbols", []):
            sym = symbol_map.get(item["id"])
            if not sym:
                continue
            entries.append(
                Citation(
                    file_path=sym.file_path,
                    symbol=sym.name,
                    line_start=sym.line_start,
                    line_end=sym.line_end,
                )
            )
        citations[module_id] = entries

    return citations
