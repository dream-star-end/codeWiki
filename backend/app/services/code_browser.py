"""
Code Browser Service - 代码浏览与文件操作服务

提供：
1. 文件树构建
2. 文件内容读取（带语法高亮token）
3. 符号定位与跳转
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re
from typing import List, Optional, Dict, Any

from app.services.db import get_repo_root, read_symbols_by_file


@dataclass
class FileNode:
    """文件树节点"""
    name: str
    path: str
    is_dir: bool
    children: List["FileNode"]
    language: Optional[str] = None
    size: Optional[int] = None


@dataclass
class FileContent:
    """文件内容"""
    path: str
    content: str
    language: str
    lines: int
    size: int
    symbols: List[Dict[str, Any]]


def _detect_language(path: str) -> str:
    """根据文件扩展名检测语言"""
    ext = Path(path).suffix.lower()
    lang_map = {
        ".py": "python",
        ".java": "java",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "javascript",
        ".tsx": "typescript",
        ".vue": "vue",
        ".html": "html",
        ".css": "css",
        ".scss": "scss",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".sql": "sql",
        ".sh": "shell",
        ".bash": "shell",
        ".go": "go",
        ".rs": "rust",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
        ".rb": "ruby",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".r": "r",
        ".xml": "xml",
        ".toml": "toml",
        ".ini": "ini",
        ".env": "shell",
        ".gitignore": "gitignore",
        ".dockerfile": "dockerfile",
    }
    return lang_map.get(ext, "plaintext")


def _should_ignore(name: str) -> bool:
    """判断是否应该忽略的文件/目录"""
    ignore_patterns = {
        "__pycache__",
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        ".idea",
        ".vscode",
        ".DS_Store",
        "*.pyc",
        "*.pyo",
        "*.class",
        ".egg-info",
        "dist",
        "build",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        "__MACOSX",
        "venv",
        ".venv",
        "env",
        ".env",
    }
    return name in ignore_patterns or name.startswith(".")


def build_file_tree(
    repo_root: str,
    max_depth: int = 10,
    include_hidden: bool = False,
) -> FileNode:
    """
    构建文件树
    
    Args:
        repo_root: 仓库根目录
        max_depth: 最大深度
        include_hidden: 是否包含隐藏文件
    
    Returns:
        FileNode: 文件树根节点
    """
    root_path = Path(repo_root)
    
    def walk(path: Path, depth: int) -> Optional[FileNode]:
        if depth > max_depth:
            return None
        
        name = path.name or str(path)
        
        if not include_hidden and _should_ignore(name):
            return None
        
        if path.is_file():
            try:
                size = path.stat().st_size
            except OSError:
                size = 0
            
            return FileNode(
                name=name,
                path=str(path.relative_to(root_path)),
                is_dir=False,
                children=[],
                language=_detect_language(str(path)),
                size=size,
            )
        
        if path.is_dir():
            children = []
            try:
                for child in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    child_node = walk(child, depth + 1)
                    if child_node:
                        children.append(child_node)
            except PermissionError:
                pass
            
            return FileNode(
                name=name,
                path=str(path.relative_to(root_path)) if path != root_path else "",
                is_dir=True,
                children=children,
            )
        
        return None
    
    root_node = walk(root_path, 0)
    if root_node:
        root_node.name = root_path.name or "root"
        root_node.path = ""
    return root_node or FileNode(name="root", path="", is_dir=True, children=[])


def get_file_content(repo_id: str, file_path: str) -> Optional[FileContent]:
    """
    获取文件内容
    
    Args:
        repo_id: 仓库ID
        file_path: 相对文件路径
    
    Returns:
        FileContent: 文件内容对象
    """
    repo_root = get_repo_root(repo_id)
    if not repo_root:
        return None
    
    full_path = Path(repo_root) / file_path
    
    if not full_path.exists() or not full_path.is_file():
        return None
    
    # 安全检查：确保路径在repo_root内
    try:
        full_path.resolve().relative_to(Path(repo_root).resolve())
    except ValueError:
        return None
    
    try:
        content = full_path.read_text(encoding="utf-8", errors="replace")
        size = full_path.stat().st_size
        lines = content.count("\n") + 1
        language = _detect_language(str(full_path))
        
        # 获取文件中的符号
        symbols = read_symbols_by_file(repo_id, file_path)
        
        return FileContent(
            path=file_path,
            content=content,
            language=language,
            lines=lines,
            size=size,
            symbols=symbols,
        )
    except Exception:
        return None


def get_file_chunk(
    repo_id: str,
    file_path: str,
    offset: int = 1,
    limit: int = 200,
) -> Optional[Dict[str, Any]]:
    """
    获取文件内容分块（按行）
    
    Args:
        repo_id: 仓库ID
        file_path: 相对文件路径
        offset: 起始行（1-based）
        limit: 行数
    """
    content = get_file_content(repo_id, file_path)
    if not content:
        return None
    lines = content.content.splitlines()
    total_lines = len(lines)
    start = max(1, int(offset))
    max_limit = max(1, int(limit))
    start_idx = start - 1
    end_idx = min(total_lines, start_idx + max_limit)
    chunk_lines = lines[start_idx:end_idx] if start_idx < total_lines else []
    return {
        "path": content.path,
        "language": content.language,
        "start_line": start,
        "end_line": start + len(chunk_lines) - 1 if chunk_lines else start - 1,
        "total_lines": total_lines,
        "content": "\n".join(chunk_lines),
    }


def search_in_file(
    repo_id: str,
    file_path: str,
    query: str,
    context: int = 2,
    limit: int = 20,
    case_sensitive: bool = False,
    use_regex: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    在单文件内搜索文本（按行）
    """
    content = get_file_content(repo_id, file_path)
    if not content:
        return None
    lines = content.content.splitlines()
    total_lines = len(lines)
    results: List[Dict[str, Any]] = []
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = None
    if use_regex:
        try:
            pattern = re.compile(query, flags)
        except re.error:
            pattern = None
    for idx, line in enumerate(lines, start=1):
        matched = False
        if use_regex and pattern:
            if pattern.search(line):
                matched = True
        else:
            if (line if case_sensitive else line.lower()).find(
                query if case_sensitive else query.lower()
            ) != -1:
                matched = True
        if not matched:
            continue
        start_ctx = max(1, idx - context)
        end_ctx = min(total_lines, idx + context)
        snippet = "\n".join(lines[start_ctx - 1:end_ctx])
        results.append(
            {
                "line": idx,
                "snippet": snippet,
                "start_line": start_ctx,
                "end_line": end_ctx,
            }
        )
        if len(results) >= limit:
            break
    return {
        "path": content.path,
        "language": content.language,
        "total_lines": total_lines,
        "results": results,
    }


