# ---
# status: active
# lifecycle: active
# owner: governance-agent
# ssot: bin/ssot/doc-ssot-lint.py
# verifier: pytest tests/test_doc_ssot_lint_json.py
# ---
"""Regression test: doc-ssot-lint JSON branch must not crash on string-sentinel findings.

M3 (2026-10-06, ADR-0464 治理门禁覆盖审计修复波 R1):
`check_l0_mapping()` returns STRING sentinels ("<l0-mapping>") for
tool-missing/timeout/parse-error cases. The human-readable branch already guarded
with `isinstance`, but the JSON branch called `fp.is_absolute()` on the sentinel
and crashed with `AttributeError`. The guard's whole purpose is to keep the JSON
path crashing-free while still failing and still listing the finding.

This test proves the contract with a synthetic sentinel finding: JSON must be
valid, must contain the finding, must exit non-zero, and must not crash.
Without the `isinstance` guard this test crashes (AttributeError) — mutation
proof: delete the guard in bin/ssot/doc-ssot-lint.py and this test goes red.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "bin/ssot/doc-ssot-lint.py"
SPEC = importlib.util.spec_from_file_location("doc_ssot_lint_regression", MODULE_PATH)
assert SPEC and SPEC.loader
LINT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LINT)


def _install_sentinel(monkeypatch) -> None:
    """Force one `<l0-mapping>` string-sentinel finding through run_lint(as_json=True)."""
    monkeypatch.setattr(LINT, "find_md_files", lambda: [])
    monkeypatch.setattr(LINT, "check_required_generated_artifacts", lambda: [])
    monkeypatch.setattr(LINT, "check_orphan_docs", lambda: [])
    monkeypatch.setattr(
        LINT,
        "check_l0_mapping",
        lambda: [("<l0-mapping>", 1, "missing tool", "synthetic sentinel finding")],
    )


def test_json_path_handles_string_sentinel_without_crash(
    monkeypatch,
    capsys,
) -> None:
    _install_sentinel(monkeypatch)

    # Must NOT raise (pre-fix this raised AttributeError: 'str' object has no attribute 'is_absolute')
    exit_code = LINT.run_lint(as_json=True)

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["ok"] is False
    assert payload["conflicts"] == 1
    assert payload["findings"] == [
        {
            "file": "<l0-mapping>",
            "line": 1,
            "label": "missing tool",
            "reason": "synthetic sentinel finding",
        }
    ]
    # A guarding gate must still FAIL — a silent pass would be a silent drop.
    assert exit_code == 1


def test_human_branch_keeps_working_with_sentinel(
    monkeypatch,
    capsys,
) -> None:
    """The human-readable branch keeps rendering the sentinel (no regression)."""
    _install_sentinel(monkeypatch)

    exit_code = LINT.run_lint(as_json=False)

    out = capsys.readouterr().out
    assert "<l0-mapping>:1" in out
    assert "missing tool" in out
    assert exit_code == 1