#!/usr/bin/env python3
"""任务投影头部 — 引用的脚本路径必须真实存在.

2026-09-19 实证:
  `.omo/tasks/*/bet-*.yaml` 头部写着
    `# 改台账后重跑: uv run --with pyyaml python bin/plan/bet-to-task.py --apply`
  而该路径在 main 上**从未存在** —— 生成器只以 `bin/_archive/bet-to-task.py`
  形式入库 (2026-09-18 归档)。照指示操作的人必然撞空。

这类"头部指针腐烂"是**静默漂移**: 生成器归档/搬家后, 已物化的产物头部仍指向
旧位置; 没人真去跑就没人发现。与 docs 链接检查同构, 但对象是**命令里的路径**。

判据 (2026-09-19 收紧): **只查命令调用上下文**。

初版把注释里的任何 `*.py` 都当路径, 实测误报 —— `.omo/tasks/done/TASK-117310A1.yaml`
的注释是**散文**, 描述项目内部模块 ("(omo/resident/cell.py)", "扫 cli.py 的命令
路由表"), 并非"运行这个脚本"的指令。

故现在要求: 该行**先出现解释器/命令关键字** (`python` / `python3` / `bash` / `sh` /
`uv run`), 才对其后的脚本路径断言存在 —— 这精确对应"照指示操作会撞空"的那一类。

用法:
    python3 bin/gac/check-task-projection-headers.py [--json]
退出码: 0 = 无悬挂引用; 1 = 存在悬挂引用
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
TASKS_DIR = _ROOT / ".omo" / "tasks"

# 只认"看起来是仓库内脚本"的路径, 避免把 URL / 外部命令误判
SCRIPT_RE = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.(?:py|sh))(?![\w/.-])")
COMMENT_RE = re.compile(r"^\s*#")
# 命令调用上下文的关键字 —— 只有先出现它, 才把同行的脚本路径当"指示"
CMD_KEYWORD_RE = re.compile(r"\b(?:python3?|bash|sh|uv\s+run)\b")


def _is_comment(line: str) -> bool:
    return bool(COMMENT_RE.match(line))


def scan(tasks_dir: Path | None = None, root: Path | None = None) -> dict:
    base = tasks_dir or TASKS_DIR
    repo = root or _ROOT
    dangling: list[dict] = []
    scanned = 0
    if not base.is_dir():
        return {"tasks_dir": str(base), "scanned": 0, "dangling": []}

    for path in sorted(base.rglob("*.yaml")):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        scanned += 1
        for lineno, line in enumerate(lines, 1):
            if not _is_comment(line):
                continue
            if not CMD_KEYWORD_RE.search(line):
                continue  # 散文提及, 非"运行此脚本"指示
            for m in SCRIPT_RE.finditer(line):
                ref = m.group(1)
                # 跳过明显是外部的 (绝对路径 / URL 片段)
                if ref.startswith(("/", "http")):
                    continue
                if not (repo / ref).exists():
                    dangling.append({
                        "file": str(path.relative_to(repo)),
                        "line": lineno,
                        "ref": ref,
                        "text": line.strip()[:110],
                    })
    return {"tasks_dir": str(base), "scanned": scanned, "dangling": dangling}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    result = scan()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))

    if result["dangling"]:
        if not args.json:
            print(f"🔴 任务投影头部引用了不存在的路径 "
                  f"({len(result['dangling'])} 处 / 扫描 {result['scanned']} 文件):",
                  file=sys.stderr)
            for d in result["dangling"]:
                print(f"   {d['file']}:{d['line']}  → {d['ref']}", file=sys.stderr)
            print("   处置: 指向真实存在的路径; 历史注记改为目录形式 (勿留悬空路径, "
                  "否则照指示操作者必撞空)", file=sys.stderr)
        return 1

    if not args.json:
        print(f"✅ 任务投影头部无悬挂引用 (扫描 {result['scanned']} 文件)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
