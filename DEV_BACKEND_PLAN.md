# Backend Development Doc (Phase 1: Analysis Engine)

## 1. Scope and Goals

Goal: build a backend analysis engine that produces accurate, verifiable codebase understanding for Python and Java. This backend is the foundation for a later web UI and future AI agent integration.

In scope
- Python and Java repositories.
- Deterministic code parsing, symbol extraction, and dependency graphing.
- Module hierarchy (coherent partitions) with traceable evidence.
- Structured documentation artifacts (JSON) for UI rendering.
- Retrieval layer that uses structure constraints (modules + dependencies) before LLM summarization.

Out of scope (Phase 1)
- Full web UI and rich visualization (comes later).
- Full multi-language coverage.
- Long-form narrative docs beyond structured summaries.

Success criteria
- Every generated statement can be traced to file paths and symbols.
- Dependency graph matches static analysis results for Python/Java.
- Module tree is stable across runs for the same repo (deterministic).


## 2. Accuracy Principles

1) Structure-first
- Use AST parsing + dependency graph + module clustering before any generation.
- Use the graph to constrain LLM context.

2) Evidence-first
- All summaries must include citations: file path, symbol name, and optional line ranges.

3) Determinism
- Sort files consistently; avoid nondeterministic traversal.
- Use fixed seeds where applicable; cap LLM usage to optional phase.


## 3. Architecture Overview

Services (logical)
- Ingest Service: clones repos, checks out commit, applies file filters.
- Analyzer Service: AST parsing, symbol extraction, dependency graph, module clustering.
- Doc Builder: generates structured docs (non-LLM baseline).
- Retrieval Layer: vector index + graph-aware retrieval.
- QA/Agent Gateway (later): uses retrieval + citations.

Core data stores
- Relational DB (Postgres): repo metadata, file records, symbols, module tree.
- Graph store (optional): dependency edges (can also live in Postgres).
- Vector store (FAISS): embeddings for code/doc chunks (chosen for easier install).
- Object store or filesystem: raw artifacts (module tree JSON, symbol map).


## 4. Recommended Tech Stack

- Python 3.12
- FastAPI for API surface
- Worker queue: Celery + Redis (or RQ/Arq)
- GitPython for repo operations
- Tree-sitter parsers for Python and Java
- NetworkX for dependency graphs
- FAISS for vector search (no external DB dependency)
- Pydantic v2 models


## 5. Pipeline Design

Step 0: Ingest
- Input: repo URL or local path
- Clone to workspace, checkout commit
- Apply include/exclude patterns

Step 1: Parse and Symbol Extraction
- For each file, parse AST
- Extract symbols: modules, classes, functions, methods, imports
- Build symbol table with stable IDs

Step 2: Dependency Graph
- Build file-level and symbol-level edges
- Edges include type: import, call, inherit, use
- Validate for Python/Java specificity

Step 3: Module Clustering
- Partition repository into modules using:
  - folder structure
  - dependency density
  - size thresholds
- Output module tree (hierarchy)

Step 4: Doc Builder (Non-LLM baseline)
- Generate structured JSON summaries:
  - module overview (files, key symbols)
  - dependency summary (incoming/outgoing)
  - entry points

Step 5: Indexing
- Build chunks for retrieval (file-level + symbol-level + module-level)
- Compute embeddings
- Store with metadata: module_id, symbol_id, file path
 - Use FAISS index on disk with deterministic IDs


## 6. Data Model (JSON Schema)

Repo
- id, url, default_branch, commit_sha, language_set

File
- id, repo_id, path, language, hash, size

Symbol
- id, repo_id, file_id, kind (class|function|method), name, signature, location

DependencyEdge
- id, repo_id, src_symbol_id, dst_symbol_id, edge_type

Module
- id, repo_id, name, path_prefix, parent_id, stats

ModuleNode
- id, module_id, file_ids, symbol_ids

DocArtifact
- id, repo_id, module_id, type (overview|api|deps), content_json

Chunk
- id, repo_id, module_id, file_id, symbol_id, text, embedding_id


## 7. API Design (Draft)

POST /repos/ingest
- body: { url | local_path, branch?, commit?, include?, exclude? }
- response: { repo_id, job_id }

GET /jobs/{job_id}
- response: { status, progress, error? }

GET /repos/{repo_id}/summary
- response: { languages, module_tree, entry_points }

GET /repos/{repo_id}/modules
- response: module tree JSON

GET /repos/{repo_id}/modules/{module_id}
- response: module details + files + key symbols

