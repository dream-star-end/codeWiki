from typing import List, Dict, Any, Optional
from collections import defaultdict
import logging
import traceback
import json
import ast
import re

logger = logging.getLogger(__name__)

from codewiki.src.be.dependency_analyzer.models.core import Node
from codewiki.src.be.llm_services import call_llm
from codewiki.src.be.utils import count_tokens
from codewiki.src.config import Config
from codewiki.src.be.prompt_template import format_cluster_prompt


def safe_parse_llm_response(response_content: str) -> Optional[Dict[str, Any]]:
    """
    安全解析LLM响应，避免使用eval()。
    
    尝试多种解析策略：
    1. 首先尝试标准JSON解析
    2. 尝试修复常见的JSON格式问题后再解析
    3. 使用ast.literal_eval作为后备（仅支持Python字面量）
    
    Args:
        response_content: LLM返回的响应内容
        
    Returns:
        解析后的字典，如果解析失败返回None
    """
    # 清理响应内容
    content = response_content.strip()
    
    # 1. 首先尝试标准JSON解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # 2. 尝试修复常见的格式问题
    try:
        # 替换单引号为双引号（JSON要求双引号）
        fixed_content = content.replace("'", '"')
        
        # 移除尾部逗号（JSON不允许）
        fixed_content = re.sub(r',\s*}', '}', fixed_content)
        fixed_content = re.sub(r',\s*]', ']', fixed_content)
        
        # 尝试解析修复后的内容
        return json.loads(fixed_content)
    except json.JSONDecodeError:
        pass
    
    # 3. 使用ast.literal_eval作为后备（更安全，只支持字面量）
    try:
        result = ast.literal_eval(content)
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError):
        pass
    
    # 4. 尝试提取JSON对象（处理可能的额外文本）
    try:
        # 查找第一个 { 和最后一个 } 之间的内容
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_str = json_match.group(0)
            # 尝试修复并解析
            fixed_json = json_str.replace("'", '"')
            fixed_json = re.sub(r',\s*}', '}', fixed_json)
            fixed_json = re.sub(r',\s*]', ']', fixed_json)
            return json.loads(fixed_json)
    except (json.JSONDecodeError, AttributeError):
        pass
    
    logger.error(f"All parsing strategies failed for content: {content[:200]}...")
    return None


def validate_module_tree(module_tree: Dict[str, Any], components: Dict[str, Node]) -> Dict[str, Any]:
    """
    验证并清理模块树，确保所有引用的组件都存在。
    
    Args:
        module_tree: 解析得到的模块树
        components: 所有可用的组件
        
    Returns:
        验证并清理后的模块树
    """
    validated_tree = {}
    
    for module_name, module_info in module_tree.items():
        if not isinstance(module_info, dict):
            logger.warning(f"Invalid module info for '{module_name}', skipping")
            continue
        
        # 验证components列表
        module_components = module_info.get("components", [])
        if not isinstance(module_components, list):
            logger.warning(f"Invalid components format for module '{module_name}'")
            module_components = []
        
        # 过滤有效的组件
        valid_components = [
            comp for comp in module_components 
            if isinstance(comp, str) and comp in components
        ]
        
        if not valid_components:
            logger.warning(f"Module '{module_name}' has no valid components, skipping")
            continue
        
        validated_tree[module_name] = {
            "path": module_info.get("path", ""),
            "components": valid_components,
            "children": {}
        }
    
    return validated_tree


# ------------------------------------------------------------
# ---------------------- Pre-clustering Analysis -------------
# ------------------------------------------------------------

