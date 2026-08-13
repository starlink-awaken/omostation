import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "ssot" / "submodule-pointer-transaction.sh"


def test_transaction_lock_resolves_the_actual_gitdir() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert 'git rev-parse --path-format=absolute --git-path "submodule-pointer-transaction.lock"' in content
    assert 'lock="$ROOT/.git/submodule-pointer-transaction.lock"' not in content


def test_transaction_requires_gitlinks_to_be_on_submodule_main() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    gate_calls = [
        line.strip()
        for line in content.splitlines()
        if "submodule-reachability-gate.py" in line
    ]
    assert gate_calls
    assert all("--require-main" in line for line in gate_calls)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def test_transaction_query_failure_preserves_index_and_head(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / "bin" / "ssot").mkdir(parents=True)
    (repo / "projects" / "runtime").mkdir(parents=True)
    (repo / ".gitmodules").write_text(
        '[submodule "projects/runtime"]\n\tpath = projects/runtime\n\turl = local\n',
        encoding="utf-8",
    )
    (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
    (repo / "bin" / "ssot" / "submodule-pointer-transaction.sh").write_bytes(
        SCRIPT.read_bytes()
    )
    sync = repo / "bin" / "ssot" / "sync-submodules-push.sh"
    sync.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    gate = repo / "bin" / "ssot" / "submodule-reachability-gate.py"
    gate.write_text(
        '#!/usr/bin/env python3\nimport sys\nprint("main ancestry query failed", file=sys.stderr)\nsys.exit(2)\n',
        encoding="utf-8",
    )
    os.chmod(sync, 0o755)
    os.chmod(gate, 0o755)

    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "baseline")
    (repo / "tracked.txt").write_text("unstaged but preserved\n", encoding="utf-8")

    head_before = _git(repo, "rev-parse", "HEAD")
    index_before = _git(repo, "write-tree")
    completed = subprocess.run(
        ["bash", str(repo / "bin" / "ssot" / "submodule-pointer-transaction.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "main ancestry query failed" in completed.stderr
    assert _git(repo, "rev-parse", "HEAD") == head_before
    assert _git(repo, "write-tree") == index_before
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "unstaged but preserved\n"
