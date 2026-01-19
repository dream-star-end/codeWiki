from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from tree_sitter_language_pack import get_parser

from app.services.parsers.base import Symbol, ImportRef
from app.services.parsers.utils import node_name, node_location, node_text


def parse_java_file(file_path: str) -> Tuple[List[Symbol], List[ImportRef]]:
    path = Path(file_path)
    source = path.read_bytes()
    parser = get_parser("java")
    tree = parser.parse(source)

    symbols: List[Symbol] = []
    imports: List[ImportRef] = []

    def walk(node, container: str | None = None):
        if node.type in {"class_declaration", "interface_declaration", "enum_declaration"}:
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

        if node.type == "method_declaration":
            name = node_name(source, node) or "<anonymous>"
            line_start, line_end = node_location(node)
            symbols.append(
                Symbol(
                    kind="method",
                    name=name,
                    file_path=str(path),
                    line_start=line_start,
                    line_end=line_end,
                    container=container,
                )
            )

        if node.type == "import_declaration":
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

        for child in node.children:
            walk(child, container)

    walk(tree.root_node)
    return symbols, imports
