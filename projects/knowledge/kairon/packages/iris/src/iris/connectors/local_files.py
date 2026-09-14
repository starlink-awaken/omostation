"""Local files connector — reads markdown notes from a local directory.

A file-based connector (no API key needed) that:
- Accepts a directory path from config
- Recursively scans for .md files
- Extracts frontmatter and content
- Returns structured Note records compatible with Iris output format
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from iris.base import BaseConnector, SyncResult, parse_frontmatter, strip_frontmatter
from iris.config import IrisConfig
from iris.models import Note


class LocalFilesConnector(BaseConnector):
    """Read-only connector for a local directory of markdown files.

    Recursively scans a directory for .md files. Each .md file becomes a Note.
    Directory path comes from config (key: local_files.directory).
    Dot-directories (names starting with '.') are excluded.
    """

    name = "local_files"
    display_name = "Local Files"

    def __init__(self, config: IrisConfig | None = None):
        self._config = config or IrisConfig()

    @property
    def root_dir(self) -> Path:
        return Path(self._config.local_files_dir)

    def _walk_md_files(self, subdir: str | None = None) -> list[Path]:
        """Walk the directory for .md files, excluding dot-dirs.

        Resolves symlinks to prevent path traversal attacks.
        """
        root = self.root_dir.resolve()
        if not root.exists():
            return []
        files: list[Path] = []
        search_dir = (root / subdir).resolve() if subdir else root
        if not search_dir.exists():
            return []
        # Resolve to realpath after symlink expansion
        if not str(search_dir.resolve()).startswith(str(root)):
            return []
        for p in search_dir.rglob("*.md"):
            resolved = p.resolve()
            # Ensure the resolved path is still within the root directory
            if not str(resolved).startswith(str(root)):
                continue
            parts = resolved.relative_to(root).parts
            if any(part.startswith(".") for part in parts):
                continue
            files.append(resolved)
        return sorted(files)

    def _path_to_note(self, path: Path, read_content: bool = True) -> Note:
        """Convert a file path to a Note model with frontmatter extraction."""
        root = self.root_dir.resolve()
        rel = path.resolve().relative_to(root)

        if read_content:
            content = path.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(content)
            tags = fm["tags"]
            body = strip_frontmatter(content)
            inline_tags = re.findall(r"(?<!\w)#([\w\-/]+)", body)
            for t in inline_tags:
                if t not in tags:
                    tags.append(t)
            title = fm["title"] or path.stem
            created = fm["created"]
        else:
            content = ""
            tags = []
            title = path.stem
            created = ""

        return Note(
            id=base64.urlsafe_b64encode(str(rel).encode()).decode().rstrip("="),
            title=title,
            platform=self.name,
            content=content,
            tags=tags,
            source_path=str(path),
            platform_notebook=str(rel.parent) if rel.parent != "." else "/",
            created_at=created,
            updated_at="",
        )

    def is_available(self) -> bool:
        return self.root_dir.exists()

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
        **kwargs: Any,
    ) -> list[Note]:
        """List notes with optional tag and subdirectory filtering."""
        files = self._walk_md_files(subdir=subdir)
        start = (int(cursor) if cursor and cursor.isdigit() else 0) if cursor else 0

        results: list[Note] = []
        for f in files[start:]:
            if len(results) >= limit:
                break
            note = self._path_to_note(f, read_content=bool(tag))
            if tag and tag not in note.tags:
                continue
            results.append(note)
        return results

    def get_item(self, id: str) -> Note | None:
        root = self.root_dir
        try:
            padded = id + "=" * (-len(id) % 4)
            rel_path = base64.urlsafe_b64decode(padded.encode()).decode()
        except Exception:
            return None
        full = (root / rel_path).resolve()
        root_resolved = root.resolve()
        if not str(full).startswith(str(root_resolved)):
            return None
        if full.exists():
            return self._path_to_note(full)
        return None

    def search(self, query: str, limit: int = 10) -> list[Note]:
        files = self._walk_md_files()
        results: list[Note] = []
        query_lower = query.lower()
        for f in files:
            if len(results) >= limit:
                break
            content = f.read_text(encoding="utf-8", errors="replace")
            if query_lower not in content.lower():
                continue
            note = self._path_to_note(f)
            # Reuse already-read content instead of reading again
            note.content = content
            results.append(note)
        return results

    def status(self) -> dict[str, Any]:
        root = self.root_dir
        if not root.exists():
            return {"error": f"Directory not found: {root}"}
        files = self._walk_md_files()
        # Count files per top-level subdirectory
        dirs: dict[str, int] = {}
        for f in files:
            parts = f.relative_to(root).parts
            top = parts[0] if len(parts) > 1 else "/"
            dirs[top] = dirs.get(top, 0) + 1

        return {
            "root_dir": str(root),
            "file_count": len(files),
            "subdirs": len(dirs),
            "top_subdirs": {k: dirs[k] for k in sorted(dirs)[:10]},
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Local files are always up-to-date (reads live from filesystem)."""
        files = self._walk_md_files()
        return SyncResult(
            connector_name=self.name,
            items_found=len(files),
            success=True,
            message=f"Read {len(files)} markdown files from {self.root_dir}",
        )

    def export(self, fmt: str = "json") -> str:
        """Export with frontmatter-aware markdown output."""
        if fmt == "json":
            items = self.list_items(limit=1000)
            data = []
            for item in items:
                d = item.to_dict()
                d.pop("raw_data", None)
                data.append(d)
            return json.dumps(data, ensure_ascii=False, indent=2)

        if fmt == "md":
            items = self.list_items(limit=1000)
            lines = ["# Local Files Export\n", f"Source: {self.root_dir}\n", "---\n"]
            for item in items:
                title = item.title or "Untitled"
                lines.append(f"\n## {title}")
                if item.tags:
                    lines.append(f"Tags: {' '.join(f'#{t}' for t in item.tags)}")
                if item.platform_notebook:
                    lines.append(f"Path: {item.platform_notebook}/{title}")
                if item.created_at:
                    lines.append(f"Created: {item.created_at}")
                lines.append("")
                # Write content without frontmatter
                content = item.content or ""
                body = strip_frontmatter(content)
                if body.strip():
                    lines.append(body)
                lines.append("\n---")
            return "\n".join(lines)

        raise ValueError(f"Unsupported format: {fmt}")
