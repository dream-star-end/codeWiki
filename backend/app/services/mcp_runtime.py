from __future__ import annotations

import os
import sys
import subprocess
import json
import platform
import signal
import time
from pathlib import Path
from typing import Dict, Optional, Any

from app.services.mcp_generator import save_mcp_server
import requests


# 进程和端口管理
_processes: Dict[str, subprocess.Popen] = {}
_port_registry: Dict[str, int] = {}  # repo_id -> port

# 端口范围配置
MCP_PORT_START = 9100
MCP_PORT_END = 9199

# 持久化文件路径
_port_file = Path(__file__).resolve().parents[2] / "workspace" / "mcp" / "port_registry.json"


def _load_port_registry():
    """加载端口注册表"""
    global _port_registry
    if _port_file.exists():
        try:
            _port_registry = json.loads(_port_file.read_text(encoding="utf-8"))
        except Exception:
            _port_registry = {}


def _save_port_registry():
    """保存端口注册表"""
    _port_file.parent.mkdir(parents=True, exist_ok=True)
    _port_file.write_text(json.dumps(_port_registry, indent=2), encoding="utf-8")


def _allocate_port(repo_id: str) -> int:
    """为 repo 分配端口"""
    _load_port_registry()
    
    # 如果已分配，返回现有端口
    if repo_id in _port_registry:
        return _port_registry[repo_id]
    
    # 分配新端口
    used_ports = set(_port_registry.values())
    for port in range(MCP_PORT_START, MCP_PORT_END + 1):
        if port not in used_ports:
            _port_registry[repo_id] = port
            _save_port_registry()
            return port
    
    # 端口用尽，抛出异常
    raise RuntimeError(f"No available ports in range {MCP_PORT_START}-{MCP_PORT_END}")


def _get_port(repo_id: str) -> Optional[int]:
    """获取 repo 的端口"""
    _load_port_registry()
    return _port_registry.get(repo_id)


def _is_running(proc: Optional[subprocess.Popen]) -> bool:
    return proc is not None and proc.poll() is None


def _get_health_info(port: Optional[int], host: str = "localhost") -> Optional[Dict[str, Any]]:
    """获取 MCP 健康检查信息"""
    if not port:
        return None
    try:
        res = requests.get(f"http://{host}:{port}/health", timeout=0.5)
        if res.status_code != 200:
            return None
        return res.json() if res.content else {"status": "ok"}
    except Exception:
        return None


def _is_port_healthy(port: Optional[int], host: str = "localhost") -> bool:
    """通过健康检查判断端口上的 MCP 是否仍在运行"""
    return _get_health_info(port, host=host) is not None


def _find_pids_by_port(port: int) -> set[int]:
    """根据端口查找监听进程 PID（跨平台尽力而为）"""
    pids: set[int] = set()
    system = platform.system().lower()
    try:
        if system == "windows":
            result = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True,
                text=True,
                check=False,
            )
            for line in (result.stdout or "").splitlines():
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                local_addr = parts[1]
                state = parts[3]
                pid = parts[4]
                if state.upper() != "LISTENING":
                    continue
                if local_addr.endswith(f":{port}"):
                    try:
                        pids.add(int(pid))
                    except Exception:
                        pass
        else:
            result = subprocess.run(
                ["lsof", "-i", f":{port}", "-sTCP:LISTEN", "-t"],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.stdout:
                for line in result.stdout.splitlines():
                    try:
                        pids.add(int(line.strip()))
                    except Exception:
                        pass
            if not pids:
                result = subprocess.run(
                    ["ss", "-lptn"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                for line in (result.stdout or "").splitlines():
                    if f":{port}" not in line:
                        continue
                    if "pid=" in line:
                        try:
                            pid_part = line.split("pid=", 1)[1]
                            pid_str = pid_part.split(",", 1)[0]
                            pids.add(int(pid_str))
                        except Exception:
                            pass
    except Exception:
        return set()
    return pids


def _kill_pid(pid: int) -> bool:
    """尝试终止指定 PID"""
    system = platform.system().lower()
    try:
        if system == "windows":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], check=False, capture_output=True)
            return True
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.3)
        try:
            os.kill(pid, 0)
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
        return True
    except Exception:
        return False


