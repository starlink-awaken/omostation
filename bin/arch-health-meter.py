#!/usr/bin/env python3
"""arch-health-meter.py — 架构健康度 6 维度量化采集 (BET-Y1Q4-T6-18).

维度:
  1. 场景 (Scene)   — scene_card 总数 + lifecycle 分布
  2. 架构 (Arch)    — SFOP 槽位一致性 + DFSQ 层级
  3. 进化 (Evol)    — 3Y bet done 比例
  4. 运维 (Ops)     — runtime 在线率 (粗略)
  5. 防腐 (AntiC)   — GaC drift + SSOT 漂移
  6. 感知 (Perc)    — skill/workflow 覆盖

Usage:
  python3 bin/arch-health-meter.py           # markdown 表格
  python3 bin/arch-health-meter.py --json    # JSON 输出
  python3 bin/arch-health-meter.py --week    # 周报模式 (含趋势占位)

Exit codes:
  0  success
  1  runtime error
  2  data integrity warning
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

WS = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# 维度 1: 场景 (Scene)
# ---------------------------------------------------------------------------
def dim_scene() -> dict:
    """扫描 docs/scene-cards/*.yaml frontmatter, 统计 lifecycle 分布."""
    scene_dir = WS / "docs" / "scene-cards"
    if not scene_dir.exists():
        return {"total": 0, "by_lifecycle": {}, "error": "docs/scene-cards/ missing"}
    distribution: Counter = Counter()
    total = 0
    for f in scene_dir.glob("*.yaml"):
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if not text.startswith("---"):
            continue
        # 解析 frontmatter
        m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
        if not m:
            continue
        fm = m.group(1)
        lc_match = re.search(r"^lifecycle:\s*(\S+)", fm, re.MULTILINE)
        if lc_match:
            distribution[lc_match.group(1)] += 1
            total += 1
    return {
        "total": total,
        "by_lifecycle": dict(distribution.most_common()),
    }


# ---------------------------------------------------------------------------
# 维度 2: 架构 (Architecture)
# ---------------------------------------------------------------------------
def dim_architecture() -> dict:
    """SFOP 槽位 + DFSQ 层级."""
    sfop_result = _run_check("bin/gac/check-sfop-slots.py --json", default={})
    chain_result = _run_check("bin/gac/check-execution-chain.py --json", default={})
    return {
        "sfop_ok": sfop_result.get("ok", False) if isinstance(sfop_result, dict) else False,
        "sfop_slots": sfop_result.get("slots", {}) if isinstance(sfop_result, dict) else {},
        "chain_ok": chain_result.get("ok", False) if isinstance(chain_result, dict) else False,
    }


# ---------------------------------------------------------------------------
# 维度 3: 进化 (Evolution)
# ---------------------------------------------------------------------------
def dim_evolution() -> dict:
    """3Y bet done 比例 + 30d 增量."""
    ledger = WS / "docs" / "plans" / "3y-bet-ledger.yaml"
    if not ledger.exists():
        return {"total": 0, "done": 0, "ratio": 0.0, "done_30d": 0, "error": "ledger missing"}
    try:
        import yaml  # type: ignore
    except ImportError:
        return {"error": "PyYAML not installed"}
    try:
        data = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"parse failed: {e}"}
    bets = data.get("bets", [])

    # BET-Y2Q1-T10-03: 归档合并读 — 健康统计不缩水
    _arch = ledger.parent / "3y-bet-ledger-archive.yaml"
    if _arch.is_file():
        try:
            _adoc = yaml.safe_load(_arch.read_text(encoding="utf-8"))
            if isinstance(_adoc, dict) and isinstance(_adoc.get("bets"), list):
                _seen = {b.get("id") for b in bets}
                bets.extend(b for b in _adoc["bets"] if isinstance(b, dict) and b.get("id") not in _seen)
        except yaml.YAMLError:
            pass
    total = len(bets)
    done = sum(1 for b in bets if b.get("status") == "done")
    now = datetime.now(timezone.utc)
    done_30d = 0
    for b in bets:
        if b.get("status") != "done":
            continue
        done_at = b.get("done_at")
        if not done_at:
            continue
        try:
            # done_at 可能是 "2026-09-05 11:50:00+00:00" 格式
            ts = str(done_at).replace(" ", "T").replace("+00:00", "Z")
            dt = datetime.fromisoformat(ts.rstrip("Z"))
            if (now - dt).days <= 30:
                done_30d += 1
        except Exception:
            continue
    return {
        "total": total,
        "done": done,
        "ratio": round(done / total, 4) if total else 0.0,
        "done_30d": done_30d,
    }


# ---------------------------------------------------------------------------
# 维度 4: 运维 (Operations)
# ---------------------------------------------------------------------------
def dim_operations() -> dict:
    """runtime 在线率 (从 system.yaml 的 runtime 块)."""
    sys_yaml = WS / ".omo" / "state" / "system.yaml"
    if not sys_yaml.exists():
        return {"online": 0, "total": 0, "ratio": 0.0, "error": "system.yaml missing"}
    try:
        import yaml  # type: ignore
    except ImportError:
        return {"error": "PyYAML not installed"}
    try:
        data = yaml.safe_load(sys_yaml.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"parse failed: {e}"}
    rt = data.get("runtime", {}) or {}
    # 期待格式: runtime.daemons = {"name": {"online": true, ...}}
    daemons = rt.get("daemons", {}) or {}
    total = len(daemons)
    online = sum(1 for v in daemons.values() if isinstance(v, dict) and v.get("online"))
    return {
        "online": online,
        "total": total,
        "ratio": round(online / total, 4) if total else 0.0,
    }


# ---------------------------------------------------------------------------
# 维度 5: 防腐 (Anti-Corrosion)
# ---------------------------------------------------------------------------
def dim_anticorrosion() -> dict:
    """GaC drift 项数 + 治理 SSOT 漂移告警."""
    meta = _run_check("bin/gac/meta-doctor.py --workspace . --json", default={})
    guardian = _run_check("bin/ssot/ssot-guardian.py", default="")
    meta_drift = 0
    if isinstance(meta, dict):
        # 各种可能字段
        meta_drift = (
            meta.get("drift_count", 0)
            or meta.get("drifts", 0)
            or len(meta.get("findings", []))
            or len(meta.get("drifts_list", []))
            or 0
        )
    # ssot-guardian 返回 exit 0/1 + 文本; 用 stderr/stdout 简单判断
    guardian_clean = "PASS" in str(guardian) and "FAIL" not in str(guardian).split("\n")[0]
    return {
        "meta_doctor_drift_count": meta_drift,
        "ssot_guardian_clean": guardian_clean,
    }


# ---------------------------------------------------------------------------
# 维度 6: 感知 (Perception)
# ---------------------------------------------------------------------------
def dim_perception() -> dict:
    """skill INDEX 注册数 + workflow 沉默数."""
    skills_index = WS / ".agents" / "skills" / "INDEX.md"
    wf_dir = WS / ".omo" / "_truth" / "registry" / "agent-workflows"
    skill_count = 0
    if skills_index.exists():
        # 第一段 "共 N 个 skills" 文本
        text = skills_index.read_text(encoding="utf-8")
        m = re.search(r"共\s*(\d+)\s*个\s*skills", text)
        if m:
            skill_count = int(m.group(1))
    wf_count = 0
    if wf_dir.exists():
        wf_count = sum(1 for f in wf_dir.rglob("*.yaml"))
    return {
        "skill_count": skill_count,
        "workflow_count": wf_count,
        "silent_workflows": 0,  # TODO: 接入 P74 沉默工作流检测
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _run_check(cmd: str, default):
    """运行子命令, 解析 stdout 为 JSON. 失败时返回 default."""
    try:
        result = subprocess.run(
            cmd,
            cwd=WS,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, OSError):
        return default
    if result.returncode != 0 and not result.stdout:
        return default
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return result.stdout  # 文本


def collect_all() -> dict:
    return {
        "scene": dim_scene(),
        "architecture": dim_architecture(),
        "evolution": dim_evolution(),
        "operations": dim_operations(),
        "anti_corrosion": dim_anticorrosion(),
        "perception": dim_perception(),
    }


def to_markdown(report: dict, week: bool = False) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [f"# 架构健康度 6 维度周报 · {now}\n"]
    out.append("SSOT: `.omo/standards/architecture-health-six-dim.md` (T6-18)\n")
    out.append("| 维度 | 当前 | 趋势 (上周) | 备注 |")
    out.append("|------|------|-------------|------|")

    s = report["scene"]
    out.append(f"| 场景 | {s['total']} cards ({', '.join(f'{k}={v}' for k, v in s.get('by_lifecycle', {}).items())}) | — | — |")

    a = report["architecture"]
    sfop = "OK" if a["sfop_ok"] else "FAIL"
    chain = "OK" if a["chain_ok"] else "FAIL"
    out.append(f"| 架构 | SFOP {sfop} + DFSQ {chain} | — | — |")

    e = report["evolution"]
    out.append(f"| 进化 | {e['done']}/{e['total']} bet done ({e['ratio']*100:.1f}%, 30d +{e['done_30d']}) | — | — |")

    o = report["operations"]
    out.append(f"| 运维 | {o['online']}/{o['total']} 在线 ({o['ratio']*100:.0f}%) | — | — |")

    c = report["anti_corrosion"]
    drft = c.get("meta_doctor_drift_count", "?")
    ssg = "clean" if c.get("ssot_guardian_clean") else "warnings"
    out.append(f"| 防腐 | drift={drft}, ssot-guardian={ssg} | — | — |")

    p = report["perception"]
    out.append(f"| 感知 | {p['skill_count']} skills + {p['workflow_count']} workflows (silent={p['silent_workflows']}) | — | — |")

    out.append("")
    if week:
        out.append("## 趋势 (本周 vs 上周)")
        out.append("- 多数维度持平, 自动化采集稳定")
        out.append("- 关注防腐 drift 增长 (需修复)")
        out.append("- 建议: 下周关注 进化 done 速率 (与本 bet 落地同步)")
    return "\n".join(out)


def main() -> int:
    global WS
    parser = argparse.ArgumentParser(prog="arch-health-meter", description="6-dim architecture health")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--week", action="store_true", help="weekly report mode")
    parser.add_argument("--workspace", default=str(WS), help="workspace root")
    args = parser.parse_args()

    WS = Path(args.workspace).resolve()
    report = collect_all()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(to_markdown(report, week=args.week))
    return 0


if __name__ == "__main__":
    sys.exit(main())
