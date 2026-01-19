from __future__ import annotations

from typing import Optional


def node_text(source: bytes, node) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def node_name(source: bytes, node) -> Optional[str]:
    name_node = node.child_by_field_name("name")
    if name_node is None:
        return None
    return node_text(source, name_node)


def node_location(node) -> tuple[int, int]:
    line_start = int(node.start_point[0]) + 1
    line_end = int(node.end_point[0]) + 1
    return line_start, line_end
