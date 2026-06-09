#!/usr/bin/env python3
"""
eCOS v5 — 健康检查集成测试 (ecos-health-check)
=================================================
端到端验证全部 X1-X3 治理脚本，输出统一健康报告。

用法:
    python3 ecos-health-check.py [--json]

检查项:
    1. CLAUDE.md 保鲜 (X2)
    2. CARDS↔STATE 一致性 (X2)
    3. CARDS 价值归因 (X3)
    4. Vault 审计 (X1)
    5. Vault 价值归因 (X3)
    6. Kairon 治理 (X1+X2)
    7. Kairon 成本核算 (X3)
    8. 域系统价值归因 (X3)
    9. X 轴覆盖率 (综合)

退出码:
    0 = 全部健康
    1 = 存在告警
    2 = 脚本缺失
"""

import sys
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path


RUNTIME_DIR = Path(__file__).parent.parent  # @驾驶舱/_runtime/
L1_DIR = RUNTIME_DIR / "_l1"  # L1运行时脚本
X_DIR = RUNTIME_DIR / "_x"  # X轴治理脚本
ECOS_SCRIPTS = Path.home() / ".ecos" / "scripts"  # ~/.ecos/scripts/
DOCS = Path.home() / "Documents"
WORKSPACE = Path.home() / "Workspace"
CARDS_DB = WORKSPACE / "data" / "cards" / "cards.db"

CHECKS = [
    {
        "id": "claude-freshness",
        "name": "CLAUDE.md 保鲜",
        "dim": "X2",
        "cmd": [
            "python3",
            str(L1_DIR / "check-claude-freshness.py"),
            "--root",
            str(DOCS),
            "--max-age-days",
            "60",
        ],
    },
    {
        "id": "cards-state",
        "name": "CARDS↔STATE 一致性",
        "dim": "X2",
        "cmd": [
            "python3",
            str(ECOS_SCRIPTS / "check-cards-state-consistency.py"),
            "--db",
            str(CARDS_DB),
            "--vault",
            str(DOCS),
        ],
        "requires": [CARDS_DB],
    },
    {
        "id": "cards-value",
        "name": "CARDS 价值归因",
        "dim": "X3",
        "cmd": [
            "python3",
            str(ECOS_SCRIPTS / "cards-value-attribution.py"),
            "--db",
            str(CARDS_DB),
        ],
        "requires": [CARDS_DB],
    },
    {
        "id": "vault-audit",
        "name": "Vault 审计",
        "dim": "X1",
        "cmd": [
            "python3",
            str(L1_DIR / "check-vault-audit.py"),
            "--vault",
            str(DOCS),
            "--since",
            "7 days ago",
        ],
    },
    {
        "id": "vault-value",
        "name": "Vault 价值归因",
        "dim": "X3",
        "cmd": [
            "python3",
            str(X_DIR / "vault-value-attribution.py"),
            "--vault",
            str(DOCS),
        ],
    },
    {
        "id": "kairon-gov",
        "name": "Kairon 治理检查",
        "dim": "X1+X2",
        "cmd": [
            "python3",
            str(ECOS_SCRIPTS / "check-kairon-governance.py"),
            "--workspace",
            str(WORKSPACE),
        ],
        "requires": [WORKSPACE / "projects" / "kairon"],
    },
    {
        "id": "kairon-cost",
        "name": "Kairon 成本核算",
        "dim": "X3",
        "cmd": [
            "python3",
            str(ECOS_SCRIPTS / "kairon-cost-attribution.py"),
            "--workspace",
            str(WORKSPACE),
        ],
        "requires": [WORKSPACE / "projects" / "kairon"],
    },
    {
        "id": "domain-value",
        "name": "域系统价值归因",
        "dim": "X3",
        "cmd": [
            "python3",
            str(X_DIR / "domain-value-attribution.py"),
            "--vault",
            str(DOCS),
        ],
    },
    {
        "id": "coverage",
        "name": "X 轴覆盖率",
        "dim": "综合",
        "cmd": ["python3", str(X_DIR / "x3-coverage-report.py")],
    },
]


