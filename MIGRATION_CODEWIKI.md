# CodeWiki Backend Migration Plan

Goal: replace the current symbol/dependency extraction with CodeWiki analyzers while keeping the API and frontend intact.

## Current state
+- CodeWiki analyzer integrated for symbol + call relationships when `CODEWIKI_ENABLED=1`.
+- File discovery uses CodeWiki RepoAnalyzer when enabled.
+- Module clustering uses CodeWiki cluster_modules when enabled (LLM-driven).
+- File discovery, module tree, docs, indexing remain in this backend.

## How it works
+- `backend/app/services/codewiki_adapter.py` loads CodeWiki and returns:
+  - `symbols` from CodeWiki `Node` list
+  - `symbol_deps` from CodeWiki call relationships
+  - `module_tree` from CodeWiki clustering
+- `backend/app/services/analysis.py` switches behavior based on `CODEWIKI_ENABLED`.

## Next steps (optional)
- Map CodeWiki relationships into richer edge types (inherit/use) if available.
- Use CodeWiki clustering only when model credentials are provided.

## Usage
+- Enable: set env `CODEWIKI_ENABLED=1`
+- Disable: set env `CODEWIKI_ENABLED=0`
