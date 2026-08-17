"""Frontmatter detection — extracted from SharedBrain D_Logos.

Detects and validates YAML frontmatter blocks in markdown documents.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class FrontmatterBlock:
    start_line: int
    end_line: int
    start_char: int
    end_char: int
    content: str
    is_valid: bool
    parsed_data: dict[str, Any] | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_line": self.start_line,
            "end_line": self.end_line,
            "is_valid": self.is_valid,
            "fields": list(self.parsed_data.keys()) if isinstance(self.parsed_data, dict) else [],
            "error_message": self.error_message,
        }


@dataclass
class DetectionResult:
    file_path: Path
    blocks: list[FrontmatterBlock] | None = None
    recommendation: str = ""
    scan_duration_ms: float = 0.0

    def __post_init__(self) -> None:
        if self.blocks is None:
            self.blocks = []

    @property
    def status(self) -> str:
        if not self.blocks:
            return "MISSING"
        if len(self.blocks) == 1 and self.blocks[0].is_valid:
            return "OK"
        if len(self.blocks) == 1 and not self.blocks[0].is_valid:
            return "INVALID"
        if len(self.blocks) > 1:
            return "MULTIPLE"
        return "UNKNOWN"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.file_path),
            "status": self.status,
            "total_blocks": len(self.blocks) if self.blocks is not None else 0,
            "valid_blocks": sum(1 for b in self.blocks if b.is_valid) if self.blocks is not None else 0,
            "blocks": [b.to_dict() for b in self.blocks] if self.blocks is not None else [],
            "recommendation": self.recommendation,
        }


class FrontmatterDetector:
    def __init__(self) -> None:
        self.pattern = re.compile(r"(?:^|\n)---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL | re.MULTILINE)

    def detect(self, content: str) -> list[FrontmatterBlock]:
        blocks = []
        for match in self.pattern.finditer(content):
            start_pos, end_pos = match.start(), match.end()
            start_line = content[:start_pos].count("\n") + 1
            end_line = content[:end_pos].count("\n") + 1
            fm_content = match.group(1)
            parsed, err, valid = None, None, True
            try:
                parsed = yaml.safe_load(fm_content)
                if not isinstance(parsed, dict):
                    valid, err = False, f"Not a dict, got {type(parsed).__name__}"
            except yaml.YAMLError as e:
                valid, err = False, str(e)[:150]
            blocks.append(FrontmatterBlock(start_line, end_line, start_pos, end_pos, fm_content, valid, parsed, err))
        return blocks

    def analyze(self, path: Path) -> DetectionResult:
        t0 = time.time()
        content = path.read_text(encoding="utf-8")
        blocks = self.detect(content)
        rec = self._recommend(blocks)
        return DetectionResult(
            file_path=path, blocks=blocks, recommendation=rec, scan_duration_ms=(time.time() - t0) * 1000
        )

    def _recommend(self, blocks: list[FrontmatterBlock]) -> str:
        if not blocks:
            return "ADD_FRONTMATTER"
        if len(blocks) == 1 and blocks[0].is_valid:
            return "OK"
        if len(blocks) == 1:
            return f"FIX_YAML: {blocks[0].error_message}"
        return f"MERGE_BLOCKS: Found {len(blocks)} blocks"
