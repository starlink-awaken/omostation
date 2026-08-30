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
import fnmatch
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import yaml

POLICY_RELATIVE_PATH = Path("docs/operations/root-directory-governance-policy.yaml")
README_NAMES = {
    "readme.md",
    "README.md",
    "Readme.md",
}


def load_policy(root: Path) -> dict[str, object]:
    policy_path = root / POLICY_RELATIVE_PATH
    if not policy_path.is_file():
        return {}
    try:
        text = policy_path.read_text(encoding="utf-8")
        # staleness 管线盖 frontmatter 后 safe_load 只解析首文档 (last-reviewed),
        # 正文 allowed_ignored_dirs 丢失 → 所有 ignored 目录误判违规 (CI .venv 实锤)
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                text = text[end + 4:]
        payload = yaml.safe_load(text) or {}
    except (OSError, yaml.YAMLError):
        return {}
    return payload if isinstance(payload, dict) else {}


def is_ignored_dir(path: Path) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", f"{path.name}/"],
        check=False,
        cwd=str(path.parent),
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def allowed_ignored_dir(name: str, policy: dict[str, object]) -> bool:
    allowed = policy.get("allowed_ignored_dirs", [])
    if not isinstance(allowed, list):
        return False
    return any(fnmatch.fnmatch(name, str(pattern)) for pattern in allowed)


def is_active_worktree(entry: Path) -> bool:
    """Return True only for a valid linked Git worktree directory."""
    git_marker = entry / ".git"
    if not git_marker.is_file():
        return False
    try:
        marker = git_marker.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    if not marker.startswith("gitdir:"):
        return False
    gitdir = Path(marker.split(":", 1)[1].strip())
    if not gitdir.is_absolute():
        gitdir = (entry / gitdir).resolve()
    return gitdir.is_dir()


def local_surface_policy(name: str, policy: dict[str, object]) -> dict[str, object] | None:
    surfaces = policy.get("local_surfaces", {})
    if not isinstance(surfaces, dict):
        return None
    value = surfaces.get(name)
    return value if isinstance(value, dict) else None


def governance_violation(row: dict[str, object]) -> bool:
    if bool(row["is_tracked"]):
        return False
    if bool(row.get("is_active_worktree")):
        return False
    if not bool(row["is_ignored"]):
        return True
    return not bool(row["policy_allowed"])

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


def count_entries(path: Path, max_depth: int = 3) -> tuple[int, int, int]:
    file_count = 0
    dir_count = 0
    byte_count = 0
    root_depth = len(path.parts)
    for root, dirs, files in os.walk(path):
        cur_depth = len(Path(root).parts) - root_depth
        if cur_depth >= max_depth:
            dirs.clear()
        dir_count += len(dirs)
        file_count += len(files)
        for name in files:
            fp = Path(root, name)
            try:
                byte_count += fp.stat().st_size
            except (OSError, FileNotFoundError):
                pass
    return file_count, dir_count, byte_count


def scan_root(
    root: Path,
    include_untracked: bool = True,
    policy: dict[str, object] | None = None,
) -> list[dict[str, object]]:
    policy = policy or load_policy(root)
    rows = []
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if entry.name in {".git", ".gitmodules"}:
            continue
        if not entry.is_dir():
            continue

        tracked = is_tracked_dir(entry)
        ignored = is_ignored_dir(entry)
        active_worktree = is_active_worktree(entry)
        surface_policy = local_surface_policy(entry.name, policy)
        if not include_untracked and not tracked:
            continue

        file_count, dir_count, byte_count = count_entries(entry)
        has_readme = any((entry / n).exists() for n in README_NAMES)
        has_agents = (entry / "AGENTS.md").exists()
        row = {
            "name": entry.name,
            "path": str(entry.relative_to(root)),
            "files": file_count,
            "dirs": dir_count,
            "bytes": byte_count,
            "kb": round(byte_count / 1024, 2),
            "has_readme": has_readme,
            "has_agents": has_agents,
            "is_tracked": tracked,
            "is_ignored": ignored,
            "is_active_worktree": active_worktree,
            "policy_allowed": allowed_ignored_dir(entry.name, policy)
            or surface_policy is not None,
            "surface_policy": surface_policy or {},
            "is_submodule": is_submodule(entry),
        }
        row["violation"] = governance_violation(row)
        if active_worktree:
            row["disposition"] = "active-worktree"
        elif tracked:
            row["disposition"] = "tracked"
        elif ignored and row["policy_allowed"]:
            row["disposition"] = "allowed-ignored"
        elif ignored:
            row["disposition"] = "ignored-unregistered"
        else:
            row["disposition"] = "untracked"
        rows.append(row)
    return rows


