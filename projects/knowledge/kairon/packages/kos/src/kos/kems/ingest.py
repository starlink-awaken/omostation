"""Controlled document import for the KEMS workspace boundary."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from kos.indexer.engine import get_handler


@dataclass(frozen=True)
class ImportPolicy:
    """Allow-list policy applied before a document reaches a KOS handler."""

    allowed_root: Path
    extensions: frozenset[str] = frozenset({".md", ".txt", ".docx", ".pdf", ".xlsx", ".xls"})
    max_bytes: int = 50 * 1024 * 1024

    def check(self, path: Path) -> Path:
        candidate = path.expanduser().resolve()
        root = self.allowed_root.expanduser().resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError("document is outside the configured KEMS workspace") from exc
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        if candidate.suffix.lower() not in self.extensions:
            raise ValueError(f"unsupported KEMS document extension: {candidate.suffix or '<none>'}")
        if candidate.stat().st_size > self.max_bytes:
            raise ValueError(f"document exceeds import limit: {self.max_bytes} bytes")
        if os.path.islink(path):
            raise PermissionError("symlinked documents are not accepted by the KEMS importer")
        return candidate


@dataclass(frozen=True)
class ImportedDocument:
    source_name: str
    source_sha256: str
    source_format: str
    content: str
    byte_size: int

    def to_dict(self) -> dict[str, str | int]:
        return {
            "source_name": self.source_name,
            "source_sha256": self.source_sha256,
            "source_format": self.source_format,
            "content": self.content,
            "byte_size": self.byte_size,
        }


def import_document(file_path: str | Path, policy: ImportPolicy) -> ImportedDocument:
    """Validate, hash, and parse one document through the existing KOS handler."""
    path = policy.check(Path(file_path))
    raw = path.read_bytes()
    content = get_handler(path).extract_text(path)
    return ImportedDocument(
        source_name=path.name,
        source_sha256=hashlib.sha256(raw).hexdigest(),
        source_format=path.suffix.lower().lstrip("."),
        content=content,
        byte_size=len(raw),
    )
