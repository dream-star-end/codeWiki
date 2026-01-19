from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable, List, Optional
import fnmatch


@dataclass(frozen=True)
class DiscoveredFile:
    path: str
    language: str


def _match_any(path: str, patterns: Iterable[str]) -> bool:
    probe = PurePosixPath(path)
    for pattern in patterns:
        if probe.match(pattern) or fnmatch.fnmatch(path, pattern):
            return True
    return False


def discover_files(
    root: str,
    include: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
) -> List[DiscoveredFile]:
    root_path = Path(root).resolve()
    include = include or ["**/*.py", "**/*.java"]
    exclude = exclude or [".git/**", "**/node_modules/**", "**/__pycache__/**"]

    discovered: List[DiscoveredFile] = []

    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root_path).as_posix()

        if _match_any(rel, exclude):
            continue
        if include and not _match_any(rel, include):
            continue

        if rel.endswith(".py"):
            language = "python"
        elif rel.endswith(".java"):
            language = "java"
        else:
            continue

        discovered.append(DiscoveredFile(path=str(path), language=language))

    return sorted(discovered, key=lambda item: item.path)
