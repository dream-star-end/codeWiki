CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL,
    error TEXT,
    created_at TEXT,
    updated_at TEXT
);
