#!/usr/bin/env python3
"""Agent Institutional Memory — 错误知识库 lookup/record/stats/check (ADR-0424 配套).

体系设计: .omo/_knowledge/pitfalls/{category}/{slug}.yaml + .index.json 缓存
原则: 遇到问题先查这里 → 没有就解决并记录 → 有就直接复用
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
PITFALLS_DIR = WORKSPACE / ".omo" / "_knowledge" / "pitfalls"
INDEX_FILE = PITFALLS_DIR / ".index.json"
CATEGORIES = ["submodule", "cron", "gate", "scoring", "coordination", "environment", "measurement"]
ROOT = Path(__file__).resolve().parents[2]
ESCALATION_THRESHOLD = 5
OBSOLETE_DAYS = 90


def _load_all() -> list[dict]:
    """Load all pitfall entries from YAML files."""
    entries = []
    if not PITFALLS_DIR.is_dir():
        return entries
    for cat_dir in sorted(PITFALLS_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        for f in sorted(cat_dir.glob("*.yaml")):
            try:
                import yaml
                d = yaml.safe_load(f.read_text())
                if isinstance(d, dict) and d.get("title"):
                    d["_path"] = str(f)
                    d["_file"] = f.name
                    entries.append(d)
            except Exception:
                continue
    return entries


def _next_seq(category: str, entries: list[dict]) -> int:
    prefix = f"PITFALL-{category[:3].upper()}"
    seqs = [int(e["id"].rsplit("-", 1)[-1]) for e in entries if e.get("id", "").startswith(prefix)]
    return max(seqs, default=0) + 1


def _save_entry(entry: dict):
    cat_dir = PITFALLS_DIR / entry["category"]
    cat_dir.mkdir(parents=True, exist_ok=True)
    import yaml
    path = cat_dir / f"{entry['id']}.yaml"
    path.write_text(yaml.dump(entry, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def cmd_lookup(args):
    entries = _load_all()
    tags = set(t.strip().lower() for t in (args.tags or "").split(",") if t.strip())
    symptom_words = set(w.lower() for w in (args.symptom or "").split() if len(w) > 2)
    results = []
    for e in entries:
        if args.category and e.get("category") != args.category:
            continue
        if e.get("status") == "obsolete":
            continue
        score = 0
        e_tags = set(t.lower() for t in e.get("tags", []))
        score += len(tags & e_tags) * 10
        text = f"{e.get('symptom','')} {e.get('title','')} {e.get('root_cause','')}".lower()
        score += sum(1 for w in symptom_words if w in text) * 5
        if score > 0:
            results.append((score, e))
    results.sort(key=lambda x: -x[0])
    top = results[: args.limit]
    if args.json:
        print(json.dumps([{"id": e["id"], "score": s, "title": e.get("title"), "solution": e.get("solution"), "tags": e.get("tags")} for s, e in top], ensure_ascii=False, indent=2))
    else:
        print(f"lookup: {len(top)} matches (of {len(entries)} total)")
        for s, e in top:
            print(f"\n  [{e['id']}] ({s}pts) {e.get('title')}")
            print(f"    symptom: {e.get('symptom','')[:80]}")
            print(f"    solution: {e.get('solution','')[:80]}")
            print(f"    tags: {e.get('tags', [])}")
    return 0


RULE_DRAFTS_DIR = ROOT / ".omo/_delivery/rule-drafts"


def _promote_rule_draft(entry: dict) -> Path | None:
    """ADR-0443 事故→规则流水线：达阈值的 pitfall 生成 GaC 规则草案等人审。

    草案带 0431 生命周期契约字段（added_at/review_before/justification 引
    pitfall 证据链）。人审后用 lib/yaml_ssot_edit.py roundtrip 入册——
    草案本身不碰 governance-checks.yaml（HITL，0431 D4）。
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    review_before = (datetime.now(UTC) + timedelta(days=90)).strftime("%Y-%m-%d")
    rule_id = f"CR-PITFALL-{entry['id'].removeprefix('PITFALL-')}"
    draft = {
        "schema": "gac-rule-draft/v1",
        "rule_id": rule_id,
        "source_pitfall": entry["id"],
        "evidence": {
            "times_encountered": entry.get("times_encountered"),
            "first_seen": entry.get("discovered_at"),
            "last_confirmed": entry.get("last_confirmed_at"),
            "symptom": entry.get("symptom"),
            "prevention": entry.get("prevention"),
        },
        "draft_rule": {
            "id": rule_id,
            "dimension": "X4",
            "executor": "gac_local_gate",
            "justification": f"pitfall {entry['id']} encountered {entry.get('times_encountered')} times (threshold {ESCALATION_THRESHOLD}): {entry.get('title')}",
            "added_at": today,
            "review_before": review_before,
        },
        "status": "awaiting_human_review",
        "generated_by": "ADR-0443 incident-to-rule pipeline",
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    RULE_DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RULE_DRAFTS_DIR / f"{rule_id}.json"
    if out.exists():
        return None  # 草案已生成过，幂等
    out.write_text(json.dumps(draft, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return out


def cmd_record(args):
    entries = _load_all()
    category = args.category
    if category not in CATEGORIES:
        print(f"error: invalid category '{category}'. Valid: {', '.join(CATEGORIES)}", file=sys.stderr)
        return 1

    # dedup check: fuzzy symptom match
    symptom_lower = args.symptom.lower()
    for e in entries:
        existing_sym = e.get("symptom", "").lower()
        common = sum(1 for w in symptom_lower.split() if w in existing_sym)
        if common >= 3 and e.get("status") == "active":
            e["times_encountered"] = e.get("times_encountered", 1) + 1
            e["last_confirmed_at"] = datetime.now(UTC).strftime("%Y-%m-%d")
            _save_entry(e)
            print(f"DEDUP: matched [{e['id']}] '{e.get('title')}' — times_encountered incremented to {e['times_encountered']}")
            if e["times_encountered"] >= ESCALATION_THRESHOLD:
                draft_path = _promote_rule_draft(e)
                if draft_path:
                    print(f"⚡ ESCALATION: {e['id']} ≥{ESCALATION_THRESHOLD} 次 → 规则草案已生成 {draft_path}（等人审入册）")
                else:
                    print(f"⚡ ESCALATION: {e['id']} ≥{ESCALATION_THRESHOLD} 次（草案已在 rule-drafts，勿重复生成）")
            return 0

    seq = _next_seq(category, entries)
    entry = {
        "schema": "agent-error/v1",
        "id": f"PITFALL-{category[:3].upper()}-{seq:03d}",
        "category": category,
        "severity": args.severity or "medium",
        "title": args.title,
        "symptom": args.symptom,
        "root_cause": args.root_cause or "",
        "solution": args.solution,
        "prevention": args.prevention or "",
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
        "discovered_by": args.agent or "unknown",
        "discovered_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "times_encountered": 1,
        "last_confirmed_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "status": args.draft and "draft" or "active",
    }
    path = _save_entry(entry)
    print(f"recorded: {entry['id']} at {path}")
    return 0


def cmd_stats(args):
    entries = _load_all()
    by_cat, by_status, escalated = {}, {}, []
    for e in entries:
        c = e.get("category", "?")
        by_cat[c] = by_cat.get(c, 0) + 1
        st = e.get("status", "?")
        by_status[st] = by_status.get(st, 0) + 1
        if e.get("times_encountered", 0) >= ESCALATION_THRESHOLD:
            escalated.append(e["id"])
    result = {"total": len(entries), "by_category": by_cat, "by_status": by_status, "escalated": escalated}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"pitfalls: {result['total']} total")
        for k, v in sorted(by_cat.items()):
            print(f"  {k}: {v}")
        print(f"  status: {by_status}")
        if escalated:
            print(f"  ⚡ escalation candidates: {escalated}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")

    lk = sub.add_parser("lookup")
    lk.add_argument("--tags", default="")
    lk.add_argument("--symptom", default="")
    lk.add_argument("--category", default="")
    lk.add_argument("--limit", type=int, default=10)
    lk.add_argument("--json", action="store_true")

    rec = sub.add_parser("record")
    rec.add_argument("--category", required=True, choices=CATEGORIES)
    rec.add_argument("--title", required=True)
    rec.add_argument("--symptom", required=True)
    rec.add_argument("--root-cause", default="")
    rec.add_argument("--solution", required=True)
    rec.add_argument("--prevention", default="")
    rec.add_argument("--severity", choices=["critical", "high", "medium", "low"], default="medium")
    rec.add_argument("--tags", default="")
    rec.add_argument("--agent", default="")
    rec.add_argument("--draft", action="store_true")

    cf = sub.add_parser("confirm")
    cf.add_argument("--id", required=True)
    rj = sub.add_parser("reject")
    rj.add_argument("--id", required=True)

    st = sub.add_parser("stats")
    st.add_argument("--json", action="store_true")

    args = ap.parse_args()
    handlers = {"lookup": cmd_lookup, "record": cmd_record, "stats": cmd_stats}
    fn = handlers.get(args.cmd)
    if fn:
        raise SystemExit(fn(args) or 0)
    ap.print_help()


if __name__ == "__main__":
    main()
