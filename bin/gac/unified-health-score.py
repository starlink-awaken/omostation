#!/usr/bin/env python3
"""Unified Health Score (UHS) — 统一健康评分计算器.

整合工具覆盖率、治理合规、场景激活、文档保鲜、价值可证、运行时健康
六个维度, 输出 0-100 统一健康评分.

公式:
    UHS = 0.20×tools + 0.20×governance + 0.15×scenes + 0.10×docs + 0.25×value + 0.10×runtime

用法:
    python3 unified-health-score.py              # 文本报告
    python3 unified-health-score.py --json       # JSON 输出
    python3 unified-health-score.py --trend      # 趋势 (最近 30 天)
    python3 unified-health-score.py --check      # CI 模式: <80 则 exit 1
"""

import json
import sys
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REPO = Path(__file__).resolve().parents[2]  # bin/gac/ → Workspace/
ECOS = REPO / "projects/ecos"
HISTORY_FILE = REPO / ".omo/state/history/uhs.jsonl"

# 权重配置
WEIGHTS = {
    "tools": 0.20,
    "governance": 0.20,
    "scenes": 0.15,
    "docs": 0.10,
    "value": 0.25,
    "runtime": 0.10,
}

# 目标分数
TARGETS = {
    "tools": 90,
    "governance": 95,
    "scenes": 87,  # 7/8 active
    "docs": 90,
    "value": 85,
    "runtime": 95,
}


def score_tools() -> float:
    """工具 CI 覆盖率 (0-100)."""
    tools_dir = ECOS / "src/ecos/ssot/tools"
    workflow = REPO / ".github/workflows/ecos-ci.yml"

    if not tools_dir.exists() or not workflow.exists():
        return 0.0

    ci_content = workflow.read_text()
    total = 0
    in_ci = 0

    for f in sorted(tools_dir.glob("*.py")):
        name = f.stem
        if name.startswith("_"):
            continue
        total += 1
        if name in ci_content:
            in_ci += 1

    if total == 0:
        return 100.0
    return round(in_ci / total * 100, 1)


def score_governance() -> float:
    """治理规则合规率 (0-100)."""
    checks_file = REPO / ".omo/_truth/registry/governance-checks.yaml"
    if not checks_file.exists():
        return 0.0

    try:
        import yaml
        content = checks_file.read_text()
        # 文件可能包含多个 YAML 文档, 用 safe_load_all 遍历
        for data in yaml.safe_load_all(content):
            if data and isinstance(data, dict) and "gac" in data:
                gac = data["gac"]
                if isinstance(gac, dict) and "rules" in gac:
                    rules = gac["rules"]
                    total = len(rules)
                    active = sum(1 for r in rules if r.get("lifecycle") == "active")
                    if total == 0:
                        return 100.0
                    return round(active / total * 100, 1)
    except Exception:
        pass
    return 0.0


def score_scenes() -> float:
    """场景激活率 (0-100).

    生命周期: draft → shadow → assisted → supervised → routine
    活跃状态: assisted, supervised, routine
    优先使用 v2/ 目录的场景卡片 (权威版本)
    """
    scene_dir = REPO / "docs/scene-cards"
    if not scene_dir.exists():
        return 0.0

    # 收集所有场景 (v2/ 优先)
    scenes = {}  # scene_id -> status

    # 先扫描根目录
    for f in sorted(scene_dir.glob("*.yaml")):
        status, scene_id = _parse_scene_status(f)
        if scene_id and scene_id not in scenes:
            scenes[scene_id] = status

    # v2/ 覆盖根目录
    for f in sorted(scene_dir.glob("v2/*.yaml")):
        status, scene_id = _parse_scene_status(f)
        if scene_id:
            scenes[scene_id] = status

    if not scenes:
        return 100.0

    total = len(scenes)
    active = sum(1 for s in scenes.values() if s in ("assisted", "supervised", "routine", "active", "pilot"))

    return round(active / total * 100, 1)


def _parse_scene_status(f: Path) -> tuple[str, str]:
    """解析场景卡片的 status 和 scene_id."""
    try:
        import yaml
        text = f.read_text()
        fm = {}
        # 解析所有 YAML 片段 (包括 --- 分隔的多个文档)
        if "---" in text:
            for part in text.split("---"):
                part = part.strip()
                if not part:
                    continue
                try:
                    data = yaml.safe_load(part)
                    if isinstance(data, dict):
                        fm.update(data)
                except Exception:
                    pass
        else:
            try:
                data = yaml.safe_load(text)
                if isinstance(data, dict):
                    fm = data
            except Exception:
                pass
        return fm.get("status", ""), fm.get("scene_id", "")
    except Exception:
        return "", ""


def score_docs() -> float:
    """文档保鲜率 (0-100)."""
    from datetime import date as date_type

    docs_dir = REPO / "docs"
    if not docs_dir.exists():
        return 0.0

    total = 0
    fresh = 0
    stale_threshold = datetime.now(UTC) - timedelta(days=30)

    for f in sorted(docs_dir.rglob("*.md")):
        try:
            text = f.read_text()
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    import yaml
                    fm = yaml.safe_load(text[3:end])
                    if isinstance(fm, dict) and "last-reviewed" in fm:
                        total += 1
                        lr = fm["last-reviewed"]
                        if isinstance(lr, str):
                            lr = date_type.fromisoformat(lr)
                        if isinstance(lr, datetime):
                            if lr >= stale_threshold:
                                fresh += 1
                        elif isinstance(lr, date_type):
                            if lr >= stale_threshold.date():
                                fresh += 1
        except Exception:
            continue

    if total == 0:
        return 100.0
    return round(fresh / total * 100, 1)


