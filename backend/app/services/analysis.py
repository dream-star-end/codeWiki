from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List, Tuple
import time
from pathlib import Path

from app.services.parsers import Symbol
from app.services.module_tree_codewiki import module_tree_from_codewiki
from app.services.chunking import build_chunks_from_docs
from app.services.faiss_index import build_index
from app.services.db import (
    upsert_repo,
    insert_files,
    insert_symbols,
    insert_edges,
    insert_file_edges,
    insert_modules,
    insert_module_nodes,
    insert_docs,
    get_repo_checkpoint,
    set_repo_checkpoint,
    record_token_usage,
)
from app.core.logging import get_job_logger
from app.services.codewiki_adapter import (
    analyze_with_codewiki,
    discover_files_with_codewiki,
    generate_docs_with_codewiki,
    load_docs_from_codewiki,
)


def _symbols_from_codewiki(symbols_data: List[Dict]) -> Tuple[List[Tuple[str, Symbol]], Dict[str, Symbol]]:
    symbol_pairs: List[Tuple[str, Symbol]] = []
    symbol_map: Dict[str, Symbol] = {}
    for sym in symbols_data:
        sid = sym["id"]
        sym_payload = {k: v for k, v in sym.items() if k != "id"}
        sym_obj = Symbol(**sym_payload)
        symbol_pairs.append((sid, sym_obj))
        symbol_map[sid] = sym_obj
    return symbol_pairs, symbol_map


def _file_edges_from_symbol_edges(symbol_map: Dict[str, Symbol], symbol_edges: List[Dict]) -> List[Dict]:
    edges: Dict[str, Dict] = {}
    for edge in symbol_edges:
        src_id = edge.get("src_symbol_id")
        dst_id = edge.get("dst_symbol_id")
        if not src_id or not dst_id:
            continue
        src_sym = symbol_map.get(src_id)
        dst_sym = symbol_map.get(dst_id)
        if not src_sym or not dst_sym:
            continue
        src_path = src_sym.file_path
        dst_path = dst_sym.file_path
        if not src_path or not dst_path or src_path == dst_path:
            continue
        key = f"{src_path}::{dst_path}"
        edges[key] = {
            "src": src_path,
            "dst": dst_path,
            "edge_type": edge.get("edge_type") or "call",
            "detail": None,
        }
    return list(edges.values())


def _module_maps_from_codewiki(tree: Dict) -> Tuple[Dict[str, List[str]], Dict[str, str]]:
    components_by_module: Dict[str, List[str]] = {}
    name_by_module: Dict[str, str] = {}

    def walk(node: Dict):
        for module_name, info in node.items():
            module_id = info.get("path") or module_name
            name_by_module[module_id] = module_name
            components_by_module[module_id] = list(info.get("components", []) or [])
            children = info.get("children", {})
            if isinstance(children, dict) and children:
                walk(children)

    if tree:
        walk(tree)
    return components_by_module, name_by_module


