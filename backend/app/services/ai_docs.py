from __future__ import annotations

import json
from typing import Dict, List, Optional

from app.services.llm_client import chat_completion_with_usage, LLMMessage
from app.services.db import read_docs, read_modules, insert_ai_doc, read_ai_doc, record_token_usage
from app.models.schemas import ModelConfig


def _repo_summary_prompt(modules: List[Dict], docs: List[Dict]) -> List[LLMMessage]:
    module_names = [m.get("path_prefix") or m.get("name") for m in modules][:20]
    overview = {
        "modules": module_names,
        "docs": docs[:10],
    }
    system = (
        "你是代码仓文档助手。请基于提供的数据直接输出仓库级总结，"
        "包括架构、关键模块、使用方式。必须简洁、分段、要点式。"
        "不要提问、不要要求用户提供更多信息。"
    )
    user = f"Repo data:\n{json.dumps(overview, ensure_ascii=True, indent=2)}"
    return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]


def _module_prompt(doc: Dict) -> List[LLMMessage]:
    system = (
        "你是代码仓文档助手。请基于提供的数据输出模块级说明，"
        "包含职责、关键符号、入口点。必须简洁、分段、要点式。"
        "不要提问、不要要求用户提供更多信息。"
    )
    user = f"Module data:\n{json.dumps(doc, ensure_ascii=True, indent=2)}"
    return [LLMMessage(role="system", content=system), LLMMessage(role="user", content=user)]


def generate_repo_ai_summary(repo_id: str, model: ModelConfig) -> str:
    cached = read_ai_doc(repo_id, doc_type="ai_repo", module_id=None)
    if cached:
        return cached
    modules = read_modules(repo_id)
    docs = read_docs(repo_id)
    if not modules and not docs:
        return "暂无可用分析数据，请先完成仓库分析。"
    content, usage = chat_completion_with_usage(_repo_summary_prompt(modules, docs), model)
    record_token_usage(
        repo_id,
        kind="llm",
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        is_estimated=usage.get("is_estimated", True),
        source="ai_summary",
    )
    insert_ai_doc(repo_id, module_id=None, doc_type="ai_repo", content=content)
    return content


def generate_module_ai_docs(repo_id: str, model: ModelConfig, max_modules: int) -> List[Dict]:
    docs = read_docs(repo_id)
    if not docs:
        return []
    results: List[Dict] = []
    for doc in docs[:max_modules]:
        module_id = doc.get("module_id")
        cached = read_ai_doc(repo_id, doc_type="ai_module", module_id=module_id)
        if cached:
            results.append({"module_id": module_id, "content": cached})
            continue
        content, usage = chat_completion_with_usage(_module_prompt(doc), model)
        record_token_usage(
            repo_id,
            kind="llm",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            is_estimated=usage.get("is_estimated", True),
            source="ai_module",
        )
        insert_ai_doc(repo_id, module_id=module_id, doc_type="ai_module", content=content)
        results.append({"module_id": module_id, "content": content})
    return results