def get_file_tree_for_repo(repo_id: str) -> Optional[FileNode]:
    """
    获取仓库的文件树
    
    Args:
        repo_id: 仓库ID
    
    Returns:
        FileNode: 文件树根节点
    """
    repo_root = get_repo_root(repo_id)
    if not repo_root:
        return None
    
    return build_file_tree(repo_root)


def file_node_to_dict(node: FileNode) -> Dict[str, Any]:
    """将 FileNode 转换为字典"""
    result = {
        "name": node.name,
        "path": node.path,
        "is_dir": node.is_dir,
    }
    if node.is_dir:
        result["children"] = [file_node_to_dict(child) for child in node.children]
    else:
        result["language"] = node.language
        result["size"] = node.size
    return result


def search_files(repo_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """
    搜索文件
    
    Args:
        repo_id: 仓库ID
        query: 搜索查询（文件名模糊匹配）
        limit: 最大返回数量
    
    Returns:
        匹配的文件列表
    """
    repo_root = get_repo_root(repo_id)
    if not repo_root:
        return []
    
    query_lower = query.lower()
    results = []
    
    def search_tree(node: FileNode):
        if len(results) >= limit:
            return
        
        if not node.is_dir:
            if query_lower in node.name.lower() or query_lower in node.path.lower():
                results.append({
                    "name": node.name,
                    "path": node.path,
                    "language": node.language,
                    "size": node.size,
                })
        else:
            for child in node.children:
                search_tree(child)
    
    tree = build_file_tree(repo_root)
    search_tree(tree)
    
    return results
