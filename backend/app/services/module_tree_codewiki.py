from __future__ import annotations

import json
from typing import Dict, Optional

from app.services.module_tree import ModuleNode, ModuleTree


def module_tree_from_codewiki(tree: Dict, symbol_map: Optional[Dict[str, Dict]] = None) -> ModuleTree:
    def build_node(name: str, info: Dict) -> ModuleNode:
        path_prefix = info.get("path") or name
        node = ModuleNode(id=path_prefix, name=name, path_prefix=path_prefix)
        components = info.get("components", [])
        if symbol_map and components:
            files = set()
            for sid in components:
                if sid not in symbol_map:
                    continue
                sym = symbol_map[sid]
                file_path = sym.file_path if hasattr(sym, "file_path") else sym.get("file_path")
                if file_path:
                    files.add(file_path)
            node.files.extend(sorted(files))
        for child_name, child_info in info.get("children", {}).items():
            child_node = build_node(child_name, child_info)
            node.children.append(child_node)
            node.files.extend(child_node.files)
        return node

    root = ModuleNode(id="root", name="root", path_prefix="")
    for name, info in tree.items():
        root.children.append(build_node(name, info))
    return ModuleTree(root=root)


def serialize_codewiki_tree(tree: Dict) -> str:
    return json.dumps(tree, ensure_ascii=True)
