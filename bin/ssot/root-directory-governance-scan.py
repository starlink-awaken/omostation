#!/usr/bin/env python3
"""Root directory governance surface scan.

Scans workspace root directories and emits:
- directory scale (file count, subdir count, total bytes)
- governance entry coverage (README/AGENTS)
- maintenance suggestions for governance onboarding

Usage:
  python3 bin/ssot/root-directory-governance-scan.py
  python3 bin/ssot/root-directory-governance-scan.py --json
  python3 bin/ssot/root-directory-governance-scan.py --output docs/operations/root-directory-governance-scan.md
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess


README_NAMES = {
    "readme.md",
    "README.md",
    "Readme.md",
}


def is_tracked_dir(path: Path) -> bool:
    rel = str(path)
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", rel],
        check=False,
        cwd=str(path.parent),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def is_submodule(path: Path) -> bool:
    gitdir = path / ".git"
    return gitdir.exists()


def count_entries(path: Path) -> tuple[int, int, int]:
    file_count = 0
    dir_count = 0
    byte_count = 0
    for _, dirs, files in os.walk(path):
        dir_count += len(dirs)
        file_count += len(files)
        for name in files:
            fp = Path(_, name)
            try:
                byte_count += fp.stat().st_size
            except FileNotFoundError:
                pass
    return file_count, dir_count, byte_count


def scan_root(root: Path, include_untracked: bool = False) -> list[dict[str, object]]:
    rows = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.name in {".git", ".gitmodules"}:
            continue
        if not entry.is_dir():
            continue

        is_tracked = is_tracked_dir(entry)
        if not is_tracked and not include_untracked:
            continue

        file_count, dir_count, byte_count = count_entries(entry)
        has_readme = any((entry / n).exists() for n in README_NAMES)
        has_agents = (entry / "AGENTS.md").exists()
        rows.append(
            {
                "name": entry.name,
                "path": str(entry.relative_to(root)),
                "files": file_count,
                "dirs": dir_count,
                "bytes": byte_count,
                "kb": round(byte_count / 1024, 2),
                "has_readme": has_readme,
                "has_agents": has_agents,
                "is_tracked": is_tracked,
                "is_submodule": is_submodule(entry),
            }
        )
    return rows


def rank_and_tag(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    for row in rows:
        file_count = int(row["files"])
        kb = float(row["kb"])
        has_readme = bool(row["has_readme"])
        has_agents = bool(row["has_agents"])

        needs_governance = not (has_readme and has_agents)
        must_action = False
        should_action = False

        if file_count >= 100 and needs_governance:
            must_action = True
        elif not has_readme or not has_agents:
            should_action = True

        if kb >= 1024 and not has_agents:
            must_action = True

        if must_action:
            level = "must"
        elif should_action:
            level = "should"
        elif kb >= 500 and not (has_readme and has_agents):
            level = "should"
        else:
            level = "ok"

        row.update(
            {
                "needs_governance": needs_governance,
                "priority": level,
            }
        )
    return sorted(rows, key=lambda x: (int(x["files"]), float(x["kb"])), reverse=True)


def render_markdown(rows: list[dict[str, object]], generated_at: str) -> str:
    total = len(rows)
    must_cnt = sum(1 for row in rows if row["priority"] == "must")
    should_cnt = sum(1 for row in rows if row["priority"] == "should")

    lines = [
        "# 主仓目录治理表面扫描",
        "",
        f"- 生成时间: {generated_at}",
        f"- 目录总数: {total}",
        f"- 必做治理项: {must_cnt}",
        f"- 建议治理项: {should_cnt}",
        "",
        "## 一、目录级体检",
        "| 目录 | 文件数 | 子目录数 | 大小(KB) | AGENTS.md | README | tracked | submodule | 优先级 |",
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {path} | {files} | {dirs} | {kb:.2f} | {agents} | {readme} | {tracked} | {submodule} | {priority} |".format(
                path=row["path"],
                files=row["files"],
                dirs=row["dirs"],
                kb=float(row["kb"]),
                agents="✅" if row["has_agents"] else "❌",
                readme="✅" if row["has_readme"] else "❌",
                tracked="✅" if row["is_tracked"] else "❌",
                submodule="✅" if row["is_submodule"] else "-",
                priority=row["priority"],
            )
        )

    must_items = [r for r in rows if r["priority"] == "must"]
    should_items = [r for r in rows if r["priority"] == "should"]

    lines += ["", "## 二、治理优先级", ""]
    if must_items:
        lines.append("### 1) 必做（高优先）")
        for item in must_items:
            miss = []
            if not item["has_agents"]:
                miss.append("AGENTS.md")
            if not item["has_readme"]:
                miss.append("README")
            lines.append(
                f"- `{item['path']}`: 文件{item['files']}，缺失 {'/'.join(miss) if miss else '治理入口'}，建议先补齐目录治理边界。"
            )
    else:
        lines.append("### 1) 必做（高优先）")
        lines.append("- 当前无必做项。")

    if should_items:
        lines.append("")
        lines.append("### 2) 建议（中优先）")
        for item in should_items:
            miss = []
            if not item["has_agents"]:
                miss.append("AGENTS.md")
            if not item["has_readme"]:
                miss.append("README")
            lines.append(
                f"- `{item['path']}`: 文件{item['files']}，缺失 {'/'.join(miss) if miss else '治理入口'}。"
            )
    else:
        lines.append("")
        lines.append("### 2) 建议（中优先）")
        lines.append("- 当前无建议项。")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=None, help="Workspace 根目录")
    p.add_argument("--include-untracked", action="store_true", help="包含未入库目录")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--output", default="", help="输出 markdown 文件")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root or ".").resolve()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=str(root), text=True).strip())

    rows = rank_and_tag(scan_root(root, include_untracked=args.include_untracked))
    generated_at = datetime.now(timezone.utc).isoformat()

    if args.json:
        payload = {
            "generated_at": generated_at,
            "rows": rows,
            "stats": {
                "total_dirs": len(rows),
                "must": sum(1 for r in rows if r["priority"] == "must"),
                "should": sum(1 for r in rows if r["priority"] == "should"),
                "ok": sum(1 for r in rows if r["priority"] == "ok"),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    text = render_markdown(rows, generated_at)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        return

    print(text)


if __name__ == "__main__":
    main()
