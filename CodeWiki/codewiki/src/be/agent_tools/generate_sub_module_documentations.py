from pydantic_ai import RunContext, Tool, Agent
from typing import Any, Dict, List
import json

from codewiki.src.be.agent_tools.deps import CodeWikiDeps
from codewiki.src.be.agent_tools.read_code_components import read_code_components_tool
from codewiki.src.be.agent_tools.str_replace_editor import str_replace_editor_tool
from codewiki.src.be.llm_services import create_fallback_models, record_usage_from_result
from codewiki.src.be.prompt_template import SYSTEM_PROMPT, LEAF_SYSTEM_PROMPT, format_user_prompt
from codewiki.src.be.utils import is_complex_module, count_tokens
from codewiki.src.be.cluster_modules import format_potential_core_components

import logging
logger = logging.getLogger(__name__)



def _normalize_sub_module_specs(raw: Any) -> Dict[str, List[str]]:
    if isinstance(raw, dict):
        normalized: Dict[str, List[str]] = {}
        for key, value in raw.items():
            if isinstance(value, list):
                normalized[key] = [str(item) for item in value]
            elif value is None:
                normalized[key] = []
            else:
                normalized[key] = [str(value)]
        return normalized

    if isinstance(raw, list):
        normalized = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = (
                item.get("sub_module_name")
                or item.get("module_name")
                or item.get("name")
            )
            components = (
                item.get("core_component_ids")
                or item.get("components")
                or item.get("core_components")
            )
            if not name:
                continue
            if isinstance(components, list):
                normalized[str(name)] = [str(c) for c in components]
            elif components is None:
                normalized[str(name)] = []
            else:
                normalized[str(name)] = [str(components)]
        return normalized

    return {}


async def generate_sub_module_documentation(
    ctx: RunContext[CodeWikiDeps],
    sub_module_specs: str
) -> str:
    """Generate detailed description of a given sub-module specs to the sub-agents

    Args:
        sub_module_specs: JSON string for sub-module specs.
            Supported formats:
            - {"sub_module_1": ["core_component_1.1", "core_component_1.2"], ...}
            - [{"sub_module_name": "...", "core_component_ids": [...]}, ...]
    """

    deps = ctx.deps
    raw = sub_module_specs
    try:
        raw = json.loads(sub_module_specs)
    except Exception:
        logger.warning("sub_module_specs is not valid JSON, skipping.")
        return "No sub-modules generated due to invalid specs."
    sub_module_specs = _normalize_sub_module_specs(raw)
    if not sub_module_specs:
        logger.warning("No valid sub_module_specs provided.")
        return "No sub-modules generated due to invalid specs."
    previous_module_name = deps.current_module_name
    
    # Create fallback models from config
    fallback_models = create_fallback_models(deps.config)

    # add the sub-module to the module tree
    value = deps.module_tree
    for key in deps.path_to_current_module:
        value = value[key]["children"]
    total_submodules = len(sub_module_specs)
    for idx, (sub_module_name, core_component_ids) in enumerate(sub_module_specs.items(), start=1):
        if deps.progress_callback:
            deps.progress_callback(max(0, idx - 1), total_submodules, f"开始 {sub_module_name}")
        value[sub_module_name] = {"components": core_component_ids, "children": {}}
    
    for sub_module_name, core_component_ids in sub_module_specs.items():

        # Create visual indentation for nested modules
        indent = "  " * deps.current_depth
        arrow = "└─" if deps.current_depth > 0 else "→"

        logger.info(f"{indent}{arrow} Generating documentation for sub-module: {sub_module_name}")

        num_tokens = count_tokens(format_potential_core_components(core_component_ids, ctx.deps.components)[-1])
        
        if is_complex_module(ctx.deps.components, core_component_ids) and ctx.deps.current_depth < ctx.deps.max_depth and num_tokens >= ctx.deps.config.max_token_per_leaf_module:
            sub_agent = Agent(
                model=fallback_models,
                name=sub_module_name,
                deps_type=CodeWikiDeps,
                system_prompt=SYSTEM_PROMPT.format(module_name=sub_module_name, custom_instructions=ctx.deps.custom_instructions),
                tools=[read_code_components_tool, str_replace_editor_tool, generate_sub_module_documentation_tool],
            )
        else:
            sub_agent = Agent(
                model=fallback_models,
                name=sub_module_name,
                deps_type=CodeWikiDeps,
                system_prompt=LEAF_SYSTEM_PROMPT.format(module_name=sub_module_name, custom_instructions=ctx.deps.custom_instructions),
                tools=[read_code_components_tool, str_replace_editor_tool],
            )

        deps.current_module_name = sub_module_name
        deps.path_to_current_module.append(sub_module_name)
        deps.current_depth += 1
        # log the current module tree
        # print(f"Current module tree: {json.dumps(deps.module_tree, indent=4)}")

        result = await sub_agent.run(
            format_user_prompt(
                module_name=deps.current_module_name,
                core_component_ids=core_component_ids,
                components=ctx.deps.components,
                module_tree=ctx.deps.module_tree,
            ),
            deps=ctx.deps
        )
        record_usage_from_result(result)
        if deps.progress_callback:
            deps.progress_callback(idx, total_submodules, f"完成 {sub_module_name}")

        # remove the sub-module name from the path to current module and the module tree
        deps.path_to_current_module.pop()
        deps.current_depth -= 1

    # restore the previous module name
    deps.current_module_name = previous_module_name

    return f"Generate successfully. Documentations: {', '.join([key + '.md' for key in sub_module_specs.keys()])} are saved in the working directory."


generate_sub_module_documentation_tool = Tool(function=generate_sub_module_documentation, name="generate_sub_module_documentation", description="Generate detailed description of a given sub-module specs to the sub-agents", takes_ctx=True)