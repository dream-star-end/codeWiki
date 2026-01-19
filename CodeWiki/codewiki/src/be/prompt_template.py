SYSTEM_PROMPT = """
<ROLE>
You are an AI documentation assistant specialized in generating comprehensive, accurate system documentation. Your documentation should help developers understand, maintain, and extend the codebase.
</ROLE>

<OBJECTIVES>
Create documentation that helps developers and maintainers understand:
1. The module's purpose and core functionality
2. Architecture and component relationships
3. How the module fits into the overall system
4. Data flow and control flow through the module
5. Public APIs and their usage patterns
</OBJECTIVES>

<ANALYSIS_CHECKLIST>
Before generating documentation, analyze:
1. **Entry Points**: main functions, CLI commands, API endpoints, public classes
2. **Design Patterns**: Factory, Singleton, Observer, Strategy, etc.
3. **Data Flow**: Input → Processing → Output paths
4. **Error Handling**: Exception types and recovery strategies
5. **Configuration**: Environment variables, config files, parameters
6. **Public API**: Classes/functions intended for external use (no underscore prefix)
7. **Internal Utilities**: Helper functions, private classes (underscore prefix)
8. **Dependencies**: External libraries and internal module dependencies
</ANALYSIS_CHECKLIST>

<ACCURACY_REQUIREMENTS>
- ONLY document what is explicitly present in the code
- DO NOT invent features or behaviors not shown in source code
- Mark uncertain information with [NEEDS VERIFICATION]
- Include actual code snippets as examples when applicable
- Verify all class/function names exist before referencing them
</ACCURACY_REQUIREMENTS>

<DOCUMENTATION_STRUCTURE>
Generate documentation following this structure:

1. **Main Documentation File** (`{module_name}.md`):
   - Brief introduction and purpose (2-3 sentences)
   - Architecture overview with Mermaid diagrams
   - Key components table with brief descriptions
   - High-level functionality of each sub-module with links
   - Usage examples where applicable

2. **Sub-module Documentation** (if applicable):
   - Detailed descriptions saved as `sub-module_name.md`
   - Core components and their responsibilities
   - API reference for public interfaces
   - Error handling patterns

3. **Visual Documentation**:
   - Architecture diagram (class/component relationships)
   - Data flow diagram (how data moves through the system)
   - Sequence diagrams for key operations
   - Dependency graph (what depends on what)
</DOCUMENTATION_STRUCTURE>

<MERMAID_BEST_PRACTICES>
- Use classDiagram for class relationships
- Use flowchart TD for data flow
- Use sequenceDiagram for process interactions
- Keep diagrams focused (max 10-15 nodes)
- Use meaningful labels and descriptions
- Validate syntax before including
</MERMAID_BEST_PRACTICES>

<WORKFLOW>
1. Analyze the provided code components and dependency graph
2. Identify entry points, public APIs, and key patterns
3. Create the main `{module_name}.md` file with overview and architecture
4. Use `generate_sub_module_documentation` for complex modules (>1 file, clear boundaries)
5. Include relevant Mermaid diagrams throughout
6. Cross-reference all generated documentation files
</WORKFLOW>

<AVAILABLE_TOOLS>
- `str_replace_editor`: File system operations for creating and editing documentation files
- `read_code_components`: Explore additional code dependencies not included in the provided components
- `generate_sub_module_documentation`: Generate detailed documentation for individual sub-modules via sub-agents
</AVAILABLE_TOOLS>
{custom_instructions}
""".strip()

LEAF_SYSTEM_PROMPT = """
<ROLE>
You are an AI documentation assistant specialized in generating accurate, developer-friendly documentation for code modules.
</ROLE>

<OBJECTIVES>
Create comprehensive documentation that helps developers:
1. Understand the module's purpose and responsibilities
2. Learn the public API and usage patterns
3. Understand component relationships and dependencies
4. Identify entry points and key workflows
</OBJECTIVES>

<ACCURACY_REQUIREMENTS>
- ONLY document what is explicitly present in the code
- DO NOT invent features or behaviors not shown in source
- Include actual code snippets from the provided source
- Verify all referenced names exist in the code
- When uncertain, indicate with [NEEDS VERIFICATION]
</ACCURACY_REQUIREMENTS>

<DOCUMENTATION_STRUCTURE>
Generate `{module_name}.md` with the following structure:

1. **Overview** (2-3 sentences)
   - Module purpose and primary responsibility
   
2. **Architecture** (Mermaid diagram)
   - Component relationships
   - Key classes and their roles
   
3. **Core Components**
   - For each public class/function:
     - Purpose and responsibility
     - Key methods/parameters
     - Usage example (if applicable)

4. **Data Flow** (if applicable)
   - How data moves through the module
   - Input → Processing → Output

5. **Dependencies**
   - What this module depends on
   - What depends on this module

6. **Usage Examples**
   - Real code patterns from the source
</DOCUMENTATION_STRUCTURE>

<MERMAID_GUIDELINES>
- Use classDiagram for OOP relationships
- Use flowchart TD for process flows
- Keep diagrams focused (max 8-10 nodes)
- Include brief labels/descriptions
- Test syntax validity before including
</MERMAID_GUIDELINES>

<WORKFLOW>
1. Analyze provided code and dependency graph
2. Identify public API, entry points, key patterns
3. Generate complete {module_name}.md documentation
4. Include appropriate Mermaid diagrams
</WORKFLOW>

<AVAILABLE_TOOLS>
- `str_replace_editor`: File system operations for creating and editing documentation files
- `read_code_components`: Explore additional code dependencies not included in the provided components
</AVAILABLE_TOOLS>
{custom_instructions}
""".strip()

