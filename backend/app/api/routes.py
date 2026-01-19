from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Depends, Body
from fastapi.responses import StreamingResponse
from typing import Optional
import uuid
import json

from app.models.schemas import (
    IngestRequest,
    IngestResponse,
    JobStatus,
    RepoSummary,
    ModuleDetails,
    DependencyGraph,
    DocArtifact,
    SearchRequest,
    SearchResponse,
    AnswerRequest,
    AnswerResponse,
    AIDocRequest,
    AIDocResponse,
    AIModuleDocsResponse,
    CodebaseExportRequest,
    SmartContextRequest,
)
from app.core.jobs import create_job, get_job, set_job, is_job_canceled
from app.core.logging import get_job_logger
from app.services.ingest import ingest_repo
from app.services.faiss_index import search_index, build_index, hybrid_search, keyword_search
from app.services.chunking import build_chunks_from_docs
from app.services.analysis import run_analysis
from app.services.db import (
    read_summary,
    read_modules,
    read_repo_list,
    create_repo,
    delete_repo,
    get_repo_owner,
    get_repo_job,
    read_running_repos_progress,
    upsert_repo_ingest_config,
    get_repo_ingest_config,
    get_repo_root,
    get_repo_url,
    set_repo_job,
    get_repo_commit,
    set_repo_commit,
    read_docs,
    read_doc_by_module,
    get_module_ids_by_files,
    get_module_files,
    insert_docs,
    record_token_usage,
)
from app.services.deps_view import read_file_deps, read_symbol_edges, read_module_edges
from app.services.llm_client import chat_completion_with_usage, chat_completion_stream, LLMMessage
from app.api.auth_routes import get_current_user
from app.services.llm_settings import get_effective_llm_config
from app.services.ai_docs import generate_repo_ai_summary, generate_module_ai_docs
from app.services.code_browser import (
    get_file_tree_for_repo,
    get_file_content,
    get_file_chunk,
    search_in_file,
    file_node_to_dict,
    search_files,
)
from app.services.symbol_navigator import (
    get_symbol_definition,
    get_symbol_references,
    search_symbols,
    get_symbol_callers,
    get_symbol_callees,
    get_call_graph,
    get_file_outline,
)
from app.services.codebase_export import (
    export_codebase,
    generate_smart_context,
    get_codebase_stats,
    ExportConfig,
)
from app.services.learning_path import (
    get_learning_path,
    get_module_learning_path,
    find_entry_points,
)
from app.services.mcp_generator import (
    generate_mcp_server_code,
    generate_cursor_mcp_config,
    generate_claude_desktop_config,
    save_mcp_server,
    get_mcp_tools_list,
)
from app.services.mcp_runtime import start_mcp_server, stop_mcp_server, get_mcp_status
from app.services.code_explain import (
    explain_code_snippet,
    explain_symbol,
    explain_file,
)
from pathlib import Path
import os
import shutil
from git import Repo, InvalidGitRepositoryError

router = APIRouter()


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/repos/ingest", response_model=IngestResponse)
def ingest_repo_endpoint(
    request: IngestRequest,
    background: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    repo_id = f"repo_{uuid.uuid4().hex}"
    job_id = create_job()
    # Use global LLM config managed by admin
    effective_model = get_effective_llm_config(request.model)

    # Create repo entry immediately so it appears in the list
    create_repo(repo_id, request.url, job_id, owner_id=user["id"])
    upsert_repo_ingest_config(
        repo_id,
        request.include,
        request.exclude,
        request.branch,
        request.commit,
        request.local_path,
    )

    def run_ingest():
        try:
            logger = get_job_logger(repo_id)
            logger.info("ingest_start repo_id=%s", repo_id)
            if is_job_canceled(job_id):
                set_job(job_id, status="canceled", progress=0, stage="已取消", detail="任务已取消")
                return
            set_job(job_id, status="running", progress=5, stage="克隆仓库", detail="正在下载或准备代码仓库...")
            repo_path = ingest_repo(request, repo_id=repo_id)
            set_job(job_id, status="running", progress=15, stage="仓库准备完成", detail="代码已就绪，开始分析")
            if repo_path:
                try:
                    repo = Repo(str(repo_path))
                    set_repo_commit(repo_id, repo.head.commit.hexsha)
                except (InvalidGitRepositoryError, Exception):
                    pass
                run_analysis(
                    repo_id,
                    str(repo_path),
                    request.include,
                    request.exclude,
                    llm_model=effective_model,
                    job_id=job_id,
                    repo_url=request.url,
                )
            set_job(job_id, status="success", progress=100, stage="完成", detail="Wiki 生成完毕！")
            logger.info("ingest_complete repo_id=%s", repo_id)
        except Exception as exc:
            set_job(job_id, status="failed", progress=100, error=str(exc), stage="失败", detail=str(exc)[:200])
            logger = get_job_logger(repo_id)
            logger.error("ingest_failed repo_id=%s error=%s", repo_id, exc)

    background.add_task(run_ingest)
    return {"repo_id": repo_id, "job_id": job_id}


@router.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str):
    return get_job(job_id)


@router.get("/repos")
def repo_list():
    return {"repos": read_repo_list()}


@router.get("/repos/my")
def repo_list_my(user: dict = Depends(get_current_user)):
    return {"repos": read_repo_list(owner_id=user["id"])}


@router.get("/repos/progress")
def repos_progress():
    """Get progress info for running/queued repos only (lightweight, for polling)."""
    return {"repos": read_running_repos_progress()}


