#!/usr/bin/env python3
"""过期雷达 (expiry radar) — 让 SLA 越界**提前**可见, 而不是在爆炸当天挡住所有人.

问题 (2026-09-21 实证, 一天内撞两颗):
  现有 freshness 守卫的判定都是**纯二元**: `(today - reviewed).days > review_days`
  → 第 90 天通过, 第 91 天失败。**没有前瞻预警, 也没有 grace 档**。
  于是过期是**突发**的, 且当多个对象在同一天被复审时, 它们会在**同一天集体越界**:

    - X2-C05 (≤14d): `.omo/_truth/registry/omo-governance-surfaces.yaml`
      last-reviewed=2026-09-06 → 09-20 还 14d 通过, 09-21 变 15d → 当天**所有 PR** 失败
    - doc-governance (≤90d): **29 个文档**全部 last-reviewed=2026-06-22
      → 09-20 是 90d 通过, 09-21 是 91d → **29 项同一天集体越界**

  两次的共同形态: 昨天 CI 全绿, 今天纯因日期滚动而全体变红, 且**没人提前知道**。
  这正是仓库最高优先债务「声明/执行鸿沟」的时间维度: SLA 被声明了, 但"何时失效"
  不可见, 于是失效变成事故而不是计划内工作。

本工具**不改判定、不放宽 SLA**, 只做前瞻: 复用两处权威注册表的阈值, 报告
"未来 N 天内将越界"以及"同一天集体越界"这一最危险形态。

权威阈值来源 (复用, 不另立):
  - `.omo/_truth/registry/document-governance.yaml` → `surfaces[].review_days`
    (+ patterns/excludes, 决定扫描范围)
  - `.omo/_truth/x2-freshness-rules.yaml` → `rules[].threshold_days`

用法:
    python3 bin/gac/check-expiry-radar.py [--horizon 7] [--json] [--strict]
退出码:
    0 = 无即将越界 (或有但非 strict)
    1 = --strict 且存在已越界/ imminent (供 cron 报警)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]
DOC_GOV = _ROOT / ".omo" / "_truth" / "registry" / "document-governance.yaml"
X2_RULES = _ROOT / ".omo" / "_truth" / "x2-freshness-rules.yaml"

# frontmatter 里的复审日期字段 (与 doc-governance-check 同源)
REVIEWED_KEY = "last-reviewed"
_DATE_RE = re.compile(r"^\s*(?:last-reviewed|last_reviewed)\s*:\s*['\"]?([0-9]{4}-[0-9]{2}-[0-9]{2})")


def _load_docs(path: Path) -> list[dict]:
    try:
        return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if isinstance(d, dict)]
    except Exception:
        return []


def _frontmatter_date(path: Path) -> date | None:
    """只扫前 20 行的 frontmatter (与判定器一致, 避免全文误匹配)."""
    try:
        for i, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines()):
            if i > 20:
                break
            m = _DATE_RE.match(line)
            if m:
                return date.fromisoformat(m.group(1))
    except (OSError, ValueError):
        return None
    return None


def _doc_gov_path(root: Path) -> Path:
    return root / ".omo" / "_truth" / "registry" / "document-governance.yaml"


def _x2_rules_path(root: Path) -> Path:
    return root / ".omo" / "_truth" / "x2-freshness-rules.yaml"


def _surfaces(root: Path = _ROOT) -> list[dict]:
    """从**该 root 下**的权威注册表读 surfaces (含 review_days/patterns/excludes).

    早期版本忽略 root 直读模块常量, 导致 scan(root=...) 的注入对阈值无效 ——
    测试实测暴露后修正。
    """
    for d in _load_docs(_doc_gov_path(root)):
        if "surfaces" in d and isinstance(d["surfaces"], list):
            return [s for s in d["surfaces"] if isinstance(s, dict)]
    return []


def scan_doc_surfaces(root: Path = _ROOT, horizon: int = 7,
                      today: date | None = None) -> list[dict]:
    """按注册表的 patterns/excludes/review_days 扫描, 算每个文档的剩余天数."""
    today = today or date.today()
    out: list[dict] = []
    for surface in _surfaces(root):
        days = surface.get("review_days")
        if not isinstance(days, int) or days <= 0:
            continue
        patterns = surface.get("patterns") or []
        excludes = surface.get("excludes") or []
        files: set[Path] = set()
        for pat in patterns:
            try:
                files.update(root.glob(pat))
            except (ValueError, IndexError):
                continue
        for pat in excludes:
            try:
                files -= set(root.glob(pat))
            except (ValueError, IndexError):
                continue
        for f in sorted(files):
            if not f.is_file():
                continue
            reviewed = _frontmatter_date(f)
            if reviewed is None:
                continue
            age = (today - reviewed).days
            if age < 0:
                continue  # 未来日期, 交给判定器
            # remaining = 距**首次 fail** 的天数。判定器 fail 条件是 `age > sla`,
            # 故 fail 始于 age = sla+1 → remaining = (sla + 1) - age。
            # (曾误用 `sla - age`, 那报的是"到 SLA 边界", 比真实 fail 日早 1 天;
            #  2026-09-21 回放实测校正, 使 expiry_date 名副其实。)
            remaining = (days + 1) - age
            if remaining <= horizon:
                out.append({
                    "surface": surface.get("id", "?"),
                    "sla_days": days,
                    "path": str(f.relative_to(root)),
                    "reviewed": reviewed.isoformat(),
                    "age_days": age,
                    "remaining_days": remaining,
                    "state": "expired" if remaining <= 0 else "imminent",
                })
    return out


def scan_x2_rules(root: Path = _ROOT, horizon: int = 7,
                   today: date | None = None) -> list[dict]:
    """X2 规则的 threshold_days: 对规则自身声明的 target 文件算剩余天数."""
    today = today or date.today()
    out: list[dict] = []
    for d in _load_docs(_x2_rules_path(root)):
        rules = d.get("rules") or d.get("checks") or []
        if not isinstance(rules, list):
            continue
        for r in rules:
            if not isinstance(r, dict):
                continue
            days = r.get("threshold_days")
            if not isinstance(days, int) or days <= 0:
                continue
            targets = r.get("targets") or r.get("target") or []
            if isinstance(targets, str):
                targets = [targets]
            for t in targets:
                if not isinstance(t, str) or "*" in t or "::" in t:
                    continue
                p = root / t.split("::")[0].strip()
                if not p.is_file():
                    continue
                reviewed = _frontmatter_date(p)
                if reviewed is None:
                    continue
                age = (today - reviewed).days
                if age < 0:
                    continue
                # 同上: fail 始于 age = threshold + 1
                remaining = (days + 1) - age
                if remaining <= horizon:
                    out.append({
                        "surface": f"x2:{r.get('id') or r.get('title', '?')}",
                        "sla_days": days,
                        "path": str(p.relative_to(root)),
                        "reviewed": reviewed.isoformat(),
                        "age_days": age,
                        "remaining_days": remaining,
                        "state": "expired" if remaining <= 0 else "imminent",
                    })
    return out


def cluster_by_expiry(items: list[dict], today: date | None = None) -> list[dict]:
    """按"越界日"聚类 —— 同一天集体越界是最危险形态 (昨天全绿, 今天全红)."""
    today = today or date.today()
    buckets: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        expiry = today + timedelta(days=it["remaining_days"])
        buckets[expiry.isoformat()].append(it)
    return [
        {"expiry_date": d, "count": len(v), "surfaces": sorted({x["surface"] for x in v}),
         "paths": [x["path"] for x in v][:5], "truncated": max(0, len(v) - 5)}
        for d, v in sorted(buckets.items())
    ]


def scan(horizon: int = 7, today: date | None = None) -> dict:
    today = today or date.today()
    docs = scan_doc_surfaces(horizon=horizon, today=today)
    x2 = scan_x2_rules(horizon=horizon, today=today)
    items = docs + x2
    expired = [i for i in items if i["state"] == "expired"]
    imminent = [i for i in items if i["state"] == "imminent"]
    clusters = [c for c in cluster_by_expiry(items, today=today) if c["count"] > 1]
    return {
        "today": today.isoformat(),
        "horizon_days": horizon,
        "sla_sources": [str(_doc_gov_path(_ROOT).relative_to(_ROOT)),
                        str(_x2_rules_path(_ROOT).relative_to(_ROOT))],
        "total": len(items),
        "expired": expired,
        "imminent": imminent,
        "mass_expiry_clusters": clusters,
        "summary": {
            "expired": len(expired),
            "imminent": len(imminent),
            "mass_clusters": len(clusters),
        },
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--horizon", type=int, default=7, help="前瞻窗口 (天, 默认 7)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", default=None,
                    help="回放用: 指定'今天'是哪一天 (YYYY-MM-DD), 用于验证预警是否本可提前发现")
    ap.add_argument("--strict", action="store_true",
                    help="存在已越界/即将越界 → exit 1 (cron 报警用)")
    args = ap.parse_args(argv)

    today = date.fromisoformat(args.today) if args.today else None
    r = scan(horizon=args.horizon, today=today)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        if not r["total"]:
            print(f"✅ 过期雷达: 未来 {r['horizon_days']}d 内无 SLA 越界 "
                  f"(阈值源: {', '.join(r['sla_sources'])})")
        else:
            print(f"⚠️  过期雷达 ({r['today']}, 前瞻 {r['horizon_days']}d): "
                  f"已越界 {r['summary']['expired']} / 即将 {r['summary']['imminent']}")
            for c in r["mass_expiry_clusters"]:
                print(f"   🔴 **集体越界** {c['expiry_date']}: {c['count']} 项 "
                      f"(surfaces: {', '.join(c['surfaces'])})")
                for p in c["paths"]:
                    print(f"      - {p}")
                if c["truncated"]:
                    print(f"      … 另 {c['truncated']} 项")
            for i in r["imminent"]:
                print(f"   ⏳ {i['remaining_days']}d 后越界: {i['path']} "
                      f"(SLA {i['sla_days']}d, last-reviewed={i['reviewed']})")
            for i in r["expired"][:10]:
                print(f"   ❌ 已越界 {-i['remaining_days']}d: {i['path']} "
                      f"(SLA {i['sla_days']}d, age={i['age_days']}d)")
            print("\n   含义: 这些日期一到, 对应 gate 会**当天对所有 PR** 变红。"
                  "\n   处置: 提前复审并更新 last-reviewed (真复审, 不是只改日期)。")

    if args.strict and r["total"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
