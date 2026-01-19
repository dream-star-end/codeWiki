from __future__ import annotations

import hashlib
import uuid
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

from app.services.module_tree import ModuleNode


def _db_path() -> Path:
    root = Path(__file__).resolve().parents[2] / "workspace"
    root.mkdir(parents=True, exist_ok=True)
    return root / "analysis.db"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    schema_path = Path(__file__).resolve().parents[2] / "db" / "schema_sqlite.sql"
    with get_conn() as conn:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        # Migration: add job_id column if not exists
        try:
            conn.execute("SELECT job_id FROM repos LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE repos ADD COLUMN job_id TEXT")
        # Migration: add commit_sha column if not exists
        try:
            conn.execute("SELECT commit_sha FROM repos LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE repos ADD COLUMN commit_sha TEXT")
        # Migration: add owner_id column if not exists
        try:
            conn.execute("SELECT owner_id FROM repos LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE repos ADD COLUMN owner_id TEXT")
        # Migration: create token_usage table if not exists
        try:
            conn.execute("SELECT id FROM token_usage LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS token_usage (
                    id TEXT PRIMARY KEY,
                    repo_id TEXT,
                    kind TEXT NOT NULL,
                    source TEXT,
                    prompt_tokens INTEGER NOT NULL,
                    completion_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    is_estimated INTEGER DEFAULT 1,
                    created_at TEXT
                )
                """
            )
        # Migration: add source column if not exists
        try:
            conn.execute("SELECT source FROM token_usage LIMIT 1")
        except sqlite3.OperationalError:
            conn.execute("ALTER TABLE token_usage ADD COLUMN source TEXT")


def create_repo(repo_id: str, url: Optional[str], job_id: str, owner_id: Optional[str] = None) -> None:
    """Create a repo entry early with job_id for tracking progress."""
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO repos (id, url, job_id, owner_id, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (repo_id, url, job_id, owner_id, _now()),
        )


def upsert_repo_ingest_config(
    repo_id: str,
    include: Optional[List[str]],
    exclude: Optional[List[str]],
    branch: Optional[str],
    commit: Optional[str],
    local_path: Optional[str],
) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO repo_ingest_config
            (repo_id, include_patterns, exclude_patterns, branch, commit_sha, local_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(repo_id) DO UPDATE SET
                include_patterns=excluded.include_patterns,
                exclude_patterns=excluded.exclude_patterns,
                branch=excluded.branch,
                commit_sha=excluded.commit_sha,
                local_path=excluded.local_path,
                updated_at=excluded.updated_at
            """,
            (
                repo_id,
                json.dumps(include or []),
                json.dumps(exclude or []),
                branch,
                commit,
                local_path,
                _now(),
                _now(),
            ),
        )


def get_repo_ingest_config(repo_id: str) -> Dict:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT include_patterns, exclude_patterns, branch, commit_sha, local_path FROM repo_ingest_config WHERE repo_id=?",
            (repo_id,),
        ).fetchone()
    if not row:
        return {}
    return {
        "include": json.loads(row["include_patterns"] or "[]"),
        "exclude": json.loads(row["exclude_patterns"] or "[]"),
        "branch": row["branch"],
        "commit": row["commit_sha"],
        "local_path": row["local_path"],
    }


def upsert_repo(repo_id: str, url: Optional[str], root_path: str, language_set: List[str]) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO repos (id, url, root_path, language_set, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                url=COALESCE(excluded.url, repos.url),
                root_path=excluded.root_path,
                language_set=excluded.language_set
            """,
            (repo_id, url, root_path, json.dumps(language_set), _now()),
        )


def insert_files(repo_id: str, files: Iterable[Dict]) -> Dict[str, str]:
    init_db()
    file_map: Dict[str, str] = {}
    with get_conn() as conn:
        for item in files:
            file_id = _hash(item["path"])
            file_map[item["path"]] = file_id
            conn.execute(
                """
                INSERT OR REPLACE INTO files (id, repo_id, path, language, hash, size, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id,
                    repo_id,
                    item["path"],
                    item["language"],
                    item.get("hash"),
                    item.get("size"),
                    _now(),
                ),
            )
    return file_map