USER_PROMPT = """
Generate comprehensive documentation for the {module_name} module using the provided module tree, dependency graph, and core components.

<MODULE_TREE>
{module_tree}
</MODULE_TREE>
* NOTE: You can refer the other modules in the module tree based on the dependencies between their core components to make the documentation more structured and avoid repeating the same information. Know that all documentation files are saved in the same folder not structured as module tree. e.g. [alt text]([ref_module_name].md)

<DEPENDENCY_GRAPH>
{dependency_info}
</DEPENDENCY_GRAPH>
* NOTE: The dependency graph shows which components depend on other components. Use this information to:
  - Understand the data flow and control flow
  - Identify entry points (components with many dependents but few dependencies)
  - Identify utility/helper components (components used by many others)
  - Create accurate architecture and sequence diagrams

<CORE_COMPONENT_CODES>
{formatted_core_component_codes}
</CORE_COMPONENT_CODES>
""".strip()

REPO_OVERVIEW_PROMPT = """
You are an AI documentation assistant. Your task is to generate a brief overview of the {repo_name} repository.

The overview should be a brief documentation of the repository, including:
- The purpose of the repository
- The end-to-end architecture of the repository visualized by mermaid diagrams
- The references to the core modules documentation

Provide `{repo_name}` repo structure and its core modules documentation:
<REPO_STRUCTURE>
{repo_structure}
</REPO_STRUCTURE>

Please generate the overview of the `{repo_name}` repository in markdown format with the following structure:
<OVERVIEW>
overview_content
</OVERVIEW>
""".strip()

MODULE_OVERVIEW_PROMPT = """
You are an AI documentation assistant. Your task is to generate a brief overview of `{module_name}` module.

The overview should be a brief documentation of the module, including:
- The purpose of the module
- The architecture of the module visualized by mermaid diagrams
- The references to the core components documentation

Provide repo structure and core components documentation of the `{module_name}` module:
<REPO_STRUCTURE>
{repo_structure}
</REPO_STRUCTURE>

Please generate the overview of the `{module_name}` module in markdown format with the following structure:
<OVERVIEW>
overview_content
</OVERVIEW>
""".strip()

CLUSTER_REPO_PROMPT = """
Here is list of all potential core components of the repository (It's normal that some components are not essential to the repository):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

Please group the components into groups such that each group is a set of components that are closely related to each other and together they form a module. DO NOT include components that are not essential to the repository.
Firstly reason about the components and then group them and return the result in the following format:
<GROUPED_COMPONENTS>
{{
    "module_name_1": {{
        "path": <path_to_the_module_1>, # the path to the module can be file or directory
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    "module_name_2": {{
        "path": <path_to_the_module_2>,
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    ...
}}
</GROUPED_COMPONENTS>
""".strip()

CLUSTER_MODULE_PROMPT = """
Here is the module tree of a repository:

<MODULE_TREE>
{module_tree}
</MODULE_TREE>

Here is list of all potential core components of the module {module_name} (It's normal that some components are not essential to the module):
<POTENTIAL_CORE_COMPONENTS>
{potential_core_components}
</POTENTIAL_CORE_COMPONENTS>

Please group the components into groups such that each group is a set of components that are closely related to each other and together they form a smaller module. DO NOT include components that are not essential to the module.

Firstly reason based on given context and then group them and return the result in the following format:
<GROUPED_COMPONENTS>
{{
    "module_name_1": {{
        "path": <path_to_the_module_1>, # the path to the module can be file or directory
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    "module_name_2": {{
        "path": <path_to_the_module_2>,
        "components": [
            <component_name_1>,
            <component_name_2>,
            ...
        ]
    }},
    ...
}}
</GROUPED_COMPONENTS>
""".strip()

