#!/usr/bin/env python3
"""Tool Governance — 工具分级治理.

分级:
  P0 Core:      CI + 测试 + 监控 + 文档
  P1 Active:    CI + 测试
  P2 Available: 可用但未接入
  P3 Deprecated: 无调用/被替代 → 归档

用法:
    python3 tool-governance.py                  # 分级报告
    python3 tool-governance.py --json           # JSON
    python3 tool-governance.py --archive <name> # 归档指定工具
    python3 tool-governance.py --list-deprecated # 列出可归档工具
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ECOS_TOOLS = REPO / "projects/ecos/src/ecos/ssot/tools"
ECOS_ARCHIVE = ECOS_TOOLS / "_archive"
WORKFLOW = REPO / ".github/workflows/ecos-ci.yml"
CI_SURFACES = REPO / ".omo/_truth/registry/ci-surfaces.yaml"


def audit_tools() -> dict:
    """工具分级审计."""
    if not ECOS_TOOLS.exists():
        return {"error": "submodule not init"}

    ci_content = WORKFLOW.read_text() if WORKFLOW.exists() else ""

    tools = []
    for f in sorted(ECOS_TOOLS.glob("*.py")):
        name = f.stem
        if name.startswith("_"):
            continue
        in_ci = name in ci_content
        has_test = (REPO / "projects/ecos/tests" / f"test_{name}.py").exists()
        tools.append({
            "name": name,
            "in_ci": in_ci,
            "has_test": has_test,
        })

    p0 = [t for t in tools if t["in_ci"] and t["has_test"]]
    p1 = [t for t in tools if t["in_ci"] or t["has_test"]]
    p2 = [t for t in tools if not t["in_ci"] and not t["has_test"]]

    return {
        "total": len(tools),
        "p0_core": len(p0),
        "p1_active": len(p1),
        "p2_available": len(p2),
        "ci_coverage": f"{len([t for t in tools if t['in_ci']])}/{len(tools)}",
        "tools": tools,
    }


def list_deprecated(dry_run: bool = True) -> list[str]:
    """列出可归档的工具 (P2 且 90天无 CI 调用)."""
    result = audit_tools()
    if "error" in result:
        return []

    deprecated = []
    for t in result["tools"]:
        if not t["in_ci"] and not t["has_test"]:
            deprecated.append(t["name"])

    return deprecated


def archive_tool(name: str, dry_run: bool = False) -> dict:
    """归档工具: 移动文件 + 更新 CI + 更新 registry."""
    src = ECOS_TOOLS / f"{name}.py"
    if not src.exists():
        return {"ok": False, "error": f"Tool {name} not found"}

    dst = ECOS_ARCHIVE / f"{name}.py"

    actions = []
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "actions": [
                f"Move {src.relative_to(REPO)} → {dst.relative_to(REPO)}",
                f"Remove {name} from {WORKFLOW.relative_to(REPO)}",
                f"Update {CI_SURFACES.relative_to(REPO)}: status → archived",
            ],
        }

    # 1. 创建归档目录
    ECOS_ARCHIVE.mkdir(exist_ok=True)

    # 2. 移动文件
    import shutil
    shutil.move(str(src), str(dst))
    actions.append(f"Moved {src.relative_to(REPO)} → {dst.relative_to(REPO)}")

    # 3. 更新 CI workflow (移除引用)
    if WORKFLOW.exists():
        content = WORKFLOW.read_text()
        if name in content:
            # 移除包含工具名的行
            lines = content.splitlines()
            new_lines = []
            for line in lines:
                # 跳过工具调用行和注释行
                if line.strip().startswith(f"uv run python3 src/ecos/ssot/tools/{name}.py"):
                    continue
                if line.strip().startswith(f"uv run python3 src/ecos/ssot/tools/$tool") and name in line:
                    continue
                new_lines.append(line)
            WORKFLOW.write_text("\n".join(new_lines))
            actions.append(f"Removed {name} references from {WORKFLOW.relative_to(REPO)}")

    # 4. 更新 ci-surfaces.yaml
    if CI_SURFACES.exists():
        import yaml
        content = CI_SURFACES.read_text()
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                data = yaml.safe_load(content[end + 3:])
                if data and "surfaces" in data:
                    for surface in data["surfaces"]:
                        if surface.get("tool") == name:
                            surface["status"] = "archived"
                    # 写回
                    new_content = content[:end + 3] + "\n" + yaml.dump(data, default_flow_style=False, allow_unicode=True)
                    CI_SURFACES.write_text(new_content)
                    actions.append(f"Updated {CI_SURFACES.relative_to(REPO)}: status → archived")

    return {"ok": True, "archived": name, "actions": actions}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Tool Governance")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--archive", metavar="NAME", help="Archive a tool")
    parser.add_argument("--list-deprecated", action="store_true",
                        help="List deprecated tools eligible for archival")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen")
    args = parser.parse_args()

    if args.list_deprecated:
        deprecated = list_deprecated()
        print("Deprecated tools (eligible for archival):")
        for name in deprecated:
            print(f"  - {name}")
        return

    if args.archive:
        result = archive_tool(args.archive, dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif result.get("ok"):
            if result.get("dry_run"):
                print(f"Dry run: archiving {args.archive}")
            else:
                print(f"Archived: {args.archive}")
            for action in result.get("actions", []):
                print(f"  ✓ {action}")
        else:
            print(f"Error: {result.get('error')}", file=sys.stderr)
            sys.exit(1)
        return

    result = audit_tools()
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Tool Governance Report")
    print("=" * 56)
    print(f"  Total: {result['total']}")
    print(f"  P0 Core (CI+Test): {result['p0_core']}")
    print(f"  P1 Active (CI|Test): {result['p1_active']}")
    print(f"  P2 Available: {result['p2_available']}")
    print(f"  CI Coverage: {result['ci_coverage']}")


if __name__ == "__main__":
    sys.exit(main())