@router.post("/repos/{repo_id}/cancel")
def cancel_repo_job(repo_id: str, user: dict = Depends(get_current_user)):
    """Cancel a running job for a repo."""
    owner_id = get_repo_owner(repo_id)
    if not owner_id:
        raise HTTPException(status_code=404, detail="repo not found")
    if user["role"] != "admin" and owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="无权限取消该任务")

    job_id = get_repo_job(repo_id)
    if not job_id:
        raise HTTPException(status_code=404, detail="job not found")

    set_job(job_id, status="canceled", progress=0, stage="已取消", detail="任务已取消")
    return {"message": "任务已取消"}


@router.post("/repos/{repo_id}/retry")
def retry_repo_job(
    repo_id: str,
    background: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Retry a failed job from the last checkpoint to reduce token usage."""
    owner_id = get_repo_owner(repo_id)
    if not owner_id:
        raise HTTPException(status_code=404, detail="repo not found")
    if user["role"] != "admin" and owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="无权限重试该任务")

    ingest_config = get_repo_ingest_config(repo_id)
    repo_url = get_repo_url(repo_id)
    if not ingest_config and not repo_url:
        raise HTTPException(status_code=400, detail="缺少重试所需的仓库信息")

    job_id = create_job()
    set_repo_job(repo_id, job_id)
    effective_model = get_effective_llm_config(None)

    def run_retry():
        try:
            logger = get_job_logger(repo_id)
            logger.info("ingest_retry_start repo_id=%s", repo_id)
            if is_job_canceled(job_id):
                set_job(job_id, status="canceled", progress=0, stage="已取消", detail="任务已取消")
                return

            set_job(job_id, status="running", progress=5, stage="准备重试", detail="正在准备重试环境...")

            repo_root = get_repo_root(repo_id)
            repo_path = None
            if repo_root and Path(repo_root).exists():
                repo_path = Path(repo_root)
            else:
                request = IngestRequest(
                    url=repo_url,
                    local_path=ingest_config.get("local_path") if ingest_config else None,
                    branch=ingest_config.get("branch") if ingest_config else None,
                    commit=ingest_config.get("commit") if ingest_config else None,
                    include=ingest_config.get("include") if ingest_config else None,
                    exclude=ingest_config.get("exclude") if ingest_config else None,
                    model=None,
                )
                set_job(job_id, status="running", progress=8, stage="准备仓库", detail="正在拉取或定位代码仓库...")
                repo_path = ingest_repo(request, repo_id=repo_id)

            set_job(job_id, status="running", progress=15, stage="仓库准备完成", detail="代码已就绪，开始分析")
            if repo_path:
                run_analysis(
                    repo_id,
                    str(repo_path),
                    ingest_config.get("include") if ingest_config else None,
                    ingest_config.get("exclude") if ingest_config else None,
                    llm_model=effective_model,
                    job_id=job_id,
                    repo_url=repo_url,
                )
            set_job(job_id, status="success", progress=100, stage="完成", detail="Wiki 生成完毕！")
            logger.info("ingest_retry_complete repo_id=%s", repo_id)
        except Exception as exc:
            set_job(job_id, status="failed", progress=100, error=str(exc), stage="失败", detail=str(exc)[:200])
            logger = get_job_logger(repo_id)
            logger.error("ingest_retry_failed repo_id=%s error=%s", repo_id, exc)

    background.add_task(run_retry)
    return {"repo_id": repo_id, "job_id": job_id}


@router.post("/repos/{repo_id}/update")
def update_repo_job(
    repo_id: str,
    background: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Update docs for repo if code changed since last commit."""
    owner_id = get_repo_owner(repo_id)
    if not owner_id:
        raise HTTPException(status_code=404, detail="repo not found")
    if user["role"] != "admin" and owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="无权限更新该项目")

    ingest_config = get_repo_ingest_config(repo_id)
    repo_url = get_repo_url(repo_id)
    repo_root = get_repo_root(repo_id)
    if not repo_root:
        raise HTTPException(status_code=400, detail="仓库路径不存在")

    job_id = create_job()
    set_repo_job(repo_id, job_id)
    effective_model = get_effective_llm_config(None)

    def run_update():
        try:
            logger = get_job_logger(repo_id)
            logger.info("ingest_update_start repo_id=%s", repo_id)
            if is_job_canceled(job_id):
                set_job(job_id, status="canceled", progress=0, stage="已取消", detail="任务已取消")
                return

            set_job(job_id, status="running", progress=5, stage="检查更新", detail="正在检查代码更新...")
            repo = Repo(repo_root)
            # Try to pull latest for remote repos
            if repo_url and repo_url.startswith(("http://", "https://", "git@")):
                try:
                    if repo.remotes:
                        repo.remotes.origin.fetch()
                        repo.remotes.origin.pull()
                except Exception as exc:
                    logger.warning("repo_update_pull_failed repo_id=%s error=%s", repo_id, exc)

            old_sha = get_repo_commit(repo_id)
            new_sha = repo.head.commit.hexsha
            if old_sha and old_sha == new_sha:
                set_job(job_id, status="success", progress=100, stage="无更新", detail="代码无变更，无需更新文档")
                logger.info("ingest_update_no_change repo_id=%s", repo_id)
                return

            changed_files: list[str] = []
            if old_sha:
                try:
                    diff_output = repo.git.diff("--name-status", f"{old_sha}..{new_sha}")
                    for line in diff_output.splitlines():
                        if not line.strip():
                            continue
                        parts = line.split("\t")
                        status = parts[0]
                        if status.startswith("R") and len(parts) >= 3:
                            rel_path = parts[2]
                        elif len(parts) >= 2:
                            rel_path = parts[1]
                        else:
                            continue
                        abs_path = Path(repo_root) / rel_path
                        if abs_path.exists():
                            changed_files.append(rel_path)
                except Exception as exc:
                    logger.warning("repo_update_diff_failed repo_id=%s error=%s", repo_id, exc)

            if changed_files:
                detail = f"检测到 {len(changed_files)} 个变更文件，执行增量更新"
                include_for_update = changed_files
            else:
                detail = "未能解析变更文件列表，执行全量更新"
                include_for_update = ingest_config.get("include") if ingest_config else None

            set_job(job_id, status="running", progress=15, stage="开始更新", detail=detail)

            # Incremental doc update: only update impacted modules if diff is available.
            updated_docs: list[dict] = []
            incremental_ok = False
            if changed_files:
                module_ids = get_module_ids_by_files(repo_id, changed_files)
                # Safety guardrails: avoid partial updates when impact is large or unclear.
                if module_ids and len(module_ids) <= 12:
                    set_job(job_id, status="running", progress=25, stage="增量更新", detail=f"更新 {len(module_ids)} 个模块文档")
                    for module_id in module_ids:
                        doc = read_doc_by_module(repo_id, module_id)
                        if not doc:
                            incremental_ok = False
                            updated_docs = []
                            break
                        old_md = doc.get("markdown", "")
                        module_files = get_module_files(repo_id, module_id)
                        rel_paths: list[str] = []
                        for file_path in module_files:
                            try:
                                rel_paths.append(Path(file_path).relative_to(Path(repo_root)).as_posix())
                            except Exception:
                                rel_paths.append(Path(file_path).as_posix())

                        if not rel_paths:
                            incremental_ok = False
                            updated_docs = []
                            break

                        try:
                            diff_output = repo.git.diff(f"{old_sha}..{new_sha}", "--", *rel_paths)
                        except Exception as exc:
                            logger.warning("module_diff_failed repo_id=%s module_id=%s error=%s", repo_id, module_id, exc)
                            incremental_ok = False
                            updated_docs = []
                            break

                        if not diff_output:
                            continue

                        # Guardrail: if diff is too large, prefer full rebuild for accuracy.
                        if len(diff_output) > 12000:
                            incremental_ok = False
                            updated_docs = []
                            break

                        prompt = (
                            "你是代码文档更新助手。根据提供的代码变更 diff，"
                            "在不丢失关键信息的前提下，更新模块文档内容。\n"
                            "要求：\n"
                            "- 保持中文\n"
                            "- 只输出更新后的完整文档内容\n"
                            "- 不要输出解释或多余说明\n\n"
                            f"【代码变更 diff（仅当前模块）】\n{diff_output}\n\n"
                            f"【原文档】\n{old_md}\n"
                        )
                        try:
                            new_md, usage = chat_completion_with_usage(
                                [LLMMessage(role="user", content=prompt)],
                                effective_model,
                            )
                            record_token_usage(
                                repo_id,
                                kind="llm",
                                prompt_tokens=usage.get("prompt_tokens", 0),
                                completion_tokens=usage.get("completion_tokens", 0),
                                total_tokens=usage.get("total_tokens", 0),
                                is_estimated=usage.get("is_estimated", True),
                                source="repo_update",
                            )
                        except Exception as exc:
                            logger.warning("module_doc_update_failed repo_id=%s module_id=%s error=%s", repo_id, module_id, exc)
                            incremental_ok = False
                            updated_docs = []
                            break
                        if new_md:
                            updated = doc.copy()
                            updated["markdown"] = new_md.strip()
                            updated_docs.append(updated)
                    else:
                        incremental_ok = True

            if incremental_ok and updated_docs:
                insert_docs(repo_id, updated_docs)
            else:
                # Fallback to full analysis when incremental update not possible or unsafe
                run_analysis(
                    repo_id,
                    str(repo_root),
                    include_for_update,
                    ingest_config.get("exclude") if ingest_config else None,
                    llm_model=effective_model,
                    job_id=job_id,
                    repo_url=repo_url,
                )

            set_job(job_id, status="running", progress=92, stage="重建索引", detail="正在重建检索索引...")
            docs = read_docs(repo_id)
            chunks = build_chunks_from_docs(docs)
            build_index(repo_id, chunks)
            set_repo_commit(repo_id, new_sha)
            set_job(job_id, status="success", progress=100, stage="完成", detail="文档更新完成")
            logger.info("ingest_update_complete repo_id=%s", repo_id)
        except InvalidGitRepositoryError:
            set_job(job_id, status="failed", progress=100, error="非 Git 仓库，无法更新", stage="失败", detail="非 Git 仓库")
        except Exception as exc:
            set_job(job_id, status="failed", progress=100, error=str(exc), stage="失败", detail=str(exc)[:200])
            logger = get_job_logger(repo_id)
            logger.error("ingest_update_failed repo_id=%s error=%s", repo_id, exc)

    background.add_task(run_update)
    return {"repo_id": repo_id, "job_id": job_id}


