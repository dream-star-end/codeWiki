from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
import re

from tree_sitter_language_pack import get_parser

from app.services.parsers import Symbol, symbol_id
from app.services.parsers.utils import node_location, node_name, node_text


@dataclass(frozen=True)
class SymbolDependency:
    src_symbol_id: str
    dst_symbol_id: str
    edge_type: str
    detail: str


def _symbol_map(symbols: Iterable[Symbol]) -> Dict[str, str]:
    return {sym.name: symbol_id(sym) for sym in symbols}


def _extract_names(raw: str) -> List[str]:
    if not raw:
        return []
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_\.]*", raw)
    return [t.split(".")[-1] for t in tokens]


def _python_symbol_edges(file_path: str, symbols: List[Symbol]) -> List[SymbolDependency]:
    source = Path(file_path).read_bytes()
    parser = get_parser("python")
    tree = parser.parse(source)

    name_to_id = _symbol_map(symbols)
    edges: List[SymbolDependency] = []
    container_stack: List[str] = []

    def current_container() -> str | None:
        if not container_stack:
            return None
        return container_stack[-1]

    def add_edge(target_name: str, edge_type: str, detail: str) -> None:
        src_name = current_container()
        if not src_name or target_name not in name_to_id:
            return
        edges.append(
            SymbolDependency(
                src_symbol_id=name_to_id[src_name],
                dst_symbol_id=name_to_id[target_name],
                edge_type=edge_type,
                detail=detail,
            )
        )

    def walk(node):
        if node.type == "class_definition":
            name = node_name(source, node)
            if name:
                container_stack.append(name)
            super_node = node.child_by_field_name("superclasses")
            if super_node is not None:
                for base_name in _extract_names(node_text(source, super_node)):
                    add_edge(base_name, "inherit", base_name)

        if node.type == "function_definition":
            name = node_name(source, node)
            if name:
                container_stack.append(name)

        if node.type == "call":
            func_node = node.child_by_field_name("function")
            if func_node is not None:
                func_name = node_text(source, func_node)
                target = func_name.split(".")[-1]
                add_edge(target, "call", func_name)

        if node.type == "attribute":
            attr_node = node.child_by_field_name("attribute")
            if attr_node is not None:
                attr_name = node_text(source, attr_node)
                add_edge(attr_name, "use", attr_name)

        for child in node.children:
            walk(child)

        if node.type in {"class_definition", "function_definition"}:
            name = node_name(source, node)
            if name and container_stack and container_stack[-1] == name:
                container_stack.pop()

    walk(tree.root_node)
    return edges


def _java_symbol_edges(file_path: str, symbols: List[Symbol]) -> List[SymbolDependency]:
    source = Path(file_path).read_bytes()
    parser = get_parser("java")
    tree = parser.parse(source)

    name_to_id = _symbol_map(symbols)
    edges: List[SymbolDependency] = []
    container_stack: List[str] = []

    def current_container() -> str | None:
        if not container_stack:
            return None
        return container_stack[-1]

    def add_edge(target_name: str, edge_type: str, detail: str) -> None:
        src_name = current_container()
        if not src_name or target_name not in name_to_id:
            return
        edges.append(
            SymbolDependency(
                src_symbol_id=name_to_id[src_name],
                dst_symbol_id=name_to_id[target_name],
                edge_type=edge_type,
                detail=detail,
            )
        )

    def walk(node):
        if node.type in {"class_declaration", "interface_declaration", "enum_declaration"}:
            name = node_name(source, node)
            if name:
                container_stack.append(name)
            superclass = node.child_by_field_name("superclass")
            if superclass is not None:
                for base_name in _extract_names(node_text(source, superclass)):
                    add_edge(base_name, "inherit", base_name)
            interfaces = node.child_by_field_name("interfaces")
            if interfaces is not None:
                for base_name in _extract_names(node_text(source, interfaces)):
                    add_edge(base_name, "inherit", base_name)

        if node.type == "method_declaration":
            name = node_name(source, node)
            if name:
                container_stack.append(name)

        if node.type == "method_invocation":
            name_node = node.child_by_field_name("name")
            method_name = node_text(source, name_node) if name_node is not None else node_text(source, node)
            target = method_name.split(".")[-1]
            add_edge(target, "call", method_name)

        if node.type == "object_creation_expression":
            type_node = node.child_by_field_name("type")
            type_name = node_text(source, type_node) if type_node is not None else ""
            target = type_name.split(".")[-1]
            add_edge(target, "call", type_name)

        if node.type == "field_access":
            name_node = node.child_by_field_name("field")
            field_name = node_text(source, name_node) if name_node is not None else ""
            target = field_name.split(".")[-1]
            add_edge(target, "use", field_name)

        for child in node.children:
            walk(child)

        if node.type in {"class_declaration", "interface_declaration", "enum_declaration", "method_declaration"}:
            name = node_name(source, node)
            if name and container_stack and container_stack[-1] == name:
                container_stack.pop()

    walk(tree.root_node)
    return edges


def build_symbol_dependencies(file_path: str, language: str, symbols: List[Symbol]) -> List[SymbolDependency]:
    if language == "python":
        return _python_symbol_edges(file_path, symbols)
    if language == "java":
        return _java_symbol_edges(file_path, symbols)
    return []