def insert_symbols(repo_id: str, symbols: Iterable[Dict], file_map: Dict[str, str]) -> None:
    init_db()
    with get_conn() as conn:
        for item in symbols:
            conn.execute(
                """
                INSERT OR REPLACE INTO symbols
                (id, repo_id, file_id, kind, name, signature, container, line_start, line_end, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    repo_id,
                    file_map[item["file_path"]],
                    item["kind"],
                    item["name"],
                    item.get("signature"),
                    item.get("container"),
                    item.get("line_start"),
                    item.get("line_end"),
                    _now(),
                ),
            )


def insert_edges(repo_id: str, edges: Iterable[Dict], kind: str) -> None:
    init_db()
    with get_conn() as conn:
        for item in edges:
            edge_id = _hash(
                "|".join(
                    [
                        str(repo_id),
                        str(item.get("src_symbol_id") or ""),
                        str(item.get("dst_symbol_id") or ""),
                        str(item.get("edge_type") or ""),
                        str(item.get("detail") or ""),
                        str(kind),
                    ]
                )
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO dependency_edges
                (id, repo_id, src_symbol_id, dst_symbol_id, edge_type, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge_id,
                    repo_id,
                    item.get("src_symbol_id"),
                    item.get("dst_symbol_id"),
                    item.get("edge_type"),
                    item.get("detail"),
                    _now(),
                ),
            )


def insert_file_edges(repo_id: str, edges: Iterable[Dict]) -> None:
    init_db()
    with get_conn() as conn:
        for item in edges:
            edge_id = _hash(
                "|".join(
                    [
                        str(repo_id),
                        str(item.get("src") or ""),
                        str(item.get("dst") or ""),
                        str(item.get("edge_type") or ""),
                        str(item.get("detail") or ""),
                    ]
                )
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO file_dependency_edges
                (id, repo_id, src_path, dst_path, edge_type, detail, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge_id,
                    repo_id,
                    item.get("src"),
                    item.get("dst"),
                    item.get("edge_type"),
                    item.get("detail"),
                    _now(),
                ),
            )


def _walk_modules(node: ModuleNode, repo_id: str, parent_id: Optional[str]) -> List[Dict]:
    items = [
        {
            "id": node.path_prefix or "root",
            "repo_id": repo_id,
            "name": node.name,
            "path_prefix": node.path_prefix,
            "parent_id": parent_id,
            "stats": json.dumps({"files": len(node.files)}),
        }
    ]
    for child in node.children:
        items.extend(_walk_modules(child, repo_id, node.path_prefix or "root"))
    return items


def insert_modules(repo_id: str, root: ModuleNode) -> None:
    init_db()
    items = _walk_modules(root, repo_id, None)
    with get_conn() as conn:
        for item in items:
            conn.execute(
                """
                INSERT OR REPLACE INTO modules
                (id, repo_id, name, path_prefix, parent_id, stats, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["id"],
                    repo_id,
                    item["name"],
                    item["path_prefix"],
                    item.get("parent_id"),
                    item.get("stats"),
                    _now(),
                ),
            )


def insert_module_nodes(repo_id: str, assignments: Iterable[Dict]) -> None:
    init_db()
    with get_conn() as conn:
        for item in assignments:
            node_id = _hash(repo_id + "|" + item["module_id"] + "|" + item["file_path"])
            conn.execute(
                """
                INSERT OR REPLACE INTO module_nodes
                (id, repo_id, module_id, file_ids, symbol_ids, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    repo_id,
                    item["module_id"],
                    json.dumps([item["file_path"]]),
                    json.dumps(item["symbol_ids"]),
                    _now(),
                ),
            )


def insert_docs(repo_id: str, docs: Iterable[Dict]) -> None:
    init_db()
    with get_conn() as conn:
        for doc in docs:
            module_id = doc.get("module_id") or "root"
            doc_type = doc.get("doc_type") or "overview"
            doc_id = _hash(repo_id + "|" + module_id + "|" + doc_type)
            conn.execute(
                """
                INSERT OR REPLACE INTO doc_artifacts
                (id, repo_id, module_id, doc_type, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, repo_id, module_id, doc_type, json.dumps(doc), _now()),
            )


