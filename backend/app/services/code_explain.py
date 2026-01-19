"""
Code Explain Service - 代码解释服务

提供：
1. 代码片段解释
2. 函数/类解释
3. 符号详情生成
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from app.services.db import get_repo_root, read_symbols_by_file, read_symbol_by_id
from app.services.code_browser import get_file_content, get_file_chunk
from app.services.llm_client import chat_completion_with_usage, LLMMessage
from app.services.llm_settings import get_effective_llm_config
from app.services.db import record_token_usage


@dataclass
class CodeExplanation:
    """代码解释结果"""
    explanation: str
    summary: Optional[str] = None
    context: Optional[str] = None
    related_symbols: Optional[List[str]] = None
    complexity: Optional[str] = None


@dataclass
class FunctionExplanation:
    """函数解释结果"""
    summary: str
    params: List[Dict[str, str]]
    returns: Optional[str] = None
    examples: Optional[List[str]] = None
    complexity: Optional[str] = None
    side_effects: Optional[List[str]] = None


def explain_code_snippet(
    repo_id: str,
    file_path: str,
    line_start: int,
    line_end: int,
    model: Optional[dict] = None,
) -> CodeExplanation:
    """
    解释代码片段
    
    Args:
        repo_id: 仓库ID
        file_path: 文件路径
        line_start: 起始行
        line_end: 结束行
        model: LLM模型配置
    
    Returns:
        CodeExplanation: 解释结果
    """
    # 获取代码内容
    chunk = get_file_chunk(repo_id, file_path, offset=max(1, line_start - 5), limit=line_end - line_start + 10)
    if not chunk:
        return CodeExplanation(explanation="无法找到指定的代码文件")
    
    code_content = chunk.get("content", "")
    language = chunk.get("language", "unknown")
    
    # 获取相关符号
    symbols = read_symbols_by_file(repo_id, file_path)
    related_symbols = []
    for sym in symbols:
        sym_start = sym.get("line_start", 0)
        sym_end = sym.get("line_end", 0)
        if sym_start <= line_end and sym_end >= line_start:
            related_symbols.append(sym.get("name", ""))
    
    # 构建提示
    prompt = f"""请解释以下 {language} 代码片段。

文件路径: {file_path}
行范围: {line_start}-{line_end}

```{language}
{code_content}
```

请提供：
1. **功能概述**: 这段代码的主要功能是什么？
2. **关键逻辑**: 解释代码的核心逻辑和流程
3. **注意事项**: 需要注意的边界情况或潜在问题
4. **相关上下文**: 与其他代码的关联

用中文回答，简洁明了。"""

    # 调用 LLM
    effective_model = get_effective_llm_config(model)
    messages = [LLMMessage(role="user", content=prompt)]
    
    try:
        explanation, usage = chat_completion_with_usage(messages, effective_model)
        record_token_usage(
            repo_id,
            kind="llm",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            is_estimated=usage.get("is_estimated", True),
            source="code_explain",
        )
    except Exception as e:
        return CodeExplanation(explanation=f"解释生成失败: {str(e)}")
    
    return CodeExplanation(
        explanation=explanation,
        related_symbols=related_symbols[:10] if related_symbols else None,
    )


def explain_symbol(
    repo_id: str,
    symbol_id: str,
    model: Optional[dict] = None,
) -> FunctionExplanation:
    """
    解释符号（函数/类）
    
    Args:
        repo_id: 仓库ID
        symbol_id: 符号ID
        model: LLM模型配置
    
    Returns:
        FunctionExplanation: 解释结果
    """
    # 获取符号信息
    symbol = read_symbol_by_id(repo_id, symbol_id)
    if not symbol:
        return FunctionExplanation(summary="无法找到指定的符号", params=[])
    
    file_path = symbol.get("file_path", "")
    line_start = symbol.get("line_start", 1)
    line_end = symbol.get("line_end", line_start + 50)
    name = symbol.get("name", "unknown")
    kind = symbol.get("kind", "function")
    signature = symbol.get("signature", "")
    
    # 获取代码内容
    chunk = get_file_chunk(repo_id, file_path, offset=line_start, limit=min(100, line_end - line_start + 1))
    if not chunk:
        return FunctionExplanation(summary="无法读取代码内容", params=[])
    
    code_content = chunk.get("content", "")
    language = chunk.get("language", "unknown")
    
    # 构建提示
    if kind in ("function", "method"):
        prompt = f"""请分析以下 {language} 函数，提供详细解释。

