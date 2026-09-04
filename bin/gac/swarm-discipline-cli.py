#!/usr/bin/env python3
"""CLI for G-CONV.7 / ADR-0220 swarm discipline gates.

Usage:
  swarm-discipline-cli.py adr-claim --session S [--number N]
  swarm-discipline-cli.py adr-check --file PATH [--session S]
  swarm-discipline-cli.py branch-claim --session S
  swarm-discipline-cli.py branch-check --branch work/S --session S
  swarm-discipline-cli.py claim-check --staged
  swarm-discipline-cli.py escape-check --flag ci_local_skip --escape-id ID
  swarm-discipline-cli.py window-start
  swarm-discipline-cli.py window-status
  swarm-discipline-cli.py inventory
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parent))
import swarm_discipline as sd


def root_from_cwd() -> Path:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except OSError:
        pass
    return Path(__file__).resolve().parents[2]


def cmd_adr_claim(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    ok, result = sd.acquire_adr_claim(root, args.session, number=args.number)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def cmd_adr_check(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    ok, reason = sd.check_adr_write_authorized(root, args.file, args.session)
    print(json.dumps({"ok": ok, "reason": reason, "file": args.file}, indent=2))
    return 0 if ok else 1


def cmd_branch_claim(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    ok, result = sd.acquire_branch_lock(root, args.session, args.branch)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if ok else 1


def cmd_branch_check(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    ok, reason = sd.check_branch_available(root, args.branch, args.session)
    print(json.dumps({"ok": ok, "reason": reason, "branch": args.branch}, indent=2))
    return 0 if ok else 1


def cmd_branch_release(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    done = sd.release_branch_lock(root, args.session, purge_orphans=not args.no_purge_orphans)
    print(json.dumps({"released": done, "session": args.session}, indent=2))
    return 0


def cmd_claim_gc(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    result = sd.claim_gc(root, ttl_hours=args.ttl_hours, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_claim_check(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    if args.staged:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        paths = [ln.strip() for ln in r.stdout.splitlines() if ln.strip()]
    else:
        paths = list(args.paths or [])
    if not paths:
        print(json.dumps({"ok": True, "reason": "no_paths", "violations": []}, indent=2))
        return 0
    ok, violations = sd.check_shared_worktree_writes(root, paths)
    print(
        json.dumps(
            {"ok": ok, "violations": violations, "paths": paths},
            ensure_ascii=False,
            indent=2,
        )
    )
    if not ok:
        print(
            "❌ D3 shared-worktree claim check failed. "
            "Use worktree (gac-worktree claim) or agent-workflow claim <run> --path <p>.",
            file=sys.stderr,
        )
    return 0 if ok else 1


def cmd_escape_digest(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    if args.dir:
        from pathlib import Path as path_cls

        records: list = []
        d = path_cls(args.dir)
        if d.is_dir():
            for path in sorted(d.glob("*.json")):
                if path.parent.name == "tokens":
                    continue
                try:
                    rec = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if isinstance(rec, dict):
                    records.append(rec)
        digest = sd.digest_escape_records(records)
    else:
        digest = sd.digest_escape_records(sd.load_escape_records(root))
    print(json.dumps(digest, indent=2, ensure_ascii=False))
    return 0


def cmd_escape_token_issue(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    rec = sd.issue_human_escape_token(
        root, escape_id=args.escape_id, ttl_seconds=args.ttl_seconds
    )
    print(json.dumps(rec, indent=2))
    return 0


def cmd_escape_check(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    escape_id = args.escape_id or __import__("os").environ.get("SWARM_ESCAPE_ID")
    fingerprints = None
    if getattr(args, "failures_file", None):
        path = Path(args.failures_file)
        if path.is_file():
            raw = path.read_text(encoding="utf-8").strip()
            if raw:
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    payload = {}
                if isinstance(payload, dict):
                    fingerprints = list(payload.get("failures") or [])
                elif isinstance(payload, list):
                    fingerprints = payload
    changed = list(getattr(args, "changed_path", None) or [])
    token = getattr(args, "token", None) or __import__("os").environ.get("SWARM_ESCAPE_TOKEN")
    verdict = sd.evaluate_escape(
        root,
        flag=args.flag,
        escape_id=escape_id,
        fingerprints=fingerprints,
        changed_paths=changed or None,
        human_token=token,
    )
    print(
        json.dumps(
            {
                "ok": verdict.get("ok"),
                "reason": verdict.get("reason"),
                "flag": args.flag,
                "decision": verdict.get("decision"),
                "surface": verdict.get("surface"),
                "check_id": verdict.get("check_id"),
                "signature": verdict.get("signature"),
                "would_block": verdict.get("would_block"),
                "sink_required": verdict.get("sink_required"),
            },
            indent=2,
        )
    )
    return 0 if verdict.get("ok") else 1


def cmd_git_argv_check(args: argparse.Namespace) -> int:
    """D4: validate git argv for --no-verify (used by bin/gac/swarm-git)."""
    root = root_from_cwd()
    escape_id = args.escape_id or __import__("os").environ.get("SWARM_ESCAPE_ID")
    argv = list(args.argv or [])
    ok, reason = sd.check_git_argv_escape(root, argv, escape_id)
    print(
        json.dumps(
            {
                "ok": ok,
                "reason": reason,
                "has_no_verify": sd.argv_has_no_verify(argv),
                "flag": sd.no_verify_flag_for_argv(argv) if sd.argv_has_no_verify(argv) else None,
            },
            indent=2,
        )
    )
    return 0 if ok else 1


def cmd_window_start(_args: argparse.Namespace) -> int:
    root = root_from_cwd()
    payload = sd.start_conflict_window(root)
    print(json.dumps(payload, indent=2))
    return 0


def cmd_window_status(args: argparse.Namespace) -> int:
    root = root_from_cwd()
    status = sd.conflict_window_status(
        root,
        scan_orphans=not args.no_orphan_scan,
        emit_orphans=bool(args.emit_orphans),
    )
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """BET-Y1Q1-T1-05A: 共享协调层只读快照 (claims/health/messages)."""
    import coordination_store as cs

    snap = cs.snapshot()
    if args.json:
        print(json.dumps(snap, indent=2, ensure_ascii=False))
        return 0
    # 人类可读三段式
    print(f" Coordination Layer ({snap['db_path']})")
    print(f" schema v{snap['schema_version']}")
    claim_counts = snap["claim_counts"]
    print(
        "\n── Claims "
        f"(total={len(snap['claims'])} state_active={claim_counts['state_active']} "
        f"expired_by_time={claim_counts['expired_by_time']} live_by_time={claim_counts['live_by_time']}) "
        "──────────────────────"
    )
    for c in snap["claims"]:
        print(
            f"  {c['state']:<8} {c['resource_type']}/{c['resource_id']} "
            f"owner={c['owner']} token={c['token']} claimed={c['claimed_at']}"
        )
    print(f"\n── Agent Health ({len(snap['agent_health'])}) ───────────")
    for h in snap["agent_health"]:
        stale_mark = " [STALE]" if any(s["agent_id"] == h["agent_id"] for s in snap["stale_agents"]) else ""
        attestation = h.get("runtime_attestation") or {}
        runtime = (
            f"rev={str(attestation.get('workspace_revision', ''))[:12]} "
            f"code={str(attestation.get('code_sha256', ''))[:12]}"
            if attestation
            else "runtime=unattested"
        )
        print(
            f"  {h['agent_id']:<24} {h['status']:<5} src={h['source']} last_seen={h['last_seen']} {runtime}{stale_mark}"
        )
    print(f"\n── Messages ({len(snap['messages'])}) ──────────────────")
    for m in snap["messages"]:
        print(f"  #{m['id']} {m['ts']} {m['from_agent']} → {m['to_agent']} ({m['msg_type']})")
    print("\n── Shadow Events ─────────────────────────────────────")
    if snap["shadow_events"]:
        for kind, n in sorted(snap["shadow_events"].items()):
            print(f"  {kind}: {n}")
    else:
        print("  (无)")
    return 0


def cmd_token_check(args: argparse.Namespace) -> int:
    """BET-Y1Q1-T1-05A: fencing token 校验.

    shadow 阶段: 判定 reject 时落 shadow_events (token_stale_rejected)
    但不阻断 submit (exit 0). DB 打不开 → exit 2 fail-closed.
    """
    import sqlite3

    import coordination_store as cs

    if args.missing_token:
        recorded = cs.emit_shadow_event(
            "token_missing_legacy",
            args.resource_type,
            args.resource_id,
            {"owner": args.owner, "local_token": args.token},
        )
        payload = {
            "ok": False,
            "reason": "missing local fencing token",
            "current_token": None,
            "local_token": args.token,
            "mode": "shadow",
            "legacy": True,
            "event_recorded": recorded,
        }
        if not recorded:
            payload["fail_closed"] = True
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 2
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    try:
        verdict = cs.check_fencing(args.resource_type, args.resource_id, args.owner, args.token)
    except (cs.CoordinationStoreError, sqlite3.Error) as exc:
        # fail-closed: DB 打不开/版本超前 → exit 2, submit 挂点据此停
        print(
            json.dumps({"ok": False, "fail_closed": True, "reason": str(exc)}),
        )
        return 2
    payload = {
        "ok": verdict.ok,
        "reason": verdict.reason,
        "current_token": verdict.current_token,
        "local_token": verdict.local_token,
        "mode": "shadow",
    }
    if not verdict.ok:
        # shadow: 只记录, 不阻断 (warning 阶段改 exit 1)
        recorded = cs.emit_shadow_event(
            "token_stale_rejected",
            args.resource_type,
            args.resource_id,
            {
                "owner": args.owner,
                "local_token": args.token,
                "current_token": verdict.current_token,
            },
        )
        payload["event_recorded"] = recorded
        if not recorded:
            payload["fail_closed"] = True
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_inventory(_args: argparse.Namespace) -> int:
    root = root_from_cwd()
    reg = sd.load_registry(root)
    inv = {
        "registry": str(root / sd.DEFAULT_REGISTRY),
        "version": reg.get("version"),
        "gates": {
            k: {
                "id": (v or {}).get("id"),
                "name": (v or {}).get("name"),
                "entry": (v or {}).get("entry"),
                "check": (v or {}).get("check"),
            }
            for k, v in (reg.get("gates") or {}).items()
        },
        "escape_exemptions": [x.get("id") for x in (reg.get("escape_hatch_exemptions") or [])],
        "cli": "bin/gac/swarm-discipline-cli.py",
        "core": "bin/gac/swarm_discipline.py",
    }
    print(json.dumps(inv, indent=2, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("adr-claim")
    s.add_argument("--session", required=True)
    s.add_argument("--number", type=int, default=None)
    s.set_defaults(func=cmd_adr_claim)

    s = sub.add_parser("adr-check")
    s.add_argument("--file", required=True)
    s.add_argument("--session", default="")
    s.set_defaults(func=cmd_adr_check)

    s = sub.add_parser("branch-claim")
    s.add_argument("--session", required=True)
    s.add_argument("--branch", default=None)
    s.set_defaults(func=cmd_branch_claim)

    s = sub.add_parser("branch-check")
    s.add_argument("--branch", required=True)
    s.add_argument("--session", required=True)
    s.set_defaults(func=cmd_branch_check)

    s = sub.add_parser("branch-release")
    s.add_argument("--session", required=True)
    s.add_argument(
        "--purge-orphans",
        action="store_true",
        default=True,
        help="B3 (ADR-0367): 顺带删除分支已不存在的孤儿 claim (默认开)",
    )
    s.add_argument("--no-purge-orphans", action="store_true", help="关闭孤儿清理")
    s.set_defaults(func=cmd_branch_release)

    s = sub.add_parser("claim-gc", help="GC 过期 claim (branch/agent/adr, D1)")
    s.add_argument(
        "--ttl-hours",
        type=int,
        default=168,
        help="TTL 小时 (默认 168=7天, claim 是长期占位)",
    )
    s.add_argument("--dry-run", action="store_true")
    s.set_defaults(func=cmd_claim_gc)

    s = sub.add_parser("claim-check")
    s.add_argument("--staged", action="store_true")
    s.add_argument("--paths", nargs="*", default=[])
    s.set_defaults(func=cmd_claim_check)

    s = sub.add_parser(
        "status",
        help="BET-Y1Q1-T1-05A: 共享协调层只读快照 (claims/health/messages)",
    )
    s.add_argument("--json", action="store_true", help="机器可读 JSON 输出")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser(
        "token-check",
        help="BET-Y1Q1-T1-05A: fencing token 校验 (shadow: 只判定不阻断)",
    )
    s.add_argument("--resource-type", required=True)
    s.add_argument("--resource-id", required=True)
    s.add_argument("--owner", required=True)
    s.add_argument("--token", type=int, required=True)
    s.add_argument(
        "--missing-token",
        action="store_true",
        help="legacy claim/mirror failure: record auditable shadow verdict",
    )
    s.set_defaults(func=cmd_token_check)

    s = sub.add_parser("escape-check")
    s.add_argument(
        "--flag",
        required=True,
        choices=["ci_local_skip", "no_verify_push", "no_verify_commit"],
    )
    s.add_argument("--escape-id", default=None)
    s.add_argument("--failures-file", default=None, help="JSON from ci-local-fast --failures-json")
    s.add_argument("--changed-path", action="append", default=[], help="Paths in this push/commit")
    s.add_argument("--token", default=None, help="single-use human escape token")
    s.set_defaults(func=cmd_escape_check)

    s = sub.add_parser("escape-digest", help="Cluster swarm-escape records (dry-run)")
    s.add_argument("--dir", default=None, help="Override swarm-escape directory")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_escape_digest)

    s = sub.add_parser("escape-token-issue", help="Issue a single-use human escape token")
    s.add_argument("--escape-id", default="emergency-human-hotfix")
    s.add_argument("--ttl-seconds", type=int, default=3600)
    s.set_defaults(func=cmd_escape_token_issue)

    s = sub.add_parser("git-argv-check", help="D4: check git argv for --no-verify")
    s.add_argument("--escape-id", default=None)
    s.add_argument("argv", nargs=argparse.REMAINDER, help="git argv after --")
    s.set_defaults(func=cmd_git_argv_check)

    s = sub.add_parser("window-start")
    s.set_defaults(func=cmd_window_start)

    s = sub.add_parser("window-status")
    s.add_argument(
        "--no-orphan-scan",
        action="store_true",
        help="skip advisory orphan_commit git scan",
    )
    s.add_argument(
        "--emit-orphans",
        action="store_true",
        help="record orphan hits into conflict events (affects M1 count)",
    )
    s.set_defaults(func=cmd_window_status)

    s = sub.add_parser("inventory")
    s.set_defaults(func=cmd_inventory)

    args = p.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
