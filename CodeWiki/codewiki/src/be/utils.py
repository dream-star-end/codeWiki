import re
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import logging
import tiktoken
import traceback


logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# ---------------------- Complexity Check --------------------
# ------------------------------------------------------------

def is_complex_module(components: dict[str, any], core_component_ids: list[str]) -> bool:
    files = set()
    for component_id in core_component_ids:
        if component_id in components:
            files.add(components[component_id].file_path)

    result = len(files) > 1

    return result


# ------------------------------------------------------------
# ---------------------- Token Counting ---------------------
# ------------------------------------------------------------

enc = tiktoken.encoding_for_model("gpt-4")

def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text.
    """
    length = len(enc.encode(text))
    return length


# ------------------------------------------------------------
# ---------------------- Smart Truncation --------------------
# ------------------------------------------------------------

# 关键代码模式权重
CODE_PATTERNS = {
    'class_def': (r'^\s*(class\s+\w+|public\s+class|interface\s+\w+|struct\s+\w+)', 10),
    'function_def': (r'^\s*(def\s+\w+|async\s+def|function\s+\w+|public\s+\w+\s+\w+\s*\()', 9),
    'method_def': (r'^\s*(public|private|protected)\s+\w+\s+\w+\s*\(', 8),
    'import_stmt': (r'^\s*(import\s+|from\s+\w+\s+import|using\s+|#include)', 7),
    'decorator': (r'^\s*@\w+', 6),
    'docstring_start': (r'^\s*("""|\'\'\'|/\*\*)', 5),
    'comment_important': (r'^\s*(#\s*(TODO|FIXME|NOTE|IMPORTANT)|//\s*(TODO|FIXME))', 5),
    'return_stmt': (r'^\s*return\s+', 4),
    'assignment': (r'^\s*\w+\s*=\s*', 3),
    'control_flow': (r'^\s*(if|else|elif|for|while|switch|case|try|except|catch)', 3),
}


def calculate_line_importance(line: str, context: Dict[str, Any] = None) -> int:
    """
    计算代码行的重要性分数。
    
    Args:
        line: 代码行
        context: 上下文信息（如当前是否在类/函数定义内）
        
    Returns:
        重要性分数 (1-10)
    """
    if not line.strip():
        return 1  # 空行最低优先级
    
    max_score = 1
    
    for pattern_name, (pattern, score) in CODE_PATTERNS.items():
        if re.match(pattern, line, re.IGNORECASE):
            max_score = max(max_score, score)
    
    return max_score


