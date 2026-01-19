from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from app.services.parsers import parse_python_file, parse_java_file, ImportRef


@dataclass(frozen=True)
class FileDependency:
    src: str
    dst: str
    edge_type: str
    detail: str


def _parse_imports(path: str, language: str) -> List[ImportRef]:
    if language == "python":
        _, imports = parse_python_file(path)
    elif language == "java":
        _, imports = parse_java_file(path)
    else:
        return []
    return imports


def _python_import_to_path(module: str, root: Path) -> str | None:
    if not module:
        return None
    # import x.y -> x/y.py or x/y/__init__.py
    parts = module.split()
    if parts and parts[0] == "import":
        module = parts[1]
    if parts and parts[0] == "from":
        module = parts[1]
    module = module.replace(".", "/")
    candidate = root / f"{module}.py"
    if candidate.exists():
        return str(candidate)
    candidate = root / module / "__init__.py"
    if candidate.exists():
        return str(candidate)
    return None


def _java_import_to_path(module: str, root: Path) -> str | None:
    if not module:
        return None
    # import com.a.B; -> com/a/B.java
    module = module.replace("import", "").replace(";", "").strip()
    module = module.replace(".", "/")
    candidate = root / f"{module}.java"
    if candidate.exists():
        return str(candidate)
    return None


def build_file_dependencies(files: Iterable[Tuple[str, str]], repo_root: str) -> List[FileDependency]:
    root = Path(repo_root)
    edges: List[FileDependency] = []

    for file_path, language in files:
        imports = _parse_imports(file_path, language)
        for imp in imports:
            if language == "python":
                dst = _python_import_to_path(imp.module, root)
            else:
                dst = _java_import_to_path(imp.module, root)

            if dst is None:
                continue
            edges.append(
                FileDependency(
                    src=file_path,
                    dst=dst,
                    edge_type="import",
                    detail=imp.module,
                )
            )

    return edges
