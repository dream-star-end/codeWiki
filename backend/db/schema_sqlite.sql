-- User management
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',  -- 'admin' or 'user'
    is_active INTEGER DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);

-- Global system settings (LLM config managed by admin)
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS repos (
    id TEXT PRIMARY KEY,
    url TEXT,
    root_path TEXT,
    default_branch TEXT,
    commit_sha TEXT,
    language_set TEXT,
    job_id TEXT,
    owner_id TEXT,  -- User who created this project
    created_at TEXT,
    FOREIGN KEY (owner_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    path TEXT NOT NULL,
    language TEXT NOT NULL,
    hash TEXT,
    size INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS symbols (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    signature TEXT,
    container TEXT,
    line_start INTEGER,
    line_end INTEGER,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS dependency_edges (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    src_symbol_id TEXT,
    dst_symbol_id TEXT,
    edge_type TEXT NOT NULL,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS file_dependency_edges (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    src_path TEXT NOT NULL,
    dst_path TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    detail TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS modules (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    name TEXT NOT NULL,
    path_prefix TEXT NOT NULL,
    parent_id TEXT,
    stats TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS module_nodes (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    module_id TEXT NOT NULL,
    file_ids TEXT NOT NULL,
    symbol_ids TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS doc_artifacts (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    module_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT
);

-- Repo ingest configuration (for retries/resume)
CREATE TABLE IF NOT EXISTS repo_ingest_config (
    repo_id TEXT PRIMARY KEY,
    include_patterns TEXT,
    exclude_patterns TEXT,
    branch TEXT,
    commit_sha TEXT,
    local_path TEXT,
    created_at TEXT,
    updated_at TEXT
);

-- Repo checkpoints for resumable stages
CREATE TABLE IF NOT EXISTS repo_checkpoints (
    repo_id TEXT NOT NULL,
    checkpoint_key TEXT NOT NULL,
    checkpoint_value TEXT,
    updated_at TEXT,
    PRIMARY KEY (repo_id, checkpoint_key)
);

-- Token usage tracking
CREATE TABLE IF NOT EXISTS token_usage (
    id TEXT PRIMARY KEY,
    repo_id TEXT,
    kind TEXT NOT NULL, -- llm / embedding
    source TEXT, -- codewiki / ai_docs / qa / etc.
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens INTEGER NOT NULL,
    is_estimated INTEGER DEFAULT 1,
    created_at TEXT
);
