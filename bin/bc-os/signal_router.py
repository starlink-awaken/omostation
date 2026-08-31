#!/usr/bin/env python3
"""signal_router.py — BCOS 统一信号路由器 (W1-D2).

将 inbox_folder / apple_mail / github_push 的信号自动路由到对应业务场景:
  - 公文 (doc_* / *.md 格式公文) → document-review
  - 会议 (meeting_* / meeting notes) → meeting-supervision
  - 调研 (research_* / 含 query/调研关键词) → research-pipeline
  - 代码 (*.py / github_push) → engineering-delivery
  - 默认 → knowledge-ingest (沉淀型)

设计原则:
- 轻量规则路由 (无 LLM, 快速)
- 可扩展 (新增信号类型)
- 幂等 (重复信号不重复触发)
- 审计日志

长期维护: 信号路由规则在 .omo/_truth/registry/signal-router-rules.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "projects/omo/src"))

logger = logging.getLogger("signal-router")

# 信号路由规则 (keyword → scene_id)
ROUTING_RULES = [
    {"pattern": r"meeting|会议|决议|纪要", "scene": "meeting-supervision", "type": "meeting"},
    {"pattern": r"research|调研|query|研究", "scene": "research-pipeline", "type": "research"},
    {"pattern": r"review|公文|审查|格式", "scene": "document-review", "type": "doc"},
    {"pattern": r"\.py$|\.ts$|\.go$|pr_|merge", "scene": "engineering-delivery", "type": "code"},
    {"pattern": r"^meeting-", "scene": "meeting-supervision", "type": "meeting"},
    {"pattern": r"^research-", "scene": "research-pipeline", "type": "research"},
    {"pattern": r"^insight-|^note-", "scene": "knowledge-ingest", "type": "note"},
]

DEFAULT_SCENE = "knowledge-ingest"

SIGNALS_LOG = ROOT / ".omo" / "state" / "routed-signals.json"


def load_log() -> list:
    if SIGNALS_LOG.exists():
        return json.loads(SIGNALS_LOG.read_text())
    return []


def save_log(entries: list) -> None:
    SIGNALS_LOG.parent.mkdir(parents=True, exist_ok=True)
    SIGNALS_LOG.write_text(json.dumps(entries, indent=2, ensure_ascii=False))


def route_signal(file_path: Path, content: str) -> dict:
    """单条信号路由."""
    name = file_path.name
    text = f"{name}\n{content[:500]}"  # 文件名 + 前 500 字
    matched_scene = DEFAULT_SCENE
    matched_type = "unknown"
    for rule in ROUTING_RULES:
        if re.search(rule["pattern"], text, re.IGNORECASE):
            matched_scene = rule["scene"]
            matched_type = rule["type"]
            break
    signal_id = hashlib.sha1(f"{name}:{len(content)}".encode()).hexdigest()[:12]
    return {
        "signal_id": signal_id,
        "source_file": str(file_path),
        "source_scene": matched_scene,
        "signal_type": matched_type,
        "routed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "size_bytes": len(content),
    }


def scan_and_route(inbox: Path, dedup: bool = True) -> list:
    """扫描 inbox_folder 信号并路由. 幂等."""
    log = load_log()
    seen_ids = {e["signal_id"] for e in log} if dedup else set()
    routed = []
    for f in sorted(inbox.glob("*")):
        if not f.is_file() or f.name.startswith("."):
            continue
        content = f.read_text(encoding="utf-8", errors="ignore")
        if not content.strip():
            continue
        result = route_signal(f, content)
        if dedup and result["signal_id"] in seen_ids:
            continue
        routed.append(result)
        log.append(result)
    save_log(log)
    return routed


CALENDAR_RULES = [
    {"pattern": r"会议|会|meeting|calendar|日程", "scene": "meeting-supervision", "type": "meeting"},
    {"pattern": r"deadline|截止|due|提醒|期限", "scene": "task-reminder", "type": "task"},
    {"pattern": r"review|审查|审核|审批|公文|格式", "scene": "document-review", "type": "doc"},
    {"pattern": r"research|调研|研究|query|论文|paper", "scene": "research-pipeline", "type": "research"},
    {"pattern": r"code|代码|review|pr_|merge|提交|commit", "scene": "engineering-delivery", "type": "code"},
    {"pattern": r"project|项目|进度|里程碑|milestone", "scene": "project-supervision", "type": "project"},
    {"pattern": r"knowledge|知识|笔记|沉淀|整理", "scene": "knowledge-curation", "type": "knowledge"},
]


def route_calendar_event(title: str, description: str = "") -> dict:
    """Route a calendar event to appropriate scene."""
    text = f"{title}\n{description[:500]}"
    matched_scene = "knowledge-ingest"
    matched_type = "unknown"
    for rule in CALENDAR_RULES:
        if re.search(rule["pattern"], text, re.IGNORECASE):
            matched_scene = rule["scene"]
            matched_type = rule["type"]
            break
    return {
        "signal_id": f"cal-{hashlib.sha1(title.encode()).hexdigest()[:12]}",
        "source": "calendar",
        "source_scene": matched_scene,
        "signal_type": matched_type,
        "title": title,
        "routed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def scan_calendar_ics(ics_path: Path) -> list:
    """Scan .ics calendar file and route events."""
    if not ics_path.exists():
        return []
    content = ics_path.read_text(encoding="utf-8", errors="ignore")
    events = []
    current_event = {}
    for line in content.splitlines():
        line = line.strip()
        if line == "BEGIN:VEVENT":
            current_event = {}
        elif line == "END:VEVENT":
            if current_event:
                events.append(current_event)
            current_event = {}
        elif line.startswith("SUMMARY:"):
            current_event["title"] = line[8:]
        elif line.startswith("DESCRIPTION:"):
            current_event["description"] = line[12:]
    routed = []
    for event in events:
        result = route_calendar_event(
            event.get("title", ""),
            event.get("description", ""),
        )
        routed.append(result)
    return routed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inbox", default="~/Documents/@感知信号")
    parser.add_argument("--calendar", help="Path to .ics calendar file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    all_routed = []

    # Route inbox signals
    inbox = Path(args.inbox).expanduser()
    if inbox.exists():
        all_routed.extend(scan_and_route(inbox))

    # Route calendar events
    if args.calendar:
        ics_path = Path(args.calendar)
        all_routed.extend(scan_calendar_ics(ics_path))

    summary = {
        "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_routed": len(all_routed),
        "by_scene": {},
    }
    for r in all_routed:
        summary["by_scene"].setdefault(r["source_scene"], 0)
        summary["by_scene"][r["source_scene"]] += 1
    if args.json:
        print(json.dumps({"summary": summary, "routed": all_routed}, indent=2, ensure_ascii=False))
    else:
        print(f"路由 {len(all_routed)} 个信号:")
        for scene, n in summary["by_scene"].items():
            print(f"  → {scene}: {n}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(main())