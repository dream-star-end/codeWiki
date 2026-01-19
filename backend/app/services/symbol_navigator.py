"""
Symbol Navigator Service - 符号导航服务

提供：
1. 符号定义查找
2. 符号引用查找
3. 符号搜索
4. 调用链分析
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from app.services.db import (
    read_symbol_by_id,
    read_symbols_by_repo,
    read_symbol_edges,
    read_symbols_by_file,
)


@dataclass
class SymbolLocation:
    """符号位置"""
    symbol_id: str
    file_path: str
    line_start: int
    line_end: int
    name: str
    kind: str
    signature: Optional[str] = None


@dataclass
class SymbolReference:
    """符号引用"""
    file_path: str
    line: int
    context: str  # 引用所在的代码行
    edge_type: str  # call, import, inherit, use


def get_symbol_definition(repo_id: str, symbol_id: str) -> Optional[SymbolLocation]:
    """
    获取符号定义位置
    
    Args:
        repo_id: 仓库ID
        symbol_id: 符号ID
    
    Returns:
        SymbolLocation: 符号定义位置
    """
    symbol = read_symbol_by_id(repo_id, symbol_id)
    if not symbol:
        return None
    
    return SymbolLocation(
        symbol_id=symbol_id,
        file_path=symbol.get("file_path", ""),
        line_start=symbol.get("line_start", 0),
        line_end=symbol.get("line_end", 0),
        name=symbol.get("name", ""),
        kind=symbol.get("kind", ""),
        signature=symbol.get("signature"),
    )


def get_symbol_references(repo_id: str, symbol_id: str) -> List[SymbolReference]:
    """
    获取符号的所有引用
    
    Args:
        repo_id: 仓库ID
        symbol_id: 符号ID
    
    Returns:
        List[SymbolReference]: 引用列表
    """
    edges = read_symbol_edges(repo_id)
    if not edges:
        return []
    
    references = []
    for edge in edges:
        # 查找指向该符号的边（被引用）
        if edge.get("dst_symbol_id") == symbol_id:
            src_symbol = read_symbol_by_id(repo_id, edge.get("src_symbol_id", ""))
            if src_symbol:
                references.append(SymbolReference(
                    file_path=src_symbol.get("file_path", ""),
                    line=src_symbol.get("line_start", 0),
                    context=src_symbol.get("name", ""),
                    edge_type=edge.get("edge_type", "use"),
                ))
    
    return references


def search_symbols(
    repo_id: str,
    query: str,
    kind: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    搜索符号
    
    Args:
        repo_id: 仓库ID
        query: 搜索查询（符号名模糊匹配）
        kind: 符号类型过滤（class, function, method）
        limit: 最大返回数量
    
    Returns:
        匹配的符号列表
    """
    symbols = read_symbols_by_repo(repo_id)
    if not symbols:
        return []
    
    query_lower = query.lower()
    results = []
    
    for symbol in symbols:
        if len(results) >= limit:
            break
        
        name = symbol.get("name", "")
        sym_kind = symbol.get("kind", "")
        
        # 名称匹配
        if query_lower not in name.lower():
            continue
        
        # 类型过滤
        if kind and sym_kind != kind:
            continue
        
        results.append({
            "id": symbol.get("id", ""),
            "name": name,
            "kind": sym_kind,
            "file_path": symbol.get("file_path", ""),
            "line_start": symbol.get("line_start", 0),
            "line_end": symbol.get("line_end", 0),
            "signature": symbol.get("signature"),
            "container": symbol.get("container"),
        })
    
    return results


def get_symbol_callers(repo_id: str, symbol_id: str) -> List[Dict[str, Any]]:
    """
    获取调用该符号的所有符号（调用者）
    
    Args:
        repo_id: 仓库ID
        symbol_id: 符号ID
    
    Returns:
        调用者列表
    """
    edges = read_symbol_edges(repo_id)
    if not edges:
        return []
    
    callers = []
    for edge in edges:
        if edge.get("dst_symbol_id") == symbol_id and edge.get("edge_type") == "call":
            caller_id = edge.get("src_symbol_id", "")
            caller = read_symbol_by_id(repo_id, caller_id)
            if caller:
                callers.append({
                    "id": caller_id,
                    "name": caller.get("name", ""),
                    "kind": caller.get("kind", ""),
                    "file_path": caller.get("file_path", ""),
                    "line_start": caller.get("line_start", 0),
                })
    
    return callers


