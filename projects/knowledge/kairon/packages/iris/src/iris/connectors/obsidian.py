"""Obsidian connector — reads and writes notes from/to the local Obsidian vault.

Enhanced with:
- Frontmatter extraction (tags, created date, aliases)
- Tag-based filtering
- Folder/notebook filtering
- Markdown export with frontmatter-aware formatting
- Write operations: create, update, delete (soft & hard)
"""

from __future__ import annotations

import base64
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from iris.base import BaseConnector, SyncResult, parse_frontmatter, strip_frontmatter
from iris.config import IrisConfig
from iris.models import Note


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe name, preserving Unicode characters."""
    slug = re.sub(r"\s+", "-", text.strip())
    slug = re.sub(r'[<>:"/\\|?*]', "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    slug = slug.lower()
    return slug or "untitled"


def _yaml_value(value: str) -> str:
    """Return a properly escaped YAML string value."""
    if not value:
        return '""'
    if any(c in value for c in ":#{}[]&*!|>%@`,"):
        return f'"{value}"'
    return value


def _generate_frontmatter(
    title: str,
    tags: list[str] | None = None,
    created_at: str = "",
    updated_at: str = "",
    iris_id: str = "",
    status: str = "active",
    **extra: Any,
) -> str:
    """Generate YAML frontmatter string for a markdown file.

    Produces output like:
    ---
    title: "My Note"
    tags:
      - tag1
      - tag2
    created_at: 2024-01-15
    ---
    """
    lines = ["---"]
    lines.append(f"title: {_yaml_value(title)}")
    if status:
        lines.append(f"status: {status}")
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {_yaml_value(t)}")
    if created_at:
        lines.append(f"created_at: {created_at}")
    if updated_at:
        lines.append(f"updated_at: {updated_at}")
    if iris_id:
        lines.append(f"iris_id: {iris_id}")
    for k, v in extra.items():
        if isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {_yaml_value(str(item))}")
        else:
            lines.append(f"{k}: {_yaml_value(str(v))}")
    lines.append("---")
    return "\n".join(lines)


class ObsidianConnector(BaseConnector):
    """Read-only connector for Obsidian vault.

    Reads .md files from the vault directory. Each .md file becomes a Note.
    Vault path comes from config (default: iCloud Obsidian path).
    Supports tag filtering and folder filtering.
    """

    name = "obsidian"
    display_name = "Obsidian"

    def __init__(self, config: IrisConfig | None = None):
        self._config = config or IrisConfig()

    @property
    def vault_path(self) -> Path:
        return Path(self._config.obsidian_vault)

    def _walk_md_files(self, folder: str | None = None) -> list[Path]:
        """Walk the vault for .md files, excluding dot-dirs.

        Resolves symlinks to prevent path traversal attacks.
        """
        vault = self.vault_path.resolve()
        if not vault.exists():
            return []
        files: list[Path] = []
        search_dir = (vault / folder).resolve() if folder else vault
        if not search_dir.exists():
            return []
        # Resolve to realpath after symlink expansion
        if not str(search_dir.resolve()).startswith(str(vault)):
            return []
        for p in search_dir.rglob("*.md"):
            resolved = p.resolve()
            # Ensure the resolved path is still within the vault
            if not str(resolved).startswith(str(vault)):
                continue
            parts = resolved.relative_to(vault).parts
            if any(part.startswith(".") for part in parts):
                continue
            files.append(resolved)
        return sorted(files)

    def _path_to_note(self, path: Path, read_content: bool = True) -> Note:
        """Convert a vault file path to a Note model with frontmatter extraction."""
        vault = self.vault_path.resolve()
        rel = path.resolve().relative_to(vault)

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
        return self.vault_path.exists()

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
        """List notes with optional tag and folder filtering."""
        files = self._walk_md_files(folder=folder)
        start = (int(cursor) if cursor.isdigit() else 0) if cursor else 0

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
        vault = self.vault_path
        try:
            padded = id + "=" * (-len(id) % 4)
            rel_path = base64.urlsafe_b64decode(padded.encode()).decode()
        except Exception:
            return None
        full = (vault / rel_path).resolve()
        vault_resolved = vault.resolve()
        if not str(full).startswith(str(vault_resolved)):
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
        vault = self.vault_path
        if not vault.exists():
            return {"error": f"Vault not found: {vault}"}
        files = self._walk_md_files()
        # Count notes per top-level folder
        folders: dict[str, int] = {}
        for f in files:
            parts = f.relative_to(vault).parts
            top = parts[0] if len(parts) > 1 else "/"
            folders[top] = folders.get(top, 0) + 1

        return {
            "vault": str(vault),
            "note_count": len(files),
            "folders": len(folders),
            "top_folders": {k: folders[k] for k in sorted(folders)[:10]},
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Obsidian is always up-to-date (reads live from filesystem)."""
        files = self._walk_md_files()
        return SyncResult(
            connector_name=self.name,
            items_found=len(files),
            success=True,
            message=f"Read {len(files)} notes from {self.vault_path}",
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
            lines = ["# Obsidian Vault Export\n", f"Source: {self.vault_path}\n", "---\n"]
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

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def _id_to_path(self, id: str) -> str | None:
        """Decode a base64 ID back to a relative vault path, with traversal check."""
        vault = self.vault_path.resolve()
        try:
            padded = id + "=" * (-len(id) % 4)
            rel_path = base64.urlsafe_b64decode(padded.encode()).decode()
        except Exception:
            return None
        full = (vault / rel_path).resolve()
        if not str(full).startswith(str(vault)):
            return None
        return rel_path

    def create_item(
        self,
        title: str = "",
        content: str = "",
        tags: list[str] | None = None,
        path: str | None = None,
        **kwargs: Any,
    ) -> Note:
        """Create a new .md file in the vault.

        Args:
            title: Note title (used in frontmatter).
            content: Markdown body (without frontmatter).
            tags: Optional list of tags.
            path: Relative vault path (e.g. "folder/note.md").
                  If None, auto-generates from title via _slugify.

        Returns:
            The created Note model.

        Raises:
            FileExistsError: If the file already exists.
            ValueError: If path traversal is detected.
        """
        if path is None:
            path = f"{_slugify(title)}.md"

        vault = self.vault_path.resolve()
        full_path = (vault / path).resolve()

        # Path traversal protection
        if not str(full_path).startswith(str(vault)):
            raise ValueError(f"Path traversal detected: {path}")

        if full_path.exists():
            raise FileExistsError(f"Note already exists: {path}")

        full_path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now().strftime("%Y-%m-%d")
        iris_id = base64.urlsafe_b64encode(str(path).encode()).decode().rstrip("=")

        frontmatter = _generate_frontmatter(
            title=title,
            tags=tags or [],
            created_at=now,
            iris_id=iris_id,
        )

        if content:
            markdown = f"{frontmatter}\n\n{content}"
        else:
            markdown = f"{frontmatter}\n"
        full_path.write_text(markdown, encoding="utf-8")

        return Note(
            id=iris_id,
            title=title,
            content=markdown,
            tags=tags or [],
            platform=self.name,
            source_path=str(full_path),
            platform_notebook=str(Path(path).parent) if Path(path).parent != "." else "/",
            created_at=now,
            updated_at=now,
        )

    def update_item(self, id: str, data: dict[str, Any]) -> Note | None:  # type: ignore[reportIncompatibleMethodOverride]
        """Update an existing note's title, content, or tags.

        Args:
            id: Base64-encoded ID of the note.
            data: Dict with optional keys: title, content, tags.

        Returns:
            Updated Note, or None if note doesn't exist.
        """
        rel = self._id_to_path(id)
        if rel is None:
            return None

        vault = self.vault_path.resolve()
        full_path = (vault / rel).resolve()
        if not full_path.exists():
            return None

        raw = full_path.read_text(encoding="utf-8", errors="replace")
        fm = parse_frontmatter(raw)
        body = strip_frontmatter(raw)

        # Merge updates
        new_title = data.get("title", fm.get("title") or full_path.stem)
        new_tags = data.get("tags", fm.get("tags", []))
        new_body = data.get("content", body)

        now = datetime.now().strftime("%Y-%m-%d")
        iris_id = base64.urlsafe_b64encode(str(rel).encode()).decode().rstrip("=")

        frontmatter = _generate_frontmatter(
            title=new_title,
            tags=new_tags,
            created_at=fm.get("created", fm.get("date", fm.get("created_at", ""))),
            updated_at=now,
            iris_id=iris_id,
        )

        if new_body:
            markdown = f"{frontmatter}\n\n{new_body}"
        else:
            markdown = f"{frontmatter}\n"
        full_path.write_text(markdown, encoding="utf-8")

        return Note(
            id=iris_id,
            title=new_title,
            content=markdown,
            tags=new_tags,
            platform=self.name,
            source_path=str(full_path),
            platform_notebook=str(Path(rel).parent) if Path(rel).parent != "." else "/",
            created_at=fm.get("created", fm.get("date", fm.get("created_at", ""))),
            updated_at=now,
        )

    def delete_item(self, item_id: str, soft: bool = True, **kwargs: Any) -> bool:
        """Delete a note from the vault.

        Args:
            id: Base64-encoded ID of the note.
            soft: If True, add ``status: deleted`` to frontmatter (safe, reversible).
                  If False, move the file into a ``_trash/`` subfolder in the vault.

        Returns:
            True if deletion succeeded, False if note not found.
        """
        rel = self._id_to_path(item_id)
        if rel is None:
            return False

        vault = self.vault_path.resolve()
        full_path = (vault / rel).resolve()
        if not full_path.exists():
            return False

        if soft:
            # Soft delete: add status: deleted to frontmatter
            raw = full_path.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(raw)
            body = strip_frontmatter(raw)

            now = datetime.now().strftime("%Y-%m-%d")
            new_fm = _generate_frontmatter(
                title=fm.get("title") or full_path.stem,
                tags=fm.get("tags", []),
                created_at=fm.get("created", fm.get("date", fm.get("created_at", ""))),
                updated_at=now,
                iris_id=item_id,
                status="deleted",
            )
            markdown = f"{new_fm}\n\n{body}" if body else f"{new_fm}\n"
            full_path.write_text(markdown, encoding="utf-8")
            return True
        else:
            # Hard delete: move to _trash/
            trash_dir = vault / "_trash"
            trash_dir.mkdir(parents=True, exist_ok=True)
            trash_path = trash_dir / rel
            trash_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(full_path), str(trash_path))
            return True
