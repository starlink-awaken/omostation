"""vocabulary_loader.py — 词汇契约 SSOT 加载器 (ADR-B/P5).

从 .omo/_truth/vocabulary.yaml 加载状态词汇契约,
供度量引擎和门禁校验使用, 替代硬编码字面量.
"""
from __future__ import annotations
from pathlib import Path
from typing import FrozenSet

DEFAULT_TERMINAL = frozenset({"closed", "resolved"})
DEFAULT_ACTIVE = frozenset({"registered", "open", "candidate", "scheduled", "in_progress", "mitigated"})


def load_vocabulary(omo_dir: Path) -> dict:
    vocab_path = omo_dir / "_truth" / "vocabulary.yaml"
    if not vocab_path.exists():
        return {"terminal": DEFAULT_TERMINAL, "active": DEFAULT_ACTIVE}
    try:
        import yaml
        data = yaml.safe_load(vocab_path.read_text(encoding="utf-8")) or {}
        lc = data.get("lifecycle", {})
        return {
            "terminal": frozenset(lc.get("terminal", DEFAULT_TERMINAL)),
            "active": frozenset(lc.get("active", DEFAULT_ACTIVE)),
        }
    except Exception:
        return {"terminal": DEFAULT_TERMINAL, "active": DEFAULT_ACTIVE}
