from __future__ import annotations

import hashlib

from app.services.parsers.base import Symbol


def symbol_id(symbol: Symbol) -> str:
    payload = "|".join(
        [
            symbol.file_path,
            symbol.kind,
            symbol.name,
            str(symbol.line_start),
            str(symbol.line_end),
            symbol.container or "",
            symbol.signature or "",
        ]
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()
