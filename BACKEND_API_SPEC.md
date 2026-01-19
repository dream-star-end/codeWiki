# Backend API Spec (Draft)

## Base
- All endpoints are JSON.
- OpenAI-compatible model config is provided per request for `/answer`.

## Health
GET /health
- 200 {"status":"ok"}

## Ingest
POST /repos/ingest
- body: { url | local_path, branch?, commit?, include?, exclude? }
- response: { repo_id, job_id }

GET /jobs/{job_id}
- response: { status, progress, error? }

## Repo Overview
GET /repos/{repo_id}/summary
- response: { repo_id, languages, module_tree, entry_points }

GET /repos/{repo_id}/modules
- response: { repo_id, modules[] }

GET /repos/{repo_id}/modules/{module_id}
- response: { module_id, name, path_prefix, files[], symbols[], dependencies_in[], dependencies_out[] }

GET /repos/{repo_id}/deps
- response: { nodes[], edges[] }

GET /repos/{repo_id}/docs/{module_id}
- response: { module_id, doc_type, content }

## Retrieval
POST /repos/{repo_id}/search
- body: { query, module_scope?, top_k? }
- response: { results[] }

POST /repos/{repo_id}/answer
- body: { query, module_scope?, max_evidence?, model: { base_url, api_key, model_name, timeout_s, max_tokens } }
- response: { answer, citations[] }

## Citation Format
- { file_path, symbol?, line_start?, line_end? }