@router.delete("/repos/{repo_id}")
def delete_repo_endpoint(repo_id: str, user: dict = Depends(get_current_user)):
    """Delete a repo. Owner can delete own; admin can delete all."""
    owner_id = get_repo_owner(repo_id)
    if owner_id and user["role"] != "admin" and owner_id != user["id"]:
        raise HTTPException(status_code=403, detail="无权限删除该项目")

    # Delete database records
    delete_repo(repo_id)

    # Remove workspace artifacts
    base_dir = Path(__file__).resolve().parents[2] / "workspace"
    for sub in [
        base_dir / repo_id,
        base_dir / "codewiki_docs" / repo_id,
        base_dir / "indexes" / repo_id,
    ]:
        if sub.exists():
            if sub.is_dir():
                def _onerror(func, path, _exc_info):
                    try:
                        os.chmod(path, 0o700)
                        func(path)
                    except Exception:
                        pass

                shutil.rmtree(sub, onerror=_onerror)
            else:
                try:
                    os.chmod(sub, 0o600)
                except Exception:
                    pass
                sub.unlink(missing_ok=True)

    if not owner_id:
        return {"message": "项目不存在或已删除"}
    return {"message": "项目已删除"}


@router.get("/repos/{repo_id}/summary", response_model=RepoSummary)
def repo_summary(repo_id: str):
    summary = read_summary(repo_id)
    if not summary:
        raise HTTPException(status_code=404, detail="summary not found")
    modules = read_modules(repo_id)
    entry_points = find_entry_points(repo_id)
    return {
        "repo_id": repo_id,
        "languages": summary.get("languages", []),
        "module_tree": {"modules": modules},
        "entry_points": entry_points,
    }


