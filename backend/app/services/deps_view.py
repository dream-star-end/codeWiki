from __future__ import annotations

import json
from typing import Dict, List

from app.services.db import get_conn, init_db, read_file_edges


def read_file_deps(repo_id: str) -> List[Dict]:
    return read_file_edges(repo_id)


def read_symbol_edges(repo_id: str) -> List[Dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT src_symbol_id, dst_symbol_id, edge_type, detail
            FROM dependency_edges
            WHERE repo_id=? AND edge_type IN ('call','inherit','use')
            """,
            (repo_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def read_module_edges(repo_id: str) -> List[Dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT module_id, file_ids
            FROM module_nodes
            WHERE repo_id=?
            """,
            (repo_id,),
        ).fetchall()

    file_to_module: Dict[str, str] = {}
    for row in rows:
        module_id = row["module_id"]
        file_ids = json.loads(row["file_ids"]) if row["file_ids"] else []
        for f in file_ids:
            file_to_module[f] = module_id

    file_deps = read_file_deps(repo_id)

    counts: Dict[str, int] = {}
    for dep in file_deps:
        src = dep.get("src")
        dst = dep.get("dst")
        if not src or not dst:
            continue
        src_module = file_to_module.get(src)
        dst_module = file_to_module.get(dst)
        if not src_module or not dst_module or src_module == dst_module:
            continue
        key = f"{src_module}->{dst_module}"
        counts[key] = counts.get(key, 0) + 1

    edges = []
    for key, count in counts.items():
        src, dst = key.split("->", 1)
        edges.append({"src": src, "dst": dst, "count": count})
    return edges