def pre_cluster_by_directory(
    leaf_nodes: List[str], 
    components: Dict[str, Node]
) -> Dict[str, List[str]]:
    """
    基于目录结构对组件进行预聚类。
    
    策略：
    1. 按目录路径分组组件
    2. 识别公共目录层级
    3. 合并过小的目录
    
    Args:
        leaf_nodes: 叶子节点列表
        components: 组件字典
        
    Returns:
        目录 -> 组件列表 的映射
    """
    import os
    
    # 按目录分组
    dir_clusters: Dict[str, List[str]] = defaultdict(list)
    
    for node in leaf_nodes:
        if node not in components:
            continue
        
        comp = components[node]
        rel_path = getattr(comp, 'relative_path', '')
        
        if rel_path:
            # 获取目录路径
            dir_path = os.path.dirname(rel_path)
            # 标准化路径分隔符
            dir_path = dir_path.replace('\\', '/')
            
            if not dir_path:
                dir_path = 'root'
            
            dir_clusters[dir_path].append(node)
    
    return dict(dir_clusters)


def analyze_dependency_density(
    cluster: List[str], 
    components: Dict[str, Node]
) -> float:
    """
    分析一个集群内的依赖密度。
    
    密度 = 集群内依赖数 / (集群大小 * (集群大小 - 1))
    
    Args:
        cluster: 组件ID列表
        components: 组件字典
        
    Returns:
        依赖密度 (0.0 - 1.0)
    """
    if len(cluster) <= 1:
        return 1.0
    
    cluster_set = set(cluster)
    internal_deps = 0
    
    for comp_id in cluster:
        if comp_id not in components:
            continue
        
        comp = components[comp_id]
        deps = getattr(comp, 'depends_on', set())
        
        if isinstance(deps, (set, list)):
            for dep in deps:
                if dep in cluster_set:
                    internal_deps += 1
    
    max_possible = len(cluster) * (len(cluster) - 1)
    if max_possible == 0:
        return 1.0
    
    return internal_deps / max_possible


def merge_small_clusters(
    clusters: Dict[str, List[str]], 
    min_size: int = 3,
    components: Dict[str, Node] = None
) -> Dict[str, List[str]]:
    """
    合并过小的集群。
    
    策略：
    1. 找到过小的集群
    2. 基于目录层级合并到父目录
    3. 或基于依赖关系合并到相关集群
    
    Args:
        clusters: 现有集群
        min_size: 最小集群大小
        components: 组件字典（用于依赖分析）
        
    Returns:
        合并后的集群
    """
    import os
    
    result = {}
    small_clusters = {}
    
    # 分离大小足够的集群和过小的集群
    for name, members in clusters.items():
        if len(members) >= min_size:
            result[name] = members
        else:
            small_clusters[name] = members
    
    # 尝试将小集群合并到父目录
    for name, members in small_clusters.items():
        merged = False
        
        # 尝试找父目录
        parts = name.split('/')
        for i in range(len(parts) - 1, 0, -1):
            parent_path = '/'.join(parts[:i])
            if parent_path in result:
                result[parent_path].extend(members)
                merged = True
                logger.debug(f"Merged small cluster '{name}' into parent '{parent_path}'")
                break
        
        if not merged:
            # 无法合并，保留原样
            if name in result:
                result[name].extend(members)
            else:
                result[name] = members
    
    return result


def suggest_module_structure(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    max_modules: int = 10
) -> Dict[str, Any]:
    """
    基于目录结构和依赖分析，建议初始模块结构。
    
    这个函数提供一个预聚类结果，可以作为LLM聚类的参考或后备。
    
    Args:
        leaf_nodes: 叶子节点列表
        components: 组件字典
        max_modules: 最大模块数
        
    Returns:
        建议的模块结构
    """
    # 1. 基于目录预聚类
    dir_clusters = pre_cluster_by_directory(leaf_nodes, components)
    
    # 2. 合并小集群
    merged_clusters = merge_small_clusters(dir_clusters, min_size=2, components=components)
    
    # 3. 如果集群太多，进一步合并
    while len(merged_clusters) > max_modules:
        # 找到最小的两个集群并合并
        sorted_clusters = sorted(merged_clusters.items(), key=lambda x: len(x[1]))
        if len(sorted_clusters) < 2:
            break
        
        name1, members1 = sorted_clusters[0]
        name2, members2 = sorted_clusters[1]
        
        # 合并到共同前缀或较大的那个
        common_prefix = ''
        parts1 = name1.split('/')
        parts2 = name2.split('/')
        for p1, p2 in zip(parts1, parts2):
            if p1 == p2:
                common_prefix = common_prefix + '/' + p1 if common_prefix else p1
            else:
                break
        
        new_name = common_prefix if common_prefix else f"{name1}_and_{name2}"
        
        del merged_clusters[name1]
        del merged_clusters[name2]
        merged_clusters[new_name] = members1 + members2
    
    # 4. 转换为模块树格式
    result = {}
    for dir_path, members in merged_clusters.items():
        # 生成模块名称
        module_name = dir_path.replace('/', '_').replace('.', '_')
        if module_name.startswith('_'):
            module_name = module_name[1:]
        if not module_name:
            module_name = 'core'
        
        # 计算依赖密度
        density = analyze_dependency_density(members, components)
        
        result[module_name] = {
            "path": dir_path,
            "components": members,
            "children": {},
            "density": round(density, 3)
        }
    
    return result


