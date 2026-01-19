"""
Learning Path Service - 学习路径推荐服务

提供：
1. 入口点分析
2. 阅读顺序推荐
3. 难度分级
4. 关键概念提取
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from collections import defaultdict

from app.services.db import (
    read_symbols_by_repo,
    read_file_edges,
    read_modules,
    read_docs,
    get_repo_root,
)
from app.services.code_browser import build_file_tree, FileNode


@dataclass
class LearningItem:
    """学习项目"""
    file_path: str
    title: str
    description: str
    difficulty: str  # beginner, intermediate, advanced
    order: int
    key_symbols: List[str]
    dependencies: List[str]


@dataclass
class LearningPath:
    """学习路径"""
    recommended_order: List[LearningItem]
    entry_points: List[Dict[str, Any]]
    key_concepts: List[str]
    difficulty_levels: Dict[str, List[str]]


def _calculate_file_complexity(symbols: List[Dict]) -> int:
    """计算文件复杂度分数"""
    score = 0
    for sym in symbols:
        kind = sym.get("kind", "")
        if kind == "class":
            score += 10
        elif kind == "function":
            score += 3
        elif kind == "method":
            score += 2
    return score


def _get_dependency_count(file_path: str, edges: List[Dict]) -> tuple[int, int]:
    """获取文件的依赖数和被依赖数"""
    incoming = 0
    outgoing = 0
    for edge in edges:
        if edge.get("dst_path") == file_path:
            incoming += 1
        if edge.get("src_path") == file_path:
            outgoing += 1
    return incoming, outgoing


def find_entry_points(repo_id: str) -> List[Dict[str, Any]]:
    """
    找出项目入口点
    
    入口点特征：
    1. 被依赖多，依赖少
    2. 包含 main 函数或 __main__
    3. 文件名包含 main, app, index, cli
    """
    symbols = read_symbols_by_repo(repo_id)
    edges = read_file_edges(repo_id)
    
    if not symbols:
        return []
    
    # 按文件分组符号
    file_symbols: Dict[str, List[Dict]] = defaultdict(list)
    for sym in symbols:
        file_symbols[sym.get("file_path", "")].append(sym)
    
    entry_points = []
    
    for file_path, syms in file_symbols.items():
        incoming, outgoing = _get_dependency_count(file_path, edges)
        
        # 计算入口点分数
        score = 0
        reasons = []
        
        # 被依赖多
        if incoming > 3:
            score += incoming * 2
            reasons.append(f"被 {incoming} 个文件依赖")
        
        # 依赖少
        if outgoing < 3:
            score += 5
            reasons.append("依赖较少")
        
        # 包含 main 函数
        for sym in syms:
            name = sym.get("name", "").lower()
            if name in ("main", "__main__", "cli", "run"):
                score += 20
                reasons.append(f"包含 {sym.get('name')} 函数")
        
        # 文件名特征
        path_lower = file_path.lower()
        if any(kw in path_lower for kw in ["main", "app", "index", "cli", "run"]):
            score += 10
            reasons.append("入口文件名")
        
        if score > 10:
            entry_points.append({
                "file_path": file_path,
                "score": score,
                "reasons": reasons,
                "symbols": [s.get("name") for s in syms[:5]],
            })
    
    # 按分数排序
    entry_points.sort(key=lambda x: x["score"], reverse=True)
    return entry_points[:10]


def generate_reading_order(repo_id: str) -> List[LearningItem]:
    """
    生成推荐阅读顺序
    
    策略：
    1. 先读入口点
    2. 按依赖关系拓扑排序
    3. 复杂度从低到高
    """
    symbols = read_symbols_by_repo(repo_id)
    edges = read_file_edges(repo_id)
    
    if not symbols:
        return []
    
    # 按文件分组
    file_symbols: Dict[str, List[Dict]] = defaultdict(list)
    for sym in symbols:
        file_symbols[sym.get("file_path", "")].append(sym)
    
    # 构建依赖图
    deps_out: Dict[str, set] = defaultdict(set)
    deps_in: Dict[str, set] = defaultdict(set)
    
    for edge in edges:
        src = edge.get("src_path", "")
        dst = edge.get("dst_path", "")
        if src and dst:
            deps_out[src].add(dst)
            deps_in[dst].add(src)
    
    # 计算每个文件的属性
    file_info = []
    for file_path, syms in file_symbols.items():
        complexity = _calculate_file_complexity(syms)
        in_count = len(deps_in.get(file_path, set()))
        out_count = len(deps_out.get(file_path, set()))
        
        # 优先级：被依赖多 + 依赖少 + 复杂度低
        priority = in_count * 3 - out_count - complexity // 5
        
        file_info.append({
            "file_path": file_path,
            "symbols": syms,
            "complexity": complexity,
            "in_count": in_count,
            "out_count": out_count,
            "priority": priority,
        })
    
    # 排序
    file_info.sort(key=lambda x: x["priority"], reverse=True)
    
    # 生成学习项
    items = []
    for idx, info in enumerate(file_info[:30]):  # 最多30个文件
        complexity = info["complexity"]
        if complexity < 15:
            difficulty = "beginner"
        elif complexity < 40:
            difficulty = "intermediate"
        else:
            difficulty = "advanced"
        
        items.append(LearningItem(
            file_path=info["file_path"],
            title=info["file_path"].split("/")[-1],
            description=f"包含 {len(info['symbols'])} 个符号",
            difficulty=difficulty,
            order=idx + 1,
            key_symbols=[s.get("name", "") for s in info["symbols"][:5]],
            dependencies=list(deps_out.get(info["file_path"], set()))[:5],
        ))
    
    return items


def extract_key_concepts(repo_id: str) -> List[str]:
    """
    提取关键概念（高频类名和函数名）
    """
    symbols = read_symbols_by_repo(repo_id)
    if not symbols:
        return []
    
    # 统计类和函数名
    name_counts: Dict[str, int] = defaultdict(int)
    for sym in symbols:
        kind = sym.get("kind", "")
        name = sym.get("name", "")
        if kind in ("class", "function") and name and not name.startswith("_"):
            name_counts[name] += 1
    
    # 按出现次数排序
    sorted_names = sorted(name_counts.items(), key=lambda x: x[1], reverse=True)
    
    # 返回前20个
    return [name for name, _ in sorted_names[:20]]


def categorize_by_difficulty(repo_id: str) -> Dict[str, List[str]]:
    """
    按难度分类文件
    """
    symbols = read_symbols_by_repo(repo_id)
    if not symbols:
        return {"beginner": [], "intermediate": [], "advanced": []}
    
    # 按文件分组
    file_symbols: Dict[str, List[Dict]] = defaultdict(list)
    for sym in symbols:
        file_symbols[sym.get("file_path", "")].append(sym)
    
    result = {"beginner": [], "intermediate": [], "advanced": []}
    
    for file_path, syms in file_symbols.items():
        complexity = _calculate_file_complexity(syms)
        
        if complexity < 15:
            result["beginner"].append(file_path)
        elif complexity < 40:
            result["intermediate"].append(file_path)
        else:
            result["advanced"].append(file_path)
    
    # 每个级别最多10个
    for key in result:
        result[key] = result[key][:10]
    
    return result


def get_learning_path(repo_id: str) -> LearningPath:
    """
    获取完整学习路径
    """
    return LearningPath(
        recommended_order=generate_reading_order(repo_id),
        entry_points=find_entry_points(repo_id),
        key_concepts=extract_key_concepts(repo_id),
        difficulty_levels=categorize_by_difficulty(repo_id),
    )


def get_module_learning_path(repo_id: str, module_id: str) -> Dict[str, Any]:
    """
    获取模块内的学习路径
    """
    docs = read_docs(repo_id)
    symbols = read_symbols_by_repo(repo_id)
    
    # 找到模块的文件
    module_files = []
    for doc in docs:
        if doc.get("module_id") == module_id:
            module_files = doc.get("files", [])
            break
    
    if not module_files:
        return {"files": [], "key_symbols": []}
    
    # 过滤模块内的符号
    module_symbols = [s for s in symbols if s.get("file_path") in module_files]
    
    # 按文件分组
    file_symbols: Dict[str, List[Dict]] = defaultdict(list)
    for sym in module_symbols:
        file_symbols[sym.get("file_path", "")].append(sym)
    
    # 排序文件
    sorted_files = sorted(
        file_symbols.items(),
        key=lambda x: _calculate_file_complexity(x[1])
    )
    
    return {
        "files": [
            {
                "path": path,
                "symbols": [s.get("name") for s in syms[:5]],
                "complexity": _calculate_file_complexity(syms),
            }
            for path, syms in sorted_files
        ],
        "key_symbols": [
            s.get("name") for s in module_symbols
            if s.get("kind") in ("class", "function") and not s.get("name", "").startswith("_")
        ][:10],
    }
