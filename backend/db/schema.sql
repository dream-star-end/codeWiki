CREATE TABLE repos (
    id TEXT PRIMARY KEY,
    url TEXT,
    default_branch TEXT,
    commit_sha TEXT,
    language_set TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE files (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(id),
    path TEXT NOT NULL,
    language TEXT NOT NULL,
    hash TEXT,
    size INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE symbols (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(id),
    file_id TEXT NOT NULL REFERENCES files(id),
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    signature TEXT,
    container TEXT,
    line_start INTEGER,
    line_end INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dependency_edges (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(id),
    src_symbol_id TEXT,
    dst_symbol_id TEXT,
    edge_type TEXT NOT NULL,
    detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE modules (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(id),
    name TEXT NOT NULL,
    path_prefix TEXT NOT NULL,
    parent_id TEXT,
    stats JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE module_nodes (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(id),
    module_id TEXT NOT NULL REFERENCES modules(id),
    file_ids TEXT[] NOT NULL,
    symbol_ids TEXT[] NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE doc_artifacts (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(id),
    module_id TEXT NOT NULL REFERENCES modules(id),
    doc_type TEXT NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL REFERENCES repos(id),
    module_id TEXT,
    file_id TEXT,
    symbol_id TEXT,
    text TEXT NOT NULL,
    embedding_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