def start_mcp_server(repo_id: str, api_base: Optional[str] = None, host: str = "localhost") -> Dict[str, Any]:
    """
    启动 MCP Server（SSE 模式）
    
    Args:
        repo_id: 仓库ID
        api_base: Codebase Analyzer 后端地址
        host: 主机地址（用于生成配置）
    
    Returns:
        包含运行状态、PID、端口、SSE URL 的字典
    """
    existing = _processes.get(repo_id)
    if _is_running(existing):
        port = _get_port(repo_id) or MCP_PORT_START
        return {
            "running": True,
            "pid": existing.pid,
            "port": port,
            "sse_url": f"http://{host}:{port}/sse",
        }

    # 分配端口
    port = _allocate_port(repo_id)
    
    # 检查 MCP Server 文件是否已存在，避免重复生成触发热重载
    mcp_dir = Path(__file__).resolve().parents[2] / "workspace" / "mcp"
    server_file = mcp_dir / f"mcp_server_{repo_id}.py"
    
    if not server_file.exists():
        # 只在文件不存在时生成
        files = save_mcp_server(repo_id, port=port, host=host)
        if not files.get("server_file"):
            return {"running": False, "error": "server_file_not_found"}
    
    server_file = str(server_file)  # 转为字符串供后续使用

    env = os.environ.copy()
    if api_base:
        env["API_BASE"] = api_base
    env["MCP_PORT"] = str(port)

    creationflags = 0
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    # 将输出写到日志文件，方便调试
    log_dir = Path(__file__).resolve().parents[2] / "workspace" / "mcp" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"mcp_{repo_id}.log"
    
    log_handle = open(log_file, "a", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, server_file],
        cwd=str(Path(server_file).parent),
        env=env,
        stdout=log_handle,
        stderr=log_handle,
        creationflags=creationflags,
    )
    _processes[repo_id] = proc
    
    return {
        "running": True,
        "pid": proc.pid,
        "port": port,
        "sse_url": f"http://{host}:{port}/sse",
    }


def stop_mcp_server(repo_id: str) -> Dict[str, Any]:
    """停止 MCP Server"""
    proc = _processes.get(repo_id)
    if not _is_running(proc):
        port = _get_port(repo_id)
        health = _get_health_info(port)
        # 仅当健康检查确认是本 repo 的服务时，才尝试按端口杀进程
        if port and health and health.get("repo_id") == repo_id:
            for pid in _find_pids_by_port(port):
                _kill_pid(pid)
            if _is_port_healthy(port):
                return {"running": True, "port": port, "error": "failed_to_stop_external"}
        _processes.pop(repo_id, None)
        return {"running": False, "port": port}

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass

    _processes.pop(repo_id, None)
    return {"running": False}


def get_mcp_status(repo_id: str, host: str = "localhost") -> Dict[str, Any]:
    """
    获取 MCP Server 状态
    
    Returns:
        包含运行状态、PID、端口、SSE URL 的字典
    """
    proc = _processes.get(repo_id)
    port = _get_port(repo_id)
    
    if _is_running(proc):
        return {
            "running": True,
            "pid": proc.pid,
            "port": port,
            "sse_url": f"http://{host}:{port}/sse" if port else None,
        }

    # 进程记录丢失时，尝试通过健康检查判断服务是否仍在运行
    if _is_port_healthy(port, host=host):
        return {
            "running": True,
            "pid": None,
            "port": port,
            "sse_url": f"http://{host}:{port}/sse" if port else None,
        }

    _processes.pop(repo_id, None)
    return {
        "running": False,
        "port": port,
        "sse_url": f"http://{host}:{port}/sse" if port else None,
    }
