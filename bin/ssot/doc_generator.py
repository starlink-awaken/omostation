#!/usr/bin/env python3
"""Doc Generator — 公文模板生成.

Usage:
  python3 bin/ssot/doc-generator.py --template forward_notice --context '{"title":"转发通知"}'
  python3 bin/ssot/doc-generator.py --list
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from _shared import utc_now
from _llm_helper import llm_ask

DRAFTS_DIR = Path.home() / "Documents" / "@工作文档" / "卫健委" / "_drafts"
TEMPLATES = {"forward_notice": "转发上级通知", "data_collection": "数据收集表格", "summary_report": "汇总报告", "meeting_notice": "会议通知", "work_plan": "工作计划"}


def generate_doc(template: str, context: dict) -> str:
    desc = TEMPLATES.get(template, template)
    response = llm_ask(f"你是卫健委公文写作助手。根据以下信息生成{desc}草稿(Markdown格式,含标题/主送/正文/落款):\n{json.dumps(context, ensure_ascii=False)[:500]}", timeout=60.0)
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
