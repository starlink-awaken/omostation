"""write-owner-audit 的范围采集面 — 回归测试.

2026-11-09 实测的失效形状: 该审计器唯一的采集面是 git 索引 (`--staged`), 而实际运行它的
场合 —— CI checkout 之后、post-commit、手工跑 `make gac-local-gate` —— 索引恒为空集,
于是「审计 0 个文件 ⇒ PASS」在每条路径上都是真绿但不是判定。它声明的
`write-owners.yaml` → `.omo/debt/` `no-direct-write` 因此从未生效。

本测试锁死三件事:
  1. `--range` 能看见交付的改动 (索引面看不见的时候它看得见);
  2. 范围面不套 env 豁免 (否则又回到「唯一跑到它的模式恰好豁免它」);
  3. 没有采集面 / 采集面拿不到 ⇒ 报错, 不算通过。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "bin" / "ssot" / "write-owner-audit.py"


def _load():
    spec = importlib.util.spec_from_file_location("write_owner_audit", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["write_owner_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return res.stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "xiamingxing")
    _git(repo, "config", "user.email", "x@example.invalid")
    return repo


def _owners(repo: Path, path: str, owner: str) -> None:
    reg = repo / ".omo" / "_truth" / "registry"
    reg.mkdir(parents=True, exist_ok=True)
    (reg / "write-owners.yaml").write_text(
        f"write_owners:\n  - path: \"{path}\"\n    owner: \"{owner}\"\n",
        encoding="utf-8",
    )


def _patch_repo(mod, monkeypatch, repo: Path) -> None:
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.setattr(
        mod, "OWNERS_YAML", repo / ".omo" / "_truth" / "registry" / "write-owners.yaml"
    )


def test_range_face_sees_delivered_change(tmp_path, monkeypatch, capsys):
    """交付的 commit 改了 script: 拥有的文件 → 范围面报违规, 即便在 CI 环境下."""
    mod = _load()
    repo = _repo(tmp_path)
    _owners(repo, ".omo/debt/*", "script:omo-debt")
    (repo / ".omo" / "debt").mkdir(parents=True, exist_ok=True)
    (repo / ".omo" / "debt" / "A.yaml").write_text("x: 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed")
    base = _git(repo, "rev-parse", "HEAD")

    (repo / ".omo" / "debt" / "A.yaml").write_text("x: 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "governance_state: hand-written broker state")
    head = _git(repo, "rev-parse", "HEAD")

    _patch_repo(mod, monkeypatch, repo)
    monkeypatch.setenv("CI", "true")

    # 历史语义: CI checkout 不 stage ⇒ 索引面为空 ⇒ PASS. 这正是原来空转的那条形状.
    monkeypatch.setattr(sys, "argv", ["write-owner-audit.py", "--staged", "--json"])
    assert mod.main() == 0
    assert json.loads(capsys.readouterr().out)["files_audited"] == 0

    # 范围面看得见交付本身
    monkeypatch.setattr(sys, "argv", ["write-owner-audit.py", "--range", f"{base}..{head}"])
    assert mod.main() == 1, "范围面必须把这条手写 broker 状态判成违规"
    assert "owned by system" in capsys.readouterr().err


def test_range_json_reports_face_and_count(tmp_path, monkeypatch, capsys):
    mod = _load()
    repo = _repo(tmp_path)
    _owners(repo, ".omo/debt/**", "script:omo-debt")
    (repo / ".omo" / "debt").mkdir(parents=True, exist_ok=True)
    (repo / ".omo" / "debt" / "B.yaml").write_text("x: 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / ".omo" / "debt" / "B.yaml").write_text("x: 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "docs(debt): 手写")

    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.setattr(
        mod, "OWNERS_YAML", repo / ".omo" / "_truth" / "registry" / "write-owners.yaml"
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        sys,
        "argv",
        ["write-owner-audit.py", "--range", f"{base}..HEAD", "--json"],
    )
    assert mod.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert report["face"] == f"range:{base}..HEAD"
    assert report["files_audited"] == 1
    assert report["rules_loaded"] == 1
    assert report["ok"] is False
    assert len(report["violations"]) == 1
    # 兼容既有键
    assert report["staged_files_audited"] == 0


def test_advisory_exits_zero_but_still_prints_violations(tmp_path, monkeypatch, capsys):
    mod = _load()
    repo = _repo(tmp_path)
    _owners(repo, ".omo/debt/*", "script:omo-debt")
    (repo / ".omo" / "debt").mkdir(parents=True, exist_ok=True)
    (repo / ".omo" / "debt" / "C.yaml").write_text("x: 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "seed")
    base = _git(repo, "rev-parse", "HEAD")
    (repo / ".omo" / "debt" / "C.yaml").write_text("x: 2\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "chore(debt): 手写")

    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.setattr(
        mod, "OWNERS_YAML", repo / ".omo" / "_truth" / "registry" / "write-owners.yaml"
    )
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        sys,
        "argv",
        ["write-owner-audit.py", "--range", f"{base}..HEAD", "--advisory", "--json"],
    )
    assert mod.main() == 0, "advisory 恒退 0, 与 change-lane-check 同口径"
    report = json.loads(capsys.readouterr().out)
    assert len(report["violations"]) == 1, "退 0 但不能把违规抹掉"


def test_no_face_is_error_not_silent_pass(tmp_path, monkeypatch, capsys):
    """缺省调用过去返回 ok=true (审计 0 个文件). 现在必须报错."""
    mod = _load()
    repo = _repo(tmp_path)
    _owners(repo, ".omo/debt/*", "script:omo-debt")
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.setattr(
        mod, "OWNERS_YAML", repo / ".omo" / "_truth" / "registry" / "write-owners.yaml"
    )
    monkeypatch.setattr(sys, "argv", ["write-owner-audit.py"])
    assert mod.main() == 2
    assert "采集面" in capsys.readouterr().err


def test_both_faces_rejected(tmp_path, monkeypatch):
    mod = _load()
    repo = _repo(tmp_path)
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.setattr(
        mod, "OWNERS_YAML", repo / ".omo" / "_truth" / "registry" / "write-owners.yaml"
    )
    monkeypatch.setattr(
        sys, "argv", ["write-owner-audit.py", "--staged", "--range", "a..b"]
    )
    assert mod.main() == 2


def test_unresolvable_range_is_not_a_pass(tmp_path, monkeypatch, capsys):
    """git diff 失败不能退化成「0 违规 = 绿」; advisory 才允许退 0, 且要打出原因."""
    mod = _load()
    repo = _repo(tmp_path)
    _owners(repo, ".omo/debt/*", "script:omo-debt")
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.setattr(
        mod, "OWNERS_YAML", repo / ".omo" / "_truth" / "registry" / "write-owners.yaml"
    )
    monkeypatch.setattr(
        sys, "argv", ["write-owner-audit.py", "--range", "nope999..HEAD", "--json"]
    )
    assert mod.main() == 1
    report = json.loads(capsys.readouterr().out)
    assert "face_unavailable" in report
    assert report["ok"] is False

    monkeypatch.setattr(
        sys,
        "argv",
        ["write-owner-audit.py", "--range", "nope999..HEAD", "--advisory", "--json"],
    )
    assert mod.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert "face_unavailable" in report


def test_duplicate_rules_do_not_double_count_files(tmp_path):
    """.omo/debt/* 与 .omo/debt/** 同时命中一个文件 ⇒ 违规条数按文件计, 不是按规则计."""
    mod = _load()
    owners = [
        {"path": ".omo/debt/*", "owner": "script:omo-debt"},
        {"path": ".omo/debt/**", "owner": "script:omo-debt"},
    ]
    v = mod.audit_staged(
        [".omo/debt/items/X.yaml"], owners, "xiamingxing", apply_env_exemption=False
    )
    assert len(v) == 1, f"一个文件只应记 1 条, 实得 {len(v)}"
    # 不同 owner 的两条规则仍要各报一次
    v2 = mod.audit_staged(
        [".omo/debt/items/X.yaml"],
        [
            {"path": ".omo/debt/*", "owner": "script:omo-debt"},
            {"path": ".omo/debt/**", "owner": "daemon:other"},
        ],
        "xiamingxing",
        apply_env_exemption=False,
    )
    assert len(v2) == 2


def test_resolve_range_auto_prefers_push_range(tmp_path, monkeypatch):
    mod = _load()
    repo = _repo(tmp_path)
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.setenv("PUSH_RANGE", "abc123..def456")
    assert mod.resolve_range("auto") == "abc123..def456"
    assert mod.resolve_range("x..y") == "x..y"


def test_resolve_range_auto_without_base_raises(tmp_path, monkeypatch):
    mod = _load()
    repo = _repo(tmp_path)  # 空 repo, 无 origin/main
    monkeypatch.setattr(mod, "WORKSPACE", repo)
    monkeypatch.delenv("PUSH_RANGE", raising=False)
    try:
        mod.resolve_range("auto")
    except RuntimeError as e:
        assert "无法定基" in str(e)
    else:
        raise AssertionError("解不出基线时必须抛错, 不能返回空面")
