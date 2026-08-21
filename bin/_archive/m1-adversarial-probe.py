#!/usr/bin/env python3
"""Run ADR-0220 D1–D4 intentional-abuse probes; write path-B evidence for m1-closeout-report.

Default output: .omo/_delivery/m1-adversarial/latest.json (under --root).
Does not push to origin/main. Cleans probe claim files after each gate.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

UTC = timezone.utc


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> dict:
    e = os.environ.copy()
    if env:
        e.update(env)
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=e, check=False)
    return {
        "cmd": cmd,
        "returncode": r.returncode,
        "stdout": r.stdout,
        "stderr": r.stderr,
    }


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
    out_dir = root / ".omo/_delivery/m1-adversarial"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = out_dir / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    cli = ["python3", "bin/gac/swarm-discipline-cli.py"]
    gates: list[dict] = []

    # ── D1 ──
    n = 9037
    for s in ("adv-d1-a", "adv-d1-b"):
        p = root / f".omo/_delivery/adr-claims/{s}.json"
        if p.is_file():
            p.unlink()
    r1 = run([*cli, "adr-claim", "--session", "adv-d1-a", "--number", str(n)], root)
    r2 = run([*cli, "adr-claim", "--session", "adv-d1-b", "--number", str(n)], root)
    r3 = run(
        [
            *cli,
            "adr-check",
            "--file",
            f".omo/_knowledge/decisions/{n:04d}-x.md",
            "--session",
            "adv-d1-b",
        ],
        root,
    )
    d1_ok = r1["returncode"] == 0 and r2["returncode"] != 0 and r3["returncode"] != 0
    gates.append(
        {
            "gate": "D1",
            "blocked": d1_ok,
            "commands": [r1, r2, r3],
            "evidence": str(run_dir / "d1.json"),
        }
    )
    (run_dir / "d1.json").write_text(json.dumps(gates[-1], indent=2) + "\n")
    for s in ("adv-d1-a", "adv-d1-b"):
        p = root / f".omo/_delivery/adr-claims/{s}.json"
        if p.is_file():
            p.unlink()

    # ── D2 ──
    branch = "work/adv-d2-contested"
    claims = root / ".omo/_delivery/branch-claims"
    claims.mkdir(parents=True, exist_ok=True)
    for p in claims.glob("*.json"):
        try:
            if json.loads(p.read_text()).get("branch") == branch:
                p.unlink()
        except Exception:
            pass
    b1 = run([*cli, "branch-claim", "--session", "adv-d2-a", "--branch", branch], root)
    b2 = run([*cli, "branch-claim", "--session", "adv-d2-b", "--branch", branch], root)
    b3 = run(
        [*cli, "branch-check", "--branch", branch, "--session", "adv-d2-b"], root
    )
    d2_ok = b1["returncode"] == 0 and b2["returncode"] != 0 and b3["returncode"] != 0
    gates.append(
        {
            "gate": "D2",
            "blocked": d2_ok,
            "commands": [b1, b2, b3],
            "evidence": str(run_dir / "d2.json"),
        }
    )
    (run_dir / "d2.json").write_text(json.dumps(gates[-1], indent=2) + "\n")
    for s in ("adv-d2-a", "adv-d2-b"):
        p = claims / f"{s}.json"
        if p.is_file():
            p.unlink()

    # ── D3 disposable main clone ──
    tmp = Path(tempfile.mkdtemp(prefix="m1-adv-d3-"))
    try:
        c0 = run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--branch",
                "main",
                "https://github.com/starlink-awaken/omostation.git",
                str(tmp / "repo"),
            ],
            root,
        )
        repo = tmp / "repo"
        hooks = repo / ".git/hooks"
        hooks.mkdir(parents=True, exist_ok=True)
        pre = repo / ".githooks/pre-commit"
        if pre.is_file():
            shutil.copy(pre, hooks / "pre-commit")
            os.chmod(hooks / "pre-commit", 0o755)
        run(["git", "config", "user.email", "adv@test.local"], repo)
        run(["git", "config", "user.name", "adv-probe"], repo)
        (repo / "docs").mkdir(exist_ok=True)
        (repo / "docs/_m1-adv-d3-probe.txt").write_text(f"probe {utc_now()}\n")
        run(["git", "add", "docs/_m1-adv-d3-probe.txt"], repo)
        c1 = run([*cli, "claim-check", "--staged"], repo)
        c2 = run(["git", "commit", "-m", "adv d3 unclaimed"], repo)
        head = run(["git", "rev-parse", "HEAD"], repo)
        main = run(["git", "rev-parse", "origin/main"], repo)
        head_s = (head["stdout"] or "").strip()
        main_s = (main["stdout"] or "").strip()
        d3_ok = c1["returncode"] != 0 and (
            c2["returncode"] != 0 or head_s == main_s
        )
        gates.append(
            {
                "gate": "D3",
                "blocked": d3_ok,
                "commands": [c0, c1, c2],
                "head_equals_main": head_s == main_s,
                "evidence": str(run_dir / "d3.json"),
            }
        )
        (run_dir / "d3.json").write_text(json.dumps(gates[-1], indent=2) + "\n")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ── D4 ──
    env_no = {k: v for k, v in os.environ.items() if k != "SWARM_ESCAPE_ID"}
    env_no["SWARM_ESCAPE_ID"] = ""
    e1 = run([*cli, "escape-check", "--flag", "no_verify_push"], root, env=env_no)
    e2 = run(
        [
            *cli,
            "escape-check",
            "--flag",
            "ci_local_skip",
            "--escape-id",
            "not-a-real-escape-id",
        ],
        root,
        env=env_no,
    )
    e3 = run(
        ["bin/gac/swarm-git", "push", "--no-verify", "origin", "HEAD"],
        root,
        env=env_no,
    )
    e4 = run(
        [
            *cli,
            "escape-check",
            "--flag",
            "no_verify_push",
            "--escape-id",
            "submodule-reachability-partial-worktree",
        ],
        root,
    )
    d4_ok = e1["returncode"] != 0 and e2["returncode"] != 0 and e3["returncode"] != 0
    gates.append(
        {
            "gate": "D4",
            "blocked": d4_ok,
            "allowlisted_ok": e4["returncode"] == 0,
            "commands": [e1, e2, e3, e4],
            "evidence": str(run_dir / "d4.json"),
        }
    )
    (run_dir / "d4.json").write_text(json.dumps(gates[-1], indent=2) + "\n")
    # cleanup allowlist probe logs
    esc = root / ".omo/_delivery/swarm-escape"
    if esc.is_dir():
        for p in esc.glob("*submodule-reachability*"):
            try:
                p.unlink()
            except OSError:
                pass

    all_blocked = all(g["blocked"] for g in gates)
    report = {
        "schema": "m1-adversarial-probe/v1",
        "generated_at": utc_now(),
        "root": str(root),
        "adr": ["0220", "0222"],
        "m1_adversarial_verdict": "pass" if all_blocked else "fail",
        "gates": gates,
        "summary": {
            "all_blocked": all_blocked,
            "passed": [g["gate"] for g in gates if g["blocked"]],
            "failed": [g["gate"] for g in gates if not g["blocked"]],
        },
    }
    (run_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "latest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if all_blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
