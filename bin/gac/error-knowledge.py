#!/usr/bin/env python3
"""Agent Institutional Memory — 错误知识库 lookup/record/stats/check (ADR-0424 配套).

体系设计: .omo/_knowledge/pitfalls/{category}/{slug}.yaml
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
CATEGORIES = ["submodule", "cron", "gate", "scoring", "coordination", "environment", "measurement"]
ROOT = Path(__file__).resolve().parents[2]
ESCALATION_THRESHOLD = 5
OBSOLETE_DAYS = 90


def _load_all(issues: list[str] | None = None) -> list[dict]:
    """Load all pitfall entries from YAML files.

    A file the recall path cannot use is never dropped silently: pass ``issues``
    and every such file is reported there (``check`` gates on it). Legacy entries
    predating the ``agent-error/v1`` schema are normalized instead of skipped —
    ``PITFALL-CRD-001`` used ``name:`` where the loader demanded ``title:``, so
    recall counted 33 while ``check`` counted 34 and the lesson was unreachable.
    """
    entries = []
    if not PITFALLS_DIR.is_dir():
        return entries
    for cat_dir in sorted(PITFALLS_DIR.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        for f in sorted(cat_dir.glob("*.yaml")):
            report = None
            try:
                import yaml

                d = yaml.safe_load(f.read_text())
            except Exception as exc:  # noqa: BLE001
                report = f"unparseable: {f} ({exc})"
                d = None
            if report is None and not isinstance(d, dict):
                report = f"not a mapping: {f}"
                d = None
            if report is None and not (d.get("title") or d.get("name")):
                report = f"no title or name: {f}"
                d = None
            if report is not None:
                if issues is not None:
                    issues.append(report)
                continue
            if not d.get("schema"):
                d.setdefault("title", d.get("name", ""))
                d.setdefault("category", cat_dir.name)
            d["_path"] = str(f)
            d["_file"] = f.name
            entries.append(d)
    return entries


def _next_seq(category: str, entries: list[dict]) -> int:
    prefix = f"PITFALL-{category[:3].upper()}"
    seqs = [int(e["id"].rsplit("-", 1)[-1]) for e in entries if e.get("id", "").startswith(prefix)]
    return max(seqs, default=0) + 1


def _save_entry(entry: dict):
    cat_dir = PITFALLS_DIR / entry["category"]
    cat_dir.mkdir(parents=True, exist_ok=True)
    import yaml

    # Loader-private keys must never reach disk: record's dedup branch re-saves an
    # entry it got from _load_all, which used to write _path (a host-absolute,
    # often already-deleted worktree path) into 6 committed pitfall files.
    public = {k: v for k, v in entry.items() if not k.startswith("_")}
    path = cat_dir / f"{entry['id']}.yaml"
    path.write_text(yaml.dump(public, allow_unicode=True, sort_keys=False), encoding="utf-8")
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
        # 没有 escape 台账（worktree-local，常不存在）只等于「本轮无新观测」，
        # 不等于「已入库的坑不需要人审草案」。晋升扫描照跑。
        return {"fed": 0, "bumped": 0, "promoted": len(promote_overdue())}
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
    fed = bumped = 0
    for key, count in counter.items():
        if count < min_count:
            continue
        surface = key.split("|", 1)[0]
        check_id = key.split("|")[1] if "|" in key else key
        symptom = excerpt.get(key, key)
        # ADR-0443 v7 (BET-Y2Q3-T10-202): 喂食目标类别必须先于匹配确定。v6 之前
        # 匹配是类别盲的，一个 submodule 面的 escape 只要词面撞上就把 gate 坑的
        # times_encountered 加上去 —— 而该计数正是规则晋升的证据，跨类污染会
        # 把不相关的坑推过阈值生成草案。新条目沿用同一类别，两者不会分叉。
        category = _SURFACE_CATEGORY.get(surface, "gate")
        matched = False
        for e in entries:
            if e.get("status") != "active":
                continue
            if e.get("category") != category:
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
    # 晋升检查（周喂食直达阈值的常见路径：count>=5 首次即晋升）。v6 把它放在
    # 每个 key 的内层循环里、遍历全表，既 O(n²) 又让「无 escape 台账」时整段
    # 不执行；改喂完扫一次，与 promote-drafts 共用同一个谓词。
    promoted = len(promote_overdue(entries))
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
        e_tags = set(str(t).lower() for t in (e.get("tags") or []))
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


def _rule_id_for(pitfall_id: str) -> str:
    return f"CR-PITFALL-{pitfall_id.removeprefix('PITFALL-')}"


def _display(path: Path) -> str:
    """仓内路径显示成相对路径；被重定向到仓外（测试、别的 checkout）时照原样报。"""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def rule_draft_queue(entries: list[dict] | None = None) -> dict[str, list[str]]:
    """人审队列点名：达阈值的坑有没有对应草案躺在队列里。

    晋升过去只在两个地方被触发，两者都不是「随时可查」：喂食内层循环（要求
    ``.omo/_delivery/swarm-escape/`` 存在，而它是 worktree-local、随 worktree 回收
    消失）和 ``record --confirm-dup``。实测 2026-09-24：37 个坑里 3 个已过阈值、
    队列里 0 份草案，且 ``stats``/``check`` 都不报缺草案 —— 管道末端从未被走到。
    """
    source = _load_all() if entries is None else entries
    queue: dict[str, list[str]] = {"drafted": [], "overdue": [], "stale_review": []}
    for e in source:
        if e.get("times_encountered", 0) < ESCALATION_THRESHOLD:
            continue
        eid = str(e.get("id", ""))
        path = RULE_DRAFTS_DIR / f"{_rule_id_for(eid)}.json"
        if not path.is_file():
            if e.get("status") != "obsolete":
                queue["overdue"].append(eid)
            continue
        queue["drafted"].append(eid)
        try:
            review_before = json.loads(path.read_text(encoding="utf-8")).get("draft_rule", {}).get("review_before")
        except (OSError, json.JSONDecodeError):
            queue["stale_review"].append(eid)
            continue
        if review_before and str(review_before) < datetime.now(UTC).strftime("%Y-%m-%d"):
            queue["stale_review"].append(eid)
    for key in queue:
        queue[key].sort()
    return queue


def promote_overdue(entries: list[dict] | None = None) -> list[Path]:
    """过一遍阈值以上的坑，缺草案的交给 ``_promote_rule_draft``（幂等，不覆盖人审结果）。"""
    source = _load_all() if entries is None else entries
    created = []
    for e in source:
        if e.get("status") not in ("active", "draft") or e.get("times_encountered", 0) < ESCALATION_THRESHOLD:
            continue
        path = _promote_rule_draft(e)
        if path is not None:
            created.append(path)
    return created


def cmd_record(args):
    entries = _load_all()
    category = args.category
    if category not in CATEGORIES:
        print(f"error: invalid category '{category}'. Valid: {', '.join(CATEGORIES)}", file=sys.stderr)
        return 1

    # Dedup is advisory. Three shared symptom words are far too weak a signal to
    # auto-merge — measured 2026-09-24, it merged a shallow-clone defect into both a
    # branch-protection entry and a git-show entry — and swallowing the new record
    # loses knowledge while inflating a counter that drives rule escalation. So the
    # default records, and only an explicit --confirm-dup <ID> increments.
    matches = [
        e
        for e in entries
        if e.get("category") == category
        and e.get("status") == "active"
        and symptom_overlap(args.symptom, str(e.get("symptom", ""))) >= 3
    ]
    if args.confirm_dup:
        target = next((e for e in matches if e["id"] == args.confirm_dup), None)
        if target is None:
            candidates = ", ".join(str(e["id"]) for e in matches) or "none"
            print(
                f"error: --confirm-dup {args.confirm_dup} is not a dedup candidate (candidates: {candidates})",
                file=sys.stderr,
            )
            return 1
        target["times_encountered"] = target.get("times_encountered", 1) + 1
        target["last_confirmed_at"] = datetime.now(UTC).strftime("%Y-%m-%d")
        _save_entry(target)
        print(
            f"DEDUP: confirmed [{target['id']}] '{target.get('title')}' — "
            f"times_encountered incremented to {target['times_encountered']}"
        )
        if target["times_encountered"] >= ESCALATION_THRESHOLD:
            draft_path = _promote_rule_draft(target)
            if draft_path:
                print(
                    f"⚡ ESCALATION: {target['id']} ≥{ESCALATION_THRESHOLD} 次 → 规则草案已生成 {draft_path}（等人审入册）"
                )
            else:
                print(f"⚡ ESCALATION: {target['id']} ≥{ESCALATION_THRESHOLD} 次（草案已在 rule-drafts，勿重复生成）")
        return 0
    if matches:
        listed = "; ".join(f"{e['id']} '{e.get('title')}'" for e in matches)
        print(f"DEDUP CANDIDATES (未自动合并，本条按新坑入库): {listed}")
        print("  确认是同一条坑时重跑并加 --confirm-dup <ID>")

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
    queue = rule_draft_queue(entries)
    result = {
        "total": len(entries),
        "by_category": by_cat,
        "by_status": by_status,
        "escalated": escalated,
        "rule_drafts_drafted": queue["drafted"],
        "overdue_rule_drafts": queue["overdue"],
        "rule_drafts_stale_review": queue["stale_review"],
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"pitfalls: {result['total']} total")
        for k, v in sorted(by_cat.items()):
            print(f"  {k}: {v}")
        print(f"  status: {by_status}")
        if escalated:
            print(f"  ⚡ escalation candidates: {escalated}")
        print(f"  rule-drafts: {len(queue['drafted'])} 在队列, {len(queue['overdue'])} overdue")
        for eid in queue["overdue"]:
            print(f"    ⏳ overdue: {eid} → CR-PITFALL-{eid.removeprefix('PITFALL-')} (跑 promote-drafts)")
        for eid in queue["stale_review"]:
            print(f"    🕰 review_before 已过期: {eid} 的草案等人复审")
    return 0


def cmd_check(args):
    """Gate: 校验 pitfalls 库一致性 (解析/必填字段/id 唯一/category 合法). exit 1 on problem."""
    problems: list[str] = []
    seen_ids: dict[str, str] = {}
    on_disk = 0

    if PITFALLS_DIR.is_dir():
        for cat_dir in sorted(PITFALLS_DIR.iterdir()):
            if not cat_dir.is_dir() or cat_dir.name.startswith("."):
                continue
            if cat_dir.name not in CATEGORIES and cat_dir.name != "submodule":
                problems.append(f"unknown category dir: {cat_dir.name}")
            on_disk += len(list(cat_dir.glob("*.yaml")))

    # check and recall now share _load_all. check used to walk the tree itself, so
    # the two counts could diverge without anything failing — and they did (34 vs 33).
    unrecallable: list[str] = []
    entries = _load_all(issues=unrecallable)
    problems.extend(unrecallable)
    if len(entries) + len(unrecallable) != on_disk:
        problems.append(
            f"recall divergence: {on_disk} files on disk, {len(entries)} recallable, "
            f"{len(unrecallable)} reported unusable"
        )

    for d in entries:
        eid = d.get("id")
        if not eid:
            problems.append(f"missing id: {d['_path']}")
            continue
        if eid in seen_ids:
            problems.append(f"duplicate id {eid}: {d['_path']} vs {seen_ids[eid]}")
        seen_ids[eid] = d["_file"]
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

    # 强制至少 1 条记录 (空库视为体系未启用, 也报问题)
    if not entries:
        problems.append("pitfalls library is empty")

    ok = not problems
    result = {"ok": ok, "total": len(entries), "problems": problems}
    # 只读段落：人审队列健康度。故意不并进 problems —— 本 check 挂在 gac-local-gate
    # (error-knowledge-check) 上，让「草案尚等人审」flip 共享门禁退出码等于把 HITL
    # 队列变红灯（spec §4 G4 与 non_goals）。
    queue = rule_draft_queue(entries)
    result["rule_drafts"] = {
        "threshold": ESCALATION_THRESHOLD,
        "dir": _display(RULE_DRAFTS_DIR),
        "drafted": queue["drafted"],
        "overdue": queue["overdue"],
        "stale_review": queue["stale_review"],
    }
    if args.json or not ok:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"error-knowledge check: ok ({len(entries)} pitfalls)")
    if not args.json:  # --json 的 stdout 必须保持单个 JSON 文档（gac-local-gate 会 parse）
        for eid in queue["overdue"]:
            print(f"  ⏳ rule-drafts overdue: {eid} → CR-PITFALL-{eid.removeprefix('PITFALL-')} (跑 promote-drafts)")
        for eid in queue["stale_review"]:
            print(f"  🕰 review_before 已过期: {eid} 的草案等人复审")
    return 0 if ok else 1


def cmd_promote_drafts(args):
    """补管道回边：扫描已入库的坑，缺草案的用 _promote_rule_draft 生成（幂等）。"""
    before = rule_draft_queue()
    payload = {
        "schema": "error-knowledge.promote.v1",
        "threshold": ESCALATION_THRESHOLD,
        "overdue_before": before["overdue"],
        "dry_run": bool(args.dry_run),
        "created": [],
        "overdue_after": before["overdue"],
    }
    if args.dry_run:
        payload["would_create"] = before["overdue"]
    else:
        created = promote_overdue()
        payload["created"] = [_display(p) for p in created]
        payload["overdue_after"] = rule_draft_queue()["overdue"]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_review_unwired(args):
    """``confirm``/``reject`` 从未接线：解析器存在但 handlers 表里没有，过去打 help 并 exit 0，

    于是「草案被人审处置」这条路在 CLI 上看起来存在、实际是空的。改成显式失败，
    真正的处置面是 ADR-0431 的人审 + ``lib/yaml_ssot_edit.py`` roundtrip 入册。
    """
    print(
        f"NOT_IMPLEMENTED: {args.cmd} --id {args.id} 没有 handler（历史上静默 exit 0）。"
        f"草案处置 = 人审后用 lib/yaml_ssot_edit.py roundtrip 写入 governance-checks.yaml"
        f"（ADR-0431 D4）；队列现状用 stats / promote-drafts --dry-run 看。",
        file=sys.stderr,
    )
    return 2


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
    rec.add_argument(
        "--confirm-dup",
        metavar="PITFALL-ID",
        default=None,
        help="确认本次症状就是该条目：只给它计数，不新增条目",
    )

    cf = sub.add_parser("confirm", help="未实现 — 见 promote-drafts / stats")
    cf.add_argument("--id", required=True)
    rj = sub.add_parser("reject", help="未实现 — 见 promote-drafts / stats")
    rj.add_argument("--id", required=True)

    fd = sub.add_parser("feed-escapes")
    pd = sub.add_parser("promote-drafts", help="扫描过阈值的坑，补齐人审草案队列")
    pd.add_argument("--dry-run", action="store_true", help="只报告会生成哪些，不落盘")
    st = sub.add_parser("stats")
    st.add_argument("--json", action="store_true")
    ck = sub.add_parser("check")
    ck.add_argument("--json", action="store_true")

    args = ap.parse_args()
    handlers = {
        "lookup": cmd_lookup,
        "record": cmd_record,
        "stats": cmd_stats,
        "feed-escapes": cmd_feed_escapes,
        "promote-drafts": cmd_promote_drafts,
        "confirm": cmd_review_unwired,
        "reject": cmd_review_unwired,
        "check": cmd_check,
    }
    fn = handlers.get(args.cmd)
    if fn:
        raise SystemExit(fn(args) or 0)
    ap.print_help()


if __name__ == "__main__":
    main()