FILTER_FOLDERS_PROMPT = """
Here is the list of relative paths of files, folders in 2-depth of project {project_name}:
```
{files}
```

In order to analyze the core functionality of the project, we need to analyze the files, folders representing the core functionality of the project.

Please shortlist the files, folders representing the core functionality and ignore the files, folders that are not essential to the core functionality of the project (e.g. test files, documentation files, etc.) from the list above.

Reasoning at first, then return the list of relative paths in JSON format.
"""

from typing import Dict, Any, List, Set
from collections import defaultdict
from codewiki.src.utils import file_manager

EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".md": "markdown",
    ".sh": "bash",
    ".json": "json",
    ".yaml": "yaml",
    ".java": "java",
    ".js": "javascript",
    ".ts": "typescript",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
    ".tsx": "typescript",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".cxx": "cpp",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".cs": "csharp",
    ".php": "php",
    ".phtml": "php",
    ".inc": "php"
}


def build_dependency_info(core_component_ids: List[str], components: Dict[str, Any]) -> str:
    """
    构建依赖关系信息字符串。
    
    Args:
        core_component_ids: 核心组件ID列表
        components: 所有组件字典
        
    Returns:
        格式化的依赖关系信息
    """
    core_set = set(core_component_ids)
    
    # 构建依赖图和反向依赖图
    depends_on: Dict[str, Set[str]] = defaultdict(set)  # 组件依赖的其他组件
    used_by: Dict[str, Set[str]] = defaultdict(set)      # 被其他组件使用
    
    for comp_id in core_component_ids:
        if comp_id not in components:
            continue
        component = components[comp_id]
        
        # 获取组件的依赖
        deps = getattr(component, 'depends_on', set())
        if isinstance(deps, (set, list)):
            for dep_id in deps:
                # 只关注模块内的依赖或可识别的外部依赖
                if dep_id in core_set:
                    depends_on[comp_id].add(dep_id)
                    used_by[dep_id].add(comp_id)
                elif dep_id in components:
                    # 外部依赖，标注
                    depends_on[comp_id].add(f"{dep_id} (external)")
    
    lines = []
    
    # 1. 统计信息
    lines.append("## Dependency Statistics")
    lines.append(f"- Total components: {len(core_component_ids)}")
    lines.append(f"- Components with dependencies: {len([c for c in depends_on if depends_on[c]])}")
    lines.append(f"- Components used by others: {len([c for c in used_by if used_by[c]])}")
    lines.append("")
    
    # 2. 识别入口点（被多个组件使用但依赖较少的组件）
    entry_points = []
    for comp_id in core_component_ids:
        deps_count = len(depends_on.get(comp_id, set()))
        used_count = len(used_by.get(comp_id, set()))
        if used_count >= 2 and deps_count <= 1:
            entry_points.append((comp_id, used_count))
    
    if entry_points:
        lines.append("## Potential Entry Points / Core Components")
        lines.append("(Components used by many others but have few dependencies)")
        for comp_id, count in sorted(entry_points, key=lambda x: -x[1])[:5]:
            lines.append(f"- {comp_id} (used by {count} components)")
        lines.append("")
    
    # 3. 详细依赖关系
    lines.append("## Component Dependencies")
    for comp_id in core_component_ids:
        if comp_id not in components:
            continue
        deps = depends_on.get(comp_id, set())
        users = used_by.get(comp_id, set())
        
        if deps or users:
            lines.append(f"### {comp_id}")
            if deps:
                lines.append(f"  Depends on: {', '.join(sorted(deps))}")
            if users:
                lines.append(f"  Used by: {', '.join(sorted(users))}")
    
    return "\n".join(lines) if lines else "No dependency information available."


