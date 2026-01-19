from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.services.module_tree import ModuleNode, ModuleTree
from app.services.module_assign import ModuleAssignment
from app.services.parsers import Symbol


@dataclass(frozen=True)
class ModuleDoc:
    module_id: str
    overview: Dict


def _module_stats(assignments: List[ModuleAssignment]) -> Dict[str, Dict]:
    stats: Dict[str, Dict] = {}
    for item in assignments:
        info = stats.setdefault(item.module_id, {"files": 0, "symbols": 0})
        info["files"] += 1
        info["symbols"] += len(item.symbol_ids)
    return stats


def build_module_docs(
    tree: ModuleTree,
    assignments: List[ModuleAssignment],
    symbols: List[Tuple[str, Symbol]],
) -> List[ModuleDoc]:
    symbol_map = {sym_id: sym for sym_id, sym in symbols}
    stats = _module_stats(assignments)

    module_docs: List[ModuleDoc] = []

    def walk(node: ModuleNode):
        node_assignments = [a for a in assignments if a.module_id == node.path_prefix]
        files = [a.file_path for a in node_assignments]
        sym_ids = [sid for a in node_assignments for sid in a.symbol_ids]
        key_symbols = []
        for sid in sym_ids:
            sym = symbol_map.get(sid)
            if not sym:
                continue
            key_symbols.append(
                {
                    "id": sid,
                    "kind": sym.kind,
                    "name": sym.name,
                    "file_path": sym.file_path,
                    "line_start": sym.line_start,
                    "line_end": sym.line_end,
                }
            )

        overview = {
            "module_id": node.path_prefix,
            "name": node.name,
            "path_prefix": node.path_prefix,
            "stats": stats.get(node.path_prefix, {"files": 0, "symbols": 0}),
            "files": files,
            "key_symbols": key_symbols,
            "entry_points": [s["name"] for s in key_symbols if s["kind"] in {"class", "function", "method"}][:10],
        }
        module_docs.append(ModuleDoc(module_id=node.path_prefix, overview=overview))

        for child in node.children:
            walk(child)

    walk(tree.root)
    return module_docs