GET /repos/{repo_id}/deps
- response: dependency graph (node list + edges)

GET /repos/{repo_id}/docs/{module_id}
- response: structured doc JSON

POST /repos/{repo_id}/search
- body: { query, module_scope? }
- response: ranked chunks with citations

POST /repos/{repo_id}/answer
- body: { query, module_scope?, max_evidence? }
- response: answer + citations
 - model config: { base_url, api_key, model_name } (OpenAI-compatible)


## 8. Accuracy Controls

- Enforce parser coverage ratio: parsed_files / total_files > 0.95
- Build per-language unit tests for AST extraction
- Validate graph metrics: edge count thresholds + orphan nodes
- Require citations for any generated response
- Record model version and prompt hash for reproducibility


## 9. Implementation Phases

Phase A: Core analyzer for Python + Java
- Implement AST parsing for both languages
- Build symbol table and file metadata
- Build dependency graph
- Output JSON artifacts

Phase B: Module clustering and docs
- Partition modules and build hierarchy
- Generate structured doc JSON
- Add deterministic ordering

Phase C: Retrieval and indexing
- Chunk code and docs
- Build embeddings index
- Implement search endpoint with citations

Phase D: QA interface (no UI yet)
- Provide answer endpoint using retrieval results
- Strictly enforce citations


## 10. Test Strategy

- Unit tests: parser and symbol extraction for each language
- Integration tests: run on small sample repos
- Regression tests: snapshot JSON artifacts for known repos
- Performance tests: repo size 50K+ LOC


## 11. Deliverables (Phase 1)

- API service with ingest + analysis endpoints
- JSON artifacts for module tree, dependency graph, symbol index
- Retrieval endpoint with citations
- CLI helper for local development


## 12. Future Web Integration (Phase 2)

- Web UI consumes module tree + docs JSON
- Visualize dependency graphs and module hierarchy
- Side-by-side code viewer and docs


## 13. Open Questions

- Preferred LLM provider for answer endpoint? (OpenAI-compatible)
- Should we store symbol line ranges (requires language-specific loc tracking)?


## 14. Implementation Checklist (Estimates + Acceptance)

Estimates assume 1-2 engineers, mid-size repo, and reuse of CodeWiki parsing code.

1) Project skeleton and config (0.5-1 day)
- Tasks: FastAPI app, settings model, CLI wrapper for local runs
- Model config: base_url, api_key, model_name, timeout, max_tokens
- Acceptance: `GET /health` returns ok; config can be set via env

2) Ingest service (0.5-1 day)
- Tasks: clone repo, checkout commit, include/exclude filters
- Acceptance: local and remote repo ingest works; job reports status

3) Python AST parsing + symbols (2-3 days)
- Tasks: tree-sitter parser, extract classes/functions/imports
- Acceptance: symbol table matches a sample repo; coverage > 95%

4) Java AST parsing + symbols (2-3 days)
- Tasks: tree-sitter parser, extract classes/methods/imports
- Acceptance: symbol table matches a sample repo; coverage > 95%

5) Dependency graph (2-3 days)
- Tasks: build file-level and symbol-level edges; edge types
- Acceptance: graph nodes/edges stable; basic graph stats reported

6) Module clustering (1-2 days)
- Tasks: hierarchical module tree from folder + dependency density
- Acceptance: module tree deterministic for a fixed commit

7) Doc builder (1-2 days)
- Tasks: structured JSON summaries (overview, deps, entry points)
- Acceptance: docs include citations for each statement

8) Chunking + FAISS index (1-2 days)
- Tasks: chunk strategy, embeddings pipeline, index persistence
- Acceptance: search returns top-k chunks with citations in < 500ms (small repo)

9) Search API (0.5-1 day)
- Tasks: `/search` endpoint with module scope filter
- Acceptance: returns ranked chunks with file paths and symbols

10) Answer API (1-2 days)
- Tasks: `/answer` endpoint using retrieval + OpenAI-compatible calls
- Acceptance: response contains citations and uses configured model

11) Storage schema (0.5-1 day)
- Tasks: Postgres tables for repo/file/symbol/module/edge/doc
- Acceptance: migration scripts run; CRUD operations work

12) Tests and fixtures (2-3 days)
- Tasks: unit tests for parsers, integration tests for pipeline
- Acceptance: green test suite; snapshot artifacts for sample repos

13) Performance checks (0.5-1 day)
- Tasks: run on 50K+ LOC repo; profile hotspots
- Acceptance: total analysis < 30 min on dev machine; memory within budget

