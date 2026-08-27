"""NotebookLM adapter — bridge to notebooklm-py for audio/video/notes generation."""

from typing import Any


def is_available() -> bool:
    """Check if notebooklm-py is installed."""
    try:
        import notebooklm  # type: ignore[reportMissingImports]

        return True
    except ImportError:
        return False


def create_client(auth_tokens: dict | None = None) -> Any | None:
    """Create a NotebookLMClient. Returns None if auth is missing or library unavailable."""
    if not is_available():
        return None
    try:
        from notebooklm import NotebookLMClient  # type: ignore[reportMissingImports]

        if auth_tokens:
            return NotebookLMClient(**auth_tokens)
        return NotebookLMClient()  # Will try saved auth
    except Exception:
        return None


def generate_audio_overview(report_path: str, auth_tokens: dict | None = None) -> dict:
    """Generate an audio overview from a research report.

    Requires notebooklm-py and valid Google auth.
    Returns {"status": "...", "url": "..."} or {"status": "unavailable", "reason": "..."}
    """
    client = create_client(auth_tokens)
    if client is None:
        return {"status": "unavailable", "reason": "notebooklm-py not configured or auth missing"}

    try:
        from pathlib import Path

        path = Path(report_path).expanduser()
        if not path.exists():
            return {"status": "error", "reason": f"Report not found: {report_path}"}

        from notebooklm import Notebook, Source  # type: ignore[reportMissingImports]

        notebook = Notebook(client, title=f"Research: {path.stem}")
        source = Source.from_file(path)
        notebook.add_source(source)

        result = notebook.generate_audio()
        return {
            "status": "generating" if hasattr(result, "status") else "complete",
            "notebook_id": getattr(notebook, "id", ""),
            "note": "Audio overview generation initiated",
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}
