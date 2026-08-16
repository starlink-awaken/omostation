"""Apple Notes connector — reads notes via osascript (AppleScript) subprocess calls.

Uses the built-in ``osascript`` command to query Apple Notes.app on macOS.
Every note's body is HTML; this connector strips all HTML tags to produce
plain-text content.

Since AppleScript does not expose a stable note ID, the connector synthesises
one using ``base64(folder_name + "::" + note_name)``.
"""

from __future__ import annotations

import base64
import logging
import re
import shutil
import subprocess
from datetime import datetime
from typing import Any

from iris.base import BaseConnector, SyncResult
from iris.config import IrisConfig
from iris.models import Note

logger = logging.getLogger(__name__)

# -- AppleScript fragments (reused across methods) ---------------------------

_APPLESCRIPT_TIMEOUT = 60  # seconds; Notes can be slow on first launch


def _run_osascript(script: str, timeout: int = _APPLESCRIPT_TIMEOUT) -> str:
    """Execute an AppleScript snippet via ``osascript``.

    Args:
        script: The raw AppleScript source (without outer ``osascript -e``).
        timeout: Seconds before ``subprocess`` kills the call.

    Returns:
        Stdout stripped.

    Raises:
        RuntimeError: If osascript is unavailable or returns an error.
    """
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise RuntimeError("osascript not found — this connector requires macOS.")
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "Apple Notes did not respond within the timeout. "
            "Make sure Notes.app is open and has Accessibility permissions."
        )

    if proc.returncode != 0:
        stderr = proc.stderr.strip()
        if stderr and "event timed out" not in stderr.lower():
            logger.warning("osascript stderr: %s", stderr)
        # Return empty string on timeout-like errors so callers can degrade
        # gracefully instead of hard-crashing.
        if stderr and "timed out" in stderr.lower():
            return ""
        raise RuntimeError(f"osascript error: {stderr or 'unknown error'}")

    return proc.stdout.strip()


# -- Helpers -----------------------------------------------------------------