def format_user_prompt(module_name: str, core_component_ids: list[str], components: Dict[str, Any], module_tree: dict[str, any]) -> str:
    """
    Format the user prompt with module name and organized core component codes.
    
    Args:
        module_name: Name of the module to document
        core_component_ids: List of component IDs to include
        components: Dictionary mapping component IDs to CodeComponent objects
        module_tree: Module tree structure
    
    Returns:
        Formatted user prompt string
    """

    # format module tree
    lines = []
    
    def _format_module_tree(tree: dict[str, any], indent: int = 0):
        for key, value in tree.items():
            if key == module_name:
                lines.append(f"{'  ' * indent}{key} (current module)")
            else:
                lines.append(f"{'  ' * indent}{key}")
            
            lines.append(f"{'  ' * (indent + 1)} Core components: {', '.join(value['components'])}")
            if isinstance(value["children"], dict) and len(value["children"]) > 0:
                lines.append(f"{'  ' * (indent + 1)} Children:")
                _format_module_tree(value["children"], indent + 2)
    
    _format_module_tree(module_tree, 0)
    formatted_module_tree = "\n".join(lines)

    # 构建依赖关系信息
    dependency_info = build_dependency_info(core_component_ids, components)

    # Group core component IDs by their file path
    grouped_components: dict[str, list[str]] = {}
    for component_id in core_component_ids:
        if component_id not in components:
            continue
        component = components[component_id]
        path = component.relative_path
        if path not in grouped_components:
            grouped_components[path] = []
        grouped_components[path].append(component_id)

    core_component_codes = ""
    for path, component_ids_in_file in grouped_components.items():
        core_component_codes += f"# File: {path}\n\n"
        core_component_codes += f"## Core Components in this file:\n"
        
        for component_id in component_ids_in_file:
            comp = components.get(component_id)
            if comp:
                # 添加组件的额外元信息
                comp_type = getattr(comp, 'component_type', 'unknown')
                display_name = getattr(comp, 'display_name', component_id)
                docstring = getattr(comp, 'docstring', '')
                core_component_codes += f"- {component_id} ({comp_type})"
                if docstring:
                    # 只显示docstring的第一行
                    first_line = docstring.split('\n')[0].strip()[:80]
                    if first_line:
                        core_component_codes += f": {first_line}"
                core_component_codes += "\n"
            else:
                core_component_codes += f"- {component_id}\n"
        
        # 获取文件扩展名对应的语言
        ext = '.' + path.split('.')[-1] if '.' in path else ''
        lang = EXTENSION_TO_LANGUAGE.get(ext, 'text')
        
        core_component_codes += f"\n## File Content:\n```{lang}\n"
        
        # Read content of the file using the first component's file path
        try:
            core_component_codes += file_manager.load_text(components[component_ids_in_file[0]].file_path)
        except (FileNotFoundError, IOError) as e:
            core_component_codes += f"# Error reading file: {e}\n"
        
        core_component_codes += "```\n\n"
        
    return USER_PROMPT.format(
        module_name=module_name, 
        formatted_core_component_codes=core_component_codes, 
        module_tree=formatted_module_tree,
        dependency_info=dependency_info
    )



def format_cluster_prompt(potential_core_components: str, module_tree: dict[str, any] = {}, module_name: str = None) -> str:
    """
    Format the cluster prompt with potential core components and module tree.
    """

    # format module tree
    lines = []

    # print(f"Module tree:\n{json.dumps(module_tree, indent=2)}")
    
    def _format_module_tree(module_tree: dict[str, any], indent: int = 0):
        for key, value in module_tree.items():
            if key == module_name:
                lines.append(f"{'  ' * indent}{key} (current module)")
            else:
                lines.append(f"{'  ' * indent}{key}")
            
            lines.append(f"{'  ' * (indent + 1)} Core components: {', '.join(value['components'])}")
            if ("children" in value) and isinstance(value["children"], dict) and len(value["children"]) > 0:
                lines.append(f"{'  ' * (indent + 1)} Children:")
                _format_module_tree(value["children"], indent + 2)
    
    _format_module_tree(module_tree, 0)
    formatted_module_tree = "\n".join(lines)


    if module_tree == {}:
        return CLUSTER_REPO_PROMPT.format(potential_core_components=potential_core_components)
    else:
        return CLUSTER_MODULE_PROMPT.format(potential_core_components=potential_core_components, module_tree=formatted_module_tree, module_name=module_name)


def format_system_prompt(module_name: str, custom_instructions: str = None) -> str:
    """
    Format the system prompt with module name and optional custom instructions.
    
    Args:
        module_name: Name of the module to document
        custom_instructions: Optional custom instructions to append
        
    Returns:
        Formatted system prompt string
    """
    custom_section = ""
    if custom_instructions:
        custom_section = f"\n\n<CUSTOM_INSTRUCTIONS>\n{custom_instructions}\n</CUSTOM_INSTRUCTIONS>"
    
    return SYSTEM_PROMPT.format(module_name=module_name, custom_instructions=custom_section).strip()


def format_leaf_system_prompt(module_name: str, custom_instructions: str = None) -> str:
    """
    Format the leaf system prompt with module name and optional custom instructions.
    
    Args:
        module_name: Name of the module to document
        custom_instructions: Optional custom instructions to append
        
    Returns:
        Formatted leaf system prompt string
    """
    custom_section = ""
    if custom_instructions:
        custom_section = f"\n\n<CUSTOM_INSTRUCTIONS>\n{custom_instructions}\n</CUSTOM_INSTRUCTIONS>"
    
    return LEAF_SYSTEM_PROMPT.format(module_name=module_name, custom_instructions=custom_section).strip()