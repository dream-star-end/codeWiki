# Copyright (c) Meta Platforms, Inc. and affiliates
"""
Topological sorting utilities for dependency graphs with cycle handling.

This module provides functions to perform topological sorting on a dependency graph,
including detection and resolution of dependency cycles.
"""

import logging
from typing import Dict, List, Set, Any
from collections import deque

from codewiki.src.be.dependency_analyzer.models.core import Node

logger = logging.getLogger(__name__)


def detect_cycles(graph: Dict[str, Set[str]]) -> List[List[str]]:
    """
    Detect cycles in a dependency graph using Tarjan's algorithm to find
    strongly connected components.
    
    Args:
        graph: A dependency graph represented as adjacency lists
               (node -> set of dependencies)
    
    Returns:
        A list of lists, where each inner list contains the nodes in a cycle
    """
    # Implementation of Tarjan's algorithm
    index_counter = [0]
    index = {}  # node -> index
    lowlink = {}  # node -> lowlink value
    onstack = set()  # nodes currently on the stack
    stack = []  # stack of nodes
    result = []  # list of cycles (strongly connected components)
    
    def strongconnect(node):
        # Set the depth index for node
        index[node] = index_counter[0]
        lowlink[node] = index_counter[0]
        index_counter[0] += 1
        stack.append(node)
        onstack.add(node)
        
        # Consider successors
        for successor in graph.get(node, set()):
            if successor not in index:
                # Successor has not yet been visited; recurse on it
                strongconnect(successor)
                lowlink[node] = min(lowlink[node], lowlink[successor])
            elif successor in onstack:
                # Successor is on the stack and hence in the current SCC
                lowlink[node] = min(lowlink[node], index[successor])
        
        # If node is a root node, pop the stack and generate an SCC
        if lowlink[node] == index[node]:
            # Start a new strongly connected component
            scc = []
            while True:
                successor = stack.pop()
                onstack.remove(successor)
                scc.append(successor)
                if successor == node:
                    break
            
            # Only include SCCs with more than one node (actual cycles)
            if len(scc) > 1:
                result.append(scc)
    
    # Visit each node
    for node in graph:
        if node not in index:
            strongconnect(node)
    
    return result

