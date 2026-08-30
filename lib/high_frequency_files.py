"""High-frequency file definitions and monitoring.

Defines files that are frequently written by multiple agents concurrently,
monitors file changes, detects concurrent modifications, and reports conflicts.

These files are known to cause ~40 concurrent write conflicts per day in the
multi-agent workspace environment.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

WORKSPACE = Path(__file__).resolve().parents[1]

# --- High-Frequency File Registry ---
# Files known to have concurrent write conflicts.
# Format: (relative_path, description, expected_writers_per_day)

HIGH_FREQUENCY_FILES: list[tuple[str, str, int]] = [
    # State files (written by omo state sync, agent-workflow, governance tools)
    (".omo/state/system.yaml", "Runtime system state", 50),
    (".omo/state/health.yaml", "Health metrics state", 30),
    (".omo/state/system_health.yaml", "System health snapshot", 20),
    # Control files (written by dashboards, gates, monitors)
    (".omo/_control/governance-data.json", "Governance dashboard data", 25),
    (".omo/_control/debt-dashboard/current.yaml", "Debt dashboard state", 15),
    # Event logs (appended by multiple agents)
    (".omo/_delivery/observability/events.jsonl", "Observability events", 100),
    (".omo/_delivery/agent-workflows/events.jsonl", "Agent workflow events", 80),
    # Registry files (written by governance tools)
    (".omo/_truth/registry/governance-checks.yaml", "Governance checks registry", 10),
    # Lock coordination files
    ("locks/", "Lock directory", 200),
]


@dataclass
class FileChangeRecord:
    """Record of a file change detected during monitoring."""

    file: str
    timestamp: str
    old_hash: str
    new_hash: str
    size_change: int
    detected_by: str = "high_frequency_monitor"


@dataclass
class ConflictReport:
    """Report of a concurrent modification conflict."""

    file: str
    detected_at: str
    writers: list[str] = field(default_factory=list)
    hash_mismatch: bool = False
    lock_violation: bool = False
    details: dict[str, Any] = field(default_factory=dict)


class HighFrequencyFileMonitor:
    """Monitor high-frequency files for concurrent modifications.

    Tracks file hashes and detects when multiple agents modify the same file
    within a short time window.
    """

    def __init__(
        self,
        workspace: Path | None = None,
        conflict_window_s: float = 5.0,
    ) -> None:
        self.workspace = workspace or WORKSPACE
        self.conflict_window_s = conflict_window_s
        # file -> (hash, timestamp, actor)
        self._snapshots: dict[str, tuple[str, float, str]] = {}
        # file -> list of recent changes
        self._recent_changes: dict[str, list[FileChangeRecord]] = {}
        # Conflicts detected
        self._conflicts: list[ConflictReport] = []

    def snapshot(self, files: list[str] | None = None, actor: str = "monitor") -> dict[str, str]:
        """Take a hash snapshot of monitored files.

        Args:
            files: Specific files to snapshot. None = all high-frequency files.
            actor: Identifier for who is taking the snapshot.

        Returns:
            Dict of file -> SHA-256 hash.
        """
        targets = files or [f[0] for f in HIGH_FREQUENCY_FILES]
        hashes: dict[str, str] = {}
        now = time.time()

        for rel in targets:
            abs_path = self.workspace / rel
            if abs_path.is_dir():
                continue
            h = self._hash_file(abs_path)
            hashes[rel] = h
            self._snapshots[rel] = (h, now, actor)

        return hashes

    def detect_changes(self, actor: str = "monitor") -> list[FileChangeRecord]:
        """Detect changes since last snapshot.

        Returns:
            List of FileChangeRecord for changed files.
        """
        changes: list[FileChangeRecord] = []
        now = time.time()

        for rel, (old_hash, old_time, old_actor) in list(self._snapshots.items()):
            abs_path = self.workspace / rel
            new_hash = self._hash_file(abs_path)

            if new_hash != old_hash:
                try:
                    new_size = abs_path.stat().st_size if abs_path.is_file() else 0
                    old_size = 0  # We don't track old size, use 0 as baseline
                except OSError:
                    new_size = 0

                record = FileChangeRecord(
                    file=rel,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    old_hash=old_hash,
                    new_hash=new_hash,
                    size_change=new_size - old_size,
                    detected_by=actor,
                )
                changes.append(record)

                # Track recent changes for conflict detection
                if rel not in self._recent_changes:
                    self._recent_changes[rel] = []
                self._recent_changes[rel].append(record)

                # Update snapshot
                self._snapshots[rel] = (new_hash, now, actor)

        return changes

    def detect_conflicts(self) -> list[ConflictReport]:
        """Detect concurrent modification conflicts.

        A conflict is detected when:
        1. Multiple changes to the same file within the conflict window
        2. A file is locked but still modified

        Returns:
            List of ConflictReport for detected conflicts.
        """
        conflicts: list[ConflictReport] = []
        now = time.time()

        for rel, changes in self._recent_changes.items():
            if len(changes) < 2:
                continue

            # Check for rapid successive changes (potential conflict)
            recent = [
                c for c in changes
                if (now - datetime.fromisoformat(c.timestamp).timestamp()) < self.conflict_window_s
            ]

            if len(recent) >= 2:
                # Multiple writers detected
                writers = list({c.detected_by for c in recent})
                conflict = ConflictReport(
                    file=rel,
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    writers=writers,
                    hash_mismatch=True,
                    details={
                        "change_count": len(recent),
                        "window_s": self.conflict_window_s,
                    },
                )
                conflicts.append(conflict)

        # Check for lock violations (file modified while locked)
        try:
            from file_lock import check_conflict, read_lock

            for rel, _ in self._snapshots.items():
                lock = read_lock(rel)
                if lock is not None:
                    conflict = check_conflict(rel)
                    if conflict is not None:
                        conflicts.append(ConflictReport(
                            file=rel,
                            detected_at=datetime.now(timezone.utc).isoformat(),
                            writers=[lock.actor],
                            lock_violation=True,
                            details=conflict,
                        ))
        except ImportError:
            pass

        self._conflicts.extend(conflicts)
        return conflicts

    def get_conflicts(self) -> list[ConflictReport]:
        """Get all detected conflicts."""
        return list(self._conflicts)

    def clear_conflicts(self) -> None:
        """Clear conflict history."""
        self._conflicts.clear()
        self._recent_changes.clear()

    def report(self) -> dict[str, Any]:
        """Generate a monitoring report."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "monitored_files": len(self._snapshots),
            "recent_changes": sum(len(c) for c in self._recent_changes.values()),
            "conflicts_detected": len(self._conflicts),
            "conflicts": [
                {
                    "file": c.file,
                    "detected_at": c.detected_at,
                    "writers": c.writers,
                    "hash_mismatch": c.hash_mismatch,
                    "lock_violation": c.lock_violation,
                }
                for c in self._conflicts
            ],
            "high_frequency_files": [
                {"path": f[0], "description": f[1], "expected_writers": f[2]}
                for f in HIGH_FREQUENCY_FILES
            ],
        }

    @staticmethod
    def _hash_file(path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        if not path.is_file():
            return ""
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return ""


def get_high_frequency_paths() -> list[str]:
    """Get list of high-frequency file paths."""
    return [f[0] for f in HIGH_FREQUENCY_FILES]


def get_high_frequency_descriptions() -> dict[str, str]:
    """Get mapping of file path to description."""
    return {f[0]: f[1] for f in HIGH_FREQUENCY_FILES}


def get_expected_writers() -> dict[str, int]:
    """Get mapping of file path to expected writers per day."""
    return {f[0]: f[2] for f in HIGH_FREQUENCY_FILES}


# --- CLI entry point ---

def main() -> int:
    """CLI interface for high-frequency file monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description="High-frequency file monitor")
    sub = parser.add_subparsers(dest="command")

    # list
    sub.add_parser("list", help="List high-frequency files")

    # snapshot
    p_snap = sub.add_parser("snapshot", help="Take file hash snapshot")
    p_snap.add_argument("--actor", default="cli", help="Actor identifier")

    # detect
    p_detect = sub.add_parser("detect", help="Detect changes since snapshot")
    p_detect.add_argument("--actor", default="cli", help="Actor identifier")

    # conflicts
    sub.add_parser("conflicts", help="Detect concurrent conflicts")

    # report
    sub.add_parser("report", help="Generate monitoring report")

    args = parser.parse_args()

    if args.command == "list":
        for path, desc, writers in HIGH_FREQUENCY_FILES:
            print(f"  {path:<60} {desc:<30} ~{writers}/day")
        return 0

    elif args.command == "snapshot":
        monitor = HighFrequencyFileMonitor()
        hashes = monitor.snapshot(actor=args.actor)
        print(json.dumps(hashes, indent=2))
        return 0

    elif args.command == "detect":
        monitor = HighFrequencyFileMonitor()
        monitor.snapshot(actor=args.actor)
        changes = monitor.detect_changes(actor=args.actor)
        print(json.dumps([{
            "file": c.file,
            "timestamp": c.timestamp,
            "old_hash": c.old_hash[:16] + "...",
            "new_hash": c.new_hash[:16] + "...",
        } for c in changes], indent=2))
        return 0

    elif args.command == "conflicts":
        monitor = HighFrequencyFileMonitor()
        monitor.snapshot()
        monitor.detect_changes()
        conflicts = monitor.detect_conflicts()
        print(json.dumps([{
            "file": c.file,
            "detected_at": c.detected_at,
            "writers": c.writers,
            "hash_mismatch": c.hash_mismatch,
            "lock_violation": c.lock_violation,
        } for c in conflicts], indent=2))
        return 1 if conflicts else 0

    elif args.command == "report":
        monitor = HighFrequencyFileMonitor()
        monitor.snapshot()
        report = monitor.report()
        print(json.dumps(report, indent=2))
        return 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
