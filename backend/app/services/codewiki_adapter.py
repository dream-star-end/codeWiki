from __future__ import annotations

import os
import sys
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Callable, Any
import asyncio
from app.models.schemas import ModelConfig


def _ensure_codewiki_on_path() -> None:
    base = Path(__file__).resolve().parents[3]
    codewiki_root = base / "CodeWiki"
    if codewiki_root.exists() and str(codewiki_root) not in sys.path:
        sys.path.insert(0, str(codewiki_root))


@dataclass(frozen=True)
class CodeWikiDocs:
    docs_dir: Path
    module_tree: Dict
    docs_by_module: Dict[str, str]
    overview: str
    token_usage: Optional[Dict[str, int]] = None


def analyze_with_codewiki(
    repo_root: str,
    languages: List[str],
    max_files: int = 200,
    progress_callback: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
) -> Tuple[List[Dict], List[Dict]]:
    _ensure_codewiki_on_path()
    from codewiki.src.be.dependency_analyzer.analysis.analysis_service import AnalysisService

    service = AnalysisService()
    result = service.analyze_local_repository(
        repo_root,
        max_files=max_files,
        languages=languages,
        progress_callback=progress_callback,
    )

    symbols: List[Dict] = []
    for node in result.get("nodes", []):
        kind = node.get("node_type") or node.get("component_type") or "function"
        symbols.append(
            {
                "id": node.get("id"),
                "kind": kind,
                "name": node.get("name"),
                "file_path": node.get("file_path"),
                "line_start": node.get("start_line") or 0,
                "line_end": node.get("end_line") or 0,
                "container": node.get("class_name"),
                "signature": None,
            }
        )

    symbol_deps: List[Dict] = []
    for rel in result.get("relationships", []):
        symbol_deps.append(
            {
                "src_symbol_id": rel.get("caller"),
                "dst_symbol_id": rel.get("callee"),
                "edge_type": "call",
                "detail": None,
            }
        )

    return symbols, symbol_deps


def discover_files_with_codewiki(
    repo_root: str,
    include: List[str] | None,
    exclude: List[str] | None,
    languages: List[str],
) -> List["DiscoveredFile"]:
    _ensure_codewiki_on_path()
    from codewiki.src.be.dependency_analyzer.analysis.repo_analyzer import RepoAnalyzer
    from codewiki.src.be.dependency_analyzer.analysis.call_graph_analyzer import CallGraphAnalyzer
    from app.services.file_discovery import DiscoveredFile

    analyzer = RepoAnalyzer(include_patterns=include, exclude_patterns=exclude)
    structure = analyzer.analyze_repository_structure(repo_root)
    code_files = CallGraphAnalyzer().extract_code_files(structure["file_tree"])
    if languages:
        code_files = [f for f in code_files if f.get("language") in languages]

    files: List[DiscoveredFile] = []
    for item in code_files:
        abs_path = str((Path(repo_root) / item["path"]).resolve())
        files.append(DiscoveredFile(path=abs_path, language=item["language"]))
    return files


def cluster_modules_with_codewiki(
    repo_root: str,
    include: List[str] | None,
    exclude: List[str] | None,
    model: ModelConfig | None = None,
) -> Dict:
    if model is None:
        return {}
    _ensure_codewiki_on_path()
    from codewiki.src.be.dependency_analyzer.analysis.repo_analyzer import RepoAnalyzer
    from codewiki.src.be.dependency_analyzer.analysis.call_graph_analyzer import CallGraphAnalyzer
    from codewiki.src.be.cluster_modules import cluster_modules
    from codewiki.src.config import Config
    from codewiki.src.be.dependency_analyzer.models.core import Node

    analyzer = RepoAnalyzer(include_patterns=include, exclude_patterns=exclude)
    structure = analyzer.analyze_repository_structure(repo_root)
    code_files = CallGraphAnalyzer().extract_code_files(structure["file_tree"])

    cga = CallGraphAnalyzer()
    analysis = cga.analyze_code_files(code_files, repo_root)
    functions = analysis.get("functions", [])
    nodes = [Node(**node) for node in functions]
    leaf_nodes = [node.id for node in nodes]
    components = {node.id: node for node in nodes}

    config = Config.from_cli(
        repo_path=repo_root,
        output_dir=str((Path(repo_root) / ".codewiki").resolve()),
        llm_base_url=model.base_url,
        llm_api_key=model.api_key,
        main_model=model.model_name,
        cluster_model=model.model_name,
    )

    return cluster_modules(leaf_nodes, components, config)


