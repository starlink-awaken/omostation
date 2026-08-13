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