def run_check(check: dict) -> dict:
    """运行单个检查"""
    # 检查依赖
    for req in check.get("requires", []):
        if not Path(req).exists():
            return {
                "id": check["id"],
                "name": check["name"],
                "dim": check["dim"],
                "pass": None,
                "status": "skipped",
                "reason": f"依赖缺失: {req}",
                "duration_ms": 0,
            }

    # 检查脚本存在
    cmd = check["cmd"]
    if not Path(cmd[1]).exists():
        return {
            "id": check["id"],
            "name": check["name"],
            "dim": check["dim"],
            "pass": None,
            "status": "missing",
            "reason": f"脚本缺失: {cmd[1]}",
            "duration_ms": 0,
        }

    start = datetime.now()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        duration = (datetime.now() - start).total_seconds() * 1000
        passed = result.returncode == 0

        return {
            "id": check["id"],
            "name": check["name"],
            "dim": check["dim"],
            "pass": passed,
            "status": "pass" if passed else "fail",
            "reason": ""
            if passed
            else (result.stderr.strip() or result.stdout.strip())[:200],
            "duration_ms": round(duration, 1),
        }
    except subprocess.TimeoutExpired:
        return {
            "id": check["id"],
            "name": check["name"],
            "dim": check["dim"],
            "pass": False,
            "status": "timeout",
            "reason": "30s 超时",
            "duration_ms": 30000,
        }
    except Exception as e:
        return {
            "id": check["id"],
            "name": check["name"],
            "dim": check["dim"],
            "pass": False,
            "status": "error",
            "reason": str(e)[:200],
            "duration_ms": 0,
        }


def format_report(results: list[dict]) -> str:
    """格式化健康报告"""
    total = len(results)
    passed = sum(1 for r in results if r["pass"] is True)
    failed = sum(1 for r in results if r["pass"] is False)
    skipped = sum(1 for r in results if r["pass"] is None)

    lines = []
    lines.append("=" * 64)
    lines.append("  eCOS v5 — 治理健康检查 (X1-X3 集成测试)")
    lines.append("=" * 64)
    lines.append(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(
        f"  检查: {total} 项  |  通过: {passed}  |  失败: {failed}  |  跳过: {skipped}"
    )
    lines.append("")

    for r in results:
        icon = {
            "pass": "✅",
            "fail": "❌",
            "skipped": "⏭️",
            "missing": "❓",
            "timeout": "⏰",
            "error": "💥",
        }
        dim_tag = f"[{r['dim']}]"
        lines.append(
            f"  {icon.get(r['status'], '?')} {dim_tag:6s} {r['name']:20s}  "
            f"{r['duration_ms']:6.0f}ms"
        )

        if r["reason"] and r["status"] != "pass":
            lines.append(f"       → {r['reason']}")

    lines.append("")
    lines.append("  ── 按维度汇总 ──")

    by_dim = {}
    for r in results:
        for dim in r["dim"].split("+"):
            dim = dim.strip()
            if dim not in by_dim:
                by_dim[dim] = {"total": 0, "pass": 0}
            by_dim[dim]["total"] += 1
            if r["pass"] is True:
                by_dim[dim]["pass"] += 1

    for dim in ["X1", "X2", "X3", "综合"]:
        if dim in by_dim:
            d = by_dim[dim]
            bar = "█" * d["pass"] + "░" * (d["total"] - d["pass"])
            lines.append(f"  {dim:4s}  [{bar}]  {d['pass']}/{d['total']}")

    lines.append("")
    overall = "✅ 全部健康" if failed == 0 else f"⚠️  {failed} 项失败"
    lines.append(f"  综合判定: {overall}")
    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 健康检查集成测试")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--skip", nargs="*", help="跳过的检查 ID")
    args = parser.parse_args()

    skip_ids = set(args.skip or [])
    results = []

    for check in CHECKS:
        if check["id"] in skip_ids:
            results.append(
                {
                    "id": check["id"],
                    "name": check["name"],
                    "dim": check["dim"],
                    "pass": None,
                    "status": "skipped",
                    "reason": "手动跳过",
                    "duration_ms": 0,
                }
            )
            continue
        results.append(run_check(check))

    if args.json:
        print(
            json.dumps(
                {
                    "generated_at": datetime.now().isoformat(),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(format_report(results))

    failed = sum(1 for r in results if r["pass"] is False)
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
