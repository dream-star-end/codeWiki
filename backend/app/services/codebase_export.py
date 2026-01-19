"""
Codebase Export Service - 代码库上下文导出服务

提供：
1. 导出为 Cursor/IDE 格式
2. 导出为 Markdown 格式
3. 智能上下文生成
4. Token 计算与裁剪
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Literal

from app.services.db import (
    get_repo_root,
    read_modules,
    read_docs,
    read_summary,
    read_symbols_by_repo,
)
from app.services.code_browser import get_file_content, build_file_tree, FileNode
from app.services.faiss_index import search_index


@dataclass
class ExportConfig:
    """导出配置"""
    format: Literal["cursor", "markdown", "json", "xml"] = "cursor"
    scope: Literal["full", "module", "files"] = "full"
    module_ids: Optional[List[str]] = None
    file_paths: Optional[List[str]] = None
    include_deps: bool = True
    max_tokens: int = 100000
    include_summary: bool = True


@dataclass
class ExportResult:
    """导出结果"""
    content: str
    token_count: int
    files_included: List[str]
    format: str


def _estimate_tokens(text: str) -> int:
    """
    估算 token 数量（简单估算，约4字符=1token）
    实际使用时可以用 tiktoken 更精确
    """
    return len(text) // 4


def _collect_files(repo_id: str, config: ExportConfig) -> List[str]:
    """收集需要导出的文件列表"""
    repo_root = get_repo_root(repo_id)
    if not repo_root:
        return []
    
    if config.file_paths:
        return config.file_paths
    
    if config.scope == "module" and config.module_ids:
        docs = read_docs(repo_id)
        files = []
        for doc in docs:
            if doc.get("module_id") in config.module_ids:
                files.extend(doc.get("files", []))
        return files
    
    # 全量导出 - 收集所有代码文件
    tree = build_file_tree(repo_root)
    files = []
    
    def collect(node: FileNode):
        if not node.is_dir:
            # 只收集代码文件
            if node.language not in ("plaintext", "markdown", "json", "yaml", "xml"):
                files.append(node.path)
        else:
            for child in node.children:
                collect(child)
    
    collect(tree)
    return files


def export_as_cursor(repo_id: str, config: ExportConfig) -> ExportResult:
    """
    导出为 Cursor/IDE 格式
    
    格式：
    <codebase>
    <file path="path/to/file.py">
    ... code ...
    </file>
    </codebase>
    """
    files = _collect_files(repo_id, config)
    
    lines = ["<codebase>"]
    included_files = []
    total_tokens = 0
    
    # 添加摘要
    if config.include_summary:
        summary = read_summary(repo_id)
        if summary:
            lines.append("<summary>")
            lines.append(f"Languages: {', '.join(summary.get('languages', []))}")
            lines.append("</summary>")
            lines.append("")
    
    for file_path in files:
        content = get_file_content(repo_id, file_path)
        if not content:
            continue
        
        file_tokens = _estimate_tokens(content.content)
        if total_tokens + file_tokens > config.max_tokens:
            break
        
        lines.append(f'<file path="{file_path}">')
        lines.append(content.content)
        lines.append("</file>")
        lines.append("")
        
        included_files.append(file_path)
        total_tokens += file_tokens
    
    lines.append("</codebase>")
    
    result_content = "\n".join(lines)
    
    return ExportResult(
        content=result_content,
        token_count=_estimate_tokens(result_content),
        files_included=included_files,
        format="cursor",
    )


def export_as_markdown(repo_id: str, config: ExportConfig) -> ExportResult:
    """
    导出为 Markdown 格式
    
    格式：
    # Project: {name}
    
    ## Overview
    ...
    
    ## Files
    ### path/to/file.py
    ```python
    ...
    ```
    """
    files = _collect_files(repo_id, config)
    
    lines = []
    included_files = []
    total_tokens = 0
    
    # 标题和摘要
    summary = read_summary(repo_id)
    if summary:
        lines.append(f"# Codebase Analysis: {repo_id}")
        lines.append("")
        lines.append("## Overview")
        lines.append("")
        languages = summary.get("languages", [])
        if languages:
            lines.append(f"**Languages**: {', '.join(languages)}")
        lines.append("")
    
    # 模块结构
    modules = read_modules(repo_id)
    if modules:
        lines.append("## Modules")
        lines.append("")
        for mod in modules[:10]:  # 最多显示10个模块
            lines.append(f"- **{mod.get('name', mod.get('path_prefix', 'unknown'))}**")
            lines.append(f"  - Path: `{mod.get('path_prefix', '')}`")
        lines.append("")
    
    # 文件内容
    lines.append("## Source Files")
    lines.append("")
    
    for file_path in files:
        content = get_file_content(repo_id, file_path)
        if not content:
            continue
        
        file_tokens = _estimate_tokens(content.content)
        if total_tokens + file_tokens > config.max_tokens:
            break
        
        lines.append(f"### {file_path}")
        lines.append("")
        lines.append(f"```{content.language}")
        lines.append(content.content)
        lines.append("```")
        lines.append("")
        
        included_files.append(file_path)
        total_tokens += file_tokens
    
    result_content = "\n".join(lines)
    
    return ExportResult(
        content=result_content,
        token_count=_estimate_tokens(result_content),
        files_included=included_files,
        format="markdown",
    )


def export_as_json(repo_id: str, config: ExportConfig) -> ExportResult:
    """
    导出为 JSON 格式
    """
    files = _collect_files(repo_id, config)
    
    data = {
        "repo_id": repo_id,
        "summary": read_summary(repo_id),
        "modules": read_modules(repo_id),
        "files": [],
    }
    
    included_files = []
    total_tokens = 0
    
    for file_path in files:
        content = get_file_content(repo_id, file_path)
        if not content:
            continue
        
        file_tokens = _estimate_tokens(content.content)
        if total_tokens + file_tokens > config.max_tokens:
            break
        
        data["files"].append({
            "path": file_path,
            "language": content.language,
            "content": content.content,
            "lines": content.lines,
            "symbols": content.symbols,
        })
        
        included_files.append(file_path)
        total_tokens += file_tokens
    
    result_content = json.dumps(data, indent=2, ensure_ascii=False)
    
    return ExportResult(
        content=result_content,
        token_count=_estimate_tokens(result_content),
        files_included=included_files,
        format="json",
    )


def generate_smart_context(
    repo_id: str,
    query: str,
    max_tokens: int = 8000,
) -> ExportResult:
    """
    根据用户查询智能生成上下文
    
    使用语义搜索找到最相关的代码片段
    """
    # 使用 FAISS 搜索相关内容
    hits = search_index(repo_id, query, top_k=20)
    
    lines = []
    included_files = set()
    total_tokens = 0
    
    lines.append(f"# Context for: {query}")
    lines.append("")
    lines.append("## Relevant Code Sections")
    lines.append("")
    
    for hit in hits:
        chunk_tokens = _estimate_tokens(hit.chunk.text)
        if total_tokens + chunk_tokens > max_tokens:
            break
        
        # 获取文件路径
        citations = hit.chunk.citations
        file_path = citations[0].file_path if citations else "unknown"
        
        lines.append(f"### From: {file_path}")
        lines.append(f"*Relevance Score: {hit.score:.3f}*")
        lines.append("")
        lines.append("```")
        lines.append(hit.chunk.text)
        lines.append("```")
        lines.append("")
        
        included_files.add(file_path)
        total_tokens += chunk_tokens
    
    result_content = "\n".join(lines)
    
    return ExportResult(
        content=result_content,
        token_count=_estimate_tokens(result_content),
        files_included=list(included_files),
        format="smart_context",
    )


def export_codebase(repo_id: str, config: ExportConfig) -> ExportResult:
    """
    主导出函数
    """
    if config.format == "cursor":
        return export_as_cursor(repo_id, config)
    elif config.format == "markdown":
        return export_as_markdown(repo_id, config)
    elif config.format == "json":
        return export_as_json(repo_id, config)
    else:
        return export_as_cursor(repo_id, config)


def get_codebase_stats(repo_id: str) -> Dict[str, Any]:
    """
    获取代码库统计信息
    """
    repo_root = get_repo_root(repo_id)
    if not repo_root:
        return {}
    
    tree = build_file_tree(repo_root)
    
    total_files = 0
    total_size = 0
    languages = {}
    
    def count(node: FileNode):
        nonlocal total_files, total_size
        if not node.is_dir:
            total_files += 1
            total_size += node.size or 0
            lang = node.language or "unknown"
            languages[lang] = languages.get(lang, 0) + 1
        else:
            for child in node.children:
                count(child)
    
    count(tree)
    
    symbols = read_symbols_by_repo(repo_id)
    modules = read_modules(repo_id)
    
    return {
        "total_files": total_files,
        "total_size": total_size,
        "total_symbols": len(symbols) if symbols else 0,
        "total_modules": len(modules) if modules else 0,
        "languages": languages,
        "estimated_tokens": total_size // 4,
    }