def insert_ai_doc(repo_id: str, module_id: Optional[str], doc_type: str, content: str) -> None:
    init_db()
    safe_module_id = module_id or "__repo__"
    with get_conn() as conn:
        doc_id = _hash(repo_id + "|" + safe_module_id + "|" + doc_type)
        conn.execute(
            """
            INSERT OR REPLACE INTO doc_artifacts
            (id, repo_id, module_id, doc_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (doc_id, repo_id, safe_module_id, doc_type, json.dumps({"content": content}), _now()),
        )


def read_ai_doc(repo_id: str, doc_type: str, module_id: Optional[str]) -> Optional[str]:
    init_db()
    safe_module_id = module_id or "__repo__"
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT content FROM doc_artifacts
            WHERE repo_id=? AND doc_type=? AND module_id IS ?
            """,
            (repo_id, doc_type, safe_module_id),
        ).fetchone()
    if not row:
        return None
    payload = json.loads(row["content"])
    return payload.get("content")


def read_summary(repo_id: str) -> Optional[Dict]:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT language_set FROM repos WHERE id=?", (repo_id,)).fetchone()
    if not row:
        return None
    languages = json.loads(row["language_set"]) if row["language_set"] else []
    return {"repo_id": repo_id, "languages": languages}


def read_modules(repo_id: str) -> List[Dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM modules WHERE repo_id=?", (repo_id,)).fetchall()
    return [dict(r) for r in rows]


def read_docs(repo_id: str) -> List[Dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute("SELECT content FROM doc_artifacts WHERE repo_id=?", (repo_id,)).fetchall()
    return [json.loads(r["content"]) for r in rows]


def read_doc_by_module(repo_id: str, module_id: str) -> Optional[Dict]:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT content FROM doc_artifacts WHERE repo_id=? AND module_id=? LIMIT 1",
            (repo_id, module_id),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["content"])


def get_module_ids_by_files(repo_id: str, files: List[str]) -> List[str]:
    """Map changed files (relative paths) to module_ids via module_nodes."""
    if not files:
        return []
    init_db()
    normalized = [Path(p).as_posix().lower() for p in files]
    module_ids: set[str] = set()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT module_id, file_ids FROM module_nodes WHERE repo_id=?",
            (repo_id,),
        ).fetchall()
    for row in rows:
        module_id = row["module_id"]
        try:
            file_ids = json.loads(row["file_ids"] or "[]")
        except Exception:
            file_ids = []
        for file_path in file_ids:
            file_norm = Path(str(file_path)).as_posix().lower()
            if any(file_norm.endswith(rel) for rel in normalized):
                module_ids.add(module_id)
                break
    return sorted(module_ids)


def get_module_files(repo_id: str, module_id: str) -> List[str]:
    """Get file list for a module from module_nodes."""
    init_db()
    files: List[str] = []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT file_ids FROM module_nodes WHERE repo_id=? AND module_id=?",
            (repo_id, module_id),
        ).fetchall()
    for row in rows:
        try:
            file_ids = json.loads(row["file_ids"] or "[]")
        except Exception:
            file_ids = []
        for file_path in file_ids:
            if file_path:
                files.append(str(file_path))
    # Deduplicate while preserving order
    seen = set()
    result = []
    for item in files:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _parse_repo_source(url: Optional[str], root_path: Optional[str]) -> Dict[str, str]:
    if url:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path.strip("/").replace(".git", "")
        parts = [p for p in path.split("/") if p]
        owner = parts[-2] if len(parts) >= 2 else ""
        repo = parts[-1] if parts else ""
        if "github" in host:
            repo_type = "github"
        elif "gitlab" in host:
            repo_type = "gitlab"
        elif "bitbucket" in host:
            repo_type = "bitbucket"
        else:
            repo_type = "web"
        return {"owner": owner, "repo": repo, "repo_type": repo_type, "source": url}
    if root_path:
        repo = Path(root_path).name
        return {"owner": "local", "repo": repo, "repo_type": "local", "source": root_path}
    return {"owner": "", "repo": "", "repo_type": "unknown", "source": ""}


