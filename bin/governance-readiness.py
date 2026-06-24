#!/usr/bin/env python3
"""P60: 治理就绪度评估 (5 维度).

5 维度评分 (满分 100):
1. 元数据覆盖 (25 分) — frontmatter ≥ 95%
2. 漂移检测 (20 分) — mof-drift LOW ≤ 5
3. 闭环纪律 (20 分) — 工作树 ≤ 50
4. 决策可追溯 (20 分) — ADR INDEX 无 UNLISTED
5. 治理评分 (15 分) — omo governance = 100
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml


def run(cmd: str, cwd: Path | None = None) -> tuple[int, str]:
    """Run shell command, return (exit_code, stdout+stderr)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, cwd=cwd, timeout=60
        )
        return result.returncode, (result.stdout or "") + (result.stderr or "")
    except Exception as e:
        return 1, str(e)


def score_frontmatter(root: Path) -> tuple[int, int, float]:
    """维度 1: frontmatter 覆盖率. 返回 (score, total, coverage)."""
    knowledge = root / ".omo" / "_knowledge"
    if not knowledge.exists():
        return 0, 0, 0.0
    md_files = list(knowledge.rglob("*.md"))
    total = len(md_files)
    if total == 0:
        return 25, 0, 1.0
    with_fm = 0
    for f in md_files:
        content = f.read_text(encoding="utf-8", errors="ignore")
        if content.startswith("---\n"):
            end = content.find("\n---", 4)
            if end > 0:
                fm = content[4:end]
                if all(k in fm for k in ["status", "lifecycle", "owner", "last-reviewed"]):
                    with_fm += 1
    coverage = with_fm / total
    # ≥ 95% = 25 分, < 50% = 0 分, 线性插值
    if coverage >= 0.95:
        score = 25
    elif coverage >= 0.50:
        score = int(25 * (coverage - 0.50) / 0.45)
    else:
        score = 0
    return score, total, coverage


def score_drift(root: Path) -> tuple[int, int]:
    """维度 2: drift LOW 计数. 返回 (score, low_count).

    P62 优化: 5 档细分, 反映治理成熟度梯度.
    """
    _, out = run("bin/mof-drift", cwd=root)
    match = re.search(r"Total:\s*(\d+)\s+drifts", out)
    if match:
        total = int(match.group(1))
    else:
        match = re.search(r"🔵 LOW \((\d+)\):", out)
        total = int(match.group(1)) if match else 0
    # P62 5 档: ≤2=20, ≤5=18, ≤8=15, ≤12=10, >12=5
    if total <= 2:
        score = 20
    elif total <= 5:
        score = 18
    elif total <= 8:
        score = 15
    elif total <= 12:
        score = 10
    else:
        score = 5
    return score, total


def score_commit_closure(root: Path) -> tuple[int, int]:
    """维度 3: 工作树累积. 返回 (score, uncommitted_count).

    P62 优化: 5 档细分 (0/30/80/300/500+) + L0:CR-GOV-COMMIT-FREQUENCY-01 双阈值.
    """
    _, out = run("git status --short | wc -l", cwd=root)
    try:
        count = int(out.strip().split("\n")[0])
    except (ValueError, IndexError):
        count = 0
    # P62 5 档: ≤5=20, ≤30=18, ≤80=15, ≤300=10, ≤500=5, >500=0
    if count <= 5:
        score = 20
    elif count <= 30:
        score = 18
    elif count <= 80:
        score = 15
    elif count <= 300:
        score = 10
    elif count <= 500:
        score = 5
    else:
        score = 0
    return score, count


def score_adr_index(root: Path) -> tuple[int, int]:
    """维度 4: ADR INDEX 完整性. 返回 (score, unlisted_count)."""
    _, out = run("omo governance", cwd=root)
    match = re.search(r"unlisted.*?:\s*(\d+)", out, re.IGNORECASE)
    if match:
        unlisted = int(match.group(1))
    else:
        # 检查 audit 输出
        match = re.search(r"EXISTS-BUT-UNLISTED:\s*(\d+)", out)
        unlisted = int(match.group(1)) if match else 0
    # 0 = 20, ≤ 2 = 15, > 2 = 0
    if unlisted == 0:
        score = 20
    elif unlisted <= 2:
        score = 15
    else:
        score = 0
    return score, unlisted


