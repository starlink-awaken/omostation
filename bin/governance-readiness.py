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

import os
import re
import subprocess
import sys
import json
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
                if all(
                    k in fm for k in ["status", "lifecycle", "owner", "last-reviewed"]
                ):
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


def write_readiness_snapshot(
    root: Path,
    total: int,
    grade: str,
    s1: int,
    s2: int,
    s3: int,
    s4: int,
    s5: int,
    total_doc: int,
    cov: float,
    drift_low: int,
    uncommitted: int,
    unlisted: int,
    gov_score: float,
) -> None:
    """P63 增: 写历史快照到 .omo/_log/readiness-YYYYMMDD-HHMMSS.json.

    通过 OMO CLI `omo readiness snapshot` 路由写入,避免直接 I/O 到 .omo/_log/.
    失败只打印警告,不阻断主流程.
    """
    import json as _json

    snapshot = {
        "score": total,
        "grade": grade,
        "phase": "P60+",
        "dimensions": {
            "frontmatter": {
                "score": s1,
                "metric": total_doc,
                "coverage": cov,
                "max": 25,
            },
            "drift_low": {"score": s2, "metric": drift_low, "max": 20},
            "commit_closure": {"score": s3, "metric": uncommitted, "max": 20},
            "adr_index": {"score": s4, "metric": unlisted, "max": 20},
            "governance_score": {"score": s5, "metric": gov_score, "max": 15},
        },
        "thresholds": {
            "A+_L4_stable": 90,
            "A_L3_mature": 80,
            "B_L2_basic": 70,
            "C_L1_starting": 60,
        },
    }
    payload = _json.dumps(snapshot, ensure_ascii=False)
    cmd = f"omo readiness snapshot '{payload}'"
    rc, out = run(cmd, cwd=root)
    if rc != 0:
        print(f"⚠️  快照写入失败 (rc={rc}): {out}")
    # P70 持久化 snapshots.jsonl 已迁入 OMO 内核 (omo_readiness.write_readiness_snapshot),
    # 避免脚本层 direct-omo-io.


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

    # P80: 环境变量 USE_TUNED_WEIGHTS=1 启用调优权重 (基于 dim-weight 调优结果)
    if os.environ.get("USE_TUNED_WEIGHTS") == "1":
        try:
            from subprocess import run as _run
            r = _run(["python3", "bin/dim-weight.py", "--format", "json"],
                      capture_output=True, text=True, cwd=str(root), timeout=30)
            if r.returncode == 0:
                dw = json.loads(r.stdout)
                tuned = dw.get("weights", {})
                w1 = tuned.get("frontmatter", 25)
                w2 = tuned.get("drift_low", 20)
                w3 = tuned.get("commit_closure", 20)
                w4 = tuned.get("adr_index", 20)
                w5 = tuned.get("governance_score", 15)
                weighted = (s1 * w1 + s2 * w2 + s3 * w3 + s4 * w4 + s5 * w5) / 100
                print(f"  ⚖️  P80 调优权重: frontmatter={w1} drift_low={w2} commit_closure={w3} adr_index={w4} governance_score={w5}")
                print(f"  📊 加权总分: {weighted:.1f} (原始 {total})")
                total = int(round(weighted))
        except Exception as e:
            print(f"⚠️  dim-weight 集成失败: {e}")

    print()
    print("─" * 70)
    print(f"{'维度':<28s}{'得分':<8s}{'指标':<15s}{'阈值':<15s}")
    print("─" * 70)
    print(
        f"{'1. 元数据覆盖 (frontmatter)':<28s}{s1:>3d}/25  {total_doc} 文档    cov={cov:.1%}     ≥95%"
    )
    print(f"{'2. 漂移检测 (drift LOW)':<28s}{s2:>3d}/20  drift={drift_low}        ≤5")
    print(
        f"{'3. 闭环纪律 (commit closure)':<28s}{s3:>3d}/20  uncommitted={uncommitted}  ≤50"
    )
    print(f"{'4. 决策可追溯 (ADR INDEX)':<28s}{s4:>3d}/20  unlisted={unlisted}     =0")
    print(
        f"{'5. 治理评分 (omo governance)':<28s}{s5:>3d}/15  score={gov_score}      =100"
    )
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

    # P63 增: 写历史快照到 .omo/_log/readiness-YYYYMMDD-HHMM.json
    write_readiness_snapshot(
        root,
        total,
        grade,
        s1,
        s2,
        s3,
        s4,
        s5,
        total_doc,
        cov,
        drift_low,
        uncommitted,
        unlisted,
        gov_score,
    )

    return 0 if total >= 90 else 1


if __name__ == "__main__":
    sys.exit(main())
