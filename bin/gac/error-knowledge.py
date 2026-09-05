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


# ADR-0443 v2 (Q8): escape 台账 → pitfall 周期喂食。
# 对聚合 ≥3 次的正常指纹（排除 preflight-clean/unattributed 归因桶），
# 复用 fuzzy 去重语义生成/递增 pitfall 条目，agent 标记 auto:escape-digest。
# ADR-0443 v4: fuzzy 去重精度——v3 实测假阳性（"git add -A" symptom 以子串匹配
# 误配无关 pitfall）。改词级交集 + 最小词长 + stopword，杜绝 "add"∈"additional" 类命中。
_STOPWORDS = frozenset(
    "the a an and or of in on at to for with without from by is are was were be been "
    "not no but if then else when after before during this that these those it its "
    "目录 文件 包含 指向 状态 后 含 被以 命中".split()
)
_MIN_TOKEN_LEN = 4


def _tokens(text: str) -> set[str]:
    import re as _re

    return {w for w in _re.split(r"[^\w]+", text.lower()) if len(w) >= _MIN_TOKEN_LEN and w not in _STOPWORDS}


def symptom_overlap(new_symptom: str, existing_symptom: str) -> int:
    """词级交集数（去 stopword、len>=4）；>=3 视为同坑。"""

    return len(_tokens(new_symptom) & _tokens(existing_symptom))


FEED_MIN_COUNT = 3
_SURFACE_CATEGORY = {
    "ci-local-fast": "gate",
    "pointer-drift": "submodule",
    "submodule-ancestry-gate": "submodule",
    "gac": "scoring",
}