def enhance_cluster_prompt_with_suggestions(
    potential_core_components: str,
    leaf_nodes: List[str],
    components: Dict[str, Node],
    module_tree: Dict[str, Any] = {},
    module_name: str = None
) -> str:
    """
    增强聚类提示，添加预聚类建议。
    
    Args:
        potential_core_components: 格式化的组件列表
        leaf_nodes: 叶子节点列表
        components: 组件字典
        module_tree: 当前模块树
        module_name: 当前模块名称
        
    Returns:
        增强后的提示
    """
    base_prompt = format_cluster_prompt(potential_core_components, module_tree, module_name)
    
    # 生成预聚类建议
    suggestions = suggest_module_structure(leaf_nodes, components, max_modules=8)
    
    if suggestions:
        suggestion_text = "\n\n<PRE_CLUSTERING_SUGGESTION>\n"
        suggestion_text += "Based on directory structure analysis, here's a suggested grouping:\n"
        
        for mod_name, mod_info in suggestions.items():
            comps = mod_info.get('components', [])[:5]  # 只显示前5个
            remaining = len(mod_info.get('components', [])) - 5
            suggestion_text += f"- {mod_name} ({mod_info.get('path', '')}):\n"
            suggestion_text += f"    Components: {', '.join(comps)}"
            if remaining > 0:
                suggestion_text += f" ... and {remaining} more"
            suggestion_text += f"\n    Density: {mod_info.get('density', 'N/A')}\n"
        
        suggestion_text += "\nNote: This is just a suggestion based on file structure. "
        suggestion_text += "Use your judgment to create a more meaningful grouping based on functionality.\n"
        suggestion_text += "</PRE_CLUSTERING_SUGGESTION>\n"
        
        base_prompt += suggestion_text
    
    return base_prompt


def format_potential_core_components(leaf_nodes: List[str], components: Dict[str, Node]) -> tuple[str, str]:
    """
    Format the potential core components into a string that can be used in the prompt.
    """
    # Filter out any invalid leaf nodes that don't exist in components
    valid_leaf_nodes = []
    for leaf_node in leaf_nodes:
        if leaf_node in components:
            valid_leaf_nodes.append(leaf_node)
        else:
            logger.warning(f"Skipping invalid leaf node '{leaf_node}' - not found in components")
    
    #group leaf nodes by file
    leaf_nodes_by_file = defaultdict(list)
    for leaf_node in valid_leaf_nodes:
        leaf_nodes_by_file[components[leaf_node].relative_path].append(leaf_node)

    potential_core_components = ""
    potential_core_components_with_code = ""
    for file, leaf_nodes in dict(sorted(leaf_nodes_by_file.items())).items():
        potential_core_components += f"# {file}\n"
        potential_core_components_with_code += f"# {file}\n"
        for leaf_node in leaf_nodes:
            potential_core_components += f"\t{leaf_node}\n"
            potential_core_components_with_code += f"\t{leaf_node}\n"
            potential_core_components_with_code += f"{components[leaf_node].source_code}\n"

    return potential_core_components, potential_core_components_with_code


