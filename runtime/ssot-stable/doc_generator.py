#!/usr/bin/env python3
"""Doc Generator — 公文模板生成.

Usage:
  python3 bin/ssot/doc-generator.py --template forward_notice --context '{"title":"转发通知"}'
  python3 bin/ssot/doc-generator.py --list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _llm_helper import llm_ask
from _shared import utc_now

DRAFTS_DIR = Path.home() / "Documents" / "@工作文档" / "卫健委" / "_drafts"
TEMPLATES = {
    "forward_notice": "转发上级通知",
    "data_collection": "数据收集表格",
    "summary_report": "汇总报告",
    "meeting_notice": "会议通知",
    "work_plan": "工作计划",
}


def generate_doc(template: str, context: dict) -> str:
    desc = TEMPLATES.get(template, template)
    # 2026-08-25 修复: 不给日期 LLM 会幻觉年份(实测产出"2024 年 X 月"),
    # 明示今天 + 要求未知留空 — 数据诚实红线。
    prompt = (
        f"你是卫健委公文写作助手。今天是 {utc_now()[:10]}。"
        f"根据以下信息生成{desc}草稿(Markdown格式,含标题/主送/正文/落款)。\n"
        f"日期不确定时用下划线留空待填, 禁止编造年份或数据:\n"
        f"{json.dumps(context, ensure_ascii=False)[:500]}"
    )
    # 失败重试一次(本地容量不足 409 时 LM Link 兜底也偶发超时, 单发失败实测存在)
    response = llm_ask(prompt, timeout=60.0) or llm_ask(prompt, timeout=60.0)
    return response or f"# {desc} (生成失败)"


def save_draft(template: str, content: str) -> Path:
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DRAFTS_DIR / f"{utc_now()[:10]}-{template}-draft.md"
    i = 1
    while path.exists():
        path = DRAFTS_DIR / f"{utc_now()[:10]}-{template}-draft-{i}.md"
        i += 1
    path.write_text(content, encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", choices=list(TEMPLATES.keys()))
    parser.add_argument("--context", type=str, default="{}")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    if args.list:
        [print(f"  {k}: {v}") for k, v in TEMPLATES.items()]
        return 0
    if not args.template:
        parser.error("--template required")
    content = generate_doc(args.template, json.loads(args.context or "{}"))
    path = save_draft(args.template, content)
    print(f"✅ 草稿: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
