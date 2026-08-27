"""Tests for the gitlink ancestry gate (--range mode of check-submodule-rewind.py).

TDD fixture scenarios (BET: gitlink ancestry gate 双落点, 2026-08-24):
  1. forward  → PASS (exit 0, no output blocking)
  2. rewind   → BLOCK (exit 1, fix guidance present)
  3. rewind + [gitlink-regress: ...] tag in base..head → WARN (exit 0) + known-debt fingerprint
"""

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "bin" / "gac" / "check-submodule-rewind.py"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _git_ok(cwd: Path, *args: str) -> str:
    result = _git(cwd, *args)
    assert result.returncode == 0, f"git {' '.join(args)} failed: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, *msg: str) -> str:
    _git_ok(cwd, "add", "-A")
    _git_ok(cwd, "commit", "-m", *msg)
    return _git_ok(cwd, "rev-parse", "HEAD")


def make_fixture(tmp_path: Path) -> dict[str, Path | str]:
    """Build a main repo with one submodule and three pointer states.

    Returns fixture with:
      commit_a: main-repo commit carrying sub pointer c1
      commit_b: forward  (sub pointer c2, descendant of c1)
      commit_c: rewind   (sub pointer back to c1)
      commit_d: rewind + [gitlink-regress: ...] tag in commit body
    """
    # --- submodule repo ---
    s = tmp_path / "sub-repo"
    s.mkdir()
    _git_ok(s, "init", "-b", "main")
    _git_ok(s, "config", "user.email", "test@example.com")
    _git_ok(s, "config", "user.name", "fixture")
    (s / "f1.txt").write_text("one\n", encoding="utf-8")
    c1 = _commit(s, "sub c1")
    (s / "f2.txt").write_text("two\n", encoding="utf-8")
    c2 = _commit(s, "sub c2")

    # --- second submodule (pointer stable, used for skip-warning scenarios) ---
    s2 = tmp_path / "sub2-repo"
    s2.mkdir()
    _git_ok(s2, "init", "-b", "main")
    _git_ok(s2, "config", "user.email", "test@example.com")
    _git_ok(s2, "config", "user.name", "fixture")
    (s2 / "g1.txt").write_text("one\n", encoding="utf-8")
    _commit(s2, "sub2 c1")

    # --- main repo ---
    m = tmp_path / "main-repo"
    m.mkdir()
    _git_ok(m, "init", "-b", "main")
    _git_ok(m, "config", "user.email", "test@example.com")
    _git_ok(m, "config", "user.name", "fixture")
    # submodule add 检出的是 sub 的 main tip (c2); 显式 pin c1 作为 commit_a 的指针
    _git_ok(m, "-c", "protocol.file.allow=always", "submodule", "add", str(s), "sub")
    _git_ok(m, "-c", "protocol.file.allow=always", "submodule", "add", str(s2), "sub2")
    _git_ok(m / "sub", "checkout", c1)
    commit_a = _commit(m, "add submodule at c1")

    # forward: bump sub to c2
    _git_ok(m / "sub", "checkout", c2)
    commit_b = _commit(m, "forward sub to c2")

    # rewind: back to c1
    _git_ok(m / "sub", "checkout", c1)
    commit_c = _commit(m, "rewind sub to c1")

    # rewind + exemption tag (tree 无变化 → allow-empty; 标签在 commit body)
    _git_ok(
        m,
        "commit",
        "--allow-empty",
        "-m",
        "rewind sub to c1 (exempt)",
        "-m",
        "[gitlink-regress: deliberate downgrade test]",
    )
    commit_d = _git_ok(m, "rev-parse", "HEAD")

    return {
        "m": m,
        "s": s,
        "c1": c1,
        "c2": c2,
        "commit_a": commit_a,
        "commit_b": commit_b,
        "commit_c": commit_c,
        "commit_d": commit_d,
    }


