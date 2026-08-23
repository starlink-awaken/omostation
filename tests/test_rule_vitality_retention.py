"""rule-vitality.jsonl retention — bounded growth (遗留项治理)."""
import importlib.util
from pathlib import Path

import pytest

TRACKER = Path(__file__).resolve().parents[3] / "bin" / "gac" / "rule-vitality-tracker.py"


def _load():
    spec = importlib.util.spec_from_file_location("rvt", TRACKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, n: int):
    path.write_text(
        "".join(f'{{"rule_id":"r{i}","timestamp":"t"}}\n' for i in range(n)),
        encoding="utf-8",
    )


def test_no_rewrite_below_trigger(tmp_path):
    mod = _load()
    f = tmp_path / "v.jsonl"
    _write(f, 100)
    assert mod.enforce_retention(f, max_lines=50, trigger_bytes=10 * 1024 * 1024) == 0
    assert len(f.read_text().splitlines()) == 100


def test_trim_above_threshold(tmp_path):
    mod = _load()
    f = tmp_path / "v.jsonl"
    _write(f, 500)
    dropped = mod.enforce_retention(f, max_lines=100, trigger_bytes=1)
    assert dropped == 400
    lines = f.read_text().splitlines()
    assert len(lines) == 100
    import json

    last = json.loads(lines[-1])
    assert last["rule_id"] == "r499"


@pytest.mark.parametrize("missing", [True, False])
def test_missing_or_empty_safe(tmp_path, missing):
    mod = _load()
    f = tmp_path / ("v.jsonl" if not missing else "nope.jsonl")
    if not missing:
        f.write_text("", encoding="utf-8")
    assert mod.enforce_retention(f, max_lines=10, trigger_bytes=1) == 0
