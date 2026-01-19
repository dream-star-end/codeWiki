from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from tree_sitter_language_pack import get_parser

from app.services.parsers.base import Symbol, ImportRef
from app.services.parsers.utils import node_name, node_location, node_text


def parse_python_file(file_path: str) -> Tuple[List[Symbol], List[ImportRef]]:
    path = Path(file_path)
    source = path.read_bytes()
    parser = get_parser("python")
    tree = parser.parse(source)

    symbols: List[Symbol] = []
    imports: List[ImportRef] = []

    def walk(node, container: str | None = None):
        if node.type == "class_definition":
            name = node_name(source, node) or "<anonymous>"
            line_start, line_end = node_location(node)
            symbols.append(
                Symbol(
                    kind="class",
                    name=name,
                    file_path=str(path),
                    line_start=line_start,
                    line_end=line_end,
                    container=container,
                )
            )
            container = name

        if node.type == "function_definition":
            name = node_name(source, node) or "<anonymous>"
            line_start, line_end = node_location(node)
            symbols.append(
                Symbol(
                    kind="function",
                    name=name,
                    file_path=str(path),
                    line_start=line_start,
                    line_end=line_end,
                    container=container,
                )
            )

        if node.type == "import_statement":
            text = node_text(source, node)
            line_start, line_end = node_location(node)
            imports.append(
                ImportRef(
                    module=text.strip(),
                    name=None,
                    file_path=str(path),
                    line_start=line_start,
                    line_end=line_end,
                )
            )

        if node.type == "import_from_statement":
            module_node = node.child_by_field_name("module_name")
            module = node_text(source, module_node) if module_node is not None else ""
            line_start, line_end = node_location(node)
            imports.append(
                ImportRef(
                    module=module,
                    name=None,
                    file_path=str(path),
                    line_start=line_start,
                    line_end=line_end,
                )
            )

        for child in node.children:
            walk(child, container)

    walk(tree.root_node)
    return symbols, imports
