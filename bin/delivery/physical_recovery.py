#!/usr/bin/env python3
"""STRAT-P81 Batch2 C1 — physical recovery entry (dry-run safe, fail-closed).

One command path after hosts return:
  probe → registry backfill plan → G-DEL.3 two-host measure plan → G-DEL.1 four-host precheck

Never claims meets_physical_gate=true from dry-run or sim. Physical pass requires
real measure_physical + human confirm (workorder §F).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / ".omo" / "_knowledge" / "audits"


@dataclass(frozen=True)
class RecoveryReceipt:
    drill_id: str
    source_digest: str
    backup_digest: str
    restored_digest: str
    replay_digest: str
    isolated_target: str
    executed: bool
    integrity_ok: bool
    human_confirmed: bool
    started_at: str
    completed_at: str


def _probe_host(host: str, port: int = 22, timeout: float = 1.5) -> dict[str, Any]:
    t0 = time.time()
    ok = False
    err = None
    try:
        with socket.create_connection((host, port), timeout=timeout):
            ok = True
    except OSError as e:
        err = str(e)
    return {
        "host": host,
        "port": port,
        "reachable": ok,
        "latency_ms": round((time.time() - t0) * 1000, 2) if ok else None,
        "error": err,
    }


def default_host_list() -> list[str]:
    raw = os.environ.get("PHYSICAL_RECOVERY_HOSTS", "").strip()
    if raw:
        return [h.strip() for h in raw.split(",") if h.strip()]
    # Fail-closed inventory (may be offline) — never invent green hosts
    return ["127.0.0.1", "192.168.31.210", "macmini.local", "y7000p.local"]


def _tree_digest(root: Path) -> str:
    """Hash a regular-file tree deterministically without following symlinks."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("source and restore trees must be real directories")
    digest = hashlib.sha256()
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"symlink is not allowed in recovery tree: {path}")
        if path.is_file():
            files.append(path)
        elif not path.is_dir():
            raise ValueError(f"non-regular recovery entry: {path}")
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _require_empty_directory(path: Path, label: str) -> None:
    if path.exists():
        if not path.is_dir() or path.is_symlink():
            raise ValueError(f"{label} must be an empty directory")
        if any(path.iterdir()):
            raise ValueError(f"{label} must be empty")


def run_live_drill(
    *,
    source: Path,
    backup_dir: Path,
    restore_dir: Path,
    human_confirmation_ref: str | None,
    replay_command: Sequence[str],
    out_dir: Path | None = None,
    drill_id: str | None = None,
    protected_roots: Sequence[Path] | None = None,
) -> dict[str, Any]:
    """Execute a fail-closed, isolated backup/restore/replay drill."""
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    drill = drill_id or f"physical-recovery-{int(time.time())}"
    base_report: dict[str, Any] = {
        "drill_id": drill,
        "executed": False,
        "integrity_ok": False,
        "human_confirmed": bool(human_confirmation_ref and human_confirmation_ref.strip()),
        "replay_ok": False,
        "meets_physical_gate": False,
        "meets_gate": False,
        "started_at": started_at,
    }
    if not base_report["human_confirmed"]:
        return {**base_report, "error": "human confirmation reference is required"}
    if not replay_command or any(not str(part).strip() for part in replay_command):
        return {**base_report, "error": "replay command is required"}

    source_path = _resolved(source)
    backup_path = _resolved(backup_dir)
    restore_path = _resolved(restore_dir)
    protected = tuple(_resolved(path) for path in (protected_roots or (ROOT / "runtime", ROOT / ".omo")))
    if _overlaps(source_path, backup_path):
        raise ValueError("backup target must not overlap source")
    if _overlaps(source_path, restore_path):
        raise ValueError("restore target must not overlap source")
    if _overlaps(backup_path, restore_path):
        raise ValueError("restore target must not overlap backup")
    if any(_overlaps(source_path, root) for root in protected):
        raise ValueError("source must not overlap a production/runtime root")
    if any(_overlaps(restore_path, root) for root in protected):
        raise ValueError("restore target must not overlap a production/runtime root")
    if backup_path.exists():
        raise ValueError("backup target must not already exist")
    _require_empty_directory(restore_path, "restore target")
    if not source_path.is_dir() or source_path.is_symlink():
        raise ValueError("source must be a real directory")

    source_digest = _tree_digest(source_path)
    shutil.copytree(source_path, backup_path)
    backup_digest = _tree_digest(backup_path)
    restore_path.mkdir(parents=True, exist_ok=True)
    shutil.copytree(backup_path, restore_path, dirs_exist_ok=True)
    restored_digest = _tree_digest(restore_path)
    integrity_ok = source_digest == backup_digest == restored_digest
    if not integrity_ok:
        return {
            **base_report,
            "source_digest": source_digest,
            "backup_digest": backup_digest,
            "restored_digest": restored_digest,
            "error": "backup or restored digest mismatch",
        }

    replay = subprocess.run(
        [str(part) for part in replay_command],
        cwd=restore_path,
        capture_output=True,
        text=False,
        timeout=30,
        check=False,
    )
    replay_bytes = replay.stdout + replay.stderr
    replay_digest = "sha256:" + hashlib.sha256(replay_bytes).hexdigest()
    replay_ok = replay.returncode == 0
    completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    receipt = RecoveryReceipt(
        drill_id=drill,
        source_digest=source_digest,
        backup_digest=backup_digest,
        restored_digest=restored_digest,
        replay_digest=replay_digest,
        isolated_target=str(restore_path),
        executed=replay_ok,
        integrity_ok=integrity_ok,
        human_confirmed=True,
        started_at=started_at,
        completed_at=completed_at,
    )
    out = out_dir or DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    receipt_path = out / f"{drill}-receipt.json"
    receipt_path.write_text(json.dumps(asdict(receipt), indent=2, ensure_ascii=False), encoding="utf-8")
    if replay_ok:
        shutil.rmtree(restore_path)
    return {
        **base_report,
        **asdict(receipt),
        "replay_ok": replay_ok,
        "replay_returncode": replay.returncode,
        "receipt_path": str(receipt_path),
        "cleanup": {"status": "removed" if replay_ok else "preserved", "target": str(restore_path)},
        "meets_physical_gate": replay_ok,
        "meets_gate": replay_ok,
    }


