from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.services.module_tree import ModuleNode, ModuleTree
from app.services.parsers import Symbol


@dataclass(frozen=True)
class ModuleAssignment:
    module_id: str
    file_path: str
    symbol_ids: List[str]


def index_nodes(root: ModuleNode) -> Dict[str, ModuleNode]:
    index: Dict[str, ModuleNode] = {}

    def walk(node: ModuleNode):
        index[node.path_prefix] = node
        for child in node.children:
            walk(child)

    walk(root)
    return index


def _best_prefix(path: str, prefixes: List[str]) -> str:
    best = ""
    for prefix in prefixes:
        if not prefix:
            continue
        if path.startswith(prefix) and len(prefix) > len(best):
            best = prefix
    return best


def assign_files_and_symbols(
    repo_root: str,
    tree: ModuleTree,
    symbols: List[Tuple[str, Symbol]],
) -> List[ModuleAssignment]:
    root_prefix = repo_root.replace("\\", "/").rstrip("/")
    index = index_nodes(tree.root)
    prefixes = sorted(index.keys(), key=len)

    file_to_symbols: Dict[str, List[str]] = {}
    for sym_id, sym in symbols:
        file_to_symbols.setdefault(sym.file_path, []).append(sym_id)

    assignments: List[ModuleAssignment] = []
    for file_path, sym_ids in file_to_symbols.items():
        rel = file_path.replace("\\", "/")
        if rel.startswith(root_prefix + "/"):
            rel = rel[len(root_prefix) + 1 :]
        module_prefix = _best_prefix(rel, prefixes)
        module_id = module_prefix if module_prefix in index else "root"
        assignments.append(ModuleAssignment(module_id=module_id, file_path=file_path, symbol_ids=sym_ids))

    return assignments
