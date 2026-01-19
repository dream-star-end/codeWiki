"""
MCP Generator Service - 自动生成 MCP Server 供 AI 调用

功能：
1. 为已分析的代码仓库生成 MCP Server
2. 提供代码搜索、文件查看、符号导航等工具
3. 支持 Cursor、Claude Desktop 等 AI IDE 调用
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from app.services.db import (
    get_repo_root,
    read_summary,
    read_modules,
    read_symbols_by_repo,
    read_file_edges,
)
from app.services.code_browser import get_file_content, get_file_tree_for_repo, file_node_to_dict
from app.services.symbol_navigator import search_symbols, get_symbol_definition, get_file_outline
from app.services.faiss_index import search_index
from app.services.learning_path import find_entry_points, get_learning_path


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPServerConfig:
    """MCP Server 配置"""
    name: str
    version: str
    description: str
    tools: List[MCPTool]


# 定义 MCP 工具集
MCP_TOOLS = [
    MCPTool(
        name="search_code",
        description="语义搜索代码库，找到与查询相关的代码片段。支持自然语言查询，返回最相关的代码及其位置。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询，可以是自然语言描述或关键词"
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果数量，默认5",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    ),
    MCPTool(
        name="get_file_content",
        description="获取指定文件的完整内容，包括代码和符号信息。",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件的相对路径"
                }
            },
            "required": ["file_path"]
        }
    ),
    MCPTool(
        name="get_file_chunk",
        description="按行获取文件内容分块，适合大文件阅读。",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件的相对路径"
                },
                "offset": {
                    "type": "integer",
                    "description": "起始行（1-based）",
                    "default": 1
                },
                "limit": {
                    "type": "integer",
                    "description": "行数",
                    "default": 200
                }
            },
            "required": ["file_path"]
        }
    ),
    MCPTool(
        name="search_in_file",
        description="在单文件内搜索文本，返回匹配行及上下文。",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件的相对路径"
                },
                "query": {
                    "type": "string",
                    "description": "搜索关键字或正则表达式"
                },
                "context": {
                    "type": "integer",
                    "description": "上下文行数",
                    "default": 2
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回数量",
                    "default": 20
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否区分大小写",
                    "default": False
                },
                "use_regex": {
                    "type": "boolean",
                    "description": "是否使用正则表达式",
                    "default": False
                }
            },
            "required": ["file_path", "query"]
        }
    ),
    MCPTool(
        name="get_file_tree",
        description="获取代码仓库的文件目录结构，了解项目组织方式。",
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    MCPTool(
        name="search_symbols",
        description="搜索代码中的类、函数、方法等符号定义。",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "符号名称（支持模糊匹配）"
                },
                "kind": {
                    "type": "string",
                    "description": "符号类型过滤：class, function, method",
                    "enum": ["class", "function", "method"]
                }
            },
            "required": ["query"]
        }
    ),
    MCPTool(
        name="get_symbol_definition",
        description="获取符号的定义位置和详细信息，用于跳转到定义。",
        input_schema={
            "type": "object",
            "properties": {
                "symbol_id": {
                    "type": "string",
                    "description": "符号的唯一标识符"
                }
            },
            "required": ["symbol_id"]
        }
    ),
    MCPTool(
        name="get_file_outline",
        description="获取文件的符号大纲，包含所有类、函数、方法的层级结构。",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件的相对路径"
                }
            },
            "required": ["file_path"]
        }
    ),
    MCPTool(
        name="get_project_summary",
        description="获取项目概览，包括语言、模块结构、入口点等信息。",
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    MCPTool(
        name="get_modules",
        description="获取项目的模块列表及其层级结构。",
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    MCPTool(
        name="get_dependencies",
        description="获取文件或模块之间的依赖关系图。",
        input_schema={
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "可选，指定文件路径查看其依赖"
                }
            },
            "required": []
        }
    ),
    MCPTool(
        name="get_entry_points",
        description="获取项目的入口点文件，了解从哪里开始阅读代码。",
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    MCPTool(
        name="get_learning_path",
        description="获取推荐的代码阅读顺序和学习路径。",
        input_schema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
]


def generate_mcp_server_code(repo_id: str, port: int = 9100) -> str:
    """
    生成独立的 MCP Server Python 代码（SSE 远程连接模式）
    
    Args:
        repo_id: 仓库ID
        port: SSE 服务端口
    
    Returns:
        MCP Server 的 Python 代码
    """
    repo_root = get_repo_root(repo_id)
    summary = read_summary(repo_id)
    
    repo_name = Path(repo_root).name if repo_root else repo_id
    languages = summary.get("languages", []) if summary else []
    
    code = f'''#!/usr/bin/env python3
"""
MCP Server for {repo_name} (SSE Mode)
Auto-generated by Codebase Analyzer

