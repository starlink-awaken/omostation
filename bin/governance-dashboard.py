#!/usr/bin/env python3
"""P86 R4: governance dashboard wrapper.

统一调用 P83-P85 治理工具, 输出一份治理健康仪表盘:
- governance-history insight (P83)
- drift-history insight (P83)
- x2 freshness check (P84)
- x2 rule lint (P85)
- adr coverage (P85)
- management cross-ref (P82+P83)
- mof m2 coverage (P84)

每个工具用 subprocess 调用, 失败继续 (dashboard 不阻塞).
输出: 单页 dashboard, 包含每个工具的关键指标.

使用:
  python3 bin/governance-dashboard.py
  python3 bin/governance-dashboard.py --json
  python3 bin/governance-dashboard.py --tools governance-history,adr-coverage  # 子集
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 工具注册表: (id, 描述, 默认参数列表)
TOOL_REGISTRY: list[tuple[str, str, str, list[str]]] = [
    # (id, 描述, bin_path, args)
    ("governance-history", "P83 governance 评分历史", "bin/governance-history-insight.py", []),
    ("drift-history", "P83 drift 漂移历史", "bin/drift-history-insight.py", []),
    ("x2-freshness", "P84 X2 freshness 11 规则", "bin/x2-freshness-check.py", []),
    ("x2-rule-lint", "P85 X2 rule schema lint", "bin/x2-rule-lint.py", []),
    ("x2-rule-add", "P87 X2 rule 交互式添加 (template 模式)", "bin/x2-rule-add.py", ["--template"]),
    ("adr-coverage", "P85 ADR 治理健康度", "bin/adr-coverage.py", []),
    ("mof-m2-coverage", "P84 M2 schema coverage 修正版", "bin/mof-m2-coverage.py", []),
    ("management-cross-ref", "P82+P83 management 跨文件引用", "bin/management-cross-ref-check.py", ["."]),
    ("god-module-roadmap", "P87 god-module refactor (示例文件)", "bin/god-module-roadmap.py",
     ["projects/omo/src/omo/omo_lint.py", "--top", "3"]),
    ("gov-trend-report", "P88 governance 趋势 (weekly 窗口)", "bin/gov-trend-report.py",
     ["--window", "weekly"]),
    ("rule-history-insight", "P89 X2 rule 状态洞察", "bin/rule-history-insight.py", []),
    ("adr-drift-check", "P89 ADR 引用 drift (信息性, 全量扫描)", "bin/adr-drift-check.py", []),
    ("adr-drift-classify", "P90 ADR drift 归类 (历史 vs 新增)", "bin/adr-drift-classify.py", []),
    ("gov-history-stats", "P91 gov history 深化 (30 天 + 类别趋势)", "bin/gov-history-stats.py",
     ["--days", "30"]),
    ("adr-trend-insight", "P92 ADR 趋势 (phase 分布 + 提交历史)", "bin/adr-trend-insight.py", []),
    ("adr-drift-auto-fix", "P93 ADR drift 自动归类 (TEMPLATE/SUBDIR/TYPO/REAL)", "bin/adr-drift-auto-fix.py", []),
    ("adr-drift-apply", "P94 ADR drift 应用 (touch SUBDIR_MISSING)", "bin/adr-drift-apply.py", []),
    ("god-module-13-list", "P94 god-module 13 error 清单 (24252L excess)", "bin/god-module-13-error-list.py", []),
    ("adr-typo-fix", "P95 ADR TYPO 字符级自动修复 (conservative)", "bin/adr-typo-fix.py", []),
    ("adr-typo-real-fix", "P96 ADR TYPO 真 Levenshtein 修复", "bin/adr-typo-real-fix.py", []),
    ("venv-yaml-check", "P96 venv 依赖一致性检查 (pyyaml 等)", "bin/venv-yaml-check.py", []),
]


def run_tool(workspace: Path, tool_id: str, bin_path: str, args: list[str]) -> dict:
    """运行单个工具, 返回结果摘要."""
    full_path = workspace / bin_path
    if not full_path.exists():
        return {
            "id": tool_id,
            "ok": False,
            "error": f"tool not found: {bin_path}",
        }
    try:
        result = subprocess.run(
            ["python3", str(full_path)] + args,
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "id": tool_id,
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout_lines": len(result.stdout.splitlines()),
            "stderr": result.stderr[:500] if result.stderr else "",
            # 截取 stdout 前 30 行作为预览
            "preview": "\n".join(result.stdout.splitlines()[:30]),
        }
    except subprocess.TimeoutExpired:
        return {"id": tool_id, "ok": False, "error": "timeout (60s)"}
    except Exception as e:
        return {"id": tool_id, "ok": False, "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="P86: governance dashboard")
    parser.add_argument("--root", default=".", help="workspace root")
    parser.add_argument("--tools", default=None,
                        help="逗号分隔的 tool id 子集 (默认全部)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    workspace = Path(args.root).resolve()
    if not (workspace / ".omo").exists():
        print(f"❌ {workspace} 不存在 .omo")
        return 1

    # 选择工具
    selected = set(args.tools.split(",")) if args.tools else None
    tools_to_run = [
        (tid, desc, bp, a)
        for tid, desc, bp, a in TOOL_REGISTRY
        if selected is None or tid in selected
    ]

    print("=" * 60)
    print("📊 P86 governance dashboard")
    print("=" * 60)
    print(f"🔧 工具数: {len(tools_to_run)}")
    print()

    results: list[dict] = []
    for tid, desc, bp, tool_args in tools_to_run:
        result = run_tool(workspace, tid, bp, tool_args)
        result["description"] = desc
        result["path"] = bp
        results.append(result)
        icon = "✅" if result["ok"] else "❌"
        print(f"  {icon} {tid:<25s} ({desc})")
        if not result["ok"]:
            err = result.get("error") or result.get("stderr", "")[:200]
            if err:
                print(f"      ⚠️  {err.splitlines()[0] if err else '(unknown)'}")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    # 汇总
    print()
    print("=" * 60)
    print("📈 治理工具健康度")
    print("=" * 60)
    ok = sum(1 for r in results if r["ok"])
    fail = len(results) - ok
    print(f"✅ OK: {ok} / {len(results)}")
    print(f"❌ FAIL: {fail}")
    if fail == 0:
        print("\n🎉 所有治理工具通过!")
        return 0
    print(f"\n⚠️  {fail} 个工具失败, 详情见上面 output")
    return 1


if __name__ == "__main__":
    sys.exit(main())