@router.get("/repos/{repo_id}/logs")
def repo_logs(repo_id: str):
    log_path = Path(__file__).resolve().parents[2] / "workspace" / "logs" / f"{repo_id}.log"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="log not found")
    return {"log": log_path.read_text(encoding="utf-8", errors="replace")}


@router.get("/repos/{repo_id}/modules")
def repo_modules(repo_id: str):
    modules = read_modules(repo_id)
    if not modules:
        raise HTTPException(status_code=404, detail="module tree not found")
    return {"repo_id": repo_id, "modules": modules}


@router.get("/repos/{repo_id}/modules/{module_id}", response_model=ModuleDetails)
def module_details(repo_id: str, module_id: str):
    docs = read_docs(repo_id) or []
    for doc in docs:
        if doc.get("module_id") == module_id:
            return {
                "module_id": module_id,
                "name": doc.get("name", ""),
                "path_prefix": doc.get("path_prefix", ""),
                "files": doc.get("files", []),
                "symbols": [s.get("name") for s in doc.get("key_symbols", [])],
                "dependencies_in": [],
                "dependencies_out": [],
            }
    raise HTTPException(status_code=404, detail="module not found")


@router.get("/repos/{repo_id}/deps", response_model=DependencyGraph)
def repo_deps(repo_id: str):
    file_deps = read_file_deps(repo_id)
    symbol_edges = read_symbol_edges(repo_id)
    module_edges = read_module_edges(repo_id)
    return {"nodes": [], "edges": [], "file_deps": file_deps, "symbol_deps": symbol_edges, "module_deps": module_edges}


@router.get("/repos/{repo_id}/docs/{module_id}", response_model=DocArtifact)
def repo_docs(repo_id: str, module_id: str):
    docs = read_docs(repo_id) or []
    for doc in docs:
        if doc.get("module_id") == module_id:
            markdown = doc.get("markdown") or doc.get("content") or ""
            meta = {k: v for k, v in doc.items() if k not in {"markdown", "content"}}
            return {"module_id": module_id, "doc_type": doc.get("doc_type", "overview"), "content": markdown, "meta": meta}
    raise HTTPException(status_code=404, detail="doc not found")


@router.post("/repos/{repo_id}/search", response_model=SearchResponse)
def repo_search(repo_id: str, request: SearchRequest):
    hits = search_index(repo_id, request.query, request.top_k)
    results = []
    for hit in hits:
        results.append(
            {
                "chunk_id": hit.chunk.id,
                "text": hit.chunk.text,
                "score": hit.score,
                "citations": [c.__dict__ for c in hit.chunk.citations],
            }
        )
    return {"results": results}


@router.post("/repos/{repo_id}/search/hybrid")
def repo_search_hybrid(
    repo_id: str,
    query: str = Body(..., embed=True),
    top_k: int = Body(8, embed=True),
    search_type: str = Body("hybrid", embed=True),
    semantic_weight: float = Body(0.7, embed=True),
    keyword_weight: float = Body(0.3, embed=True),
):
    """
    混合搜索接口
    
    Args:
        repo_id: 仓库ID
        query: 查询字符串
        top_k: 返回结果数
        search_type: 搜索类型 (hybrid/semantic/keyword)
        semantic_weight: 语义搜索权重
        keyword_weight: 关键词搜索权重
    
    Returns:
        搜索结果列表
    """
    if search_type == "keyword":
        hits = keyword_search(repo_id, query, top_k)
    elif search_type == "semantic":
        hits = search_index(repo_id, query, top_k)
    else:  # hybrid
        hits = hybrid_search(
            repo_id, query, top_k,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
        )
    
    results = []
    for hit in hits:
        results.append({
            "chunk_id": hit.chunk.id,
            "text": hit.chunk.text,
            "score": hit.score,
            "citations": [c.__dict__ for c in hit.chunk.citations],
        })
    
    return {
        "results": results,
        "search_type": search_type,
        "query": query,
    }


@router.post("/repos/{repo_id}/answer", response_model=AnswerResponse)
def repo_answer(repo_id: str, request: AnswerRequest):
    hits = search_index(repo_id, request.query, request.max_evidence)
    if not hits:
        return {"answer": "", "citations": []}

    evidence = []
    citations = []
    for hit in hits:
        evidence.append(f"{hit.chunk.text}")
        citations.extend(hit.chunk.citations)

    system_prompt = (
        "You are a codebase analysis assistant. Use only the provided evidence. "
        "Answer concisely and include only verifiable facts."
    )
    user_prompt = "\n\n".join(["Evidence:", *evidence, "Question:", request.query])

    effective_model = get_effective_llm_config(request.model)
    answer, usage = chat_completion_with_usage(
        [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt),
        ],
        effective_model,
    )
    record_token_usage(
        repo_id,
        kind="llm",
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        is_estimated=usage.get("is_estimated", True),
        source="repo_answer",
    )

    return {"answer": answer, "citations": [c.__dict__ for c in citations]}


