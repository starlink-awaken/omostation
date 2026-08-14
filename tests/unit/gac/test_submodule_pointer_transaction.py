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

    gate_arg_definitions = [
        line.strip()
        for line in content.splitlines()
        if line.strip().startswith("gate_args=(")
    ]
    assert len(gate_arg_definitions) == 2
    assert all("--require-main" in line for line in gate_arg_definitions)
    assert content.count('submodule-reachability-gate.py" "${gate_args[@]}"') == 2


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return completed.stdout.strip()


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    os.chmod(path, 0o755)


def _init_transaction_fixture(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    runtime_remote = tmp_path / "runtime-remote"
    cockpit_remote = tmp_path / "cockpit-remote"
    for remote in (runtime_remote, cockpit_remote):
        remote.mkdir()
        _git(remote, "init", "-q")
        _git(remote, "config", "user.name", "Test")
        _git(remote, "config", "user.email", "test@example.com")
        (remote / "tracked.txt").write_text("baseline\n", encoding="utf-8")
        _git(remote, "add", "tracked.txt")
        _git(remote, "commit", "-qm", "baseline")

    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "user.email", "test@example.com")
    _git(
        repo,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(runtime_remote),
        "projects/runtime",
    )
    _git(
        repo,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(cockpit_remote),
        "projects/cockpit",
    )
    _git(repo, "commit", "-qam", "baseline")
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")

    (runtime_remote / "tracked.txt").write_text("updated\n", encoding="utf-8")
    _git(runtime_remote, "commit", "-qam", "update")
    _git(repo / "projects/runtime", "fetch", "-q", "origin")
    _git(repo / "projects/runtime", "checkout", "-q", "FETCH_HEAD")
    _git(repo, "submodule", "deinit", "-f", "--", "projects/cockpit")

    (repo / "bin" / "ssot").mkdir(parents=True)
    (repo / "bin" / "ssot" / "submodule-pointer-transaction.sh").write_bytes(
        SCRIPT.read_bytes()
    )
    _write_executable(repo / "bin" / "ssot" / "sync-submodules-push.sh", "#!/bin/sh\nexit 0\n")
    _write_executable(
        repo / "bin" / "ssot" / "submodule-reachability-gate.py",
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "pathlib.Path('gate-args.txt').write_text('\\n'.join(sys.argv[1:]))\n",
    )
    _write_executable(repo / "bin" / "change-lane-check.py", "#!/usr/bin/env python3\n")
    _write_executable(repo / "bin" / "ssot" / "ssot-guardian.py", "#!/usr/bin/env python3\n")
    return repo


def test_transaction_defaults_to_incremental_changed_gitlinks(tmp_path: Path) -> None:
    repo = _init_transaction_fixture(tmp_path)

    completed = subprocess.run(
        ["bash", str(repo / "bin" / "ssot" / "submodule-pointer-transaction.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (repo / "gate-args.txt").read_text(encoding="utf-8").splitlines() == [
        "--source",
        "worktree",
        "--fetch",
        "--require-main",
        "--changed-from",
        "origin/main",
    ]
    assert _git(repo, "diff", "--cached", "--name-only") == "projects/runtime"


def test_transaction_all_mode_keeps_the_full_gate_contract(tmp_path: Path) -> None:
    repo = _init_transaction_fixture(tmp_path)

    completed = subprocess.run(
        [
            "bash",
            str(repo / "bin" / "ssot" / "submodule-pointer-transaction.sh"),
            "--all",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (repo / "gate-args.txt").read_text(encoding="utf-8").splitlines() == [
        "--source",
        "worktree",
        "--fetch",
        "--require-main",
    ]
    assert _git(repo, "diff", "--cached", "--name-only") == "projects/runtime"


def test_transaction_rejects_unrelated_staged_changes_before_side_effects(
    tmp_path: Path,
) -> None:
    repo = _init_transaction_fixture(tmp_path)
    (repo / "unrelated.txt").write_text("must stay untouched\n", encoding="utf-8")
    _git(repo, "add", "unrelated.txt")

    completed = subprocess.run(
        ["bash", str(repo / "bin" / "ssot" / "submodule-pointer-transaction.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 2
    assert "index must be clean" in completed.stderr
    assert not (repo / "gate-args.txt").exists()
    assert _git(repo, "diff", "--cached", "--name-only") == "unrelated.txt"


def test_transaction_failure_unstages_its_pointer_without_losing_worktree_change(
    tmp_path: Path,
) -> None:
    repo = _init_transaction_fixture(tmp_path)
    _write_executable(
        repo / "bin" / "ssot" / "ssot-guardian.py",
        "#!/usr/bin/env python3\nraise SystemExit(7)\n",
    )

    completed = subprocess.run(
        ["bash", str(repo / "bin" / "ssot" / "submodule-pointer-transaction.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 7
    assert _git(repo, "diff", "--cached", "--name-only") == ""
    assert _git(repo, "diff", "--name-only") == "projects/runtime"


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
        [
            "bash",
            str(repo / "bin" / "ssot" / "submodule-pointer-transaction.sh"),
            "--all",
        ],
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
