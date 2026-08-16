"""NotebookLM connector — wraps notebooklm-py via minerva adapter.

Capabilities:
- Check availability (notebooklm-py installed + Google auth)
- Generate audio overview from research reports
- List generated audio files from workspace published dir

This connector is write-oriented — NotebookLM's value is creating
audio/video content, not reading existing notebooks via API.

Dependencies:
  pip install notebooklm-py
  Google auth tokens (cookies or IRIS_NOTEBOOKLM_AUTH env var)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

from iris.base import BaseConnector, SyncResult
from iris.models import KnowledgeArtifact, Note

logger = logging.getLogger(__name__)

AUDIO_DIR = Path.home() / "Workspace" / "workspace-published" / "audio"


class NotebookLMConnector(BaseConnector):
    """Connector for Google NotebookLM.

    Wraps minerva's notebooklm_adapter for audio generation.
    Lists generated audio files from workspace-published/audio.
    """

    name = "notebooklm"
    display_name = "NotebookLM"

    def __init__(self) -> None:
        self._adapter = None
        self._available = False
        self._init_adapter()

    def _init_adapter(self) -> None:
        try:
            from minerva.creative.notebooklm_adapter import (
                create_client,
                is_available,
            )

            if is_available():
                self._adapter = create_client()
                self._available = self._adapter is not None
        except ImportError:
            self._available = False

    def is_available(self) -> bool:
        if not self._available:
            self._init_adapter()
        return self._available

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> list[KnowledgeArtifact]:
        """List generated audio files and available notebooks.

        Scans workspace-published/audio/ for generated files
        and reports them as Notes.
        """
        notes: list[KnowledgeArtifact] = []

        # Scan generated audio files
        if AUDIO_DIR.exists():
            for f in sorted(AUDIO_DIR.glob("*.*"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
                ext = f.suffix.lower()
                if ext in (".mp3", ".wav", ".m4a", ".ogg"):
                    notes.append(
                        Note(
                            id=f"audio/{f.stem}",
                            title=f"🎧 {f.stem}",
                            content=f"Generated audio: {f.name}\nSize: {f.stat().st_size / 1024:.0f} KB",
                            platform=self.name,
                            source_path=str(f),
                            tags=["audio", "notebooklm"],
                            created_at="",
                        )
                    )

        return notes[:limit]

    def get_item(self, id: str) -> KnowledgeArtifact | None:
        for note in self.list_items(limit=50):
            if note.id == id:
                return note
        return None

    def search(self, query: str, limit: int = 10) -> list[KnowledgeArtifact]:
        items = self.list_items(limit=limit)
        query_lower = query.lower()
        return [n for n in items if query_lower in n.title.lower() or query_lower in cast(Note, n).content.lower()]

    def status(self) -> dict[str, Any]:
        return {
            "available": self.is_available(),
            "adapter_loaded": self._adapter is not None,
            "generated_audio_count": len(list(AUDIO_DIR.glob("*.*"))) if AUDIO_DIR.exists() else 0,
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        items = self.list_items(limit=50)
        return SyncResult(
            connector_name=self.name,
            items_found=len(items),
            success=True,
            message=f"Found {len(items)} NotebookLM artifacts",
        )
