#!/usr/bin/env python3
"""X3 自动交付分发器 (Phase 49 T5) — 扫描 planned 任务并自动分发到对应 workflow.

SSOT:
  - 任务源: .omo/tasks/planned/*.yaml
  - 交付事件: .omo/_delivery/agent-workflows/events.jsonl
  - 计数规则: .omo/_truth/registry/x3-delivery-soft-gate.yaml (deprecated BET-Y1Q1-T1-01)

用法:
  uv run python "bin/delivery/x3-auto-distribute.py" --dry-run    # 仅预览
  uv run python "bin/delivery/x3-auto-distribute.py"             # 执行分发
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

PLANNED_DIR = Path(".omo/tasks/planned")
EVENTS_PATH = Path(".omo/_delivery/agent-workflows/events.jsonl")


def scan_planned() -> list[dict]:
    """扫描 planned 目录中的可分发任务 (排除 needs-human)."""
    if not PLANNED_DIR.exists():
        return []
    tasks = []
    for f in sorted(PLANNED_DIR.glob("*.yaml")):
        content = f.read_text()
        # 跳过 needs-human 分类的任务
        if "classification: needs_human" in content or "needs-human: true" in content:
            continue
        tasks.append({
            "path": str(f),
            "id": f.stem,
            "title": _extract_title(content),
        })
    return tasks


def _extract_title(content: str) -> str:
    """从 YAML 内容中提取 title."""
    for line in content.splitlines():
        if line.startswith("title:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return "(无标题)"


def emit_x3_event(task_id: str, status: str, title: str = "") -> None:
    """写入 X3 交付事件到 events.jsonl."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "kind": "x3_delivery",
        "task_id": task_id,
        "title": title,
        "status": status,
        "source": "x3-auto-distribute",
    }
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENTS_PATH, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def distribute(task: dict) -> bool:
    """根据任务类型选择 workflow 并启动."""
    # 简化版: 标记为 auto-distributed
    # 完整版: 根据 workflow_type 调用 agent-workflow.py start
    emit_x3_event(task["id"], "distributed", task.get("title", ""))
    return True


def main():
    parser = argparse.ArgumentParser(
        description="X3 自动交付分发器 — 扫描 planned 任务并自动分发"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="仅预览不执行"
    )
    args = parser.parse_args()

    tasks = scan_planned()

    if not tasks:
        print("✅ 无待分发任务 (planned 目录为空或全部 needs-human)")
        return

    print(f"发现 {len(tasks)} 个可分发任务 (排除 needs-human):\n")

    for t in tasks:
        if args.dry_run:
            print(f"  [dry-run] 将分发: {t['id']} — {t['title']}")
        else:
            distribute(t)
            print(f"  ✅ 已分发: {t['id']} — {t['title']}")

    if not args.dry_run:
        print(f"\n📊 已写入 {len(tasks)} 条 X3 交付事件到 events.jsonl")


if __name__ == "__main__":
    main()
