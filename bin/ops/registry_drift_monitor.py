#!/usr/bin/env python3
"""Registry drift monitor — detect script-registry registration omissions.

Concurrent agents frequently add ``bin/*`` scripts without registering them in
the script-registry (``bin/ssot/script-registry.py``), which trips the
governance-verify gate (script-registry-validate + gac-validate
subtraction-quota). This monitor scans ``origin/main`` in an isolated worktree
and reports any missing registrations / baseline drift.

Usage:
    python3 bin/ops/registry_drift_monitor.py            # check + report
    python3 bin/ops/registry_drift_monitor.py --register # check + register missing
    python3 bin/ops/registry_drift_monitor.py --json     # machine-readable report

Exit code: 0 = healthy, 1 = drift found (missing registrations or baseline over).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Workspace root = repo root (parents: bin/ops/registry_drift_monitor.py → bin → root)
WORKSPACE = Path(__file__).resolve().parents[2]
REGISTRY_SCRIPT = WORKSPACE / "bin" / "ssot" / "script-registry.py"
GAC_VALIDATE_SCRIPT = WORKSPACE / "bin" / "gac" / "gac-validate.py"


def _run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    """Run a command, returning (returncode, combined output)."""
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False
    )
    out = proc.stdout + proc.stderr
    return proc.returncode, out.strip()


def _prepare_worktree(root: Path) -> Path:
    """Fetch latest main and reuse/create an isolated worktree at HEAD."""
    _run(["git", "fetch", "origin", "main"], cwd=root)
    wt_dir = Path(tempfile.gettempdir()) / "reg-drift-check"
    if wt_dir.exists():
        _run(["git", "fetch", "origin", "main"], cwd=wt_dir)
        _run(["git", "checkout", "-q", "--detach", "origin/main"], cwd=wt_dir)
    else:
        rc, out = _run(
            ["git", "worktree", "add", "-d", str(wt_dir), "origin/main"], cwd=root
        )
        if rc != 0:
            raise RuntimeError(f"worktree add failed: {out}")
    return wt_dir


def check(root: Path, *, register: bool = False, as_json: bool = False) -> dict:
    """Run script-registry validate + gac-validate against latest main."""
    wt = _prepare_worktree(root)
    main_sha = subprocess.run(
        ["git", "rev-parse", "--short", "origin/main"],
        cwd=root, capture_output=True, text=True, check=False,
    ).stdout.strip()

    result: dict = {
        "main": main_sha,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script_registry": {"ok": False, "missing": [], "detail": ""},
        "gac_validate": {"ok": False, "detail": ""},
    }

    # script-registry validate
    rc, out = _run(["python3", str(REGISTRY_SCRIPT), "validate"], cwd=wt)
    result["script_registry"]["detail"] = out
    if rc == 0:
        result["script_registry"]["ok"] = True
    else:
        # extract missing lines
        for line in out.splitlines():
            if line.strip().startswith("- ") and not line.startswith("Missing"):
                result["script_registry"]["missing"].append(line.strip()[2:])

    # register missing if requested
    if register and result["script_registry"]["missing"]:
        for script in result["script_registry"]["missing"]:
            _run(["python3", str(REGISTRY_SCRIPT), "register", script], cwd=wt)
        rc2, out2 = _run(["python3", str(REGISTRY_SCRIPT), "validate"], cwd=wt)
        result["script_registry"]["detail"] += "\n[after register]\n" + out2
        result["script_registry"]["ok"] = rc2 == 0
        if rc2 == 0:
            result["script_registry"]["missing"] = []

    # gac-validate
    rc, out = _run(["python3", str(GAC_VALIDATE_SCRIPT), "--gate"], cwd=wt)
    result["gac_validate"]["detail"] = out
    result["gac_validate"]["ok"] = rc == 0

    result["healthy"] = (
        result["script_registry"]["ok"] and result["gac_validate"]["ok"]
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", action="store_true", help="register missing scripts")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    try:
        result = check(WORKSPACE, register=args.register, as_json=args.json)
    except Exception as exc:  # pragma: no cover - infra failure
        print(f"❌ monitor failed: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"=== {result['checked_at']} main={result['main']} "
            f"registry={'PASS' if result['script_registry']['ok'] else 'FAIL'} "
            f"gac={'PASS' if result['gac_validate']['ok'] else 'FAIL'} ==="
        )
        if result["script_registry"]["missing"]:
            print("Missing registrations:")
            for m in result["script_registry"]["missing"]:
                print(f"  - {m}")
        if not result["script_registry"]["ok"]:
            print(result["script_registry"]["detail"])
        if not result["gac_validate"]["ok"]:
            print(result["gac_validate"]["detail"])

    return 0 if result["healthy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
