from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.services.dependency_graph import FileDependency
from app.services.module_assign import ModuleAssignment
from app.services.module_tree import ModuleTree, ModuleNode


@dataclass(frozen=True)
class RefineResult:
    tree: ModuleTree
    assignments: List[ModuleAssignment]
    merge_map: Dict[str, str]


def refine_module_tree(
    tree: ModuleTree,
    assignments: List[ModuleAssignment],
    file_deps: List[FileDependency],
    min_files: int = 2,
    parent_edge_ratio: float = 0.6,
) -> RefineResult:
    parent_map: Dict[str, str] = {}

    def walk(node: ModuleNode, parent: ModuleNode | None):
        if parent is not None:
            parent_map[node.path_prefix] = parent.path_prefix
        for child in node.children:
            walk(child, node)

    walk(tree.root, None)

    file_to_module: Dict[str, str] = {}
    module_files: Dict[str, List[str]] = {}
    for item in assignments:
        file_to_module[item.file_path] = item.module_id
        module_files.setdefault(item.module_id, []).append(item.file_path)

    module_edge_counts: Dict[Tuple[str, str], int] = {}
    for edge in file_deps:
        src_mod = file_to_module.get(edge.src)
        dst_mod = file_to_module.get(edge.dst)
        if not src_mod or not dst_mod or src_mod == dst_mod:
            continue
        module_edge_counts[(src_mod, dst_mod)] = module_edge_counts.get((src_mod, dst_mod), 0) + 1

    merge_map: Dict[str, str] = {}
    for module_id, files in module_files.items():
        if module_id == "root":
            continue
        parent_id = parent_map.get(module_id)
        if not parent_id:
            continue

        total_edges = sum(count for (src, _), count in module_edge_counts.items() if src == module_id)
        parent_edges = module_edge_counts.get((module_id, parent_id), 0)
        file_count = len(files)

        if file_count <= min_files:
            merge_map[module_id] = parent_id
            continue
        if total_edges > 0 and (parent_edges / total_edges) >= parent_edge_ratio:
            merge_map[module_id] = parent_id

    def resolve(module_id: str) -> str:
        while module_id in merge_map:
            module_id = merge_map[module_id]
        return module_id

    new_assignments: List[ModuleAssignment] = []
    for item in assignments:
        new_assignments.append(
            ModuleAssignment(
                module_id=resolve(item.module_id),
                file_path=item.file_path,
                symbol_ids=item.symbol_ids,
            )
        )

    def prune(node: ModuleNode) -> ModuleNode:
        children = [prune(child) for child in node.children if child.path_prefix not in merge_map]
        return ModuleNode(
            id=node.id,
            name=node.name,
            path_prefix=node.path_prefix,
            files=node.files,
            children=children,
        )

    pruned_root = prune(tree.root)

    for item in new_assignments:
        if item.module_id == pruned_root.path_prefix:
            pruned_root.files.append(item.file_path)

    return RefineResult(tree=ModuleTree(root=pruned_root), assignments=new_assignments, merge_map=merge_map)
