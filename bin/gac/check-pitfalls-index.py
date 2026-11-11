#!/usr/bin/env python3
"""AGENTS.md §7 索引条首短语的字面可命中门禁 (CR-X2-PITFALLS-INDEX-INTEGRITY).

判一个方向: 索引里每个「…」短语必须能在 docs/pitfalls.md 逐字命中.
命中不了的短语 = agent 按它 rg 零结果, 会据此下「条目不存在」的错误结论.
反方向 (正文条目未被索引登记) 不判 —— 正文 append-only, 索引有意只挑高频.

warn 期恒 exit 0, ENFORCE_AFTER 之后由本脚本退出码转阻断 (不进 SOFT_CHECKS).
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ENFORCE_AFTER = datetime.date(2026, 12, 12)
PHRASE_RE = re.compile("「([^」]+)」")
SECTION_START = "## 7."
SECTION_END = "## 8."
BODY_ENTRY_RE = re.compile(r"^- \*\*")


def resolve_workspace(arg: str | None) -> Path:
    if arg:
        return Path(arg).resolve()
    return Path(__file__).resolve().parents[2]


def _is_separator(line: str) -> bool:
    body = line.strip().strip("|")
    return bool(body) and set(body.replace("|", "").replace(" ", "")) <= set("-:")


def extract_index_phrases(agents_text: str) -> list[dict]:
    """§7 表行里的「…」短语, 带行号. 只扫表行, 正文散文里的引号不算登记."""
    lines = agents_text.splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(SECTION_START)), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith(SECTION_END)), len(lines))
    out = []
    for idx in range(start, end):
        line = lines[idx]
        if not line.strip().startswith("|") or _is_separator(line):
            continue
        for m in PHRASE_RE.finditer(line):
            out.append({"line": idx + 1, "phrase": m.group(1)})
    return out


def count_body_entries(body_text: str) -> int:
    return sum(1 for l in body_text.splitlines() if BODY_ENTRY_RE.match(l))


def check(workspace: Path) -> dict:
    agents_path = workspace / "AGENTS.md"
    body_path = workspace / "docs" / "pitfalls.md"
    result = {
        "ok": False,
        "total": 0,
        "dead": 0,
        "hittable": 0,
        "dead_list": [],
        "body_entries": 0,
        "error": None,
    }
    missing = [str(p.relative_to(workspace)) for p in (agents_path, body_path) if not p.is_file()]
    if missing:
        result["error"] = "missing_required_files:" + ",".join(missing)
        return result
    agents_text = agents_path.read_text(encoding="utf-8", errors="replace")
    body_text = body_path.read_text(encoding="utf-8", errors="replace")
    phrases = extract_index_phrases(agents_text)
    if not phrases:
        result["error"] = "index_section_not_found: AGENTS.md §7 无表行短语 (仪器没跑, 不是零死链)"
        return result
    dead = [p for p in phrases if p["phrase"] not in body_text]
    result.update(
        total=len(phrases),
        dead=len(dead),
        hittable=len(phrases) - len(dead),
        dead_list=dead,
        body_entries=count_body_entries(body_text),
    )
    result["ok"] = not dead
    return result


def should_block(result: dict, today: datetime.date, strict: bool) -> bool:
    if result["error"]:
        return True
    if strict:
        return result["dead"] > 0
    return result["dead"] > 0 and today >= ENFORCE_AFTER


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--workspace", help="仓根 (默认按 __file__ 上溯)")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--strict", action="store_true", help="不等限期, 立即按死链数判红")
    ap.add_argument("--enforce-after", default=str(ENFORCE_AFTER))
    args = ap.parse_args(argv)

    workspace = resolve_workspace(args.workspace)
    result = check(workspace)
    today = datetime.date.today()
    blocking = should_block(result, today, args.strict)

    if args.as_json:
        payload = dict(result)
        payload.update(
            checked_at=today.isoformat(),
            enforce_after=args.enforce_after,
            blocking=blocking,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if result["error"]:
            print(f"[FAIL] {result['error']}")
        else:
            print(
                f"[{'OK' if result['ok'] else 'WARN'}] §7 登记短语={result['total']} "
                f"字面可命中={result['hittable']} 不可命中={result['dead']} "
                f"(正文条目={result['body_entries']})"
            )
            for item in result["dead_list"]:
                print(f"  DEAD L{item['line']}: {item['phrase']}")
            print(
                f"enforce_after={args.enforce_after} blocking={blocking}"
                f"{' (warn 期: 不阻断)' if result['dead'] and not blocking else ''}"
            )
    return 1 if blocking else 0


if __name__ == "__main__":
    sys.exit(main())
