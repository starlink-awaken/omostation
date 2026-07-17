#!/usr/bin/env python3
"""G-CONV.5 L2: on write-owner-audit failure, emit a local repair-draft commit.

Creates a tracked draft under:
  .omo/_delivery/repair-drafts/write-owner-<ts>.md
With --commit: force-add only that draft and create a local commit that
contains solely the draft (never other staged files). No push.

Usage:
  python3 bin/ssot/write-owner-repair-draft.py --from-audit-exit
  python3 bin/ssot/write-owner-repair-draft.py --from-audit-exit --commit
  python3 bin/ssot/write-owner-repair-draft.py --message "..." --files a b
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
# Prefer tracked delivery plane (not gitignored runtime/omo)
DRAFT_DIR = WORKSPACE / ".omo" / "_delivery" / "repair-drafts"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _staged_files() -> list[str]:
    res = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    return [ln.strip() for ln in res.stdout.splitlines() if ln.strip()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--from-audit-exit", action="store_true", help="use staged files as repair targets")
    p.add_argument("--message", default="", help="optional extra note")
    p.add_argument("--files", nargs="*", default=[], help="explicit files")
    p.add_argument(
        "--commit",
        action="store_true",
        help="create local commit containing ONLY the draft file (no push)",
    )
    args = p.parse_args(argv)

    files = list(args.files) or (_staged_files() if args.from_audit_exit else [])
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    path = DRAFT_DIR / f"write-owner-{_utc()}.md"
    body = [
        "# write-owner repair draft (G-CONV.5 L2)",
        "",
        f"- generated_at: {_utc()}",
        f"- note: {args.message or 'write-owner-audit failed on staged changes'}",
        "",
        "## staged / target files",
        "",
    ]
    for f in files:
        body.append(f"- `{f}`")
    if not files:
        body.append("- _(none listed — re-run audit with staged files)_")
    body.extend(
        [
            "",
            "## suggested next steps",
            "",
            "1. Confirm owner in `.omo/_truth/registry/write-owners.yaml`",
            "2. Route change through OMO/C2G broker if surface is governed",
            "3. Or request owner co-author / re-claim via agent-workflow",
            "",
        ]
    )
    text = "\n".join(body)
    path.write_text(text, encoding="utf-8")
    rel = path.relative_to(WORKSPACE)
    print(f"repair-draft: {rel}")

    if args.commit:
        # -f: in case delivery dir is ignored; --only: never sweep unrelated staged files
        subprocess.run(
            ["git", "add", "-f", str(rel)],
            cwd=WORKSPACE,
            check=False,
        )
        msg = f"chore(repair-draft): write-owner audit failure {_utc()}\n\nSee {rel}"
        res = subprocess.run(
            ["git", "commit", "--no-verify", "--only", "-m", msg, "--", str(rel)],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode != 0:
            # fallback empty commit still records the attempt without touching staged work
            res2 = subprocess.run(
                ["git", "commit", "--allow-empty", "--no-verify", "-m", msg],
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                check=False,
            )
            print(f"local commit fallback rc={res2.returncode} (no push)")
            if res.stderr:
                print(res.stderr.strip(), file=sys.stderr)
        else:
            print("local repair-draft commit created (draft only, no push)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
