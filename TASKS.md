# Backend Task Checklist (Python + Java, API-first)

Status legend: [ ] pending, [x] done

## Phase 0 - Project setup
- [x] Create baseline FastAPI app skeleton and API stubs (0.5 day)
  - Acceptance: `GET /health` returns ok; server starts clean
- [x] Define request/response schema models (0.5 day)
  - Acceptance: OpenAPI shows all endpoints and models

## Phase 1 - Ingest + Job system
- [x] Implement job store and status reporting (0.5 day)
  - Acceptance: job status transitions: queued -> running -> success/failed
- [x] Implement repo ingest (clone or local path) (0.5-1 day)
  - Acceptance: repo cloned to workspace; errors surfaced in job status
- [x] Add include/exclude filters to ingest stage (0.5 day)
  - Acceptance: filtered file count matches patterns

## Phase 2 - Parsing and symbols
- [x] Python AST parsing with tree-sitter (2-3 days)
  - Acceptance: classes/functions/imports extracted on sample repo
- [x] Java AST parsing with tree-sitter (2-3 days)
  - Acceptance: classes/methods/imports extracted on sample repo
- [x] Normalize symbol IDs and locations (0.5 day)
  - Acceptance: deterministic IDs across runs

## Phase 3 - Dependency graph
- [x] Build file-level dependency edges (1 day)
  - Acceptance: imports generate edges; graph metrics stable
- [x] Build symbol-level dependency edges (1-2 days)
  - Acceptance: call/inherit/use edges built for sampled symbols

## Phase 4 - Module clustering
- [x] Build module tree from path + dependency density (1-2 days)
  - Acceptance: module tree stable for a fixed commit
- [x] Assign files/symbols into module nodes (0.5 day)
  - Acceptance: 100% files assigned to modules
- [x] Refine module clustering with dependency density (1 day)
  - Acceptance: merges/splits reflect dependency edges

## Phase 5 - Doc builder
- [x] Generate structured module overview JSON (1 day)
  - Acceptance: includes key symbols + entry points + deps
- [x] Add citation map to all statements (1 day)
  - Acceptance: every statement has file/symbol references

## Phase 6 - Retrieval + FAISS
- [x] Chunking strategy (file/symbol/module) (0.5-1 day)
  - Acceptance: chunk metadata includes module_id + symbol_id
- [x] Build FAISS index + persistence (0.5-1 day)
  - Acceptance: index reloads and returns top-k chunks
- [x] Implement `/search` endpoint (0.5 day)
  - Acceptance: returns ranked chunks with citations

## Phase 7 - Answer API (OpenAI-compatible)
- [x] Implement LLM client with base_url/api_key/model_name (0.5 day)
  - Acceptance: can call any OpenAI-compatible endpoint
- [x] Implement `/answer` endpoint with evidence constraints (1 day)
  - Acceptance: response includes citations; respects module scope

## Phase 8 - Storage + tests
- [x] Define DB schema + migrations (0.5-1 day)
  - Acceptance: tables for repo/file/symbol/module/edge/doc
- [x] Unit tests for parsing and symbol extraction (1-2 days)
  - Acceptance: tests green; fixtures for Python/Java
- [x] Integration tests for pipeline (1-2 days)
  - Acceptance: sample repo end-to-end run produces artifacts

## Phase 9 - Performance + hardening
- [x] Run 50K+ LOC repo benchmark (0.5 day)
  - Acceptance: analysis completes under 30 min on dev machine
- [x] Add logging + tracing (0.5 day)
  - Acceptance: job logs stored per repo and stage

## Phase 10 - Production readiness
- [x] DB persistence (replace JSON storage) (2-3 days)
  - Acceptance: analysis results written/read from DB; JSON kept only as cache
- [x] Dependency outputs (symbol-level + module-level views) (1-2 days)
  - Acceptance: `/deps` returns file + symbol + module aggregation
- [x] Job queue persistence (1-2 days)
  - Acceptance: jobs survive restart and can resume
