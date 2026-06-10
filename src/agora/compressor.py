"""Content compression utilities for context window optimization.

The Compressor class reduces content size by applying type-specific strategies:
JSON key shortening, HTML-to-markdown, URL ref substitution, stacktrace
trimming, and plaintext summarization.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from agora import persistence_db as _persist  # type: ignore[import-not-found]


@dataclass
class CompressedResult:
    """Result of a compression operation."""

    content: str
    original_len: int
    compressed_len: int
    ratio: float
    stats: dict = field(default_factory=dict)

    @property
    def saved(self) -> int:
        return self.original_len - self.compressed_len


# Map of common verbose JSON keys to terse equivalents.
_DEFAULT_JSON_KEY_MAP = {
    "description": "desc",
    "identifier": "id",
    "metadata": "meta",
    "configuration": "config",
    "properties": "props",
    "attributes": "attrs",
    "parameters": "params",
    "arguments": "args",
    "message": "msg",
    "content": "val",
    "value": "val",
    "status": "st",
    "context": "ctx",
    "response": "resp",
    "request": "req",
    "handler": "hnd",
    "service": "svc",
    "definition": "defn",
    "reference": "ref",
    "category": "cat",
    "priority": "pri",
    "severity": "sev",
    "timestamp": "ts",
    "duration": "dur",
    "endpoint": "ep",
    "protocol": "proto",
    "version": "ver",
    "pattern": "ptn",
    "template": "tpl",
    "resource": "rsrc",
    "component": "comp",
    "extension": "ext",
}


class Compressor:
    """Compress content based on detected or explicit content type.

    Usage::

        c = Compressor()
        result = c.compress(some_string)
        print(result.ratio, result.content)
    """

    def __init__(self, json_key_map: dict[str, str] | None = None):
        self._key_map = json_key_map or dict(_DEFAULT_JSON_KEY_MAP)
        self._reverse_map: dict[str, str] = {}
        self._url_refs: dict[str, str] = {}
        self._url_counter = 0
        self._dedup_seen: set[int] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compress(self, content: str, content_type: str = "auto") -> CompressedResult:
        """Compress *content* according to *content_type*.

        When *content_type* is ``"auto"`` the type is inferred via
        :meth:`detect_type`.
        """
        original_len = len(content)
        if not content.strip():
            return CompressedResult(content, original_len, 0, 0.0)

        ctype = self.detect_type(content) if content_type == "auto" else content_type

        stats: dict = {"type": ctype}

        if ctype == "json":
            compressed = self._compress_json(content, stats)
        elif ctype == "html":
            compressed = self._compress_html(content, stats)
        elif ctype == "error":
            compressed = self._compress_stacktrace(content, stats)
        elif ctype in ("code", "plaintext"):
            compressed = self._compress_plaintext(content, ctype, stats)
        else:
            compressed = content

        compressed_len = len(compressed)
        ratio = 1.0 - (compressed_len / original_len) if original_len else 0.0

        # ── 持久化压缩统计 ──
        self._record_stats(ctype, original_len, compressed_len)

        return CompressedResult(
            content=compressed,
            original_len=original_len,
            compressed_len=compressed_len,
            ratio=ratio,
            stats=stats,
        )

    def detect_type(self, content: str) -> str:
        """Detect the content type of *content*.

        Returns one of ``json``, ``html``, ``error``, ``code``, ``plaintext``.
        """
        if not content or not content.strip():
            return "plaintext"

        stripped = content.strip()

        # JSON detection — first non-whitespace char is { or [
        if stripped[0] in ("{", "["):
            try:
                json.loads(stripped)
                return "json"
            except (json.JSONDecodeError, ValueError):
                pass

        # HTML detection — look for typical opening tags
        if re.search(
            r"<\s*(html|div|span|p|body|head|table|article|section)",
            stripped[:500],
            re.IGNORECASE,
        ):
            return "html"

        # Error / stacktrace detection
        if re.search(
            r"Traceback\s*\(|Error|Exception|at\s+\S+\.\w+\(.*\)", stripped[:600]
        ):
            return "error"

        # Code detection — heuristics for source code blocks
        code_patterns = [
            r"(?:^|\n)\s*(?:def|class|function|import|from|var|let|const|fn|pub|impl)\s",
            r"(?:^|\n)\s*(?:#|//|--|%)\s",
            r"(?:^|\n)\s*{",
            r"(?:^|\n)\s*(?:if|for|while|switch|match)\s+",
        ]
        score = 0
        for pat in code_patterns:
            if re.search(pat, stripped, re.MULTILINE):
                score += 1
        if score >= 2:
            return "code"

        return "plaintext"

    # ------------------------------------------------------------------
    # JSON compression
    # ------------------------------------------------------------------

    def _compress_json(self, content: str, stats: dict) -> str:
        parsed = json.loads(content)
        self._reverse_map.clear()
        compressed = self._walk_and_shorten(parsed)
        stats["key_shorten_count"] = len(self._reverse_map)
        stats["reverse_map"] = dict(self._reverse_map)
        return json.dumps(compressed, ensure_ascii=False, separators=(",", ":"))

    def _walk_and_shorten(self, node):
        """Recursively shorten all dict keys using *self._key_map*."""
        if isinstance(node, dict):
            new = {}
            for k, v in node.items():
                short = self._key_map.get(k, k)
                if short != k:
                    self._reverse_map[short] = k
                new[short] = self._walk_and_shorten(v)
            return new
        if isinstance(node, list):
            return [self._walk_and_shorten(item) for item in node]
        return node

    # ------------------------------------------------------------------
    # HTML compression (HTML -> markdown)
    # ------------------------------------------------------------------

    def _compress_html(self, content: str, stats: dict) -> str:
        original = content
        # Remove comments
        content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
        # Replace <br>, </p>, </div>, </li>, </tr> with newlines
        content = re.sub(
            r"</?(?:br|p|div|li|tr|h[1-6]|section|article|blockquote)[^>]*>",
            "\n",
            content,
            flags=re.IGNORECASE,
        )
        # Strip remaining tags
        content = re.sub(r"<[^>]+>", "", content)
        # Decode HTML entities
        content = html.unescape(content)
        # Collapse blank lines
        content = re.sub(r"\n{3,}", "\n\n", content)
        content = content.strip()

        stats["tags_removed"] = len(re.findall(r"<[^>]+>", original))
        stats["lines"] = content.count("\n") + 1
        return content

    # ------------------------------------------------------------------
    # URL ref substitution
    # ------------------------------------------------------------------

    def _compress_urls(self, content: str, stats: dict) -> str:
        self._url_refs.clear()
        self._url_counter = 0

        url_pattern = re.compile(r"https?://\S+")

        def _replace_url(m: re.Match) -> str:
            self._url_counter += 1
            ref = f"{{ref_{self._url_counter}}}"
            self._url_refs[ref] = m.group(0)
            return ref

        result = url_pattern.sub(_replace_url, content)
        stats["urls_replaced"] = self._url_counter
        stats["url_map"] = dict(self._url_refs)
        return result

    # ------------------------------------------------------------------
    # Stacktrace compression
    # ------------------------------------------------------------------

    def _compress_stacktrace(self, content: str, stats: dict) -> str:
        lines = content.splitlines()
        if not lines:
            return content

        # Keep first line (Traceback or initial context)
        kept = [lines[0]] if lines else []

        # Find the last line with exception type
        exc_line = None
        for line in reversed(lines):
            if re.match(r"^\w+(?:Error|Exception|Warning|Fault|Exit|Interrupt)", line):
                exc_line = line
                break

        # Collect "key frames" — lines that contain meaningful file paths
        # but skip internal / library frames
        key_frames = []
        skip_dirs = ("/lib/", "/site-packages/", "/usr/lib/", "node_modules/")
        for line in lines[1:]:
            frame_match = re.match(r'^\s*File "([^"]+)"', line)
            if frame_match:
                path = frame_match.group(1)
                if any(sd in path for sd in skip_dirs):
                    continue
                key_frames.append(line)

        if exc_line:
            key_frames.append(exc_line)

        kept.extend(key_frames)
        stats["original_lines"] = len(lines)
        stats["kept_lines"] = len(kept)
        stats["frames_removed"] = len(lines) - len(kept)
        return "\n".join(kept)

    # ------------------------------------------------------------------
    # Plaintext / code compression
    # ------------------------------------------------------------------

    def _compress_plaintext(self, content: str, ctype: str, stats: dict) -> str:
        # Step 1: URL ref substitution
        content = self._compress_urls(content, stats)

        # Step 2: Dedup — collapse repeated blocks > threshold
        content = self._dedup(content, stats)

        # Step 3: For long plaintext, summary truncation
        if ctype == "plaintext" and len(content) > 3000:
            content = self._summarize_truncation(content, stats)

        return content

    def _dedup(self, content: str, stats: dict) -> str:
        lines = content.splitlines()
        if len(lines) < 6:
            return content

        # Detect repeated contiguous blocks (3+ identical lines)
        new_lines: list[str] = []
        i = 0
        dedup_count = 0
        while i < len(lines):
            # Look ahead for repeated blocks of 3+ lines
            best_repeat = 0
            best_length = 0
            for block_len in range(min(10, (len(lines) - i) // 2), 2, -1):
                block = tuple(lines[i : i + block_len])
                # How many times does this block repeat consecutively?
                repeat = 1
                j = i + block_len
                while (
                    j + block_len <= len(lines)
                    and tuple(lines[j : j + block_len]) == block
                ):
                    repeat += 1
                    j += block_len
                if repeat > best_repeat:
                    best_repeat = repeat
                    best_length = block_len

            if best_repeat > 1:
                new_lines.extend(lines[i : i + best_length])
                new_lines.append(f"[重复 {best_repeat}x，共 {best_length} 行]")
                i += best_length * best_repeat
                dedup_count += 1
            else:
                new_lines.append(lines[i])
                i += 1

        stats["dedup_blocks"] = dedup_count
        return "\n".join(new_lines)

    def _summarize_truncation(self, content: str, stats: dict) -> str:
        """Summarize long plaintext by keeping head, tail, and a summary in between."""
        # Split into paragraphs
        paragraphs = re.split(r"\n\s*\n", content)
        if len(paragraphs) < 3:
            # Fallback: just truncate at 3000
            summary = content[:3000]
            stats["truncated"] = True
            stats["original_paragraphs"] = len(paragraphs)
            return summary

        head = paragraphs[0]
        tail_text = "\n\n".join(paragraphs[-2:])

        middle_count = len(paragraphs) - 3
        summary_line = (
            f"\n\n[... 省略 {middle_count} 段落，共约 {len(content)} 字符 ...]\n\n"
        )

        result = head + summary_line + tail_text
        stats["truncated"] = True
        stats["original_paragraphs"] = len(paragraphs)
        stats["kept_paragraphs"] = 3
        return result

    # ── 压缩统计持久化 ─────────────────────────────────────────────

    def _record_stats(
        self, content_type: str, original_len: int, compressed_len: int
    ) -> None:
        """将单次压缩记录写入 usage.db 的 compression_stats 表。"""
        try:
            ratio = 1.0 - (compressed_len / max(original_len, 1))
            conn = _persist._get_db(str(Path.home() / ".kos" / "usage.db"))
            conn.execute("""
                CREATE TABLE IF NOT EXISTS compression_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_type TEXT DEFAULT '',
                    original_len INTEGER DEFAULT 0,
                    compressed_len INTEGER DEFAULT 0,
                    ratio REAL DEFAULT 0.0,
                    timestamp TEXT DEFAULT (datetime('now'))
                )
            """)
            conn.execute(
                "INSERT INTO compression_stats (content_type, original_len, compressed_len, ratio) VALUES (?, ?, ?, ?)",
                (content_type, original_len, compressed_len, round(ratio, 4)),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass  # 统计不影响主功能