def feed_from_escapes(escape_dir: Path | None = None, *, min_count: int = FEED_MIN_COUNT) -> dict[str, int]:
    """Aggregate escape fingerprints into pitfalls (weekly-cycle entry point).

    Returns counts: {"fed": 新增条目, "bumped": 递增条目, "promoted": 触发晋升草案}.
    """

    directory = escape_dir or (ROOT / ".omo/_delivery/swarm-escape")
    if not directory.is_dir():
        return {"fed": 0, "bumped": 0, "promoted": 0}
    counter: dict[str, int] = {}
    excerpt: dict[str, str] = {}
    for path in sorted(directory.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        key = str(record.get("fingerprint_key") or "")
        if not key or key.startswith(("preflight-clean", "unspecified")):
            continue
        counter[key] = counter.get(key, 0) + 1
        if key not in excerpt:
            fps = record.get("fingerprints") or []
            excerpt[key] = str(fps[0].get("output_excerpt", ""))[:200] if fps and isinstance(fps[0], dict) else key
    entries = _load_all()
    fed = bumped = promoted = 0
    for key, count in counter.items():
        if count < min_count:
            continue
        surface = key.split("|", 1)[0]
        check_id = key.split("|")[1] if "|" in key else key
        symptom = excerpt.get(key, key)
        matched = False
        for e in entries:
            if e.get("status") != "active":
                continue
            common = symptom_overlap(symptom, str(e.get("symptom", "")))
            if common >= 3:
                e["times_encountered"] = e.get("times_encountered", 1) + count
                e["last_confirmed_at"] = datetime.now(UTC).strftime("%Y-%m-%d")
                # ADR-0443 v6: 定向提取后的新观测若含失败标记而旧 symptom 无
                # （v5 旧头部截断遗留），以最新观测更新 symptom —— 语义是
                # "最近一次观测"，非伪造历史。
                if any(m in symptom for m in ("FAIL", "\u274c", "Error")) and not any(
                    m in str(e.get("symptom", "")) for m in ("FAIL", "\u274c", "Error")
                ):
                    e["symptom"] = symptom[:240]
                _save_entry(e)
                bumped += 1
                matched = True
                break
        if not matched:
            category = _SURFACE_CATEGORY.get(surface, "gate")
            seq = _next_seq(category, entries)
            entry = {
                "schema": "agent-error/v1",
                "id": f"PITFALL-{category[:3].upper()}-{seq:03d}",
                "category": category,
                "severity": "medium",
                "title": f"auto: {check_id} 反复豁免 ({count}x)",
                "symptom": symptom,
                "root_cause": "escape 台账周期喂食（ADR-0443 v2 Q8），根因待人工复盘",
                "solution": "",
                "prevention": "",
                "tags": ["auto-fed", surface],
                "discovered_by": "auto:escape-digest",
                "discovered_at": datetime.now(UTC).strftime("%Y-%m-%d"),
                "times_encountered": count,
                "last_confirmed_at": datetime.now(UTC).strftime("%Y-%m-%d"),
                "status": "active",
            }
            entries.append(entry)
            _save_entry(entry)
            fed += 1
        # 晋升检查（周喂食直达阈值的常见路径：count>=5 首次即晋升）
        for e in entries:
            if e.get("times_encountered", 0) >= ESCALATION_THRESHOLD and _promote_rule_draft(e) is not None:
                promoted += 1
    return {"fed": fed, "bumped": bumped, "promoted": promoted}


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
        text = f"{e.get('symptom', '')} {e.get('title', '')} {e.get('root_cause', '')}".lower()
        score += sum(1 for w in symptom_words if w in text) * 5
        if score > 0:
            results.append((score, e))
    results.sort(key=lambda x: -x[0])
    top = results[: args.limit]
    if args.json:
        print(
            json.dumps(
                [
                    {
                        "id": e["id"],
                        "score": s,
                        "title": e.get("title"),
                        "solution": e.get("solution"),
                        "tags": e.get("tags"),
                    }
                    for s, e in top
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"lookup: {len(top)} matches (of {len(entries)} total)")
        for s, e in top:
            print(f"\n  [{e['id']}] ({s}pts) {e.get('title')}")
            print(f"    symptom: {e.get('symptom', '')[:80]}")
            print(f"    solution: {e.get('solution', '')[:80]}")
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
        common = symptom_overlap(args.symptom, str(e.get("symptom", "")))
        if common >= 3 and e.get("status") == "active":
            e["times_encountered"] = e.get("times_encountered", 1) + 1
            e["last_confirmed_at"] = datetime.now(UTC).strftime("%Y-%m-%d")
            _save_entry(e)
            print(
                f"DEDUP: matched [{e['id']}] '{e.get('title')}' — times_encountered incremented to {e['times_encountered']}"
            )
            if e["times_encountered"] >= ESCALATION_THRESHOLD:
                draft_path = _promote_rule_draft(e)
                if draft_path:
                    print(
                        f"⚡ ESCALATION: {e['id']} ≥{ESCALATION_THRESHOLD} 次 → 规则草案已生成 {draft_path}（等人审入册）"
                    )
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


def cmd_feed_escapes(args):
    counts = feed_from_escapes()
    print(json.dumps({"schema": "error-knowledge.feed.v1", **counts}, ensure_ascii=False))
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


def cmd_check(args):
    """Gate: 校验 pitfalls 库一致性 (解析/必填字段/id 唯一/category 合法). exit 1 on problem."""
    import yaml

    problems: list[str] = []
    entries: list[dict] = []
    seen_ids: dict[str, str] = {}

    if PITFALLS_DIR.is_dir():
        for cat_dir in sorted(PITFALLS_DIR.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("."):
                continue
            if cat_dir.name not in CATEGORIES and cat_dir.name != "submodule":
                problems.append(f"unknown category dir: {cat_dir.name}")
            for f in sorted(cat_dir.glob("*.yaml")):
                try:
                    d = yaml.safe_load(f.read_text())
                except Exception as exc:  # noqa: BLE001
                    problems.append(f"unparseable: {f} ({exc})")
                    continue
                if not isinstance(d, dict):
                    problems.append(f"not a mapping: {f}")
                    continue
                eid = d.get("id")
                if not eid:
                    problems.append(f"missing id: {f}")
                    continue
                if eid in seen_ids:
                    problems.append(f"duplicate id {eid}: {f} vs {seen_ids[eid]}")
                seen_ids[eid] = f.name
                # schema: agent-error/v1 条目严格校验必填字段; legacy 格式 (无 schema, 如 CRD-001) 只查可解析/id
                # auto 喂食条目 (discovered_by 含 auto:) 的 solution/prevention 允许留空待人工复盘
                if d.get("schema") == "agent-error/v1":
                    is_auto = "auto:" in str(d.get("discovered_by", ""))
                    for key in ("schema", "title", "symptom", "category", "status"):
                        if not d.get(key):
                            problems.append(f"{eid}: missing required field '{key}'")
                    if not d.get("solution") and not is_auto:
                        problems.append(f"{eid}: missing required field 'solution'")
                    if d.get("category") and d["category"] not in CATEGORIES:
                        problems.append(f"{eid}: invalid category '{d['category']}'")
                    if d.get("id") and not d["id"].startswith("PITFALL-"):
                        problems.append(f"{eid}: id must start with PITFALL-")
                d["_path"] = str(f)
                d["_file"] = f.name
                entries.append(d)

    # 强制至少 1 条记录 (空库视为体系未启用, 也报问题)
    if not entries:
        problems.append("pitfalls library is empty")

    ok = not problems
    result = {"ok": ok, "total": len(entries), "problems": problems}
    if args.json or not ok:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"error-knowledge check: ok ({len(entries)} pitfalls)")
    return 0 if ok else 1


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

    fd = sub.add_parser("feed-escapes")
    st = sub.add_parser("stats")
    st.add_argument("--json", action="store_true")
    ck = sub.add_parser("check")
    ck.add_argument("--json", action="store_true")

    args = ap.parse_args()
    handlers = {"lookup": cmd_lookup, "record": cmd_record, "stats": cmd_stats, "feed-escapes": cmd_feed_escapes, "check": cmd_check}
    fn = handlers.get(args.cmd)
    if fn:
        raise SystemExit(fn(args) or 0)
    ap.print_help()


if __name__ == "__main__":
    main()