def get_symbol_callees(repo_id: str, symbol_id: str) -> List[Dict[str, Any]]:
    """
    获取该符号调用的所有符号（被调用者）
    
    Args:
        repo_id: 仓库ID
        symbol_id: 符号ID
    
    Returns:
        被调用者列表
    """
    edges = read_symbol_edges(repo_id)
    if not edges:
        return []
    
    callees = []
    for edge in edges:
        if edge.get("src_symbol_id") == symbol_id and edge.get("edge_type") == "call":
            callee_id = edge.get("dst_symbol_id", "")
            callee = read_symbol_by_id(repo_id, callee_id)
            if callee:
                callees.append({
                    "id": callee_id,
                    "name": callee.get("name", ""),
                    "kind": callee.get("kind", ""),
                    "file_path": callee.get("file_path", ""),
                    "line_start": callee.get("line_start", 0),
                })
    
    return callees


def get_call_graph(repo_id: str, symbol_id: str, depth: int = 2) -> Dict[str, Any]:
    """
    获取符号的调用图（向上和向下）
    
    Args:
        repo_id: 仓库ID
        symbol_id: 符号ID
        depth: 遍历深度
    
    Returns:
        调用图数据
    """
    visited = set()
    
    def get_upstream(sid: str, current_depth: int) -> Dict[str, Any]:
        if current_depth > depth or sid in visited:
            return {}
        visited.add(sid)
        
        symbol = read_symbol_by_id(repo_id, sid)
        if not symbol:
            return {}
        
        callers = get_symbol_callers(repo_id, sid)
        upstream = []
        for caller in callers:
            upstream.append(get_upstream(caller["id"], current_depth + 1))
        
        return {
            "id": sid,
            "name": symbol.get("name", ""),
            "kind": symbol.get("kind", ""),
            "file_path": symbol.get("file_path", ""),
            "callers": [u for u in upstream if u],
        }
    
    visited.clear()
    
    def get_downstream(sid: str, current_depth: int) -> Dict[str, Any]:
        if current_depth > depth or sid in visited:
            return {}
        visited.add(sid)
        
        symbol = read_symbol_by_id(repo_id, sid)
        if not symbol:
            return {}
        
        callees = get_symbol_callees(repo_id, sid)
        downstream = []
        for callee in callees:
            downstream.append(get_downstream(callee["id"], current_depth + 1))
        
        return {
            "id": sid,
            "name": symbol.get("name", ""),
            "kind": symbol.get("kind", ""),
            "file_path": symbol.get("file_path", ""),
            "callees": [d for d in downstream if d],
        }
    
    upstream = get_upstream(symbol_id, 0)
    visited.clear()
    downstream = get_downstream(symbol_id, 0)
    
    return {
        "symbol_id": symbol_id,
        "upstream": upstream.get("callers", []),
        "downstream": downstream.get("callees", []),
    }


def get_file_outline(repo_id: str, file_path: str) -> List[Dict[str, Any]]:
    """
    获取文件大纲（符号层级结构）
    
    Args:
        repo_id: 仓库ID
        file_path: 文件路径
    
    Returns:
        符号大纲列表
    """
    symbols = read_symbols_by_file(repo_id, file_path)
    if not symbols:
        return []
    
    # 按行号排序
    symbols.sort(key=lambda s: s.get("line_start", 0))
    
    # 构建层级结构
    outline = []
    class_stack = []
    
    for symbol in symbols:
        kind = symbol.get("kind", "")
        container = symbol.get("container")
        
        item = {
            "id": symbol.get("id", ""),
            "name": symbol.get("name", ""),
            "kind": kind,
            "line_start": symbol.get("line_start", 0),
            "line_end": symbol.get("line_end", 0),
            "signature": symbol.get("signature"),
            "children": [],
        }
        
        if kind == "class":
            outline.append(item)
            class_stack = [item]
        elif kind in ("method", "function"):
            if container and class_stack:
                # 作为类的方法
                class_stack[-1]["children"].append(item)
            else:
                # 顶级函数
                outline.append(item)
        else:
            outline.append(item)
    
    return outline