@router.post("/repos/{repo_id}/answer/stream")
def repo_answer_stream(repo_id: str, request: AnswerRequest):
    """Stream chat completion response using Server-Sent Events.
    
    Supports deep thinking mode for GLM models.
    See: https://docs.bigmodel.cn/cn/guide/capabilities/thinking
    """
    hits = search_index(repo_id, request.query, request.max_evidence)
    
    def generate():
        if not hits:
            yield f"data: {json.dumps({'type': 'done', 'content': ''})}\n\n"
            return

        evidence = []
        citations = []
        for hit in hits:
            evidence.append(f"{hit.chunk.text}")
            citations.extend(hit.chunk.citations)

        # Send citations first
        yield f"data: {json.dumps({'type': 'citations', 'citations': [c.__dict__ for c in citations]})}\n\n"

        system_prompt = (
            "你是一个代码库分析助手。仅使用提供的证据回答问题。"
            "用中文简洁回答，只陈述可验证的事实。"
        )
        user_prompt = "\n\n".join(["证据:", *evidence, "问题:", request.query])
        stream_usage = None

        try:
            effective_model = get_effective_llm_config(request.model)
            for chunk in chat_completion_stream(
                [
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=user_prompt),
                ],
                effective_model,
                enable_thinking=True,  # Enable deep thinking for supported models
            ):
                if chunk["type"] == "usage":
                    stream_usage = chunk.get("usage") or {}
                    continue
                # chunk is now a dict with 'type' and 'text'
                if chunk["type"] == "thinking":
                    yield f"data: {json.dumps({'type': 'thinking', 'content': chunk['text']})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk['text']})}\n\n"
            if stream_usage:
                record_token_usage(
                    repo_id,
                    kind="llm",
                    prompt_tokens=int(stream_usage.get("prompt_tokens") or 0),
                    completion_tokens=int(stream_usage.get("completion_tokens") or 0),
                    total_tokens=int(stream_usage.get("total_tokens") or 0),
                    is_estimated=False,
                    source="repo_answer_stream",
                )
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/repos/{repo_id}/ai/summary", response_model=AIDocResponse)
def repo_ai_summary(repo_id: str, request: AIDocRequest):
    effective_model = get_effective_llm_config(request.model)
    content = generate_repo_ai_summary(repo_id, effective_model)
    return {"doc_type": "ai_repo", "content": content}


@router.post("/repos/{repo_id}/ai/modules", response_model=AIModuleDocsResponse)
def repo_ai_modules(repo_id: str, request: AIDocRequest):
    effective_model = get_effective_llm_config(request.model)
    items = generate_module_ai_docs(repo_id, effective_model, request.max_modules)
    return {"doc_type": "ai_module", "modules": items}


# ============== 代码浏览器 API ==============

@router.get("/repos/{repo_id}/files")
def repo_file_tree(repo_id: str):
    """获取仓库文件树"""
    tree = get_file_tree_for_repo(repo_id)
    if not tree:
        raise HTTPException(status_code=404, detail="repo not found")
    return {"repo_id": repo_id, "tree": file_node_to_dict(tree)}


@router.get("/repos/{repo_id}/files/chunk")
def repo_file_chunk(
    repo_id: str,
    file_path: str = Query(..., description="文件路径"),
    offset: int = Query(1, description="起始行（1-based）"),
    limit: int = Query(200, description="行数"),
):
    """获取文件内容分块"""
    chunk = get_file_chunk(repo_id, file_path, offset=offset, limit=limit)
    if not chunk:
        raise HTTPException(status_code=404, detail="file not found")
    return chunk


@router.get("/repos/{repo_id}/files/search-in-file")
def repo_search_in_file(
    repo_id: str,
    file_path: str = Query(..., description="文件路径"),
    q: str = Query(..., description="搜索查询"),
    context: int = Query(2, description="上下文行数"),
    limit: int = Query(20, description="最大返回数量"),
    case_sensitive: bool = Query(False, description="区分大小写"),
    use_regex: bool = Query(False, description="使用正则表达式"),
):
    """在单文件内搜索"""
    result = search_in_file(
        repo_id,
        file_path,
        q,
        context=context,
        limit=limit,
        case_sensitive=case_sensitive,
        use_regex=use_regex,
    )
    if not result:
        raise HTTPException(status_code=404, detail="file not found")
    return result


@router.get("/repos/{repo_id}/files/{file_path:path}")
def repo_file_content(repo_id: str, file_path: str):
    """获取文件内容"""
    content = get_file_content(repo_id, file_path)
    if not content:
        raise HTTPException(status_code=404, detail="file not found")
    return {
        "path": content.path,
        "content": content.content,
        "language": content.language,
        "lines": content.lines,
        "size": content.size,
        "symbols": content.symbols,
    }


@router.get("/repos/{repo_id}/files-search")
def repo_file_search(
    repo_id: str,
    q: str = Query(..., description="搜索查询"),
    limit: int = Query(20, description="最大返回数量"),
):
    """搜索文件"""
    results = search_files(repo_id, q, limit)
    return {"results": results}


# ============== 符号导航 API ==============

@router.get("/repos/{repo_id}/symbols")
def repo_symbols_search(
    repo_id: str,
    q: str = Query(..., description="搜索查询"),
    kind: Optional[str] = Query(None, description="符号类型过滤"),
    limit: int = Query(50, description="最大返回数量"),
):
    """搜索符号"""
    results = search_symbols(repo_id, q, kind, limit)
    return {"results": results}


