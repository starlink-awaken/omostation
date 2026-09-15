"""Distillation Engine — compress multiple entries into a concise summary."""

from __future__ import annotations


class DistillationEngine:
    """Compresses a collection of entries into a single summary string.

    The engine supports multiple strategies via the *method* parameter and
    can optionally limit the output length.

    Typical usage::

        engine = DistillationEngine()
        summary = engine.distill(entries, method="concat_titles")
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def distill(
        self,
        entries: list[dict | str],
        method: str = "concat_titles",
        max_length: int = 500,
    ) -> str:
        """Distill a list of entries into a single summary.

        Args:
            entries: Entries to compress. Each entry may be a dict (with
                ``title`` and ``content`` keys) or a plain string.
            method: Strategy to use:
                - ``"concat_titles"`` — join titles/newline.
                - ``"truncate_content"`` — take first sentence of each content.
                - ``"first"`` — return the first entry as-is.
            max_length: Maximum length of the returned summary (characters).

        Returns:
            A condensed summary string.
        """
        if not entries:
            return ""

        if method == "first":
            result = self._render_entry(entries[0])
        elif method == "truncate_content":
            parts: list[str] = []
            for entry in entries:
                content = self._get_content(entry)
                # Take first sentence (up to first period or newline)
                sentence = content.split(".")[0].split("\n")[0].strip()
                if sentence:
                    parts.append(sentence)
            result = " | ".join(parts)
        elif method == "concat_titles":
            titles: list[str] = []
            for entry in entries:
                if isinstance(entry, dict):
                    title = entry.get("title", entry.get("id", ""))
                else:
                    title = str(entry)[:80]
                if title:
                    titles.append(str(title))
            result = "\n".join(titles)
        else:
            result = f"Unknown method: {method}"

        if len(result) > max_length:
            result = result[: max_length - 3] + "..."

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _render_entry(entry: dict | str) -> str:
        """Render a single entry to a string."""
        if isinstance(entry, dict):
            title = entry.get("title", "")
            content = entry.get("content", "")
            return f"{title}: {content}".strip(": ")
        return str(entry)

    @staticmethod
    def _get_content(entry: dict | str) -> str:
        """Extract the content string from an entry."""
        if isinstance(entry, dict):
            return str(entry.get("content", ""))
        return str(entry)