def run_gate(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class TestForwardPointer:
    def test_forward_pointer_passes(self, tmp_path):
        fx = make_fixture(tmp_path)
        result = run_gate(fx["m"], "--range", fx["commit_a"], fx["commit_b"], "--cwd", str(fx["m"]))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "FAIL" not in result.stdout


class TestRewindBlocks:
    def test_rewind_blocks_with_fix_guidance(self, tmp_path):
        fx = make_fixture(tmp_path)
        result = run_gate(fx["m"], "--range", fx["commit_b"], fx["commit_c"], "--cwd", str(fx["m"]))
        assert result.returncode == 1, result.stdout + result.stderr
        assert "回退" in result.stdout
        assert "sub" in result.stdout
        # 拦截消息必须含修复指引与豁免说明
        assert "gitlink-regress" in result.stdout

    def test_rewind_blocks_json_mode(self, tmp_path):
        import json

        fx = make_fixture(tmp_path)
        result = run_gate(
            fx["m"],
            "--range",
            fx["commit_b"],
            fx["commit_c"],
            "--cwd",
            str(fx["m"]),
            "--json",
        )
        assert result.returncode == 1
        data = json.loads(result.stdout)
        assert data["ok"] is False
        assert len(data["violations"]) == 1
        assert data["violations"][0]["path"] == "sub"
        assert data["exempted"] is False


class TestExemptionTag:
    def test_exempt_rewind_warns_and_writes_debt(self, tmp_path):
        fx = make_fixture(tmp_path)
        result = run_gate(fx["m"], "--range", fx["commit_b"], fx["commit_d"], "--cwd", str(fx["m"]))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "WARN" in result.stdout
        debt_file = fx["m"] / ".omo" / "_truth" / "registry" / "gate-known-debt.yaml"
        assert debt_file.is_file(), f"debt file not written: {result.stdout}"
        content = debt_file.read_text(encoding="utf-8")
        assert "submodule-ancestry-gate" in content
        assert "gitlink-ancestry" in content

    def test_exemption_preserves_existing_debt_entries(self, tmp_path):
        import yaml

        fx = make_fixture(tmp_path)
        debt_file = fx["m"] / ".omo" / "_truth" / "registry" / "gate-known-debt.yaml"
        debt_file.parent.mkdir(parents=True, exist_ok=True)
        debt_file.write_text(
            "version: 1\ngrowth_policy: shrink_only\nentries:\n"
            "  - fingerprint: other-surface|other-check|ab12cd34\n"
            "    active: true\n",
            encoding="utf-8",
        )
        result = run_gate(fx["m"], "--range", fx["commit_b"], fx["commit_d"], "--cwd", str(fx["m"]))
        assert result.returncode == 0, result.stdout + result.stderr
        data = yaml.safe_load(debt_file.read_text(encoding="utf-8"))
        keys = [e.get("fingerprint") for e in data["entries"]]
        assert "other-surface|other-check|ab12cd34" in keys, "existing entry must survive"
        assert any(k.startswith("gitlink-ancestry|") for k in keys), "new fingerprint must be appended"
        assert data["growth_policy"] == "shrink_only"

    def test_exemption_survives_unrelated_uninit_warning(self, tmp_path):
        fx = make_fixture(tmp_path)
        shutil.rmtree(fx["m"] / "sub2")
        result = run_gate(fx["m"], "--range", fx["commit_b"], fx["commit_d"], "--cwd", str(fx["m"]))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "WARN" in result.stdout
        debt_file = fx["m"] / ".omo" / "_truth" / "registry" / "gate-known-debt.yaml"
        assert debt_file.is_file()

    def test_exempt_rewind_is_idempotent(self, tmp_path):
        import yaml

        fx = make_fixture(tmp_path)
        first = run_gate(fx["m"], "--range", fx["commit_b"], fx["commit_d"], "--cwd", str(fx["m"]))
        assert first.returncode == 0
        second = run_gate(fx["m"], "--range", fx["commit_b"], fx["commit_d"], "--cwd", str(fx["m"]))
        assert second.returncode == 0, second.stdout + second.stderr
        debt_file = fx["m"] / ".omo" / "_truth" / "registry" / "gate-known-debt.yaml"
        data = yaml.safe_load(debt_file.read_text(encoding="utf-8"))
        keys = [e.get("fingerprint") for e in data["entries"]]
        assert sum(1 for k in keys if k.startswith("gitlink-ancestry|")) == 1, "no duplicate entries"

    def test_no_write_debt_flag_skips_write(self, tmp_path):
        fx = make_fixture(tmp_path)
        result = run_gate(
            fx["m"],
            "--range",
            fx["commit_b"],
            fx["commit_d"],
            "--cwd",
            str(fx["m"]),
            "--no-write-debt",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        debt_file = fx["m"] / ".omo" / "_truth" / "registry" / "gate-known-debt.yaml"
        assert not debt_file.exists(), "debt file must not be written with --no-write-debt"


class TestTolerances:
    def test_doc_mention_of_tag_does_not_exempt(self, tmp_path):
        fx = make_fixture(tmp_path)
        m: Path = fx["m"]
        _git_ok(m, "checkout", "-b", "doc-scenario", fx["commit_b"])
        _git_ok(m / "sub", "checkout", fx["c1"])
        _git_ok(m, "add", "sub")
        _git_ok(m, "commit", "-m", "rewind (no tag)")
        _git_ok(
            m,
            "commit",
            "--allow-empty",
            "-m",
            "docs: 豁免语法说明",
            "-m",
            "豁免: commit body 含 [gitlink-regress: <理由>] 标签 → 降级 warning",
        )
        doc_head = _git_ok(m, "rev-parse", "HEAD")
        result = run_gate(m, "--range", fx["commit_b"], doc_head, "--cwd", str(m))
        assert result.returncode == 1, result.stdout + result.stderr
        assert "回退" in result.stdout

    def test_uninitialized_submodule_warns_and_passes(self, tmp_path):
        fx = make_fixture(tmp_path)
        shutil.rmtree(fx["m"] / "sub")
        result = run_gate(fx["m"], "--range", fx["commit_a"], fx["commit_b"], "--cwd", str(fx["m"]))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "未初始化" in result.stdout or "uninit" in result.stdout.lower()

    def test_unchanged_pointer_skips(self, tmp_path):
        fx = make_fixture(tmp_path)
        result = run_gate(fx["m"], "--range", fx["commit_a"], fx["commit_a"], "--cwd", str(fx["m"]))
        assert result.returncode == 0, result.stdout + result.stderr

    def test_missing_base_gracefully_skips(self, tmp_path):
        fx = make_fixture(tmp_path)
        result = run_gate(fx["m"], "--range", "no-such-ref", "HEAD", "--cwd", str(fx["m"]))
        assert result.returncode == 0, result.stdout + result.stderr
        assert "no-such-ref" in result.stdout or "无法解析" in result.stdout or "skip" in result.stdout.lower()

    def test_head_defaults_to_head(self, tmp_path):
        fx = make_fixture(tmp_path)
        result = run_gate(fx["m"], "--range", fx["commit_b"], "--cwd", str(fx["m"]))
        assert result.returncode in (0, 1), "single-arg range must accept default head"