def read_repo_list(owner_id: Optional[str] = None) -> List[Dict]:
    from app.core.jobs import get_job
    
    init_db()
    with get_conn() as conn:
        token_rows = conn.execute(
            "SELECT repo_id, SUM(total_tokens) as total_tokens FROM token_usage WHERE repo_id IS NOT NULL GROUP BY repo_id"
        ).fetchall()
        token_map = {row["repo_id"]: row["total_tokens"] for row in token_rows}
        codewiki_rows = conn.execute(
            "SELECT repo_id, SUM(total_tokens) as total_tokens FROM token_usage WHERE repo_id IS NOT NULL AND source='codewiki' GROUP BY repo_id"
        ).fetchall()
        codewiki_map = {row["repo_id"]: row["total_tokens"] for row in codewiki_rows}
        use_codewiki_map = len(codewiki_map) > 0
        if owner_id:
            rows = conn.execute(
                """
                SELECT r.id, r.url, r.root_path, r.language_set, r.job_id, r.owner_id, r.created_at,
                       u.username as owner_name
                FROM repos r
                LEFT JOIN users u ON u.id = r.owner_id
                WHERE r.owner_id = ?
                ORDER BY r.created_at DESC
                """,
                (owner_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT r.id, r.url, r.root_path, r.language_set, r.job_id, r.owner_id, r.created_at,
                       u.username as owner_name
                FROM repos r
                LEFT JOIN users u ON u.id = r.owner_id
                ORDER BY r.created_at DESC
                """
            ).fetchall()
        repos: List[Dict] = []
        for row in rows:
            repo_id = row["id"]
            job_id = row["job_id"] if "job_id" in row.keys() else None
            source_info = _parse_repo_source(row["url"], row["root_path"])
            language_set = json.loads(row["language_set"]) if row["language_set"] else []
            modules_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM modules WHERE repo_id=?", (repo_id,)
            ).fetchone()["cnt"]
            symbols_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM symbols WHERE repo_id=?", (repo_id,)
            ).fetchone()["cnt"]
            files_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM files WHERE repo_id=?", (repo_id,)
            ).fetchone()["cnt"]
            module_paths = conn.execute(
                "SELECT path_prefix FROM modules WHERE repo_id=?", (repo_id,)
            ).fetchall()
            depth = 0
            for item in module_paths:
                prefix = item["path_prefix"] or ""
                if not prefix:
                    continue
                depth = max(depth, len([p for p in prefix.split("/") if p]))
            name = source_info["repo"]
            if source_info["owner"] and source_info["repo"]:
                name = f"{source_info['owner']}/{source_info['repo']}"
            
            # Get job status if job_id exists
            job_status = None
            job_progress = 0
            job_stage = ""
            job_detail = ""
            if job_id:
                job = get_job(job_id)
                job_status = job.status
                job_progress = job.progress
                job_stage = job.stage or ""
                job_detail = job.detail or ""
            
            repos.append(
                {
                    "id": repo_id,
                    "name": name or repo_id,
                    "owner": source_info["owner"],
                    "repo": source_info["repo"],
                    "repo_type": source_info["repo_type"],
                    "source": source_info["source"],
                    "languages": language_set,
                    "modules": modules_count,
                    "symbols": symbols_count,
                    "files": files_count,
                    "depth": depth,
                    "created_at": row["created_at"],
                    "job_id": job_id,
                    "job_status": job_status,
                    "job_progress": job_progress,
                    "job_stage": job_stage,
                    "job_detail": job_detail,
                    "owner_id": row["owner_id"] if "owner_id" in row.keys() else None,
                    "owner_name": row["owner_name"] if "owner_name" in row.keys() else None,
                    "token_usage": (codewiki_map.get(repo_id, 0) if use_codewiki_map else token_map.get(repo_id, 0)) or 0,
                }
            )
    return repos


def get_repo_owner(repo_id: str) -> Optional[str]:
    """Get repo owner id."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT owner_id FROM repos WHERE id=?", (repo_id,)).fetchone()
    return row["owner_id"] if row else None


def read_running_repos_progress() -> List[Dict]:
    """Get progress info for running/queued repos only (lightweight)."""
    from app.core.jobs import get_job
    
    init_db()
    result = []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, job_id FROM repos WHERE job_id IS NOT NULL"
        ).fetchall()
        
        for row in rows:
            repo_id = row["id"]
            job_id = row["job_id"]
            if job_id:
                job = get_job(job_id)
                # Only include running or queued jobs
                if job.status in ("running", "queued"):
                    result.append({
                        "id": repo_id,
                        "job_status": job.status,
                        "job_progress": job.progress,
                        "job_stage": job.stage or "",
                        "job_detail": job.detail or "",
                    })
    return result


