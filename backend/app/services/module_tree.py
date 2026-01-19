from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from app.services.file_discovery import DiscoveredFile


@dataclass
class ModuleNode:
    id: str
    name: str
    path_prefix: str
    files: List[str] = field(default_factory=list)
    children: List["ModuleNode"] = field(default_factory=list)


@dataclass
class ModuleTree:
    root: ModuleNode


def build_module_tree(repo_root: str, files: List[DiscoveredFile]) -> ModuleTree:
    root_path = Path(repo_root).resolve()
    root = ModuleNode(id="root", name="root", path_prefix="")
    nodes: Dict[str, ModuleNode] = {"": root}

    for item in files:
        rel_path = Path(item.path).resolve().relative_to(root_path).as_posix()
        parts = rel_path.split("/")[:-1]
        prefix = ""
        for part in parts:
            prefix = f"{prefix}/{part}".strip("/")
            if prefix not in nodes:
                nodes[prefix] = ModuleNode(id=prefix, name=part, path_prefix=prefix)
                parent_prefix = "/".join(prefix.split("/")[:-1])
                parent = nodes.get(parent_prefix, root)
                parent.children.append(nodes[prefix])

        nodes[""].files.append(item.path)
        if parts:
            leaf_prefix = "/".join(parts)
            nodes[leaf_prefix].files.append(item.path)

    return ModuleTree(root=root)