def resolve_cycles(graph: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """
    Resolve cycles in a dependency graph by identifying strongly connected
    components and breaking cycles.
    
    Args:
        graph: A dependency graph represented as adjacency lists
               (node -> set of dependencies)
    
    Returns:
        A new acyclic graph with the same nodes but with cycles broken
    """
    # Detect cycles (SCCs)
    cycles = detect_cycles(graph)
    
    if not cycles:
        logger.debug("No cycles detected in the dependency graph")
        return graph
    
    logger.debug(f"Detected {len(cycles)} cycles in the dependency graph")
    
    # Create a copy of the graph to modify
    new_graph = {node: deps.copy() for node, deps in graph.items()}
    
    # Process each cycle
    for i, cycle in enumerate(cycles):
        logger.debug(f"Cycle {i+1}: {' -> '.join(cycle)}")
        
        # Strategy: Break the cycle by removing the "weakest" dependency
        # Here, we just arbitrarily remove the last edge to make the graph acyclic
        # In a real-world scenario, you might use heuristics to determine which edge to break
        # For example, removing edges between different modules before edges within the same module
        for j in range(len(cycle) - 1):
            current = cycle[j]
            next_node = cycle[j + 1]
            
            if next_node in new_graph[current]:
                logger.debug(f"Breaking cycle by removing dependency: {current} -> {next_node}")
                new_graph[current].remove(next_node)
                break
    
    return new_graph

def topological_sort(graph: Dict[str, Set[str]]) -> List[str]:
    """
    Perform a topological sort on a dependency graph.
    
    Args:
        graph: A dependency graph represented as adjacency lists
               (node -> set of dependencies)
    
    Returns:
        A list of nodes in topological order (dependencies first)
    """
    # First, check for and resolve cycles
    acyclic_graph = resolve_cycles(graph)
    
    # Initialize in-degree counter for all nodes
    in_degree = {node: 0 for node in acyclic_graph}
    
    # Count in-degrees
    for node, dependencies in acyclic_graph.items():
        for dep in dependencies:
            if dep in in_degree:
                in_degree[dep] += 1
    
    # Queue of nodes with no dependencies (in-degree of 0)
    queue = deque([node for node, degree in in_degree.items() if degree == 0])
    
    # Result list to store the topological order
    result = []
    
    # Process nodes in topological order
    while queue:
        node = queue.popleft()
        result.append(node)
        
        # Reduce in-degree for each node that depends on the current node
        for dependent, deps in acyclic_graph.items():
            if node in deps:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
    
    # Check if the sort was successful (all nodes included)
    if len(result) != len(acyclic_graph):
        logger.warning("Topological sort failed: graph has cycles that weren't resolved")
        # Return all nodes in some order to avoid breaking the process
        return list(acyclic_graph.keys())
    
    # Reverse the result to get dependencies first
    return result[::-1]

def dependency_first_dfs(graph: Dict[str, Set[str]]) -> List[str]:
    """
    Perform a depth-first traversal of the dependency graph, starting from root nodes
    that have no dependencies.
    
    The graph uses natural dependency direction:
    - If A depends on B, the graph has an edge A → B
    - This means an edge from X to Y represents "X depends on Y"
    - Root nodes (nodes with no incoming edges/dependencies) are processed first,
      followed by nodes that depend on them
    
    Args:
        graph: A dependency graph with natural direction (A→B if A depends on B)
    
    Returns:
        A list of nodes in an order where dependencies come before their dependents
    """
    # First, resolve cycles to ensure we have a DAG
    acyclic_graph = resolve_cycles(graph)
    
    # Find root nodes (nodes with no dependencies)
    root_nodes = []
    # Create a reverse graph to easily check if a node has incoming edges
    has_incoming_edge = {node: False for node in acyclic_graph}
    
    for node, deps in acyclic_graph.items():
        for dep in deps:
            has_incoming_edge[dep] = True
    
    # Nodes with no incoming edges are root nodes
    for node in acyclic_graph:
        if not has_incoming_edge.get(node, False) and node in acyclic_graph:
            root_nodes.append(node)
    
    if not root_nodes:
        logger.warning("No root nodes found in the graph, using arbitrary starting point")
        root_nodes = list(acyclic_graph.keys())[:1]  # Use the first node as starting point
    
    # Track visited nodes
    visited = set()
    result = []
    
    # DFS function that processes dependencies first
    def dfs(node):
        if node in visited:
            return
        visited.add(node)
        
        # Visit all dependencies first
        for dep in sorted(acyclic_graph.get(node, set())):
            dfs(dep)
        
        # Add this node to the result after all its dependencies
        result.append(node)
    
    # Start DFS from each root node
    for root in sorted(root_nodes):
        dfs(root)
    
    # Check if all nodes were visited
    if len(result) != len(acyclic_graph):
        # Some nodes weren't visited - try to visit remaining nodes
        for node in sorted(acyclic_graph.keys()):
            if node not in visited:
                dfs(node)
    
    return result

def build_graph_from_components(components: Dict[str, Any]) -> Dict[str, Set[str]]:
    """
    Build a dependency graph from a collection of code components.
    
    The graph uses the natural dependency direction:
    - If A depends on B, we create an edge A → B
    - This means an edge from node X to node Y represents "X depends on Y"
    - Root nodes (nodes with no dependencies) are components that don't depend on anything
    
    Args:
        components: A dictionary of code components, where each component
                   has a 'depends_on' attribute
    
    Returns:
        A dependency graph with natural dependency direction
    """
    graph = {}
    
    for comp_id, component in components.items():
        # Initialize the node's adjacency list
        if comp_id not in graph:
            graph[comp_id] = set()
        
        # Add dependencies
        for dep_id in component.depends_on:
            # Only include dependencies that are actual components in our repository
            if dep_id in components:
                graph[comp_id].add(dep_id)
    
    return graph 


def analyze_component_distribution(components: Dict[str, Node]) -> Dict[str, Any]:
    """
    分析组件类型分布，为类型选择提供依据。
    
    Args:
        components: 组件字典
        
    Returns:
        包含类型统计和建议的字典
    """
    from collections import Counter
    
    type_counts = Counter(comp.component_type for comp in components.values())
    
    # 计算OOP类型（类、接口、结构体）的总数
    oop_types = {"class", "interface", "struct", "enum", "record", "abstract class"}
    oop_count = sum(type_counts.get(t, 0) for t in oop_types)
    
    # 计算函数类型的总数
    func_types = {"function", "async_function", "method"}
    func_count = sum(type_counts.get(t, 0) for t in func_types)
    
    total = len(components)
    
    return {
        "type_counts": dict(type_counts),
        "oop_count": oop_count,
        "func_count": func_count,
        "total": total,
        "oop_ratio": oop_count / total if total > 0 else 0,
        "func_ratio": func_count / total if total > 0 else 0
    }


def determine_valid_types(components: Dict[str, Node]) -> Set[str]:
    """
    动态确定应该包含的有效组件类型。
    
    基于代码库的实际类型分布来决定，而不是简单的有/无判断。
    
    Args:
        components: 组件字典
        
    Returns:
        有效的组件类型集合
    """
    dist = analyze_component_distribution(components)
    
    # 基础OOP类型
    valid_types = {"class", "interface", "struct", "enum", "record", "abstract class", "annotation"}
    
    # 决策逻辑：
    # 1. 如果OOP类型占比 < 10%，说明是C风格代码库，包含函数
    # 2. 如果OOP类型数量为0，必须包含函数
    # 3. 如果OOP类型数量很少（<5）但函数很多，也包含重要函数
    
    if dist["oop_count"] == 0:
        # 纯函数式/C风格代码库
        valid_types.update({"function", "async_function"})
        logger.debug("No OOP types found, including functions")
    elif dist["oop_ratio"] < 0.1 and dist["func_count"] > 20:
        # OOP类型稀少，主要是函数
        valid_types.update({"function", "async_function"})
        logger.debug(f"Low OOP ratio ({dist['oop_ratio']:.2%}), including functions")
    elif dist["oop_count"] < 5 and dist["func_count"] > 50:
        # 几乎没有OOP，包含函数
        valid_types.update({"function", "async_function"})
        logger.debug(f"Very few OOP types ({dist['oop_count']}), including functions")
    
    return valid_types


def calculate_component_importance(comp_id: str, components: Dict[str, Node], 
                                   graph: Dict[str, Set[str]]) -> float:
    """
    计算组件的重要性分数。
    
    重要性基于：
    1. 被其他组件依赖的程度（被依赖越多越重要）
    2. 是否是入口点（main, __main__, 公开API）
    3. 文档完整度（有docstring的更重要）
    
    Args:
        comp_id: 组件ID
        components: 组件字典
        graph: 依赖图
        
    Returns:
        重要性分数（0-100）
    """
    if comp_id not in components:
        return 0
    
    comp = components[comp_id]
    score = 0
    
    # 1. 计算被依赖程度
    used_by_count = sum(1 for deps in graph.values() if comp_id in deps)
    score += min(used_by_count * 5, 30)  # 最多30分
    
    # 2. 入口点加分
    name = comp.name if hasattr(comp, 'name') else comp_id.split('.')[-1]
    if name in ('main', '__main__', 'run', 'start', 'execute'):
        score += 20
    elif not name.startswith('_'):  # 公开API
        score += 10
    
    # 3. 有docstring加分
    if hasattr(comp, 'has_docstring') and comp.has_docstring:
        score += 15
    elif hasattr(comp, 'docstring') and comp.docstring:
        score += 15
    
    # 4. 代码长度（适中的代码更可能是核心组件）
    if hasattr(comp, 'source_code'):
        lines = len(comp.source_code.split('\n'))
        if 10 <= lines <= 200:
            score += 10
        elif 5 <= lines < 10:
            score += 5
    
    # 5. 组件类型加分
    comp_type = comp.component_type if hasattr(comp, 'component_type') else ''
    if comp_type in ('class', 'interface'):
        score += 10
    elif comp_type in ('struct', 'enum'):
        score += 5
    
    return min(score, 100)


def get_leaf_nodes(graph: Dict[str, Set[str]], components: Dict[str, Node]) -> List[str]:
    """
    找出叶子节点（没有被其他节点依赖的节点）。
    
    使用智能类型选择和重要性排序来优化结果。
    
    Args:
        graph: 依赖图（A→B 表示 A 依赖 B）
        components: 组件字典
    
    Returns:
        叶子节点列表，按重要性排序
    """
    # 解决循环依赖
    acyclic_graph = resolve_cycles(graph)
    
    # 获取所有节点作为初始叶子节点集
    leaf_nodes = set(acyclic_graph.keys())
    
    # 动态确定有效类型
    valid_types = determine_valid_types(components)
    logger.debug(f"Valid component types: {valid_types}")
    
    def filter_and_score_nodes(candidates: Set[str]) -> List[tuple]:
        """过滤并评分候选节点"""
        scored_nodes = []
        
        for node in candidates:
            # 处理 __init__ 别名
            display_node = node
            if node.endswith(".__init__"):
                display_node = node.replace(".__init__", "")
            
            # 跳过无效标识符
            if not isinstance(node, str) or not node.strip():
                continue
            
            # 跳过错误相关的节点名
            lower_node = node.lower()
            if any(err in lower_node for err in ['error', 'exception', 'failed', 'invalid']):
                # 但保留 Exception 类（它们可能是自定义异常）
                if 'exception' in lower_node:
                    comp = components.get(node)
                    if comp and comp.component_type == 'class':
                        pass  # 保留自定义异常类
                    else:
                        continue
                else:
                    continue
            
            # 检查组件是否存在且类型有效
            if node in components:
                comp = components[node]
                if comp.component_type in valid_types:
                    importance = calculate_component_importance(node, components, acyclic_graph)
                    scored_nodes.append((display_node, importance))
            elif display_node in components:
                # 尝试使用显示名称
                comp = components[display_node]
                if comp.component_type in valid_types:
                    importance = calculate_component_importance(display_node, components, acyclic_graph)
                    scored_nodes.append((display_node, importance))
        
        return scored_nodes
    
    # 第一轮：处理所有节点
    scored_nodes = filter_and_score_nodes(leaf_nodes)
    
    # 如果节点太多（>400），进行裁剪
    if len(scored_nodes) >= 400:
        logger.info(f"Leaf nodes too many ({len(scored_nodes)}), applying importance-based filtering")
        
        # 策略1：移除被其他节点依赖的节点
        for node, deps in acyclic_graph.items():
            for dep in deps:
                leaf_nodes.discard(dep)
        
        # 重新过滤评分
        scored_nodes = filter_and_score_nodes(leaf_nodes)
        
        # 如果仍然太多，取重要性最高的节点
        if len(scored_nodes) >= 400:
            logger.info(f"Still too many nodes ({len(scored_nodes)}), taking top 400 by importance")
            scored_nodes.sort(key=lambda x: -x[1])
            scored_nodes = scored_nodes[:400]
    
    if not scored_nodes:
        logger.warning("No valid leaf nodes found in the graph")
        return []
    
    # 按重要性排序，返回节点ID
    scored_nodes.sort(key=lambda x: -x[1])
    result = [node for node, _ in scored_nodes]
    
    logger.debug(f"Found {len(result)} leaf nodes")
    return result