def load_docs_from_codewiki(output_dir: Path) -> CodeWikiDocs:
    _ensure_codewiki_on_path()
    from codewiki.src.config import MODULE_TREE_FILENAME, OVERVIEW_FILENAME

    docs_dir = output_dir
    module_tree_path = docs_dir / MODULE_TREE_FILENAME
    overview_path = docs_dir / OVERVIEW_FILENAME
    module_tree = {}
    if module_tree_path.exists():
        module_tree = json.loads(module_tree_path.read_text(encoding="utf-8"))
    overview = overview_path.read_text(encoding="utf-8", errors="replace") if overview_path.exists() else ""

    docs_by_module: Dict[str, str] = {}

    def walk(tree: Dict):
        for module_name, info in tree.items():
            module_id = info.get("path") or module_name
            doc_path = docs_dir / f"{module_name}.md"
            if doc_path.exists():
                docs_by_module[module_id] = doc_path.read_text(encoding="utf-8", errors="replace")
            children = info.get("children", {})
            if isinstance(children, dict) and children:
                walk(children)

    if module_tree:
        walk(module_tree)

    return CodeWikiDocs(
        docs_dir=docs_dir,
        module_tree=module_tree,
        docs_by_module=docs_by_module,
        overview=overview,
        token_usage=None,
    )


def generate_docs_with_codewiki(
    repo_root: str,
    include: Optional[List[str]],
    exclude: Optional[List[str]],
    model: ModelConfig,
    output_dir: Path,
    progress_callback: Optional[Callable[[float, float, str], None]] = None,
) -> CodeWikiDocs:
    if not model or not model.base_url or not model.api_key or not model.model_name:
        raise ValueError("model config missing for CodeWiki documentation generation")
    _ensure_codewiki_on_path()

    from codewiki.src.config import Config, MODULE_TREE_FILENAME, OVERVIEW_FILENAME
    from codewiki.src.be.documentation_generator import DocumentationGenerator
    from codewiki.src.be.llm_services import reset_token_usage, get_token_usage

    agent_instructions = {}
    if include:
        agent_instructions["include_patterns"] = include
    if exclude:
        agent_instructions["exclude_patterns"] = exclude
    agent_instructions.setdefault(
        "custom_instructions",
        "所有输出必须为中文，使用简洁清晰的小标题与要点列表。",
    )
    if not agent_instructions:
        agent_instructions = None

    output_dir.mkdir(parents=True, exist_ok=True)
    config = Config.from_cli(
        repo_path=repo_root,
        output_dir=str(output_dir),
        llm_base_url=model.base_url,
        llm_api_key=model.api_key,
        main_model=model.model_name,
        cluster_model=model.model_name,
        fallback_model=model.model_name,
        agent_instructions=agent_instructions,
    )

    generator = DocumentationGenerator(config, progress_callback=progress_callback)
    reset_token_usage()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(generator.run())
    else:
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                new_loop.run_until_complete(generator.run())
            finally:
                new_loop.close()
        else:
            loop.run_until_complete(generator.run())

    token_usage = get_token_usage()
    docs_dir = Path(config.docs_dir)
    module_tree_path = docs_dir / MODULE_TREE_FILENAME
    overview_path = docs_dir / OVERVIEW_FILENAME
    module_tree = {}
    if module_tree_path.exists():
        module_tree = json.loads(module_tree_path.read_text(encoding="utf-8"))
    overview = overview_path.read_text(encoding="utf-8", errors="replace") if overview_path.exists() else ""

    docs_by_module: Dict[str, str] = {}

    def walk(tree: Dict):
        for module_name, info in tree.items():
            module_id = info.get("path") or module_name
            doc_path = docs_dir / f"{module_name}.md"
            if doc_path.exists():
                docs_by_module[module_id] = doc_path.read_text(encoding="utf-8", errors="replace")
            children = info.get("children", {})
            if isinstance(children, dict) and children:
                walk(children)

    if module_tree:
        walk(module_tree)

    return CodeWikiDocs(
        docs_dir=docs_dir,
        module_tree=module_tree,
        docs_by_module=docs_by_module,
        overview=overview,
        token_usage=token_usage,
    )


def codewiki_enabled() -> bool:
    return os.getenv("CODEWIKI_ENABLED", "1") == "1"