函数名: {name}
签名: {signature}
位置: {file_path}:{line_start}-{line_end}

```{language}
{code_content}
```

请按以下格式回答（JSON格式）：
{{
  "summary": "函数功能的一句话概述",
  "params": [
    {{"name": "参数名", "type": "类型", "description": "说明"}}
  ],
  "returns": "返回值说明",
  "complexity": "simple/medium/complex",
  "side_effects": ["副作用1", "副作用2"],
  "examples": ["使用示例1"]
}}

用中文回答。只输出JSON，不要其他文字。"""
    else:
        prompt = f"""请分析以下 {language} 类/结构，提供详细解释。

名称: {name}
类型: {kind}
位置: {file_path}:{line_start}-{line_end}

```{language}
{code_content}
```

请按以下格式回答（JSON格式）：
{{
  "summary": "类功能的概述",
  "params": [
    {{"name": "属性名", "type": "类型", "description": "说明"}}
  ],
  "complexity": "simple/medium/complex",
  "examples": ["使用示例"]
}}

用中文回答。只输出JSON，不要其他文字。"""

    # 调用 LLM
    effective_model = get_effective_llm_config(model)
    messages = [LLMMessage(role="user", content=prompt)]
    
    try:
        result, usage = chat_completion_with_usage(messages, effective_model)
        record_token_usage(
            repo_id,
            kind="llm",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            is_estimated=usage.get("is_estimated", True),
            source="symbol_explain",
        )
        
        # 解析 JSON
        import json
        # 尝试提取 JSON
        result = result.strip()
        if result.startswith("```json"):
            result = result[7:]
        if result.startswith("```"):
            result = result[3:]
        if result.endswith("```"):
            result = result[:-3]
        result = result.strip()
        
        data = json.loads(result)
        return FunctionExplanation(
            summary=data.get("summary", ""),
            params=data.get("params", []),
            returns=data.get("returns"),
            examples=data.get("examples"),
            complexity=data.get("complexity"),
            side_effects=data.get("side_effects"),
        )
    except Exception as e:
        return FunctionExplanation(
            summary=f"解释生成失败: {str(e)}",
            params=[],
        )


def explain_file(
    repo_id: str,
    file_path: str,
    model: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    解释整个文件
    
    Args:
        repo_id: 仓库ID
        file_path: 文件路径
        model: LLM模型配置
    
    Returns:
        Dict: 文件解释结果
    """
    # 获取文件内容
    content = get_file_content(repo_id, file_path)
    if not content:
        return {"error": "无法读取文件"}
    
    # 获取符号
    symbols = read_symbols_by_file(repo_id, file_path)
    
    # 如果文件太大，只取前500行
    code_lines = content.content.split("\n")
    if len(code_lines) > 500:
        code_preview = "\n".join(code_lines[:500]) + "\n... (省略剩余内容)"
    else:
        code_preview = content.content
    
    # 构建提示
    symbol_list = ", ".join([s.get("name", "") for s in symbols[:20]])
    
    prompt = f"""请分析以下 {content.language} 文件，提供详细解释。

文件路径: {file_path}
行数: {content.lines}
主要符号: {symbol_list}

```{content.language}
{code_preview}
```

请提供：
1. **文件概述**: 这个文件的主要功能和职责
2. **核心组件**: 主要的类/函数及其作用
3. **依赖关系**: 文件的依赖和被依赖情况
4. **使用建议**: 如何正确使用这个文件

用中文回答，简洁明了。"""

    # 调用 LLM
    effective_model = get_effective_llm_config(model)
    messages = [LLMMessage(role="user", content=prompt)]
    
    try:
        explanation, usage = chat_completion_with_usage(messages, effective_model)
        record_token_usage(
            repo_id,
            kind="llm",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            is_estimated=usage.get("is_estimated", True),
            source="file_explain",
        )
        
        return {
            "file_path": file_path,
            "language": content.language,
            "lines": content.lines,
            "symbols": [{"name": s.get("name"), "kind": s.get("kind")} for s in symbols[:20]],
            "explanation": explanation,
        }
    except Exception as e:
        return {"error": f"解释生成失败: {str(e)}"}