def run_analysis(
    repo_id: str,
    repo_root: str,
    include: List[str] | None,
    exclude: List[str] | None,
    llm_model=None,
    job_id: str | None = None,
    repo_url: str | None = None,
) -> None:
    from app.core.jobs import set_job, is_job_canceled

    def update_progress(progress: int, stage: str, detail: str):
        if job_id:
            set_job(job_id, status="running", progress=progress, stage=stage, detail=detail)

    def ensure_not_canceled():
        if job_id and is_job_canceled(job_id):
            update_progress(0, "已取消", "任务已取消")
            raise RuntimeError("job canceled")

    logger = get_job_logger(repo_id)
    logger.info("analysis_start repo_root=%s", repo_root)
    if not llm_model or not llm_model.base_url or not llm_model.api_key or not llm_model.model_name:
        raise ValueError("model config missing for CodeWiki analysis")

    update_progress(20, "扫描文件", "正在扫描代码仓库中的文件...")
    ensure_not_canceled()
    files = discover_files_with_codewiki(repo_root, include, exclude, languages=[])
    logger.info("files_discovered count=%s", len(files))
    languages = sorted({f.language for f in files})
    update_progress(25, "扫描完成", f"发现 {len(files)} 个源文件，{len(languages)} 种语言")
    ensure_not_canceled()

    upsert_repo(repo_id, url=repo_url, root_path=repo_root, language_set=languages)


    file_records = []
    for item in files:
        file_records.append(
            {
                "path": item.path,
                "language": item.language,
                "size": None,
                "hash": None,
            }
        )

    parse_total = min(len(files), 200) if files else 0
    update_progress(30, "解析符号", f"准备解析 {parse_total} 个文件...")
    ensure_not_canceled()

    last_parse_update = {"progress": -1, "ts": 0.0}

    def _on_parse_progress(current: int, total: int, file_info: Dict):
        if total <= 0:
            return
        progress = 30 + int((current / total) * 10)
        now = time.time()
        if progress == last_parse_update["progress"] and (now - last_parse_update["ts"]) < 2:
            return
        last_parse_update["progress"] = progress
        last_parse_update["ts"] = now
        path = file_info.get("path") if isinstance(file_info, dict) else None
        suffix = f"，当前文件: {path}" if path else ""
        update_progress(progress, "解析符号", f"解析进度 {current}/{total}{suffix}")

    symbols_data, symbol_deps = analyze_with_codewiki(
        repo_root,
        languages=[f.language for f in files] if files else [],
        max_files=parse_total or 200,
        progress_callback=_on_parse_progress,
    )
    symbol_pairs, symbol_map = _symbols_from_codewiki(symbols_data)
    update_progress(40, "解析完成", f"发现 {len(symbol_pairs)} 个符号，正在分析依赖关系...")
    ensure_not_canceled()
    # Keep symbol_pairs for DB insertion and downstream mappings.

    file_deps = _file_edges_from_symbol_edges(symbol_map, symbol_deps)
    logger.info("file_deps count=%s", len(file_deps))
    logger.info("symbol_deps count=%s", len(symbol_deps))
    update_progress(45, "依赖分析完成", f"文件依赖: {len(file_deps)}，符号依赖: {len(symbol_deps)}")
    ensure_not_canceled()

    update_progress(50, "生成文档", "AI 正在分析代码结构，生成模块文档...")
    ensure_not_canceled()
    docs_output_dir = Path(__file__).resolve().parents[2] / "workspace" / "codewiki_docs" / repo_id

    docs_checkpoint = get_repo_checkpoint(repo_id, "docs_generated")
    if docs_checkpoint and docs_output_dir.exists():
        update_progress(55, "加载文档", "检测到已有文档，跳过生成以节省 Token")
        docs_result = load_docs_from_codewiki(docs_output_dir)
    else:
        doc_progress_state = {"progress": -1, "ts": 0.0}

        def _on_doc_progress(current: float, total: float, detail: str):
            if total <= 0:
                return
            progress = 50 + int((current / total) * 20)
            now = time.time()
            if progress == doc_progress_state["progress"] and (now - doc_progress_state["ts"]) < 2:
                return
            doc_progress_state["progress"] = progress
            doc_progress_state["ts"] = now
            detail_text = detail or "模块文档"
            update_progress(progress, "生成文档", f"生成进度 {current}/{total}，模块: {detail_text}")

        docs_result = generate_docs_with_codewiki(
            repo_root,
            include,
            exclude,
            llm_model,
            docs_output_dir,
            progress_callback=_on_doc_progress,
        )
        try:
            usage = docs_result.token_usage or {}
            if any((usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), usage.get("total_tokens", 0))):
                record_token_usage(
                    repo_id,
                    kind="llm",
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    is_estimated=False,
                    source="codewiki",
                )
        except Exception:
            pass
        set_repo_checkpoint(repo_id, "docs_generated", str(docs_output_dir))
    update_progress(75, "文档生成完成", f"生成 {len(docs_result.docs_by_module)} 个模块文档")
    ensure_not_canceled()
    module_tree = module_tree_from_codewiki(docs_result.module_tree, symbol_map)

    components_by_module, name_by_module = _module_maps_from_codewiki(docs_result.module_tree)

    assignments = []
    for module_id, components in components_by_module.items():
        file_symbol_map: Dict[str, List[str]] = {}
        for sid in components:
            sym = symbol_map.get(sid)
            if not sym or not sym.file_path:
                continue
            file_symbol_map.setdefault(sym.file_path, []).append(sid)
        for file_path, symbol_ids in file_symbol_map.items():
            assignments.append(
                {
                    "module_id": module_id,
                    "file_path": file_path,
                    "symbol_ids": symbol_ids,
                }
            )

    docs_payloads: List[Dict] = []
    docs_payloads.append(
        {
            "module_id": "root",
            "name": "overview",
            "path_prefix": "",
            "doc_type": "overview",
            "markdown": docs_result.overview,
            "files": [],
            "key_symbols": [],
            "doc_path": str(docs_result.docs_dir / "overview.md"),
        }
    )
    for module_id, markdown in docs_result.docs_by_module.items():
        components = components_by_module.get(module_id, [])
        files = sorted(
            {
                symbol_map[sid].file_path
                for sid in components
                if sid in symbol_map and symbol_map[sid].file_path
            }
        )
        key_symbols = []
        for sid in components[:20]:
            sym = symbol_map.get(sid)
            if not sym:
                continue
            key_symbols.append(
                {
                    "id": sid,
                    "kind": sym.kind,
                    "name": sym.name,
                    "file_path": sym.file_path,
                    "line_start": sym.line_start,
                    "line_end": sym.line_end,
                }
            )
        module_name = name_by_module.get(module_id, module_id.split("/")[-1])
        docs_payloads.append(
            {
                "module_id": module_id,
                "name": module_name,
                "path_prefix": module_id,
                "doc_type": "codewiki",
                "markdown": markdown,
                "files": files,
                "key_symbols": key_symbols,
                "doc_path": str(docs_result.docs_dir / f"{module_name}.md"),
            }
        )

    update_progress(80, "构建索引", "正在构建向量索引，用于智能问答...")
    ensure_not_canceled()
    chunks = build_chunks_from_docs(docs_payloads)
    build_index(repo_id, chunks)
    logger.info("chunks count=%s", len(chunks))
    update_progress(85, "索引完成", f"创建 {len(chunks)} 个文档块")
    ensure_not_canceled()

    update_progress(90, "保存数据", "正在保存分析结果到数据库...")
    ensure_not_canceled()
    file_map = insert_files(repo_id, file_records)
    insert_symbols(repo_id, [_serialize_symbol(sid, sym) for sid, sym in symbol_pairs], file_map)
    insert_edges(repo_id, [_edge_dict(edge) for edge in file_deps], kind="file")
    insert_edges(repo_id, [_edge_dict(edge) for edge in symbol_deps], kind="symbol")
    insert_file_edges(repo_id, [_edge_dict(edge) for edge in file_deps])
    insert_modules(repo_id, module_tree.root)
    insert_module_nodes(repo_id, assignments)
    update_progress(95, "数据保存完成", "正在完成最后的清理工作...")
    ensure_not_canceled()
    insert_docs(repo_id, docs_payloads)

    logger.info("analysis_complete repo_id=%s", repo_id)



def _serialize_symbol(sid: str, sym: Symbol) -> Dict:
    return {
        "id": sid,
        "kind": sym.kind,
        "name": sym.name,
        "file_path": sym.file_path,
        "line_start": sym.line_start,
        "line_end": sym.line_end,
        "container": sym.container,
        "signature": sym.signature,
    }


def _edge_dict(edge) -> Dict:
    if hasattr(edge, "__dataclass_fields__"):
        return asdict(edge)
    return edge


def _serialize_tree(tree) -> Dict:
    def walk(node):
        return {
            "id": node.id,
            "name": node.name,
            "path_prefix": node.path_prefix,
            "files": node.files,
            "children": [walk(child) for child in node.children],
        }

    return walk(tree.root)
