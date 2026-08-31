#!/usr/bin/env python3
"""policy_radar.py — 政策法规雷达与每日晨报引擎（BET-Y1Q4-T7-03）.

巡检卫健委/医保局/工信部政策公告 + arXiv/bioRxiv 数字医疗文献，规则打标
（白名单关键词→业务标签）与价值评分，产物为当日晨报 JSON/Markdown。
网络异常走缓存快照降级（BET circuit_breaker 契约）。

研判 v1 为规则打标——比 LLM 稳，先满足"零噪音+≥90% 准确"；LLM 深度
研判留给数字大脑 P0 管线后续站。
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from datetime import UTC, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / ".omo/state/policy-radar"
SCHEMA = "bcos.policy-radar.v1"

# ── 信源白名单（无自媒体，BET non_goal）────────────────────────────
SOURCES = [
    {
        "id": "nhc",
        "kind": "policy",
        "name": "国家卫健委",
        "url": "http://www.nhc.gov.cn/wjw/pcrb/list.shtml",
        "lang": "zh",
    },
    {
        "id": "nhsa",
        "kind": "policy",
        "name": "国家医保局",
        "url": "https://www.nhsa.gov.cn/col/col7/index.html",
        "lang": "zh",
    },
    {
        "id": "miit",
        "kind": "policy",
        "name": "工信部",
        "url": "https://www.miit.gov.cn/jgsj/zwgk/index.html",
        "lang": "zh",
    },
    {
        "id": "arxiv-healph",
        "kind": "paper",
        "name": "arXiv heal-ph",
        "url": "http://export.arxiv.org/rss/heal-ph",
        "lang": "en",
    },
    {
        "id": "arxiv-cs-ai",
        "kind": "paper",
        "name": "arXiv cs.AI",
        "url": "http://export.arxiv.org/rss/cs.AI",
        "lang": "en",
    },
]

# ── 业务标签（done_when 契约：医疗大模型/数据要素互联互通等）────────
TAG_RULES = [
    (
        "医疗大模型",
        [
            "医疗大模型",
            "医学人工智能",
            "医疗AI",
            "医学大模型",
            "medical.*large.*model",
            "clinical.*LLM",
            "Med.?LLM",
            "biomedical.*LLM",
        ],
    ),
    (
        "数据要素互联互通",
        ["数据要素", "互联互通", "数据共享", "互认", "data.*interoperab", "interoperab", "FHIR", "health.*data.*exchange"],
    ),
    ("医保支付", ["医保支付", "支付范围", "报销", "医保目录", "DRG", "DIP", "reimburse", "insurance.*coverage"]),
    ("政务数字化", ["政务", "数字政府", "一网通办", "电子证照", "数字化改革", "e-?government", "digital.*governance"]),
    ("文献前沿", ["arxiv", "biorxiv", "preprint", "benchmark", "dataset", "survey", "综述"]),
]
GENERIC_POLICY = ("通知", "公告", "意见", "方案", "办法", "指南", "标准")

TITLE_PENALTY = re.compile(r"招标|采购|中标|招聘|会议报名|培训通知")


def _score_and_tag(title: str, kind: str) -> tuple[int, list[str]]:
    """标题级打分：标签命中 +1/词，政策文书词 +1，惩罚词 -2。"""
    tags: list[str] = []
    score = 0
    for tag, words in TAG_RULES:
        hits = sum(1 for w in words if re.search(w, title, re.IGNORECASE))
        if hits:
            tags.append(tag)
            score += hits
    if kind == "policy" and any(w in title for w in GENERIC_POLICY):
        score += 1
        if not tags:
            tags.append("其他政策")
    if TITLE_PENALTY.search(title):
        score -= 2
    return score, tags


def _extract_titles(html: str, kind: str, limit: int = 20) -> list[str]:
    """从 HTML/RSS 提取标题（li/a 标题 or RSS <title>）。"""
    titles: list[str] = []
    if kind == "paper":  # RSS
        titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", html, re.S)
        titles = titles[1:] if len(titles) > 1 else titles  # 去频道名
    else:  # 政策列表页: 常见 title="" 或 <a ...>文本</a>
        titles = re.findall(r'title="([^"]{6,80})"', html)
        if not titles:
            titles = re.findall(r"<a[^>]*>([^<]{8,60})</a>", html)
    seen: set[str] = set()
    out = []
    for t in titles:
        t = " ".join(str(t).split())
        # 频道级标题过滤（首跑实测：RSS 频道名混入条目）
        if not t or t in seen or re.search(r"updates on arxiv\.org|^arxiv\b", t, re.IGNORECASE):
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= limit:
            break
    return out


def _fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "omostation-policy-radar/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def collect(now: datetime | None = None) -> dict:
    """抓取→打标→评分→每源 top3（总量 ≤15）。失败源走缓存降级。"""
    now = now or datetime.now(UTC)
    cache_path = STATE_DIR / "cache.json"
    cached: dict = {}
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached = {}

    brief_items: list[dict] = []
    degraded_sources: list[str] = []
    fresh_snapshot: dict = {}
    for src in SOURCES:
        raw = None
        try:
            raw = _fetch(src["url"])
        except (urllib.error.URLError, TimeoutError, OSError):
            snap = cached.get("sources", {}).get(src["id"])
            if snap:
                degraded_sources.append(src["id"])
                items = snap.get("items", [])
            else:
                degraded_sources.append(src["id"])
                items = []
        else:
            items = []
            for title in _extract_titles(raw, src["kind"]):
                score, tags = _score_and_tag(title, src["kind"])
                if score > 0 and tags:  # 白名单外的零分不入报（零噪音）
                    items.append({"title": title, "score": score, "tags": tags})
            items.sort(key=lambda x: -x["score"])
            items = items[:3]
            fresh_snapshot[src["id"]] = {"items": items, "fetched_at": now.isoformat()}
        for it in items:
            brief_items.append({"source": src["name"], "source_id": src["id"], "kind": src["kind"], **it})

    brief_items.sort(key=lambda x: -x["score"])
    brief_items = brief_items[:15]

    result = {
        "schema": SCHEMA,
        "generated_at": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "degraded_sources": degraded_sources,
        "is_degraded": bool(degraded_sources),
        "items": brief_items,
    }
    if fresh_snapshot:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        merged = {**(cached.get("sources") or {}), **fresh_snapshot}
        cache_path.write_text(json.dumps({"sources": merged}, ensure_ascii=False, indent=1), encoding="utf-8")
    return result


def render_markdown(brief: dict) -> str:
    lines = [f"# 每日业务与技术早报 {brief['date']}", ""]
    if brief.get("is_degraded"):
        lines.append(f"> ⚠ 缓存快照降级版（源不可达：{', '.join(brief['degraded_sources'])}）")
        lines.append("")
    if not brief["items"]:
        lines.append("今日无高价值条目（白名单零命中）。")
        return "\n".join(lines)
    by_tag: dict[str, list[dict]] = {}
    for it in brief["items"]:
        for t in it["tags"]:
            by_tag.setdefault(t, []).append(it)
    for tag in sorted(by_tag):
        lines.append(f"## {tag}")
        for it in by_tag[tag][:4]:
            lines.append(f"- [{it['source']}] {it['title']}")
        lines.append("")
    return "\n".join(lines)


def generate(now: datetime | None = None) -> int:
    brief = collect(now)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    day = brief["date"].replace("-", "")
    (STATE_DIR / f"brief-{day}.json").write_text(json.dumps(brief, ensure_ascii=False, indent=1), encoding="utf-8")
    md = render_markdown(brief)
    (STATE_DIR / f"brief-{day}.md").write_text(md, encoding="utf-8")
    print(
        f"policy-radar: brief-{day} | {len(brief['items'])} items"
        f"{' | degraded: ' + ','.join(brief['degraded_sources']) if brief['is_degraded'] else ''}"
    )
    print(md[:400])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--generate-morning-brief", action="store_true")
    args = parser.parse_args(argv)
    if not args.generate_morning_brief:
        parser.print_help()
        return 2
    return generate()


if __name__ == "__main__":
    raise SystemExit(main())
