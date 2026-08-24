#!/usr/bin/env python3
"""episode-source-aggregator.py — Three-source episode draft aggregator for cockpit attest.

Read-only aggregator that collects value episode drafts from:
1. **ledger** — runtime/omo/event-ledger.sqlite3 (Action.Succeeded.v1 / Outcome.Human.v1)
2. **git** — merge commits (filtered: only "Merge pull request #N")
3. **debt** — .omo/debt/items/*.yaml (closed OR resolved+closed_at)

Output: JSON array of draft entries sorted by confidence (high>medium>low), then occurred_at desc.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    yaml = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = WORKSPACE / "runtime" / "omo" / "event-ledger.sqlite3"
DEFAULT_DEBT_DIR = WORKSPACE / ".omo" / "debt" / "items"
DEFAULT_STATE_DIR = WORKSPACE / ".omo" / "state"
NEGATIVE_SAMPLES_FILE = "attest-negative-samples.json"

CONFIDENCE_ORDER = {"high": 0, "medium": 1, "low": 2}

SYNC_MERGE_PATTERNS = [
    re.compile(r"^Merge origin/main"),
    re.compile(r"^Merge branch 'main' of\s"),
]

PR_MERGE_PATTERN = re.compile(r"^Merge pull request #(\d+)\s+from\s+(\S+?):\s*(.*)")
PR_MERGE_PATTERN_NO_COLON = re.compile(r"^Merge pull request #(\d+)\s+from\s+(\S+)\s*$")


# ---------------------------------------------------------------------------
# Ledger source
# ---------------------------------------------------------------------------

def _collect_ledger(db_path: Path, since_days: int = 7) -> list[dict[str, Any]]:
    if not db_path.exists():
        return []

    cutoff = (datetime.now(timezone.utc) - timedelta(days=since_days)).isoformat()
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """SELECT event_id, event_type, episode_id, principal_id,
                      occurred_at, payload_json, evidence_uri
               FROM event_log
               WHERE event_type IN ('Action.Succeeded.v1', 'Outcome.Human.v1')
                 AND occurred_at >= ?
               ORDER BY occurred_at DESC""",
            (cutoff,),
        ).fetchall()
    finally:
        conn.close()

    entries: list[dict[str, Any]] = []
    for row in rows:
        payload = json.loads(row["payload_json"])
        episode_id = row["episode_id"] or payload.get("episode_id", "")
        if not episode_id:
            continue

        summary_parts: list[str] = []
        if row["event_type"] == "Action.Succeeded.v1":
            cap = payload.get("capability", "")
            if cap:
                summary_parts.append(f"action:{cap}")
            status = payload.get("status", "")
            if status:
                summary_parts.append(status)
        elif row["event_type"] == "Outcome.Human.v1":
            verdict = payload.get("verdict", "")
            if verdict:
                summary_parts.append(f"verdict:{verdict}")
            time_saved = payload.get("estimated_time_saved_seconds")
            if time_saved:
                summary_parts.append(f"saved:{time_saved}s")

        summary = " | ".join(summary_parts) if summary_parts else row["event_type"]

        evidence_uri = row["evidence_uri"]
        if not evidence_uri:
            result = payload.get("result", {})
            if isinstance(result, dict):
                evidence_uri = result.get("evidence_uri")

        entries.append({
            "source": "ledger",
            "confidence": "high",
            "ref_id": f"ledger-{row['event_id']}",
            "episode_id": episode_id,
            "request_id": payload.get("correlation_id", row["event_id"]),
            "summary": summary,
            "occurred_at": row["occurred_at"],
            "evidence_uri": evidence_uri,
        })

    return entries


# ---------------------------------------------------------------------------
# Git source
# ---------------------------------------------------------------------------

def _collect_git(repo: Path, since_days: int = 7) -> list[dict[str, Any]]:
    try:
        result = subprocess.run(
            ["git", "log", "--merges", f"--since={since_days} days ago",
             "--format=%H|%ad|%s", "--date=iso-strict"],
            cwd=repo, check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError:
        return []

    entries: list[dict[str, Any]] = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        full_sha, date_str, subject = parts

        if any(p.match(subject) for p in SYNC_MERGE_PATTERNS):
            continue

        m = PR_MERGE_PATTERN.match(subject)
        if m:
            pr_num = m.group(1)
            summary = m.group(3).strip() if m.group(3) else m.group(2).strip()
        else:
            m2 = PR_MERGE_PATTERN_NO_COLON.match(subject)
            if m2:
                pr_num = m2.group(1)
                summary = m2.group(2).strip()
            else:
                continue

        short_sha = full_sha[:12]
        episode_id = f"git-{short_sha}"

        entries.append({
            "source": "git",
            "confidence": "medium",
            "ref_id": episode_id,
            "episode_id": episode_id,
            "request_id": f"pr-{pr_num}",
            "summary": summary,
            "occurred_at": date_str,
        })

    return entries


# ---------------------------------------------------------------------------
# Debt source
# ---------------------------------------------------------------------------

def _collect_debt(items_dir: Path) -> list[dict[str, Any]]:
    if not items_dir.exists():
        return []

    entries: list[dict[str, Any]] = []
    for yaml_file in sorted(items_dir.glob("*.yaml")):
        try:
            if yaml is not None:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            else:
                data = _parse_yaml_minimal(yaml_file)
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        state = str(data.get("lifecycle_state", "")).strip().strip('"')
        closed_at = data.get("closed_at")

        if state == "closed":
            pass
        elif state == "resolved" and closed_at:
            pass
        else:
            continue

        item_id = data.get("id", yaml_file.stem)
        title = data.get("title", yaml_file.stem)
        occurred_at = str(closed_at) if closed_at else str(data.get("opened_at", ""))

        entries.append({
            "source": "debt",
            "confidence": "low",
            "ref_id": f"debt-{item_id}",
            "episode_id": f"debt-{item_id}",
            "request_id": f"debt-{item_id}",
            "summary": str(title),
            "occurred_at": occurred_at,
        })

    return entries


def _parse_yaml_minimal(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                result[key] = value
    return result


# ---------------------------------------------------------------------------
# Dedup, sort, negative samples
# ---------------------------------------------------------------------------

def _dedup(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for e in entries:
        ref = e["ref_id"]
        if ref not in best:
            best[ref] = e
        else:
            existing_conf = CONFIDENCE_ORDER.get(best[ref]["confidence"], 99)
            new_conf = CONFIDENCE_ORDER.get(e["confidence"], 99)
            if new_conf < existing_conf:
                best[ref] = e
    return list(best.values())


def _sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda e: (
            CONFIDENCE_ORDER.get(e["confidence"], 99),
            e.get("occurred_at", ""),
        ),
    )


def _apply_negative_samples(
    entries: list[dict[str, Any]],
    state_dir: Path,
) -> list[dict[str, Any]]:
    neg_file = state_dir / NEGATIVE_SAMPLES_FILE
    if not neg_file.exists():
        return entries

    try:
        negative_ids = set(json.loads(neg_file.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError):
        return entries

    return [e for e in entries if e["ref_id"] not in negative_ids]


def _add_negative_sample(state_dir: Path, ref_id: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    neg_file = state_dir / NEGATIVE_SAMPLES_FILE

    existing: list[str] = []
    if neg_file.exists():
        try:
            existing = json.loads(neg_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, TypeError):
            existing = []

    if ref_id not in existing:
        existing.append(ref_id)
        neg_file.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _self_test() -> bool:
    import tempfile

    print("Running self-test...", file=sys.stderr)

    sync_subjects = [
        "Merge origin/main: some stuff",
        "Merge branch 'main' of https://github.com/org/repo",
    ]
    for s in sync_subjects:
        assert any(p.match(s) for p in SYNC_MERGE_PATTERNS), f"Should match sync: {s}"

    pr_subject = "Merge pull request #42 from org/feature"
    assert PR_MERGE_PATTERN_NO_COLON.match(pr_subject), "Should match PR merge"
    m = PR_MERGE_PATTERN_NO_COLON.match(pr_subject)
    assert m and m.group(1) == "42"
    assert m and "feature" in m.group(2)

    entries = [
        {"ref_id": "x", "confidence": "low", "occurred_at": "2026-08-20"},
        {"ref_id": "x", "confidence": "high", "occurred_at": "2026-08-20"},
        {"ref_id": "y", "confidence": "medium", "occurred_at": "2026-08-20"},
    ]
    deduped = _dedup(entries)
    assert len(deduped) == 2
    x_entry = next(e for e in deduped if e["ref_id"] == "x")
    assert x_entry["confidence"] == "high"

    unsorted = [
        {"ref_id": "a", "confidence": "low", "occurred_at": "2026-08-20"},
        {"ref_id": "b", "confidence": "high", "occurred_at": "2026-08-20"},
        {"ref_id": "c", "confidence": "medium", "occurred_at": "2026-08-20"},
    ]
    sorted_entries = _sort_entries(unsorted)
    assert sorted_entries[0]["confidence"] == "high"
    assert sorted_entries[1]["confidence"] == "medium"
    assert sorted_entries[2]["confidence"] == "low"

    with tempfile.TemporaryDirectory() as td:
        state_dir = Path(td)
        _add_negative_sample(state_dir, "ref-1")
        _add_negative_sample(state_dir, "ref-2")
        neg_file = state_dir / NEGATIVE_SAMPLES_FILE
        data = json.loads(neg_file.read_text())
        assert "ref-1" in data
        assert "ref-2" in data
        _add_negative_sample(state_dir, "ref-1")
        data2 = json.loads(neg_file.read_text())
        assert data2.count("ref-1") == 1

    with tempfile.TemporaryDirectory() as td:
        items_dir = Path(td) / "items"
        items_dir.mkdir()
        (items_dir / "closed.yaml").write_text(
            'id: "D-C"\ntitle: "Closed"\nlifecycle_state: "closed"\nclosed_at: "2026-08-20"\n',
            encoding="utf-8",
        )
        (items_dir / "resolved.yaml").write_text(
            'id: "D-R"\ntitle: "Resolved"\nlifecycle_state: "resolved"\nclosed_at: "2026-08-22"\n',
            encoding="utf-8",
        )
        (items_dir / "open-resolved.yaml").write_text(
            'id: "D-OR"\ntitle: "Open Resolved"\nlifecycle_state: "resolved"\n',
            encoding="utf-8",
        )
        (items_dir / "open.yaml").write_text(
            'id: "D-O"\ntitle: "Open"\nlifecycle_state: "open"\n',
            encoding="utf-8",
        )
        debt_entries = _collect_debt(items_dir)
        assert len(debt_entries) == 2, f"Expected 2, got {len(debt_entries)}"
        ids = {e["ref_id"] for e in debt_entries}
        assert "debt-D-C" in ids
        assert "debt-D-R" in ids

    print("Self-test PASSED", file=sys.stderr)
    return True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Three-source episode draft aggregator for cockpit attest (read-only).",
    )
    parser.add_argument("--since", type=int, default=7,
                        help="Look back N days (default: 7)")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output as JSON array")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max entries to output (0 = unlimited)")
    parser.add_argument("--add-negative", type=str, metavar="REF_ID",
                        help="Append ref_id to negative samples file")
    parser.add_argument("--self-test", action="store_true",
                        help="Run internal self-test and exit")
    parser.add_argument("--ledger", type=str, default=None,
                        help="Override ledger DB path")
    parser.add_argument("--debt-dir", type=str, default=None,
                        help="Override debt items directory")
    parser.add_argument("--state-dir", type=str, default=None,
                        help="Override state directory")
    parser.add_argument("--repo", type=str, default=None,
                        help="Override git repo path")

    args = parser.parse_args()

    if args.self_test:
        ok = _self_test()
        sys.exit(0 if ok else 1)

    if args.add_negative:
        state_dir = Path(args.state_dir) if args.state_dir else DEFAULT_STATE_DIR
        _add_negative_sample(state_dir, args.add_negative)
        print(f"Added negative sample: {args.add_negative}", file=sys.stderr)
        return

    ledger_path = Path(args.ledger) if args.ledger else DEFAULT_LEDGER
    debt_dir = Path(args.debt_dir) if args.debt_dir else DEFAULT_DEBT_DIR
    state_dir = Path(args.state_dir) if args.state_dir else DEFAULT_STATE_DIR
    repo = Path(args.repo) if args.repo else WORKSPACE

    all_entries: list[dict[str, Any]] = []
    all_entries.extend(_collect_ledger(ledger_path, since_days=args.since))
    all_entries.extend(_collect_git(repo, since_days=args.since))
    all_entries.extend(_collect_debt(debt_dir))

    deduped = _dedup(all_entries)
    sorted_entries = _sort_entries(deduped)
    filtered = _apply_negative_samples(sorted_entries, state_dir)

    if args.limit > 0:
        filtered = filtered[:args.limit]

    if args.json_output:
        print(json.dumps(filtered, indent=2, ensure_ascii=False))
    else:
        for e in filtered:
            conf_tag = f"[{e['confidence'].upper()}]"
            print(f"{conf_tag} {e['source']:6s} {e['ref_id']:30s} {e['summary'][:60]}")

        if not filtered:
            print("(no episodes found)", file=sys.stderr)


if __name__ == "__main__":
    main()