@router.get("/repos/{repo_id}/symbols/{symbol_id}")
def repo_symbol_detail(repo_id: str, symbol_id: str):
    """获取符号详情"""
    location = get_symbol_definition(repo_id, symbol_id)
    if not location:
        raise HTTPException(status_code=404, detail="symbol not found")
    
    references = get_symbol_references(repo_id, symbol_id)
    callers = get_symbol_callers(repo_id, symbol_id)
    callees = get_symbol_callees(repo_id, symbol_id)
    
    return {
        "symbol_id": location.symbol_id,
        "name": location.name,
        "kind": location.kind,
        "file_path": location.file_path,
        "line_start": location.line_start,
        "line_end": location.line_end,
        "signature": location.signature,
        "references": [{"file_path": r.file_path, "line": r.line, "edge_type": r.edge_type} for r in references],
        "callers": callers,
        "callees": callees,
    }


@router.get("/repos/{repo_id}/symbols/{symbol_id}/definition")
def repo_symbol_definition(repo_id: str, symbol_id: str):
    """跳转到符号定义"""
    location = get_symbol_definition(repo_id, symbol_id)
    if not location:
        raise HTTPException(status_code=404, detail="symbol not found")
    return {
        "file_path": location.file_path,
        "line_start": location.line_start,
        "line_end": location.line_end,
    }


@router.get("/repos/{repo_id}/symbols/{symbol_id}/references")
def repo_symbol_references(repo_id: str, symbol_id: str):
    """获取符号引用"""
    references = get_symbol_references(repo_id, symbol_id)
    return {
        "symbol_id": symbol_id,
        "references": [
            {"file_path": r.file_path, "line": r.line, "context": r.context, "edge_type": r.edge_type}
            for r in references
        ],
    }


@router.get("/repos/{repo_id}/symbols/{symbol_id}/call-graph")
def repo_symbol_call_graph(
    repo_id: str,
    symbol_id: str,
    depth: int = Query(2, description="遍历深度"),
):
    """获取符号调用图"""
    graph = get_call_graph(repo_id, symbol_id, depth)
    return graph


@router.get("/repos/{repo_id}/outline/{file_path:path}")
def repo_file_outline(repo_id: str, file_path: str):
    """获取文件大纲"""
    outline = get_file_outline(repo_id, file_path)
    return {"file_path": file_path, "outline": outline}


# ============== Codebase 导出 API ==============

@router.post("/repos/{repo_id}/codebase/export")
def repo_codebase_export(repo_id: str, request: CodebaseExportRequest):
    """导出代码库上下文"""
    config = ExportConfig(
        format=request.format,
        scope=request.scope,
        module_ids=request.module_ids,
        file_paths=request.file_paths,
        include_deps=request.include_deps,
        max_tokens=request.max_tokens,
        include_summary=request.include_summary,
    )
    result = export_codebase(repo_id, config)
    return {
        "content": result.content,
        "token_count": result.token_count,
        "files_included": result.files_included,
        "format": result.format,
    }


@router.post("/repos/{repo_id}/codebase/context")
def repo_smart_context(repo_id: str, request: SmartContextRequest):
    """根据查询生成智能上下文"""
    result = generate_smart_context(repo_id, request.query, request.max_tokens)
    return {
        "content": result.content,
        "token_count": result.token_count,
        "files_included": result.files_included,
    }


@router.get("/repos/{repo_id}/codebase/stats")
def repo_codebase_stats(repo_id: str):
    """获取代码库统计信息"""
    stats = get_codebase_stats(repo_id)
    if not stats:
        raise HTTPException(status_code=404, detail="repo not found")
    return stats


# ============== 学习路径 API ==============

@router.get("/repos/{repo_id}/learning-path")
def repo_learning_path(repo_id: str):
    """获取仓库学习路径"""
    path = get_learning_path(repo_id)
    return {
        "recommended_order": [
            {
                "file_path": item.file_path,
                "title": item.title,
                "description": item.description,
                "difficulty": item.difficulty,
                "order": item.order,
                "key_symbols": item.key_symbols,
                "dependencies": item.dependencies,
            }
            for item in path.recommended_order
        ],
        "entry_points": path.entry_points,
        "key_concepts": path.key_concepts,
        "difficulty_levels": path.difficulty_levels,
    }


@router.get("/repos/{repo_id}/learning-path/{module_id}")
def repo_module_learning_path(repo_id: str, module_id: str):
    """获取模块内学习路径"""
    return get_module_learning_path(repo_id, module_id)


@router.get("/repos/{repo_id}/entry-points")
def repo_entry_points(repo_id: str):
    """获取项目入口点"""
    return {"entry_points": find_entry_points(repo_id)}


# ============== MCP Server 生成 API ==============

@router.get("/repos/{repo_id}/mcp/tools")
def repo_mcp_tools(repo_id: str):
    """获取 MCP 工具列表"""
    return {"tools": get_mcp_tools_list()}


@router.get("/repos/{repo_id}/mcp/server-code")
def repo_mcp_server_code(repo_id: str):
    """获取 MCP Server Python 代码"""
    code = generate_mcp_server_code(repo_id)
    return {"code": code, "filename": f"mcp_server_{repo_id}.py"}


@router.get("/repos/{repo_id}/mcp/cursor-config")
def repo_mcp_cursor_config(repo_id: str):
    """获取 Cursor MCP 配置（SSE 远程连接模式）"""
    # 获取或分配端口
    status = get_mcp_status(repo_id)
    port = status.get("port") or 9100
    config = generate_cursor_mcp_config(repo_id, port=port, host="localhost")
    return {"config": config}


@router.get("/repos/{repo_id}/mcp/claude-config")
def repo_mcp_claude_config(repo_id: str):
    """获取 Claude Desktop MCP 配置（SSE 远程连接模式）"""
    status = get_mcp_status(repo_id)
    port = status.get("port") or 9100
    config = generate_claude_desktop_config(repo_id, port=port, host="localhost")
    return {"config": config}