def cluster_modules(
    leaf_nodes: List[str],
    components: Dict[str, Node],
    config: Config,
    current_module_tree: dict[str, Any] = {},
    current_module_name: str = None,
    current_module_path: List[str] = [],
    max_retries: int = 2
) -> Dict[str, Any]:
    """
    Cluster the potential core components into modules.
    
    Args:
        leaf_nodes: 待聚类的叶子节点列表
        components: 所有组件字典
        config: 配置对象
        current_module_tree: 当前模块树
        current_module_name: 当前模块名称
        current_module_path: 当前模块路径
        max_retries: 最大重试次数
        
    Returns:
        模块树字典
    """
    potential_core_components, potential_core_components_with_code = format_potential_core_components(leaf_nodes, components)

    if count_tokens(potential_core_components_with_code) <= config.max_token_per_module:
        logger.debug(f"Skipping clustering for {current_module_name} because the potential core components are too few: {count_tokens(potential_core_components_with_code)} tokens")
        return {}

    # 使用增强的提示，包含预聚类建议
    prompt = enhance_cluster_prompt_with_suggestions(
        potential_core_components, 
        leaf_nodes, 
        components, 
        current_module_tree, 
        current_module_name
    )
    
    # 带重试的LLM调用
    module_tree = None
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            response = call_llm(prompt, config, model=config.cluster_model)
            
            # 验证响应格式
            if "<GROUPED_COMPONENTS>" not in response or "</GROUPED_COMPONENTS>" not in response:
                logger.warning(f"Attempt {attempt + 1}: Invalid LLM response format - missing component tags")
                last_error = "Missing component tags in response"
                continue
            
            response_content = response.split("<GROUPED_COMPONENTS>")[1].split("</GROUPED_COMPONENTS>")[0]
            
            # 使用安全解析方法替代eval()
            parsed_tree = safe_parse_llm_response(response_content)
            
            if parsed_tree is None:
                logger.warning(f"Attempt {attempt + 1}: Failed to parse LLM response")
                last_error = "Failed to parse response content"
                continue
            
            if not isinstance(parsed_tree, dict):
                logger.warning(f"Attempt {attempt + 1}: Invalid module tree format - expected dict, got {type(parsed_tree)}")
                last_error = f"Invalid format: {type(parsed_tree)}"
                continue
            
            # 验证并清理模块树
            module_tree = validate_module_tree(parsed_tree, components)
            
            if module_tree:
                break
            else:
                last_error = "Validation produced empty module tree"
                
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1}: Exception during clustering: {e}")
            last_error = str(e)
            continue
    
    if module_tree is None:
        logger.error(f"All {max_retries + 1} attempts failed. Last error: {last_error}")
        logger.error(f"Response preview: {response[:300] if 'response' in dir() else 'N/A'}...")
        return {}

    # 检查模块树大小
    if len(module_tree) <= 1:
        logger.debug(f"Skipping clustering for {current_module_name} because the module tree is too small: {len(module_tree)} modules")
        return {}

    # 更新全局模块树
    if current_module_tree == {}:
        current_module_tree = module_tree
    else:
        value = current_module_tree
        for key in current_module_path:
            value = value[key]["children"]
        for module_name, module_info in module_tree.items():
            # 安全删除path字段
            if "path" in module_info:
                del module_info["path"]
            value[module_name] = module_info

    # 递归处理子模块
    for module_name, module_info in module_tree.items():
        sub_leaf_nodes = module_info.get("components", [])
        
        # 组件已在validate_module_tree中验证过，这里直接使用
        current_module_path.append(module_name)
        module_info["children"] = {}
        module_info["children"] = cluster_modules(
            sub_leaf_nodes, 
            components, 
            config, 
            current_module_tree, 
            module_name, 
            current_module_path,
            max_retries
        )
        current_module_path.pop()

    return module_tree