def rank_and_tag(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    for row in rows:
        file_count = int(row["files"])
        kb = float(row["kb"])
        has_readme = bool(row["has_readme"])
        has_agents = bool(row["has_agents"])
        active_worktree = bool(row.get("is_active_worktree"))
        violation = bool(row.get("violation", governance_violation(row)))
        row["violation"] = violation

        needs_governance = not (has_readme and has_agents)
        must_action = violation
        should_action = False

        if active_worktree:
            needs_governance = False
            must_action = False
            should_action = False
        elif file_count >= 100 and needs_governance:
            must_action = True
        elif not has_readme or not has_agents:
            should_action = True

        if kb >= 1024 and not has_agents and not active_worktree:
            must_action = True

        if must_action:
            level = "must"
        elif should_action or kb >= 500 and not (has_readme and has_agents):
            level = "should"
        else:
            level = "ok"

        row.update(
            {
                "needs_governance": needs_governance,
                "priority": level,
            }
        )
    return sorted(rows, key=lambda x: (bool(x["violation"]), int(x["files"]), float(x["kb"])), reverse=True)


def render_markdown(rows: list[dict[str, object]], generated_at: str) -> str:
    total = len(rows)
    must_cnt = sum(1 for row in rows if row["priority"] == "must")
    should_cnt = sum(1 for row in rows if row["priority"] == "should")
    violation_cnt = sum(1 for row in rows if row["violation"])

    lines = [
        "# 主仓目录治理表面扫描",
        "",
        f"- 生成时间: {generated_at}",
        f"- 目录总数: {total}",
        f"- 必做治理项: {must_cnt}",
        f"- 建议治理项: {should_cnt}",
        f"- 目录卫生违规: {violation_cnt}",
        "",
        "## 一、目录级体检",
        "| 目录 | 文件数 | 子目录数 | 大小(KB) | AGENTS.md | README | tracked | ignored | policy | disposition | 优先级 |",
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {path} | {files} | {dirs} | {kb:.2f} | {agents} | {readme} | {tracked} | {ignored} | {policy} | {disposition} | {priority} |".format(
                path=row["path"],
                files=row["files"],
                dirs=row["dirs"],
                kb=float(row["kb"]),
                agents="yes" if row["has_agents"] else "no",
                readme="yes" if row["has_readme"] else "no",
                tracked="yes" if row["is_tracked"] else "no",
                ignored="yes" if row["is_ignored"] else "no",
                policy="yes" if row["policy_allowed"] else "no",
                disposition=row["disposition"],
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
            if item["violation"]:
                miss.append(f"目录卫生:{item['disposition']}")
            if not item["has_agents"]:
                miss.append("AGENTS.md")
            if not item["has_readme"]:
                miss.append("README")
            lines.append(
                f"- `{item['path']}`: 文件{item['files']}，问题 {'/'.join(miss) if miss else '治理入口'}。"
            )
    else:
        lines.append("### 1) 必做（高优先）")
        lines.append("- 当前无必做项。")

    lines.append("")
    lines.append("### 2) 建议（中优先）")
    if should_items:
        for item in should_items:
            miss = []
            if not item["has_agents"]:
                miss.append("AGENTS.md")
            if not item["has_readme"]:
                miss.append("README")
            lines.append(f"- `{item['path']}`: 文件{item['files']}，缺失 {'/'.join(miss) if miss else '治理入口'}。")
    else:
        lines.append("- 当前无建议项。")

    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=None, help="Workspace 根目录")
    p.add_argument("--include-untracked", action="store_true", help="兼容旧调用，默认已扫描未跟踪目录")
    p.add_argument("--tracked-only", action="store_true", help="仅扫描已跟踪目录（不建议用于门禁）")
    p.add_argument("--check", action="store_true", help="发现未登记根目录时返回非零")
    p.add_argument("--json", action="store_true", help="输出 JSON")
    p.add_argument("--output", default="", help="输出 markdown 文件")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root or ".").resolve()
    root = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=str(root), text=True).strip())

    policy = load_policy(root)
    rows = rank_and_tag(
        scan_root(root, include_untracked=not args.tracked_only, policy=policy)
    )
    generated_at = datetime.now(timezone.utc).isoformat()
    violations = [row for row in rows if row["violation"]]

    if args.json:
        payload = {
            "generated_at": generated_at,
            "policy": str(POLICY_RELATIVE_PATH),
            "rows": rows,
            "stats": {
                "total_dirs": len(rows),
                "tracked": sum(1 for r in rows if r["is_tracked"]),
                "ignored": sum(1 for r in rows if r["is_ignored"]),
                "untracked": sum(1 for r in rows if not r["is_tracked"]),
                "violations": len(violations),
                "must": sum(1 for r in rows if r["priority"] == "must"),
                "should": sum(1 for r in rows if r["priority"] == "should"),
                "ok": sum(1 for r in rows if r["priority"] == "ok"),
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        text = render_markdown(rows, generated_at)
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
        else:
            print(text)

    return 1 if args.check and violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