Languages: {', '.join(languages)}
Repo ID: {repo_id}
Port: {port}

Usage:
1. Install dependencies: pip install mcp httpx starlette uvicorn
2. Run: python mcp_server_{repo_id}.py
3. Connect via SSE at http://localhost:{port}/sse
"""
import asyncio
import json
import httpx
import os
from contextlib import asynccontextmanager

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

# Configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
REPO_ID = "{repo_id}"
PORT = int(os.getenv("MCP_PORT", "{port}"))

server = Server("{repo_name}-codebase")
sse = SseServerTransport("/messages/")


async def call_api(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    """Call the Codebase Analyzer API"""
    async with httpx.AsyncClient() as client:
        url = f"{{API_BASE}}{{endpoint}}"
        try:
            if method == "GET":
                response = await client.get(url, timeout=30.0)
            else:
                response = await client.post(url, json=data, timeout=30.0)
            
            if response.status_code >= 400:
                return {{"error": f"HTTP {{response.status_code}}: {{response.text[:200]}}"}}
            
            content = response.text
            if not content or not content.strip():
                return {{"error": "Empty response from API"}}
            
            return response.json()
        except httpx.RequestError as e:
            return {{"error": f"Request failed: {{str(e)}}"}}
        except Exception as e:
            return {{"error": f"API call failed: {{str(e)}}"}}


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="search_code",
            description="语义搜索代码库，找到与查询相关的代码片段",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "query": {{"type": "string", "description": "搜索查询"}},
                    "top_k": {{"type": "integer", "description": "返回数量", "default": 5}}
                }},
                "required": ["query"]
            }}
        ),
        Tool(
            name="get_file_content",
            description="获取指定文件的完整内容",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "file_path": {{"type": "string", "description": "文件路径"}}
                }},
                "required": ["file_path"]
            }}
        ),
        Tool(
            name="get_file_chunk",
            description="按行获取文件内容分块",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "file_path": {{"type": "string", "description": "文件路径"}},
                    "offset": {{"type": "integer", "description": "起始行", "default": 1}},
                    "limit": {{"type": "integer", "description": "行数", "default": 200}}
                }},
                "required": ["file_path"]
            }}
        ),
        Tool(
            name="get_file_tree",
            description="获取项目文件目录结构",
            inputSchema={{"type": "object", "properties": {{}}, "required": []}}
        ),
        Tool(
            name="search_in_file",
            description="在单文件内搜索文本",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "file_path": {{"type": "string", "description": "文件路径"}},
                    "query": {{"type": "string", "description": "搜索查询"}},
                    "context": {{"type": "integer", "description": "上下文行数", "default": 2}},
                    "limit": {{"type": "integer", "description": "最大返回数量", "default": 20}},
                    "case_sensitive": {{"type": "boolean", "description": "区分大小写", "default": False}},
                    "use_regex": {{"type": "boolean", "description": "使用正则", "default": False}}
                }},
                "required": ["file_path", "query"]
            }}
        ),
        Tool(
            name="search_symbols",
            description="搜索代码符号（类、函数、方法）",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "query": {{"type": "string", "description": "符号名称"}},
                    "kind": {{"type": "string", "description": "类型过滤", "enum": ["class", "function", "method"]}}
                }},
                "required": ["query"]
            }}
        ),
        Tool(
            name="get_project_summary",
            description="获取项目概览信息",
            inputSchema={{"type": "object", "properties": {{}}, "required": []}}
        ),
        Tool(
            name="get_modules",
            description="获取项目模块列表",
            inputSchema={{"type": "object", "properties": {{}}, "required": []}}
        ),
        Tool(
            name="get_file_outline",
            description="获取文件符号大纲",
            inputSchema={{
                "type": "object",
                "properties": {{
                    "file_path": {{"type": "string", "description": "文件路径"}}
                }},
                "required": ["file_path"]
            }}
        ),
        Tool(
            name="get_entry_points",
            description="获取项目入口点",
            inputSchema={{"type": "object", "properties": {{}}, "required": []}}
        ),
        Tool(
            name="get_learning_path",
            description="获取推荐学习路径",
            inputSchema={{"type": "object", "properties": {{}}, "required": []}}
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "search_code":
            result = await call_api(
                f"/repos/{{REPO_ID}}/search",
                method="POST",
                data={{"query": arguments["query"], "top_k": arguments.get("top_k", 5)}}
            )
            
        elif name == "get_file_content":
            file_path = arguments["file_path"]
            result = await call_api(f"/repos/{{REPO_ID}}/files/{{file_path}}")
            
        elif name == "get_file_chunk":
            file_path = arguments["file_path"]
            offset = arguments.get("offset", 1)
            limit = arguments.get("limit", 200)
            result = await call_api(
                f"/repos/{{REPO_ID}}/files/chunk?file_path={{file_path}}&offset={{offset}}&limit={{limit}}"
            )
            
        elif name == "get_file_tree":
            result = await call_api(f"/repos/{{REPO_ID}}/files")
            
        elif name == "search_in_file":
            file_path = arguments["file_path"]
            query = arguments["query"]
            context = arguments.get("context", 2)
            limit = arguments.get("limit", 20)
            case_sensitive = arguments.get("case_sensitive", False)
            use_regex = arguments.get("use_regex", False)
            result = await call_api(
                f"/repos/{{REPO_ID}}/files/search-in-file?file_path={{file_path}}&q={{query}}&context={{context}}&limit={{limit}}&case_sensitive={{case_sensitive}}&use_regex={{use_regex}}"
            )
            
        elif name == "search_symbols":
            query = arguments["query"]
            kind = arguments.get("kind", "")
            url = f"/repos/{{REPO_ID}}/symbols?q={{query}}"
            if kind:
                url += f"&kind={{kind}}"
            result = await call_api(url)
            
        elif name == "get_project_summary":
            result = await call_api(f"/repos/{{REPO_ID}}/summary")
            
        elif name == "get_modules":
            result = await call_api(f"/repos/{{REPO_ID}}/modules")
            
        elif name == "get_file_outline":
            file_path = arguments["file_path"]
            result = await call_api(f"/repos/{{REPO_ID}}/outline/{{file_path}}")
            
        elif name == "get_entry_points":
            result = await call_api(f"/repos/{{REPO_ID}}/entry-points")
            
        elif name == "get_learning_path":
            result = await call_api(f"/repos/{{REPO_ID}}/learning-path")
            
        else:
            result = {{"error": f"Unknown tool: {{name}}"}}
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
        
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {{str(e)}}")]


async def handle_sse(request):
    """Handle SSE connection"""
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )


async def handle_messages(request):
    """Handle POST messages from client"""
    await sse.handle_post_message(request.scope, request.receive, request._send)


async def health_check(request):
    """Health check endpoint"""
    return JSONResponse({{"status": "ok", "repo_id": REPO_ID}})


app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages/", endpoint=handle_messages, methods=["POST"]),
        Route("/health", endpoint=health_check),
    ]
)


if __name__ == "__main__":
    import uvicorn
    print(f"Starting MCP Server for {{REPO_ID}} on port {{PORT}}")
    print(f"SSE endpoint: http://localhost:{{PORT}}/sse")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
'''
    return code


def generate_cursor_mcp_config(repo_id: str, port: int = 9100, host: str = "localhost") -> Dict[str, Any]:
    """
    生成 Cursor MCP 配置（SSE 远程连接模式）
    
    Args:
        repo_id: 仓库ID
        port: MCP Server SSE 端口
        host: MCP Server 主机地址
    
    Returns:
        Cursor MCP 配置 JSON
    """
    repo_root = get_repo_root(repo_id)
    repo_name = Path(repo_root).name if repo_root else repo_id
    
    return {
        "mcpServers": {
            f"{repo_name}-codebase": {
                "url": f"http://{host}:{port}/sse"
            }
        }
    }


def generate_claude_desktop_config(repo_id: str, port: int = 9100, host: str = "localhost") -> Dict[str, Any]:
    """
    生成 Claude Desktop MCP 配置（SSE 远程连接模式）
    """
    repo_root = get_repo_root(repo_id)
    repo_name = Path(repo_root).name if repo_root else repo_id
    
    return {
        "mcpServers": {
            f"{repo_name}-codebase": {
                "url": f"http://{host}:{port}/sse"
            }
        }
    }


def save_mcp_server(repo_id: str, output_dir: Optional[str] = None, port: int = 9100, host: str = "localhost") -> Dict[str, Any]:
    """
    保存 MCP Server 文件到指定目录
    
    Args:
        repo_id: 仓库ID
        output_dir: 输出目录，默认为 workspace/mcp
        port: SSE 服务端口
        host: 主机地址（用于生成配置）
    
    Returns:
        生成的文件路径信息和端口
    """
    if output_dir is None:
        output_dir = str(Path(__file__).resolve().parents[2] / "workspace" / "mcp")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成 MCP Server 代码
    server_code = generate_mcp_server_code(repo_id, port)
    server_file = output_path / f"mcp_server_{repo_id}.py"
    server_file.write_text(server_code, encoding="utf-8")
    
    # 生成 Cursor 配置
    cursor_config = generate_cursor_mcp_config(repo_id, port, host)
    cursor_file = output_path / f"cursor_config_{repo_id}.json"
    cursor_file.write_text(json.dumps(cursor_config, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # 生成 Claude Desktop 配置
    claude_config = generate_claude_desktop_config(repo_id, port, host)
    claude_file = output_path / f"claude_config_{repo_id}.json"
    claude_file.write_text(json.dumps(claude_config, indent=2, ensure_ascii=False), encoding="utf-8")
    
    # 生成 README
    readme = generate_mcp_readme(repo_id, port, host)
    readme_file = output_path / f"README_{repo_id}.md"
    readme_file.write_text(readme, encoding="utf-8")
    
    return {
        "server_file": str(server_file),
        "cursor_config": str(cursor_file),
        "claude_config": str(claude_file),
        "readme": str(readme_file),
        "port": port,
        "sse_url": f"http://{host}:{port}/sse",
    }


def generate_mcp_readme(repo_id: str, port: int = 9100, host: str = "localhost") -> str:
    """生成 MCP 使用说明（SSE 远程连接模式）"""
    repo_root = get_repo_root(repo_id)
    repo_name = Path(repo_root).name if repo_root else repo_id
    
    return f'''# {repo_name} Codebase MCP Server (SSE 模式)

这是一个自动生成的 MCP Server，支持 **SSE 远程连接**，让 AI 可以直接查询和理解 `{repo_name}` 代码库。

## 功能

- 🔍 **代码搜索** - 语义搜索找到相关代码
- 📄 **文件查看** - 获取任意文件内容
- 🔗 **符号导航** - 查找类、函数、方法定义
- 📊 **项目结构** - 了解模块和依赖关系
- 📚 **学习路径** - 获取推荐阅读顺序

## 连接信息

- **SSE 端点**: `http://{host}:{port}/sse`
- **健康检查**: `http://{host}:{port}/health`

## 安装依赖（手动运行时需要）

```bash
pip install mcp httpx starlette uvicorn
```

## 使用方法

### 方式一：系统自动管理（推荐）

在 Wiki 详情页点击「启动 MCP 服务」即可，服务将自动在后台运行。

### 方式二：手动启动

```bash
# 设置后端地址（可选，默认 http://localhost:8000）
export API_BASE="http://localhost:8000"
export MCP_PORT="{port}"

# 启动服务
python mcp_server_{repo_id}.py
```

## 客户端配置

### Cursor

将以下内容添加到 Cursor MCP 配置：

**Windows**: `%APPDATA%\\Cursor\\User\\globalStorage\\cursor.mcp\\config.json`
**macOS**: `~/Library/Application Support/Cursor/User/globalStorage/cursor.mcp/config.json`

```json
{{
  "mcpServers": {{
    "{repo_name}-codebase": {{
      "url": "http://{host}:{port}/sse"
    }}
  }}
}}
```

### Claude Desktop

将以下内容添加到 Claude Desktop 配置：

**Windows**: `%APPDATA%\\Claude\\claude_desktop_config.json`
**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{{
  "mcpServers": {{
    "{repo_name}-codebase": {{
      "url": "http://{host}:{port}/sse"
    }}
  }}
}}
```

### 自定义 MCP Client

任何支持 SSE 传输的 MCP 客户端都可以连接：

```json
{{
  "url": "http://{host}:{port}/sse",
  "transport": "sse"
}}
```

## 可用工具

| 工具名 | 说明 |
|--------|------|
| `search_code` | 语义搜索代码 |
| `get_file_content` | 获取文件内容 |
| `get_file_chunk` | 分块读取文件 |
| `get_file_tree` | 获取目录结构 |
| `search_in_file` | 文件内搜索 |
| `search_symbols` | 搜索符号定义 |
| `get_project_summary` | 项目概览 |
| `get_modules` | 模块列表 |
| `get_file_outline` | 文件大纲 |
| `get_entry_points` | 入口点 |
| `get_learning_path` | 学习路径 |

## 示例

在 Cursor 中，AI 可以这样使用：

```
我想了解这个项目的整体结构
→ AI 调用 get_project_summary 和 get_modules

帮我找到处理用户认证的代码
→ AI 调用 search_code("用户认证")

这个函数是做什么的？
→ AI 调用 get_file_content 查看代码
```

## 注意事项

- 确保 Codebase Analyzer 后端服务运行在 `http://localhost:8000`
- MCP Server 启动后，配置 Cursor/Claude Desktop 即可使用
- 配置后重启 IDE 生效
- 如遇问题检查 `http://{host}:{port}/health`
'''


def get_mcp_tools_list() -> List[Dict[str, Any]]:
    """获取 MCP 工具列表（用于 API 展示）"""
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.input_schema,
        }
        for tool in MCP_TOOLS
    ]
