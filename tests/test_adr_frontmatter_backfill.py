"""C3 (ADR-0367): adr-frontmatter-backfill idempotency + canonical padding tests."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "adr" / "adr-frontmatter-backfill.py"


def load_module(path: Path, name: str):
    adr_dir = str(ROOT / "bin" / "adr")
    if adr_dir not in sys.path:
        sys.path.insert(0, adr_dir)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canonical_id_zero_pads() -> None:
    mod = load_module(SCRIPT, "adr_frontmatter_backfill")
    assert mod.canonical_id("8") == "ADR-0008"
    assert mod.canonical_id("306") == "ADR-0306"


def test_backfill_adds_missing_id_and_is_idempotent(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    path = decisions / "0012-foo-bar.md"
    path.write_text("---\ntitle: Foo\nstatus: ACCEPTED\n---\nbody\n", encoding="utf-8")

    mod = load_module(SCRIPT, "adr_frontmatter_backfill")
    note = mod.backfill(path, "12", dry_run=False)
    assert note is not None
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nid: ADR-0012\n"), text

    again = mod.backfill(path, "12", dry_run=False)
    assert again is None  # 幂等: 二次运行无改动


def test_backfill_fixes_mismatched_id(tmp_path: Path) -> None:
    decisions = tmp_path / "decisions"
    decisions.mkdir()
    path = decisions / "0055-xyz.md"
    path.write_text("---\nid: 55-xyz\nstatus: ACCEPTED\n---\nbody\n", encoding="utf-8")

    mod = load_module(SCRIPT, "adr_frontmatter_backfill")
    note = mod.backfill(path, "55", dry_run=False)
    assert note is not None
    assert "id: ADR-0055" in path.read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(subprocess.call([sys.executable, "-m", "pytest", str(__file__), "-v"]))