@router.post("/repos/{repo_id}/mcp/generate")
def repo_mcp_generate(repo_id: str, force: bool = False):
    """
    生成并保存 MCP Server 文件（SSE 模式）
    
    返回所有生成文件的路径
    """
    from pathlib import Path as _Path
    # routes.py -> api -> app -> backend, 所以 parents[2] 是 backend 目录
    mcp_dir = _Path(__file__).resolve().parents[2] / "workspace" / "mcp"
    server_file = mcp_dir / f"mcp_server_{repo_id}.py"
    
    # 只在文件不存在、强制刷新或缺少新工具时才重新生成，避免触发热重载
    needs_refresh = False
    if server_file.exists():
        try:
            content = server_file.read_text(encoding="utf-8", errors="ignore")
            if "search_in_file" not in content or "get_file_chunk" not in content:
                needs_refresh = True
        except Exception:
            needs_refresh = True
    if force or not server_file.exists() or needs_refresh:
        files = save_mcp_server(repo_id)
        return {
            "status": "success",
            "files": files,
            "sse_url": files.get("sse_url"),
            "port": files.get("port"),
            "message": "MCP Server 文件已生成（SSE 模式），请点击启动按钮开启服务"
        }
    
    # 文件已存在，返回现有信息
    status = get_mcp_status(repo_id)
    port = status.get("port") or 9100
    return {
        "status": "exists",
        "files": {"server_file": str(server_file)},
        "sse_url": f"http://localhost:{port}/sse",
        "port": port,
        "message": "MCP Server 文件已存在"
    }


@router.get("/repos/{repo_id}/mcp/status")
def repo_mcp_status(repo_id: str):
    """获取 MCP 服务运行状态"""
    return get_mcp_status(repo_id)


@router.post("/repos/{repo_id}/mcp/start")
def repo_mcp_start(repo_id: str, payload: dict = Body(default=None)):
    """启动 MCP 服务"""
    api_base = payload.get("api_base") if isinstance(payload, dict) else None
    return start_mcp_server(repo_id, api_base=api_base)


@router.post("/repos/{repo_id}/mcp/stop")
def repo_mcp_stop(repo_id: str):
    """停止 MCP 服务"""
    return stop_mcp_server(repo_id)


# ============== 对话历史 API ==============

from app.services.conversation import (
    create_conversation,
    get_conversation,
    list_conversations,
    add_message,
    delete_conversation,
    clear_conversation,
    get_context_messages,
)


@router.get("/repos/{repo_id}/conversations")
def repo_list_conversations(repo_id: str, limit: int = Query(50, description="最大返回数量")):
    """列出仓库的所有对话"""
    conversations = list_conversations(repo_id, limit)
    return {"conversations": conversations}


@router.post("/repos/{repo_id}/conversations")
def repo_create_conversation(repo_id: str, title: Optional[str] = None):
    """创建新对话"""
    conv = create_conversation(repo_id, title)
    return conv.to_dict()


@router.get("/repos/{repo_id}/conversations/{conversation_id}")
def repo_get_conversation(repo_id: str, conversation_id: str):
    """获取对话详情"""
    conv = get_conversation(conversation_id)
    if not conv or conv.repo_id != repo_id:
        raise HTTPException(status_code=404, detail="conversation not found")
    return conv.to_dict()


@router.delete("/repos/{repo_id}/conversations/{conversation_id}")
def repo_delete_conversation(repo_id: str, conversation_id: str):
    """删除对话"""
    conv = get_conversation(conversation_id)
    if not conv or conv.repo_id != repo_id:
        raise HTTPException(status_code=404, detail="conversation not found")
    delete_conversation(conversation_id)
    return {"message": "对话已删除"}


@router.post("/repos/{repo_id}/conversations/{conversation_id}/clear")
def repo_clear_conversation(repo_id: str, conversation_id: str):
    """清空对话消息"""
    conv = get_conversation(conversation_id)
    if not conv or conv.repo_id != repo_id:
        raise HTTPException(status_code=404, detail="conversation not found")
    clear_conversation(conversation_id)
    return {"message": "对话已清空"}


@router.post("/repos/{repo_id}/chat")
def repo_chat(
    repo_id: str,
    message: str = Body(..., embed=True),
    conversation_id: Optional[str] = Body(None, embed=True),
    model: Optional[dict] = Body(None, embed=True),
):
    """
    带历史的对话接口
    
    如果提供 conversation_id，将使用历史上下文；
    否则创建新对话。
    """
    # 获取或创建对话
    if conversation_id:
        conv = get_conversation(conversation_id)
        if not conv or conv.repo_id != repo_id:
            raise HTTPException(status_code=404, detail="conversation not found")
    else:
        conv = create_conversation(repo_id)
        conversation_id = conv.id
    
    # 添加用户消息
    add_message(conversation_id, "user", message)
    
    # 获取历史上下文
    context_messages = get_context_messages(conversation_id, max_messages=10, max_tokens=4000)
    
    # 搜索相关内容
    hits = search_index(repo_id, message, 5)
    evidence = []
    citations = []
    for hit in hits:
        evidence.append(hit.chunk.text)
        citations.extend([c.__dict__ for c in hit.chunk.citations])
    
    # 构建系统提示
    system_prompt = (
        "你是一个代码库分析助手。使用提供的证据回答问题。"
        "用中文简洁回答，只陈述可验证的事实。"
    )
    
    # 构建消息列表
    llm_messages = [LLMMessage(role="system", content=system_prompt)]
    
    # 添加历史消息（排除最后一条刚添加的用户消息）
    for ctx_msg in context_messages[:-1]:
        llm_messages.append(LLMMessage(role=ctx_msg["role"], content=ctx_msg["content"]))
    
    # 添加当前问题和证据
    user_prompt = "\n\n".join(["证据:", *evidence, "问题:", message]) if evidence else message
    llm_messages.append(LLMMessage(role="user", content=user_prompt))
    
    # 调用 LLM
    effective_model = get_effective_llm_config(model)
    answer, usage = chat_completion_with_usage(llm_messages, effective_model)
    
    # 记录 token 使用
    record_token_usage(
        repo_id,
        kind="llm",
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        is_estimated=usage.get("is_estimated", True),
        source="repo_chat",
    )
    
    # 添加助手消息
    add_message(conversation_id, "assistant", answer, citations=citations)
    
    return {
        "answer": answer,
        "citations": citations,
        "conversation_id": conversation_id,
    }