def score_value() -> float:
    """价值可证度 (0-100).

    优先读 OMO North Star meter (带 value-evidence.jsonl fallback).
    """
    import os
    import subprocess

    try:
        principal = os.environ.get("OMO_PRINCIPAL_ID", "xiamingxing")
        meter = REPO / "bin/bc-os/north_star_meter_v2.py"
        proc = subprocess.run(
            ["python3", str(meter), "--json", "--principal-id", principal],
            cwd=REPO, capture_output=True, text=True, timeout=60,
        )
        payload = json.loads(proc.stdout)
        readiness = str(payload.get("readiness") or "")
    except Exception:
        return 0.0

    if readiness == "passed":
        return 100.0
    elif readiness == "collecting":
        return 50.0
    elif readiness == "not_ready":
        return 25.0
    return 0.0


def score_runtime() -> float:
    """运行时健康度 (0-100)."""
    health_file = REPO / ".omo/state/health.yaml"
    if not health_file.exists():
        return 0.0

    try:
        import yaml
        content = health_file.read_text()
        # 跳过注释行，找到第一个 ---
        lines = content.splitlines()
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() == "---":
                start_idx = i
                break
        yaml_content = "\n".join(lines[start_idx:])
        data = yaml.safe_load(yaml_content)
        if data:
            # 使用 service_online_ratio 作为运行时健康度
            ratio = data.get("service_online_ratio", 0)
            return float(ratio) * 100
    except Exception:
        pass
    return 100.0  # 默认健康


def compute_uhs(scores: dict[str, float]) -> float:
    """计算统一健康评分."""
    return round(sum(WEIGHTS[k] * scores[k] for k in WEIGHTS), 1)


def grade(uhs: float) -> str:
    """评分等级."""
    if uhs >= 90:
        return "A"
    elif uhs >= 80:
        return "B"
    elif uhs >= 70:
        return "C"
    elif uhs >= 60:
        return "D"
    else:
        return "F"


def record_history(uhs: float, scores: dict[str, float]):
    """记录健康分历史."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "uhs": uhs,
        **scores,
    }
    with open(HISTORY_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def get_trend(days: int = 30) -> list[dict]:
    """获取最近 N 天的健康分趋势."""
    if not HISTORY_FILE.exists():
        return []

    cutoff = datetime.now(UTC) - timedelta(days=days)
    records = []

    with open(HISTORY_FILE) as f:
        for line in f:
            try:
                record = json.loads(line.strip())
                ts = datetime.fromisoformat(record["timestamp"])
                if ts >= cutoff:
                    records.append(record)
            except Exception:
                continue

    return records


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Unified Health Score")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--trend", action="store_true", help="Show trend")
    parser.add_argument("--check", action="store_true", help="CI mode: exit 1 if <80")
    parser.add_argument("--sync", action="store_true", help="Write UHS into system.yaml::health_score")
    args = parser.parse_args()

    if args.trend:
        records = get_trend()
        if args.json:
            print(json.dumps(records, ensure_ascii=False, indent=2))
        else:
            print("=" * 56)
            print("  UHS Trend (Last 30 days)")
            print("=" * 56)
            for r in records[-10:]:
                print(f"  {r['timestamp'][:10]}: UHS={r['uhs']} (tools={r['tools']}, gov={r['governance']}, scenes={r['scenes']})")
        return

    # 计算各维度分数
    scores = {
        "tools": score_tools(),
        "governance": score_governance(),
        "scenes": score_scenes(),
        "docs": score_docs(),
        "value": score_value(),
        "runtime": score_runtime(),
    }

    uhs = compute_uhs(scores)
    g = grade(uhs)

    # 记录历史
    record_history(uhs, scores)

    # --sync: 写入 system.yaml::health_score (整合方案#1: UHS 为唯一权威分数)
    if getattr(args, "sync", False):
        try:
            import yaml as _y
            sys_yaml_path = WORKSPACE / ".omo" / "state" / "system.yaml"
            if sys_yaml_path.is_file():
                sd = _y.safe_load(sys_yaml_path.read_text()) or {}
                sd["health_score"] = int(round(uhs))
                sys_yaml_path.write_text(
                    _y.dump(sd, allow_unicode=True, sort_keys=False), encoding="utf-8"
                )
                print(f"  ✅ system.yaml::health_score synced = {int(round(uhs))}")
        except Exception as e:
            print(f"  ⚠️ sync failed: {e}", file=__import__("sys").stderr)

    if args.json:
        print(json.dumps({
            "timestamp": datetime.now(UTC).isoformat(),
            "uhs": uhs,
            "grade": g,
            "scores": scores,
            "targets": TARGETS,
            "gaps": {k: TARGETS[k] - scores[k] for k in TARGETS if scores[k] < TARGETS[k]},
        }, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Unified Health Score (UHS)")
    print("=" * 56)
    print(f"  UHS: {uhs} / 100  (Grade: {g})")
    print()
    for k, v in scores.items():
        target = TARGETS[k]
        gap = v - target
        status = "✓" if gap >= 0 else f"↓ {gap:.0f}"
        print(f"  {k:12s}: {v:5.1f} / {target}  [{status}]")
    print()

    # 差距分析
    gaps = {k: TARGETS[k] - scores[k] for k in TARGETS if scores[k] < TARGETS[k]}
    if gaps:
        print("  Gaps to 90%:")
        for k, gap in sorted(gaps.items(), key=lambda x: -x[1]):
            print(f"    - {k}: need +{gap:.1f} points")
    else:
        print("  ✓ All dimensions at target!")

    if args.check:
        if uhs < 80:
            print(f"\n  FAIL: UHS {uhs} < 80", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())
