from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Symbol:
    kind: str
    name: str
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    container: Optional[str] = None


@dataclass(frozen=True)
class ImportRef:
    module: str
    name: Optional[str]
    file_path: str
    line_start: int
    line_end: int
