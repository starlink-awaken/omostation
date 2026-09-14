"""D0 regression tests for write surfaces inside tracked submodules."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

MODULE_PATH = Path(__file__).parents[1] / "bin/plan/bet-ledger.py"
SPEC = importlib.util.spec_from_file_location("bet_ledger", MODULE_PATH)
assert SPEC and SPEC.loader
BET_LEDGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BET_LEDGER)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "d0-test@example.invalid")
    _git(path, "config", "user.name", "D0 Test")


def _workspace_with_gitlink(tmp_path: Path) -> tuple[Path, Path, str]:
    root = tmp_path / "workspace"
    child = root / "projects" / "omo"
    _init_repo(root)
    (root / "README.md").write_text("tracked root file\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-qm", "root baseline")

    _init_repo(child)
    tracked = child / "src" / "contract.py"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("CONTRACT = 1\n", encoding="utf-8")
    _git(child, "add", "src/contract.py")
    _git(child, "commit", "-qm", "child baseline")
    child_sha = _git(child, "rev-parse", "HEAD")

    _git(
        root,
        "update-index",
        "--add",
        "--cacheinfo",
        f"160000,{child_sha},projects/omo",
    )
    _git(root, "commit", "-qm", "track child gitlink")
    return root, child, child_sha


def _verify(root: Path, surface: str, monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(BET_LEDGER, "WS", root)
    data = {
        "bets": [
            {
                "id": "BET-TEST",
                "title": "D0 fixture",
                "done_when": [],
                "verify": [],
                "write_surfaces": [surface],
            }
        ]
    }
    return BET_LEDGER.cmd_verify(
        data,
        SimpleNamespace(bet_id="BET-TEST", execute=False),
    )


def test_verify_accepts_file_in_index_pinned_submodule_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _ = _workspace_with_gitlink(tmp_path)

    assert _verify(root, "projects/omo/src/contract.py", monkeypatch) == 0


def test_verify_accepts_directory_in_index_pinned_submodule_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _ = _workspace_with_gitlink(tmp_path)

    assert _verify(root, "projects/omo/src/", monkeypatch) == 0
    assert _verify(root, "projects/omo/src", monkeypatch) == 0


def test_verify_rejects_absent_directory_in_pinned_submodule(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _ = _workspace_with_gitlink(tmp_path)

    assert _verify(root, "projects/omo/tests/", monkeypatch) == 1


def test_verify_rejects_uncommitted_child_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, child, _ = _workspace_with_gitlink(tmp_path)
    dirty = child / "src" / "dirty.py"
    dirty.write_text("DIRTY = True\n", encoding="utf-8")

    assert _verify(root, "projects/omo/src/dirty.py", monkeypatch) == 1


def test_verify_uses_staged_gitlink_instead_of_child_worktree_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, child, _ = _workspace_with_gitlink(tmp_path)
    added = child / "src" / "new_contract.py"
    added.write_text("CONTRACT = 2\n", encoding="utf-8")
    _git(child, "add", "src/new_contract.py")
    _git(child, "commit", "-qm", "new child contract")
    new_sha = _git(child, "rev-parse", "HEAD")

    assert _verify(root, "projects/omo/src/new_contract.py", monkeypatch) == 1

    _git(
        root,
        "update-index",
        "--cacheinfo",
        f"160000,{new_sha},projects/omo",
    )
    assert _verify(root, "projects/omo/src/new_contract.py", monkeypatch) == 0


def test_gitlink_prefix_match_respects_path_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _ = _workspace_with_gitlink(tmp_path)

    assert _verify(root, "projects/omo2/src/contract.py", monkeypatch) == 1


def test_complete_accepts_index_pinned_submodule_surface(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, _, _ = _workspace_with_gitlink(tmp_path)
    spec_path = root / "docs" / "superpowers" / "specs" / "accepted.md"
    spec_path.parent.mkdir(parents=True)
    spec_path.write_text(
        "---\n"
        "schema_version: specification/v1\n"
        "spec_version: 1.0.0\n"
        "status: accepted\n"
        "bet_id: BET-TEST\n"
        "---\n\n"
        "# Test specification\n",
        encoding="utf-8",
    )
    ledger = root / "ledger.yaml"
    ledger.write_text(
        "bets:\n- id: BET-TEST\n  status: candidate\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(BET_LEDGER, "WS", root)
    monkeypatch.setattr(BET_LEDGER, "LEDGER", ledger)
    monkeypatch.setattr(
        BET_LEDGER,
        "validate_completion_evidence",
        lambda matrix, *, workspace, value_indicator_policy, done_at=None, bet_status=None: ("outcome_accepted", []),
    )
    monkeypatch.setitem(
        sys.modules,
        "chain_bind",
        SimpleNamespace(
            evaluate_complete=lambda bet, workspace, force: SimpleNamespace(ok=True, reasons=[])
        ),
    )
    data = {
        "bets": [
            {
                "id": "BET-TEST",
                "status": "candidate",
                "accepted_specifications": [
                    {
                        "spec_ref": "repo://docs/superpowers/specs/accepted.md",
                        "spec_version": "1.0.0",
                        "content_digest": f"sha256:{BET_LEDGER._file_sha256(spec_path)}",
                        "decision_ref": "decision://accepted/BET-TEST",
                    }
                ],
                "completion_evidence": {},
                "write_surfaces": ["projects/omo/src/contract.py"],
            }
        ]
    }

    rc = BET_LEDGER.cmd_complete(
        data,
        SimpleNamespace(bet_id="BET-TEST", force=False),
    )

    assert rc == 0
    assert "status: done" in ledger.read_text(encoding="utf-8")


def test_complete_writes_only_target_block_not_later_done_bets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression: cmd_complete 的写盘段曾因块边界按 '\\n- id:' 定位, 而 152/160 bet
    块以 '- appetite:' 开头, block 会吞进后续多个块 → 误检到别的 done bet 的
    'status: done' → 静默跳过写盘却报成功 (T6-02 complete 实录 2026-09-08)。

    同时验证: completion_evidence 里 8 空格缩进的 axis status (engineering/
    operational/value) 不会被误改, 只锚定 2 空格缩进的块级 status。
    """
    root = tmp_path
    ledger = root / "ledger.yaml"
    ledger.write_text(
        "bets:\n"
        "- id: BET-DONE-PREV\n"
        "  status: done\n"
        "  done_at: 2026-01-01\n"
        "- id: BET-TEST\n"
        "  non_goals:\n"
        "  - x\n"
        "  completion_evidence:\n"
        "    schema_version: completion-evidence-matrix/v1\n"
        "    axes:\n"
        "      engineering:\n"
        "        status: VERIFIED\n"
        "      operational:\n"
        "        status: PROVEN\n"
        "      value:\n"
        "        status: NOT_PROVEN\n"
        "        evidence: {}\n"
        "    overall_state: delivery_accepted\n"
        "  status: candidate\n"
        "  title: Test\n"
        "- id: BET-DONE-NEXT\n"
        "  status: done\n"
        "  done_at: 2026-01-02\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(BET_LEDGER, "WS", root)
    monkeypatch.setattr(BET_LEDGER, "LEDGER", ledger)
    monkeypatch.setattr(BET_LEDGER, "_is_spec_binding_required", lambda bet, workspace: False)
    monkeypatch.setattr(BET_LEDGER, "resolve_value_indicator_policy", lambda bet: (False, None))
    monkeypatch.setattr(
        BET_LEDGER,
        "validate_completion_evidence",
        lambda matrix, *, workspace, value_indicator_policy, done_at=None, bet_status=None: (
            "delivery_accepted",
            [],
        ),
    )
    data = {
        "bets": [
            {"id": "BET-TEST", "status": "candidate", "completion_evidence": {}},
        ]
    }
    rc = BET_LEDGER.cmd_complete(data, SimpleNamespace(bet_id="BET-TEST", force=True))
    out = ledger.read_text(encoding="utf-8")
    assert rc == 0
    # 目标块置 done + done_at
    assert "  status: done\n  done_at: " in out
    # 相邻 done 块原样保留（不被吞改）
    assert "  done_at: 2026-01-02" in out
    assert "  done_at: 2026-01-01" in out
    # evidence 的 axis status 未被误改为 done
    assert "        status: VERIFIED" in out
    assert "        status: PROVEN" in out
    assert "        status: NOT_PROVEN" in out


def test_verify_execute_fails_when_command_exits_nonzero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BET_LEDGER, "WS", tmp_path)
    data = {
        "bets": [
            {
                "id": "BET-TEST",
                "title": "verify exit",
                "done_when": [],
                "verify": [
                    {
                        "cmd": "python3 -c 'raise SystemExit(7)'",
                        "expect": "exit 0",
                    }
                ],
                "write_surfaces": [],
            }
        ]
    }
    rc = BET_LEDGER.cmd_verify(data, SimpleNamespace(bet_id="BET-TEST", execute=True))
    assert rc == 1


def test_verify_execute_passes_when_command_exits_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(BET_LEDGER, "WS", tmp_path)
    data = {
        "bets": [
            {
                "id": "BET-TEST",
                "title": "verify exit",
                "done_when": [],
                "verify": [
                    {
                        "cmd": "python3 -c 'raise SystemExit(0)'",
                        "expect": "exit 0",
                    }
                ],
                "write_surfaces": [],
            }
        ]
    }
    rc = BET_LEDGER.cmd_verify(data, SimpleNamespace(bet_id="BET-TEST", execute=True))
    assert rc == 0