def get_repo_job(repo_id: str) -> Optional[str]:
    """Get job id for a repo."""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT job_id FROM repos WHERE id=?", (repo_id,)).fetchone()
    return row["job_id"] if row else None


def get_repo_commit(repo_id: str) -> Optional[str]:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT commit_sha FROM repos WHERE id=?", (repo_id,)).fetchone()
    return row["commit_sha"] if row else None


def set_repo_commit(repo_id: str, commit_sha: str) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute("UPDATE repos SET commit_sha=? WHERE id=?", (commit_sha, repo_id))


def set_repo_job(repo_id: str, job_id: str) -> None:
    """Update job id for a repo."""
    init_db()
    with get_conn() as conn:
        conn.execute("UPDATE repos SET job_id=? WHERE id=?", (job_id, repo_id))


def get_repo_url(repo_id: str) -> Optional[str]:
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT url FROM repos WHERE id=?", (repo_id,)).fetchone()
    return row["url"] if row else None


def set_repo_checkpoint(repo_id: str, checkpoint_key: str, checkpoint_value: str) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO repo_checkpoints (repo_id, checkpoint_key, checkpoint_value, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(repo_id, checkpoint_key) DO UPDATE SET
                checkpoint_value=excluded.checkpoint_value,
                updated_at=excluded.updated_at
            """,
            (repo_id, checkpoint_key, checkpoint_value, _now()),
        )


def get_repo_checkpoint(repo_id: str, checkpoint_key: str) -> Optional[str]:
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT checkpoint_value FROM repo_checkpoints WHERE repo_id=? AND checkpoint_key=?",
            (repo_id, checkpoint_key),
        ).fetchone()
    return row["checkpoint_value"] if row else None


def delete_repo(repo_id: str) -> None:
    """Delete repo and all related records."""
    init_db()
    with get_conn() as conn:
        conn.execute("DELETE FROM doc_artifacts WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM module_nodes WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM modules WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM file_dependency_edges WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM dependency_edges WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM symbols WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM files WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM token_usage WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM repo_checkpoints WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM repo_ingest_config WHERE repo_id=?", (repo_id,))
        conn.execute("DELETE FROM repos WHERE id=?", (repo_id,))


def record_token_usage(
    repo_id: Optional[str],
    kind: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    is_estimated: bool = True,
    source: Optional[str] = None,
) -> None:
    init_db()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO token_usage
            (id, repo_id, kind, source, prompt_tokens, completion_tokens, total_tokens, is_estimated, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                repo_id,
                kind,
                source,
                int(prompt_tokens),
                int(completion_tokens),
                int(total_tokens),
                1 if is_estimated else 0,
                _now(),
            ),
        )


def get_token_usage_summary() -> Dict[str, Dict[str, int]]:
    init_db()
    with get_conn() as conn:
        overall = conn.execute(
            "SELECT COALESCE(SUM(total_tokens), 0) as total_tokens, COALESCE(SUM(CASE WHEN is_estimated=1 THEN total_tokens ELSE 0 END), 0) as estimated_tokens FROM token_usage"
        ).fetchone()
        llm = conn.execute(
            """
            SELECT
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(CASE WHEN is_estimated=1 THEN total_tokens ELSE 0 END), 0) as estimated_tokens
            FROM token_usage
            WHERE kind='llm'
            """
        ).fetchone()
        embedding = conn.execute(
            """
            SELECT
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(CASE WHEN is_estimated=1 THEN total_tokens ELSE 0 END), 0) as estimated_tokens
            FROM token_usage
            WHERE kind='embedding'
            """
        ).fetchone()
    return {
        "overall": {
            "total_tokens": overall["total_tokens"] if overall else 0,
            "estimated_tokens": overall["estimated_tokens"] if overall else 0,
        },
        "llm": {
            "prompt_tokens": llm["prompt_tokens"] if llm else 0,
            "completion_tokens": llm["completion_tokens"] if llm else 0,
            "total_tokens": llm["total_tokens"] if llm else 0,
            "estimated_tokens": llm["estimated_tokens"] if llm else 0,
        },
        "embedding": {
            "prompt_tokens": embedding["prompt_tokens"] if embedding else 0,
            "total_tokens": embedding["total_tokens"] if embedding else 0,
            "estimated_tokens": embedding["estimated_tokens"] if embedding else 0,
        },
    }


def read_file_edges(repo_id: str) -> List[Dict]:
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT src_path, dst_path, edge_type, detail
            FROM file_dependency_edges
            WHERE repo_id=?
            """,
            (repo_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_repo_root(repo_id: str) -> Optional[str]:
    """获取仓库根目录路径"""
    init_db()
    with get_conn() as conn:
        row = conn.execute("SELECT root_path FROM repos WHERE id=?", (repo_id,)).fetchone()
    if not row:
        return None
    return row["root_path"]


def read_symbols_by_file(repo_id: str, file_path: str) -> List[Dict]:
    """获取指定文件中的所有符号"""
    init_db()
    file_id = _hash(file_path)
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.kind, s.name, s.signature, s.container, s.line_start, s.line_end, f.path as file_path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.repo_id=? AND s.file_id=?
            ORDER BY s.line_start
            """,
            (repo_id, file_id),
        ).fetchall()
    return [dict(r) for r in rows]


def read_symbol_by_id(repo_id: str, symbol_id: str) -> Optional[Dict]:
    """根据ID获取符号"""
    init_db()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT s.id, s.kind, s.name, s.signature, s.container, s.line_start, s.line_end, f.path as file_path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.repo_id=? AND s.id=?
            """,
            (repo_id, symbol_id),
        ).fetchone()
    if not row:
        return None
    return dict(row)


def read_symbols_by_repo(repo_id: str) -> List[Dict]:
    """获取仓库中的所有符号"""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT s.id, s.kind, s.name, s.signature, s.container, s.line_start, s.line_end, f.path as file_path
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.repo_id=?
            ORDER BY f.path, s.line_start
            """,
            (repo_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def read_symbol_edges(repo_id: str) -> List[Dict]:
    """获取符号依赖边"""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT src_symbol_id, dst_symbol_id, edge_type, detail
            FROM dependency_edges
            WHERE repo_id=?
            """,
            (repo_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def read_files_by_repo(repo_id: str) -> List[Dict]:
    """获取仓库中的所有文件"""
    init_db()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, path, language, hash, size
            FROM files
            WHERE repo_id=?
            ORDER BY path
            """,
            (repo_id,),
        ).fetchall()
    return [dict(r) for r in rows]