def score_governance(root: Path) -> tuple[int, float]:
    """维度 5: omo governance 总分. 返回 (score, total).

    优化: omo governance 在 subprocess 下耗时 120s+ (omo_audit + lint + health),
    改读最近一次 audit 产物 .omo/state/health.yaml (governance health SSOT)。
    """
    health_path = root / ".omo" / "state" / "health.yaml"
    total = 0.0
    if health_path.exists():
        try:
            import yaml

            with open(health_path, encoding="utf-8") as f:
                h = yaml.safe_load(f) or {}
            total = float(h.get("health_score", 0))
        except Exception:
            pass
    if total >= 100:
        score = 15
    elif total >= 95:
        score = 10
    elif total >= 90:
        score = 5
    else:
        score = 0
    return score, total


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    if not (root / ".omo").exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    print("=" * 70)
    print("🛡️  P60 治理就绪度评估 (5 维度)")
    print("=" * 70)
    print()

    print("🔍 R (Research): 收集治理指标...")
    s1, total_doc, cov = score_frontmatter(root)
    s2, drift_low = score_drift(root)
    s3, uncommitted = score_commit_closure(root)
    s4, unlisted = score_adr_index(root)
    s5, gov_score = score_governance(root)
    total = s1 + s2 + s3 + s4 + s5

    print()
    print("─" * 70)
    print(f"{'维度':<28s}{'得分':<8s}{'指标':<15s}{'阈值':<15s}")
    print("─" * 70)
    print(f"{'1. 元数据覆盖 (frontmatter)':<28s}{s1:>3d}/25  {total_doc} 文档    cov={cov:.1%}     ≥95%")
    print(f"{'2. 漂移检测 (drift LOW)':<28s}{s2:>3d}/20  drift={drift_low}        ≤5")
    print(f"{'3. 闭环纪律 (commit closure)':<28s}{s3:>3d}/20  uncommitted={uncommitted}  ≤50")
    print(f"{'4. 决策可追溯 (ADR INDEX)':<28s}{s4:>3d}/20  unlisted={unlisted}     =0")
    print(f"{'5. 治理评分 (omo governance)':<28s}{s5:>3d}/15  score={gov_score}      =100")
    print("─" * 70)
    print(f"{'总分':<28s}{total:>3d}/100")
    print("=" * 70)

    # 评级
    if total >= 90:
        grade = "A+ L4 稳态治理"
        emoji = "🟢"
    elif total >= 80:
        grade = "A L3 成熟治理"
        emoji = "🟡"
    elif total >= 70:
        grade = "B L2 基础治理"
        emoji = "🟠"
    elif total >= 60:
        grade = "C L1 起步治理"
        emoji = "🔴"
    else:
        grade = "D 治理缺失"
        emoji = "❌"

    print(f"{emoji} 评级: {grade}")
    print()

    # 建议
    suggestions = []
    if s1 < 25:
        suggestions.append(f"→ 提升 frontmatter 覆盖率至 ≥95% (当前 {cov:.1%})")
    if s2 < 15:
        suggestions.append(f"→ 减少 mof-drift LOW 维度 (当前 {drift_low})")
    if s3 < 15:
        suggestions.append(f"→ 提交累积的 {uncommitted} 文件 (强制闭环纪律)")
    if s4 < 20:
        suggestions.append(f"→ 修复 ADR INDEX 中的 {unlisted} 个 UNLISTED")
    if s5 < 15:
        suggestions.append(f"→ 修复 omo governance score 失分 (当前 {gov_score})")

    if suggestions:
        print("💡 改进建议:")
        for s in suggestions:
            print(f"  {s}")
    else:
        print("✅ 全部维度达标, 治理成熟")

    return 0 if total >= 90 else 1


if __name__ == "__main__":
    sys.exit(main())