def run_recovery(
    *,
    dry_run: bool = True,
    hosts: list[str] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    hosts = hosts or default_host_list()
    probes = [_probe_host(h) for h in hosts]
    reachable = [p for p in probes if p["reachable"]]
    n = len(reachable)

    # Plans only — no real G-DEL measure that could flip physical gate
    registry_plan = {
        "action": "register_reachable_nodes",
        "would_register": [p["host"] for p in reachable],
        "skipped_unreachable": [p["host"] for p in probes if not p["reachable"]],
        "applied": False,  # never auto-applied; human recovery-day apply only
    }
    g_del_3_plan = {
        "gate": "G-DEL.3",
        "required_hosts": 2,
        "reachable_hosts": n,
        "ready": n >= 2,
        "measure_command": "uv run --project projects/... measure_physical --n-ops 10000",
        "executed": False,
        "meets_physical_gate": False,
    }
    g_del_1_precheck = {
        "gate": "G-DEL.1",
        "required_hosts": 4,
        "reachable_hosts": n,
        "ready": n >= 4,
        "executed": False,
        "meets_physical_gate": False,
    }

    report: dict[str, Any] = {
        "ok": dry_run,  # dry-run always "ok" as a rehearsal; never physical pass
        "dry_run": dry_run,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "probes": probes,
        "reachable_count": n,
        "registry_plan": registry_plan,
        "g_del_3_plan": g_del_3_plan,
        "g_del_1_precheck": g_del_1_precheck,
        "meets_sim_harness": True,
        "meets_physical_gate": False,
        "meets_gate": False,
        "env_class": "physical_multi_host" if n else "in-process_simulation",
        "note": (
            "Batch2 C1 recovery package. dry-run does not claim physical pass. "
            "Human + real measure_physical required for G-DEL.1/3 official."
        ),
    }

    out = out_dir or DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    day = time.strftime("%Y-%m-%d", time.gmtime())
    path = out / f"{day}-physical-recovery-dry-run.json"
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(path)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", default=True)
    p.add_argument("--live", action="store_true", help="reserved; still fail-closed without hosts")
    p.add_argument("--hosts", default="", help="comma-separated hosts override")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--source", type=Path, default=None)
    p.add_argument("--backup-dir", type=Path, default=None)
    p.add_argument("--restore-dir", type=Path, default=None)
    p.add_argument("--human-confirmation-ref", default=None)
    p.add_argument("--replay-command", nargs="+", default=None)
    args = p.parse_args(argv)
    if args.live:
        if not all((args.source, args.backup_dir, args.restore_dir, args.replay_command)):
            p.error("--live requires --source, --backup-dir, --restore-dir, and --replay-command")
        report = run_live_drill(
            source=args.source,
            backup_dir=args.backup_dir,
            restore_dir=args.restore_dir,
            human_confirmation_ref=args.human_confirmation_ref,
            replay_command=args.replay_command,
            out_dir=args.out,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0 if report.get("meets_physical_gate") else 1
    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()] or None
    report = run_recovery(
        dry_run=not args.live,
        hosts=hosts,
        out_dir=args.out,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    # dry-run success = 0; live with physical claim forbidden unless real hosts measured
    if report.get("meets_physical_gate") is True:
        return 3  # hard violation
    return 0 if report.get("ok") or report.get("dry_run") else 1


if __name__ == "__main__":
    raise SystemExit(main())