def smart_truncate_code(
    content: str, 
    max_tokens: int,
    preserve_structure: bool = True
) -> Tuple[str, int]:
    """
    智能截断代码内容，保留重要部分。
    
    策略:
    1. 保留所有类/函数定义行
    2. 保留所有import语句
    3. 保留docstring
    4. 截断函数体内部实现细节
    5. 使用 "... [N lines omitted] ..." 标记截断位置
    
    Args:
        content: 原始代码内容
        max_tokens: 最大token数
        preserve_structure: 是否保留代码结构（类/函数定义）
        
    Returns:
        (截断后的内容, 实际token数)
    """
    current_tokens = count_tokens(content)
    
    if current_tokens <= max_tokens:
        return content, current_tokens
    
    lines = content.split('\n')
    
    # 第一遍：计算每行的重要性
    line_info = []
    for i, line in enumerate(lines):
        importance = calculate_line_importance(line)
        line_info.append({
            'index': i,
            'content': line,
            'importance': importance,
            'tokens': count_tokens(line + '\n')
        })
    
    # 策略1: 保留高优先级行，逐步移除低优先级行
    result_lines = lines.copy()
    
    # 按重要性分组
    importance_groups = {}
    for info in line_info:
        imp = info['importance']
        if imp not in importance_groups:
            importance_groups[imp] = []
        importance_groups[imp].append(info)
    
    # 从最低优先级开始移除
    current_content = content
    current_tokens = count_tokens(current_content)
    
    for importance_level in sorted(importance_groups.keys()):
        if current_tokens <= max_tokens:
            break
        
        if importance_level >= 5:  # 不移除重要性 >= 5 的行
            break
        
        # 收集连续的低优先级行段落
        low_priority_lines = [info['index'] for info in importance_groups[importance_level]]
        
        if not low_priority_lines:
            continue
        
        # 找出连续的行段落
        segments = []
        start = low_priority_lines[0]
        end = start
        
        for idx in low_priority_lines[1:]:
            if idx == end + 1:
                end = idx
            else:
                if end - start >= 2:  # 至少3行才值得压缩
                    segments.append((start, end))
                start = idx
                end = idx
        
        if end - start >= 2:
            segments.append((start, end))
        
        # 从后向前替换，避免索引问题
        for start, end in reversed(segments):
            omitted_count = end - start + 1
            # 保留第一行和最后一行的缩进
            indent = len(result_lines[start]) - len(result_lines[start].lstrip())
            replacement = ' ' * indent + f'# ... [{omitted_count} lines omitted] ...'
            
            result_lines = result_lines[:start] + [replacement] + result_lines[end+1:]
        
        current_content = '\n'.join(result_lines)
        current_tokens = count_tokens(current_content)
    
    # 策略2: 如果仍然超出，进行更激进的截断
    if current_tokens > max_tokens:
        # 保留前N行和后M行
        target_tokens = max_tokens - 100  # 留出余量
        
        header_lines = []
        footer_lines = []
        header_tokens = 0
        footer_tokens = 0
        
        # 从头部添加
        for line in result_lines[:len(result_lines)//2]:
            line_tokens = count_tokens(line + '\n')
            if header_tokens + line_tokens < target_tokens * 0.6:
                header_lines.append(line)
                header_tokens += line_tokens
            else:
                break
        
        # 从尾部添加
        for line in reversed(result_lines[len(result_lines)//2:]):
            line_tokens = count_tokens(line + '\n')
            if footer_tokens + line_tokens < target_tokens * 0.3:
                footer_lines.insert(0, line)
                footer_tokens += line_tokens
            else:
                break
        
        omitted = len(result_lines) - len(header_lines) - len(footer_lines)
        result_lines = header_lines + [f'\n# ... [{omitted} lines omitted for brevity] ...\n'] + footer_lines
        current_content = '\n'.join(result_lines)
        current_tokens = count_tokens(current_content)
    
    return current_content, current_tokens


def truncate_file_content(
    file_content: str,
    max_tokens: int,
    component_ids: List[str] = None,
    components: Dict[str, Any] = None
) -> str:
    """
    截断文件内容，优先保留指定组件的代码。
    
    Args:
        file_content: 文件内容
        max_tokens: 最大token数
        component_ids: 需要保留的组件ID列表
        components: 组件字典
        
    Returns:
        截断后的内容
    """
    current_tokens = count_tokens(file_content)
    
    if current_tokens <= max_tokens:
        return file_content
    
    # 如果有组件信息，优先保留组件代码
    if component_ids and components:
        # 收集组件的行范围
        important_ranges = []
        for comp_id in component_ids:
            if comp_id in components:
                comp = components[comp_id]
                start_line = getattr(comp, 'start_line', 0)
                end_line = getattr(comp, 'end_line', 0)
                if start_line and end_line:
                    important_ranges.append((start_line - 1, end_line))  # 转换为0-indexed
        
        if important_ranges:
            lines = file_content.split('\n')
            result_lines = []
            
            # 添加文件头部（import语句等）
            for i, line in enumerate(lines[:50]):  # 前50行
                if re.match(r'^\s*(import|from|using|#include)', line):
                    result_lines.append(line)
                elif i < 10:  # 前10行始终保留
                    result_lines.append(line)
            
            # 添加组件代码
            for start, end in sorted(important_ranges):
                if start > 0 and result_lines:
                    result_lines.append(f'\n# ... [lines {len(result_lines)+1} - {start} omitted] ...\n')
                
                for i in range(start, min(end, len(lines))):
                    result_lines.append(lines[i])
            
            file_content = '\n'.join(result_lines)
    
    # 使用智能截断
    truncated, _ = smart_truncate_code(file_content, max_tokens)
    return truncated


def estimate_prompt_tokens(
    components: Dict[str, Any],
    component_ids: List[str],
    base_prompt_tokens: int = 2000
) -> int:
    """
    估算生成提示所需的token数。
    
    Args:
        components: 组件字典
        component_ids: 组件ID列表
        base_prompt_tokens: 基础提示token数
        
    Returns:
        估算的总token数
    """
    total = base_prompt_tokens
    
    files_seen = set()
    for comp_id in component_ids:
        if comp_id in components:
            comp = components[comp_id]
            file_path = getattr(comp, 'file_path', '')
            
            if file_path not in files_seen:
                files_seen.add(file_path)
                source = getattr(comp, 'source_code', '')
                total += count_tokens(source) if source else 0
    
    return total


# ------------------------------------------------------------
# ---------------------- Mermaid Validation -----------------
# ------------------------------------------------------------

async def validate_mermaid_diagrams(md_file_path: str, relative_path: str) -> str:
    """
    Validate all Mermaid diagrams in a markdown file.
    
    Args:
        md_file_path: Path to the markdown file to check
        relative_path: Relative path to the markdown file
    Returns:
        "All mermaid diagrams are syntax correct" if all diagrams are valid,
        otherwise returns error message with details about invalid diagrams
    """

    try:
        # Read the markdown file
        file_path = Path(md_file_path)
        if not file_path.exists():
            return f"Error: File '{md_file_path}' does not exist"
        
        content = file_path.read_text(encoding='utf-8')
        
        # Extract all mermaid code blocks
        mermaid_blocks = extract_mermaid_blocks(content)
        
        if not mermaid_blocks:
            return "No mermaid diagrams found in the file"
        
        # Validate each mermaid diagram sequentially to avoid segfaults
        errors = []
        for i, (line_start, diagram_content) in enumerate(mermaid_blocks, 1):
            error_msg = await validate_single_diagram(diagram_content, i, line_start)
            if error_msg:
                errors.append("\n")
                errors.append(error_msg)
        
        # if errors:
        #     logger.debug(f"Mermaid syntax errors found in file: {md_file_path}: {errors}")
        
        if errors:
            return "Mermaid syntax errors found in file: " + relative_path + "\n" + "\n".join(errors)
        else:
            return "All mermaid diagrams in file: " + relative_path + " are syntax correct"
            
    except Exception as e:
        return f"Error processing file: {str(e)}"


def extract_mermaid_blocks(content: str) -> List[Tuple[int, str]]:
    """
    Extract all mermaid code blocks from markdown content.
    
    Returns:
        List of tuples containing (line_number, diagram_content)
    """
    mermaid_blocks = []
    lines = content.split('\n')
    i = 0
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for mermaid code block start
        if line == '```mermaid' or line.startswith('```mermaid'):
            start_line = i + 1
            diagram_lines = []
            i += 1
            
            # Collect lines until we find the closing ```
            while i < len(lines):
                if lines[i].strip() == '```':
                    break
                diagram_lines.append(lines[i])
                i += 1
            
            if diagram_lines:  # Only add non-empty diagrams
                diagram_content = '\n'.join(diagram_lines)
                mermaid_blocks.append((start_line, diagram_content))
        
        i += 1
    
    return mermaid_blocks


async def validate_single_diagram(diagram_content: str, diagram_num: int, line_start: int) -> str:
    """
    Validate a single mermaid diagram.
    
    Args:
        diagram_content: The mermaid diagram content
        diagram_num: Diagram number for error reporting
        line_start: Starting line number in the file
        
    Returns:
        Error message if invalid, empty string if valid
    """
    import sys
    import os
    from io import StringIO

    core_error = ""
    
    try:
        from mermaid_parser.parser import parse_mermaid_py
        # logger.debug("Using mermaid-parser-py to validate mermaid diagrams")
    
        try:
            # Redirect stderr to suppress mermaid parser JavaScript errors
            old_stderr = sys.stderr
            sys.stderr = open(os.devnull, 'w')
            
            try:
                json_output = await parse_mermaid_py(diagram_content)
            finally:
                # Restore stderr
                sys.stderr.close()
                sys.stderr = old_stderr
        except Exception as e:
            error_str = str(e)
            
            # Extract the core error information from the exception message
            # Look for the pattern that contains "Parse error on line X:"
            error_pattern = r"Error:(.*?)(?=Stack Trace:|$)"
            match = re.search(error_pattern, error_str, re.DOTALL)
            
            if match:
                core_error = match.group(0).strip()
                core_error = core_error
            else:
                logger.error(f"No match found for error pattern, fallback to mermaid-py\n{error_str}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise Exception(error_str)

    except Exception as e:
        logger.warning("Using mermaid-py to validate mermaid diagrams")
        try:
            import mermaid as md
            # Create Mermaid object and check response
            render = md.Mermaid(diagram_content)
            core_error = render.svg_response.text
            
        except Exception as e:
            return f"  Diagram {diagram_num}: Exception during validation - {str(e)}"

    # Check if response indicates a parse error
    if core_error:
        # Extract line number from parse error and calculate actual line in markdown file
        line_match = re.search(r'line (\d+)', core_error)
        if line_match:
            error_line_in_diagram = int(line_match.group(1))
            actual_line_in_file = line_start + error_line_in_diagram
            newline = '\n'
            return f"Diagram {diagram_num}: Parse error on line {actual_line_in_file}:{newline}{newline.join(core_error.split(newline)[1:])}"
        else:
            return f"Diagram {diagram_num}: {core_error}"
    
    return ""  # No error


# ------------------------------------------------------------
# ---------------------- Documentation Validation ------------
# ------------------------------------------------------------

def extract_code_references(doc_content: str) -> List[str]:
    """
    从文档中提取代码引用（类名、函数名等）。
    
    Args:
        doc_content: 文档内容
        
    Returns:
        引用的代码名称列表
    """
    references = set()
    
    # 匹配反引号中的标识符（如 `ClassName`, `function_name`）
    backtick_pattern = r'`([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)`'
    for match in re.finditer(backtick_pattern, doc_content):
        ref = match.group(1)
        # 过滤常见的非代码引用
        if ref.lower() not in {'true', 'false', 'none', 'null', 'undefined', 'self', 'this'}:
            references.add(ref)
    
    # 匹配类图中的类名
    class_diagram_pattern = r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    for match in re.finditer(class_diagram_pattern, doc_content):
        references.add(match.group(1))
    
    return list(references)


def extract_markdown_links(doc_content: str) -> List[str]:
    """
    从文档中提取Markdown链接目标。
    
    Args:
        doc_content: 文档内容
        
    Returns:
        链接目标列表
    """
    links = []
    
    # 匹配 [text](url) 格式的链接
    link_pattern = r'\[([^\]]*)\]\(([^)]+)\)'
    for match in re.finditer(link_pattern, doc_content):
        url = match.group(2)
        # 只保留本地文件链接
        if not url.startswith(('http://', 'https://', '#')):
            links.append(url)
    
    return links


async def validate_generated_documentation(
    doc_content: str,
    components: Dict[str, Any],
    module_name: str,
    working_dir: str = None
) -> Tuple[bool, List[str]]:
    """
    验证生成的文档与代码是否一致。
    
    检查项：
    1. 文档中提及的类/函数是否真实存在
    2. Mermaid图表语法是否正确
    3. 链接目标文件是否存在
    4. 文档结构是否完整
    
    Args:
        doc_content: 文档内容
        components: 组件字典
        module_name: 模块名称
        working_dir: 工作目录（用于检查链接）
        
    Returns:
        (是否通过验证, 问题列表)
    """
    import os
    
    issues = []
    
    # 1. 检查代码引用
    references = extract_code_references(doc_content)
    component_names = set()
    
    for comp_id in components:
        # 添加完整ID
        component_names.add(comp_id)
        # 添加简短名称
        parts = comp_id.split('.')
        if parts:
            component_names.add(parts[-1])  # 最后一部分（类/函数名）
            if len(parts) >= 2:
                component_names.add('.'.join(parts[-2:]))  # 最后两部分
    
    for ref in references:
        # 检查是否存在匹配
        found = False
        for comp_name in component_names:
            if ref in comp_name or comp_name.endswith(ref):
                found = True
                break
        
        if not found and len(ref) > 3:  # 忽略太短的引用
            # 可能是外部依赖，记录警告而非错误
            issues.append(f"[WARNING] Referenced '{ref}' not found in codebase (may be external)")
    
    # 2. 验证Mermaid图表
    mermaid_blocks = extract_mermaid_blocks(doc_content)
    for i, (line_start, diagram_content) in enumerate(mermaid_blocks, 1):
        error_msg = await validate_single_diagram(diagram_content, i, line_start)
        if error_msg:
            issues.append(f"[ERROR] {error_msg}")
    
    # 3. 检查链接
    if working_dir:
        links = extract_markdown_links(doc_content)
        for link in links:
            link_path = os.path.join(working_dir, link)
            if not os.path.exists(link_path):
                issues.append(f"[WARNING] Broken link: {link}")
    
    # 4. 检查文档结构
    structure_checks = [
        ('# ', 'Missing main heading'),
        ('## ', 'Missing section headings'),
    ]
    
    for pattern, message in structure_checks:
        if pattern not in doc_content:
            issues.append(f"[WARNING] {message}")
    
    # 判断是否通过（只有ERROR才算失败）
    has_errors = any('[ERROR]' in issue for issue in issues)
    
    return not has_errors, issues


def validate_documentation_sync(
    doc_content: str,
    components: Dict[str, Any],
    module_name: str,
    working_dir: str = None
) -> Tuple[bool, List[str]]:
    """
    同步版本的文档验证。
    
    Args:
        doc_content: 文档内容
        components: 组件字典
        module_name: 模块名称
        working_dir: 工作目录
        
    Returns:
        (是否通过验证, 问题列表)
    """
    import asyncio
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        validate_generated_documentation(doc_content, components, module_name, working_dir)
    )


def generate_validation_report(
    working_dir: str,
    components: Dict[str, Any]
) -> str:
    """
    生成整个文档目录的验证报告。
    
    Args:
        working_dir: 文档目录
        components: 组件字典
        
    Returns:
        验证报告字符串
    """
    import os
    
    report_lines = ["# Documentation Validation Report", ""]
    
    total_files = 0
    files_with_errors = 0
    files_with_warnings = 0
    
    # 遍历所有.md文件
    for filename in os.listdir(working_dir):
        if not filename.endswith('.md'):
            continue
        
        total_files += 1
        filepath = os.path.join(working_dir, filename)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            passed, issues = validate_documentation_sync(
                content, 
                components, 
                filename.replace('.md', ''),
                working_dir
            )
            
            errors = [i for i in issues if '[ERROR]' in i]
            warnings = [i for i in issues if '[WARNING]' in i]
            
            if errors:
                files_with_errors += 1
            if warnings:
                files_with_warnings += 1
            
            if issues:
                report_lines.append(f"## {filename}")
                report_lines.append(f"Status: {'❌ FAILED' if errors else '⚠️ WARNINGS'}")
                for issue in issues:
                    report_lines.append(f"  - {issue}")
                report_lines.append("")
        
        except Exception as e:
            report_lines.append(f"## {filename}")
            report_lines.append(f"Status: ❌ ERROR reading file: {e}")
            report_lines.append("")
            files_with_errors += 1
    
    # 添加摘要
    summary = [
        "",
        "---",
        "## Summary",
        f"- Total files: {total_files}",
        f"- Files with errors: {files_with_errors}",
        f"- Files with warnings: {files_with_warnings}",
        f"- Files OK: {total_files - files_with_errors - files_with_warnings}"
    ]
    
    report_lines = summary + ["", "---", ""] + report_lines
    
    return "\n".join(report_lines)


if __name__ == "__main__":
    # Test with the provided file
    import asyncio
    test_file = "output/docs/SWE_agent-docs/agent_hooks.md"
    result = asyncio.run(validate_mermaid_diagrams(test_file, "agent_hooks.md"))
    print(result)