def _strip_html(body: str) -> str:
    """Remove all HTML tags from a string and collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", body)
    # Decode common HTML entities
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _make_note_id(folder: str, title: str) -> str:
    """Synthesise a stable, unique ID for a note.

    AppleScript does not expose a stable note identifier, so we use
    ``base64(folder + "::" + title)`` as a surrogate.
    """
    raw = f"{folder}::{title}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_note_id(note_id: str) -> tuple[str, str] | None:
    """Reverse ``_make_note_id`` — returns ``(folder, title)`` or ``None``."""
    try:
        padded = note_id + "=" * (-len(note_id) % 4)
        decoded = base64.urlsafe_b64decode(padded.encode()).decode()
        if "::" not in decoded:
            return None
        folder, title = decoded.split("::", 1)
        return folder, title
    except Exception:
        return None


_AS_DATE_FORMATS = [
    "%A, %B %d, %Y at %I:%M:%S %p",  # "Friday, January 15, 2024 at 10:30:00 AM"
    "%A, %B %d, %Y at %I:%M %p",  # "Friday, January 15, 2024 at 10:30 AM"
    "%Y-%m-%d %H:%M:%S",  # fallback ISO
    "%Y-%m-%d",
]


def _parse_notes_date(raw: str) -> str:
    """Try to parse an AppleScript date string into ISO ``YYYY-MM-DD``.

    Returns empty string on failure.
    """
    if not raw:
        return ""
    s = raw.strip()
    for fmt in _AS_DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
    # If nothing matched, return the raw value trimmed (better than nothing)
    return s[:10]


# -- Connector ---------------------------------------------------------------


class AppleNotesConnector(BaseConnector):
    """Read-only connector for macOS Apple Notes.

    Uses ``osascript`` (AppleScript) subprocess calls to read notes from the
    local Apple Notes application.  The connector is only available on macOS.
    """

    name = "applenotes"
    display_name = "Apple Notes"

    def __init__(self, config: IrisConfig | None = None):
        self._config = config or IrisConfig()

    # ------------------------------------------------------------------
    # Availability & status
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Check whether ``osascript`` is available on this system."""
        return bool(shutil.which("osascript"))

    def status(self) -> dict[str, Any]:
        """Return folder count, note count, and health info."""
        if not self.is_available():
            return {"available": False, "error": "osascript not found — macOS required"}
        try:
            folders = self.list_folders()
            notes_count = 0
            for folder in folders:
                script = (
                    f'tell application "Notes"\n'
                    f'  set folderRef to folder "{folder}"\n'
                    f"  get name of every note in folderRef\n"
                    f"end tell"
                )
                out = _run_osascript(script)
                if out:
                    notes_count += len([n for n in out.split(",") if n.strip()])
        except Exception as exc:
            return {
                "available": True,
                "folders": 0,
                "note_count": 0,
                "error": str(exc),
            }
        return {
            "available": True,
            "folders": len(folders),
            "note_count": notes_count,
        }

    # ------------------------------------------------------------------
    # Folders
    # ------------------------------------------------------------------

    def list_folders(self) -> list[str]:
        """Return the names of all folders in Apple Notes."""
        out = _run_osascript('tell application "Notes" to get name of every folder')
        if not out:
            return []
        # osascript returns a comma-separated list, e.g. "Notes,便笺,Work"
        return [f.strip() for f in out.split(",") if f.strip()]

    # ------------------------------------------------------------------
    # Read items
    # ------------------------------------------------------------------

    def _fetch_note_body(self, folder: str, title: str) -> str:
        """Fetch the HTML body of a single note and strip tags.

        Returns plain-text body or empty string on failure.
        """
        escaped_folder = folder.replace('"', '\\"')
        escaped_title = title.replace('"', '\\"')
        script = (
            f'tell application "Notes"\n'
            f'  set folderRef to folder "{escaped_folder}"\n'
            f'  set noteRef to note "{escaped_title}" of folderRef\n'
            f"  get body of noteRef\n"
            f"end tell"
        )
        try:
            html = _run_osascript(script)
        except RuntimeError:
            return ""
        if not html:
            return ""
        return _strip_html(html)

    def _fetch_note_dates(self, folder: str, title: str) -> tuple[str, str]:
        """Fetch creation date and modification date for a note.

        Returns ``(created_at, updated_at)`` as ISO ``YYYY-MM-DD`` strings.
        """
        escaped_folder = folder.replace('"', '\\"')
        escaped_title = title.replace('"', '\\"')
        script = (
            f'tell application "Notes"\n'
            f'  set folderRef to folder "{escaped_folder}"\n'
            f'  set noteRef to note "{escaped_title}" of folderRef\n'
            f"  get {{creation date, modification date}} of noteRef\n"
            f"end tell"
        )
        try:
            out = _run_osascript(script)
        except RuntimeError:
            return ("", "")
        if not out:
            return ("", "")

        # osascript returns dates as a comma-joined AppleScript list, e.g.:
        #   date "Friday, January 15, 2024 at 10:30:00 AM", date "Friday, January 15, 2024 at 10:30:00 AM"
        parts = [p.strip() for p in out.split(",")]
        created_raw = ""
        updated_raw = ""
        for p in parts:
            if p.startswith("date "):
                if not created_raw:
                    created_raw = p[5:].strip('"')
                elif not updated_raw:
                    updated_raw = p[5:].strip('"')
        return (
            _parse_notes_date(created_raw),
            _parse_notes_date(updated_raw),
        )

    def _folder_to_note_list(self, folder: str) -> list[Note]:
        """Fetch all notes inside *folder* and return them as ``Note`` objects.

        This is the core workhorse used by ``list_items``, ``sync``, and
        ``search``.
        """
        escaped_folder = folder.replace('"', '\\"')
        script = (
            f'tell application "Notes"\n'
            f'  set folderRef to folder "{escaped_folder}"\n'
            f"  get name of every note in folderRef\n"
            f"end tell"
        )
        out = _run_osascript(script)
        if not out:
            return []

        note_names = [n.strip() for n in out.split(",") if n.strip()]
        notes: list[Note] = []
        for note_name in note_names:
            note_id = _make_note_id(folder, note_name)
            body = self._fetch_note_body(folder, note_name)
            created_at, updated_at = self._fetch_note_dates(folder, note_name)
            notes.append(
                Note(
                    id=note_id,
                    title=note_name,
                    platform=self.name,
                    content=body,
                    tags=[],  # Apple Notes does not expose tags via AppleScript
                    source_path=f"applenotes://{folder}/{note_name}",
                    platform_notebook=folder,
                    created_at=created_at,
                    updated_at=updated_at,
                )
            )
        return notes

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
        """List recent notes, ordered by creation date descending.

        Because AppleScript does not expose a "list all notes globally"
        command, we iterate over every folder and then sort by creation date.

        Args:
            limit: Maximum number of notes to return.
            cursor: Base64 note ID — items after this note will be returned
                    (for offset-based pagination).

        Returns:
            Up to *limit* notes sorted newest-first.
        """
        folders = self.list_folders()
        all_notes: list[Note] = []
        for folder in folders:
            try:
                all_notes.extend(self._folder_to_note_list(folder))
            except RuntimeError as exc:
                logger.warning("Failed to read folder '%s': %s", folder, exc)
                continue

        # Sort by created_at descending — notes without a date sort last.
        all_notes.sort(
            key=lambda n: n.created_at or "0000-00-00",
            reverse=True,
        )

        # Cursor-based slicing
        start = 0
        if cursor:
            for i, note in enumerate(all_notes):
                if note.id == cursor:
                    start = i + 1
                    break

        return all_notes[start : start + limit]

    def get_item(self, id: str) -> Note | None:
        """Retrieve a single note by its synthesised ID.

        The ID is ``base64(folder + "::" + title)``.
        """
        decoded = _decode_note_id(id)
        if not decoded:
            return None
        folder, title = decoded

        # Verify the folder still exists
        folders = self.list_folders()
        if folder not in folders:
            logger.debug("Folder '%s' not found for note ID '%s'", folder, id)
            return None

        body = self._fetch_note_body(folder, title)
        created_at, updated_at = self._fetch_note_dates(folder, title)
        return Note(
            id=id,
            title=title,
            platform=self.name,
            content=body,
            tags=[],
            source_path=f"applenotes://{folder}/{title}",
            platform_notebook=folder,
            created_at=created_at,
            updated_at=updated_at,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 10) -> list[Note]:
        """Search notes by title and content (case-insensitive).

        Because AppleScript does not expose a native search, we fetch
        all notes and filter them in Python.

        Args:
            query: Search string (case-insensitive).
            limit: Maximum number of matching notes to return.

        Returns:
            Matching notes, ranked by title match first, then by content.
        """
        folders = self.list_folders()
        q = query.lower()
        results: list[tuple[Note, int]] = []  # (note, score)

        for folder in folders:
            try:
                notes = self._folder_to_note_list(folder)
            except RuntimeError:
                continue
            for note in notes:
                score = 0
                if q in note.title.lower():
                    score += 10  # title match is more relevant
                if q in note.content.lower():
                    score += 1
                if score > 0:
                    results.append((note, score))

        # Sort by relevance (descending), then by date
        results.sort(key=lambda r: (-r[1], r[0].created_at or "0000-00-00"))
        return [r[0] for r in results[:limit]]

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def sync(self, dry_run: bool = False) -> SyncResult:
        """Scan all notes across all folders.

        This connector reads live from Apple Notes, so "sync" is always
        up-to-date.  When *dry_run* is ``True`` only the count is returned
        without fetching bodies.
        """
        if not self.is_available():
            return SyncResult(
                connector_name=self.name,
                items_found=0,
                success=False,
                message="osascript not available — requires macOS with Notes.app",
            )

        try:
            folders = self.list_folders()
        except RuntimeError as exc:
            return SyncResult(
                connector_name=self.name,
                items_found=0,
                success=False,
                errors=[str(exc)],
                message="Failed to list folders",
            )

        total = 0
        errors: list[str] = []
        for folder in folders:
            escaped_folder = folder.replace('"', '\\"')
            script = (
                f'tell application "Notes"\n'
                f'  set folderRef to folder "{escaped_folder}"\n'
                f"  get name of every note in folderRef\n"
                f"end tell"
            )
            try:
                out = _run_osascript(script)
                if out:
                    note_names = [n.strip() for n in out.split(",") if n.strip()]
                    total += len(note_names)
            except RuntimeError as exc:
                errors.append(f"Folder '{folder}': {exc}")

        return SyncResult(
            connector_name=self.name,
            items_found=total,
            success=len(errors) == 0,
            errors=errors if errors else [],
            message=(
                f"Found {total} notes in {len(folders)} folders"
                if not dry_run
                else f"Dry run: {total} notes across {len(folders)} folders"
            ),
        )