@router.post("/repos/{repo_id}/chat/stream")
def repo_chat_stream(
    repo_id: str,
    message: str = Body(..., embed=True),
    conversation_id: Optional[str] = Body(None, embed=True),
    model: Optional[dict] = Body(None, embed=True),
    search_type: str = Body("hybrid", embed=True),
):
    """
    带历史的流式对话接口
    
    Args:
        search_type: 搜索类型 (hybrid/semantic/keyword)
    """
    # 获取或创建对话
    if conversation_id:
        conv = get_conversation(conversation_id)
        if not conv or conv.repo_id != repo_id:
            raise HTTPException(status_code=404, detail="conversation not found")
    else:
        conv = create_conversation(repo_id)
        conversation_id = conv.id
    
    # 添加用户消息
    add_message(conversation_id, "user", message)
    
    # 获取历史上下文
    context_messages = get_context_messages(conversation_id, max_messages=10, max_tokens=4000)
    
    # 使用混合搜索
    if search_type == "keyword":
        hits = keyword_search(repo_id, message, 5)
    elif search_type == "semantic":
        hits = search_index(repo_id, message, 5)
    else:  # hybrid
        hits = hybrid_search(repo_id, message, 5)
    
    def generate():
        evidence = []
        citations = []
        for hit in hits:
            evidence.append(hit.chunk.text)
            citations.extend([c.__dict__ for c in hit.chunk.citations])
        
        # 发送 conversation_id 和 citations
        yield f"data: {json.dumps({'type': 'meta', 'conversation_id': conversation_id})}\n\n"
        yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
        
        # 构建消息
        system_prompt = (
            "你是一个代码库分析助手。使用提供的证据回答问题。"
            "用中文简洁回答，只陈述可验证的事实。"
        )
        
        llm_messages = [LLMMessage(role="system", content=system_prompt)]
        for ctx_msg in context_messages[:-1]:
            llm_messages.append(LLMMessage(role=ctx_msg["role"], content=ctx_msg["content"]))
        
        user_prompt = "\n\n".join(["证据:", *evidence, "问题:", message]) if evidence else message
        llm_messages.append(LLMMessage(role="user", content=user_prompt))
        
        # 流式生成
        full_content = ""
        full_thinking = ""
        stream_usage = None
        
        try:
            effective_model = get_effective_llm_config(model)
            for chunk in chat_completion_stream(
                llm_messages,
                effective_model,
                enable_thinking=True,
            ):
                if chunk["type"] == "usage":
                    stream_usage = chunk.get("usage") or {}
                    continue
                if chunk["type"] == "thinking":
                    full_thinking += chunk["text"]
                    yield f"data: {json.dumps({'type': 'thinking', 'content': chunk['text']})}\n\n"
                else:
                    full_content += chunk["text"]
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk['text']})}\n\n"
            
            # 保存助手消息
            add_message(
                conversation_id, 
                "assistant", 
                full_content,
                thinking=full_thinking if full_thinking else None,
                citations=citations if citations else None,
            )
            
            if stream_usage:
                record_token_usage(
                    repo_id,
                    kind="llm",
                    prompt_tokens=int(stream_usage.get("prompt_tokens") or 0),
                    completion_tokens=int(stream_usage.get("completion_tokens") or 0),
                    total_tokens=int(stream_usage.get("total_tokens") or 0),
                    is_estimated=False,
                    source="repo_chat_stream",
                )
            
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============== 代码解释 API ==============

@router.post("/repos/{repo_id}/explain/snippet")
def repo_explain_snippet(
    repo_id: str,
    file_path: str = Body(..., embed=True),
    line_start: int = Body(..., embed=True),
    line_end: int = Body(..., embed=True),
    model: Optional[dict] = Body(None, embed=True),
):
    """
    解释代码片段
    """
    result = explain_code_snippet(repo_id, file_path, line_start, line_end, model)
    return {
        "explanation": result.explanation,
        "summary": result.summary,
        "context": result.context,
        "related_symbols": result.related_symbols,
        "complexity": result.complexity,
    }


@router.post("/repos/{repo_id}/explain/symbol/{symbol_id}")
def repo_explain_symbol(
    repo_id: str,
    symbol_id: str,
    model: Optional[dict] = Body(None, embed=True),
):
    """
    解释符号（函数/类）
    """
    result = explain_symbol(repo_id, symbol_id, model)
    return {
        "summary": result.summary,
        "params": result.params,
        "returns": result.returns,
        "examples": result.examples,
        "complexity": result.complexity,
        "side_effects": result.side_effects,
    }


@router.post("/repos/{repo_id}/explain/file")
def repo_explain_file(
    repo_id: str,
    file_path: str = Body(..., embed=True),
    model: Optional[dict] = Body(None, embed=True),
):
    """
    解释整个文件
    """
    return explain_file(repo_id, file_path, model)
