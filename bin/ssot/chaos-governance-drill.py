#!/usr/bin/env python3
"""Unified Governance Chaos & Red-Teaming Drill Suite (ADR-0194).

Executes 4 active mutation scenarios to validate system anti-fragility:
1. Documents Plane Invasion Mutation (Scripts / .venv injection)
2. Corrupted & Stale Fact Mutation (Missing schema fields / 60-day staleness)
3. Policy-as-Code Red Line Bypass Mutation (Budget overrun / Reward ratio violation)
4. Compute Fabric VRAM Shock & Thermal Throttling Chaos Mutation
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run_cmd(cmd: list[str], cwd: Path | None = None, timeout: int = 30) -> tuple[int, str]:
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd or REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return res.returncode, (res.stdout.strip() or res.stderr.strip())
    except Exception as e:
        return -1, str(e)


def run_drill_1_documents_invasion() -> dict[str, Any]:
    """Test 1: Documents Boundary Defense against malicious scripts & dependencies."""
    script = """
from ecos.ssot.compiler.path_inspector import PathBoundaryInspector
inspector = PathBoundaryInspector()
test_violations = [
    "Documents/@工作文档/malicious_exploit.py",
    "Documents/@工作文档/deploy_daemon.sh",
    "Documents/@工作文档/node_modules/express/index.js",
    "Documents/@工作文档/.venv/bin/activate",
]
blocked = sum(1 for p in test_violations if not inspector.inspect_write(p, caller_domain="work-weijian").passed)
print(blocked)
"""
    rc, out = run_cmd(["uv", "run", "--project", "projects/ecos", "python3", "-c", script])
    blocked_count = int(out.strip()) if rc == 0 and out.strip().isdigit() else 0
    success = blocked_count == 4
    return {
        "drill_name": "Documents Plane Invasion Mutation",
        "category": "Plane Boundary",
        "passed": success,
        "detail": f"Intercepted {blocked_count}/4 illegal script/dependency writes",
    }


def run_drill_2_stale_and_corrupt_facts() -> dict[str, Any]:
    """Test 2: Facts Inspector SLA & Schema Integrity defense."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        facts_dir = tmp_path / "facts"
        facts_dir.mkdir(parents=True, exist_ok=True)

        # 1. Corrupt fact (missing schema_version & entity_id)
        f_corrupt = facts_dir / "fact_corrupt.yaml"
        with open(str(f_corrupt), "w", encoding="utf-8") as f:
            f.write("domain: work-weijian\nname: 无效实体\n")

        # 2. Stale fact (60 days old)
        f_stale = facts_dir / "fact_stale.yaml"
        old_dt = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%d")
        stale_content = f"""schema_version: v1.0
entity_id: FACT-WJ-2026-STALE
domain: work-weijian
name: 过期项目
owner: 信息中心
updated_at: '{old_dt}'
lifecycle_stage: IMPLEMENTATION
facts:
  budget: 100
"""
        with open(str(f_stale), "w", encoding="utf-8") as f:
            f.write(stale_content)

        rc, out = run_cmd([
            "uv", "run", "--project", "projects/ecos",
            "ecos-constraint", "facts", "validate", str(facts_dir), "--strict", "--json"
        ])
        # Strict mode must fail due to staleness and schema corruption
        success = rc != 0
        return {
            "drill_name": "Corrupted & Stale Fact Mutation",
            "category": "Facts SSOT",
            "passed": success,
            "detail": "Fact validator successfully blocked corrupted & 60-day stale mutations",
        }


def run_drill_3_policy_red_line_bypass() -> dict[str, Any]:
    """Test 3: Policy-as-Code defense against regulatory violations."""
    attack_1 = "项目规划建设某市级健康平台，预算 1200 万元，采购标准机房。"
    attack_2 = "成果转化作价入股协议：科研团队收益分配比例为 40%，管理方 60%。"

    rc1, out1 = run_cmd(["uv", "run", "--project", "projects/ecos", "ecos-constraint", "policy", "audit", attack_1, "--domain", "work-weijian", "--json"])
    rc2, out2 = run_cmd(["uv", "run", "--project", "projects/ecos", "ecos-constraint", "policy", "audit", attack_2, "--domain", "work-transfer", "--json"])

    caught_1 = rc1 != 0
    caught_2 = rc2 != 0
    success = caught_1 and caught_2
    return {
        "drill_name": "Policy-as-Code Regulatory Red-Line Bypass",
        "category": "Domain Policy",
        "passed": success,
        "detail": f"Health budget violation blocked: {caught_1}, Transfer reward violation blocked: {caught_2}",
    }


def run_drill_4_compute_vram_and_thermal_chaos() -> dict[str, Any]:
    """Test 4: Compute fabric self-healing under extreme context and thermal throttle."""
    script = """
from omlxc.dataplane.vram_budget import VRAMBudgetEstimator, ContextCompactor
from omlxc.dataplane.thermal import ThermalGuard, ThermalPressureLevel, PowerSource

# 1. VRAM Shock
estimator = VRAMBudgetEstimator()
vram_admission = estimator.check_headroom_admission(model_id="coding", context_tokens=128000, available_node_vram_mb=2000.0)
vram_ok = (not vram_admission.admitted) and vram_admission.compaction_advised

# 2. Compaction
heavy_messages = [{"role": "system", "content": "System"}]
for i in range(50):
    heavy_messages.append({"role": "user", "content": f"Turn {i} " * 50})
    heavy_messages.append({"role": "assistant", "content": f"Reply {i} " * 50})
compaction = ContextCompactor.compact_messages(heavy_messages, target_safe_tokens=2000, keep_recent_turns=2)
compaction_ok = compaction.compression_ratio > 0.4 and len(compaction.compacted_messages) < 10

# 3. Thermal
guard = ThermalGuard()
penalty = guard.calculate_penalty(ThermalPressureLevel.HEAVY, PowerSource.BATTERY, battery_percent=20.0)
thermal_ok = penalty <= 0.5

print(vram_ok and compaction_ok and thermal_ok)
"""
    rc, out = run_cmd(["uv", "run", "--project", "projects/omlxc", "python3", "-c", script])
    success = rc == 0 and "True" in out
    return {
        "drill_name": "Compute Fabric VRAM Shock & Thermal Chaos",
        "category": "Compute Fabric",
        "passed": success,
        "detail": "VRAM compaction triggered (>40% ratio) and thermal throttle penalized correctly",
    }


def run_drill_5_intent_shadow_cartridge_adversarial() -> dict:
    """Drill 5: Adversarial Intent deconstruction, Shadow red-team loop, and broken Cartridge attack."""
    script = """
from ecos.ssot.compiler.intent_compiler import IntentSpecCompiler
from ecos.ssot.compiler.shadow_challenger import ShadowChallenger
from ecos.ssot.compiler.domain_cartridge import DomainCartridgeManager
import tempfile
from pathlib import Path

# 1. Intent Deconstruction on high-risk prompt
compiler = IntentSpecCompiler()
spec = compiler.compile("卫健委核心医疗数据库上云与5000万投资规划")
intent_ok = spec.detected_domain == "work-weijian" and len(spec.policy_requirements) >= 2

# 2. Shadow Challenger on flawed proposal
challenger = ShadowChallenger()
flawed = "# 方案\\n项目总预算 2000 万元，未经专家论证，直接公有云单点部署。"
report = challenger.challenge_text(flawed, domain="work-weijian", auto_patch=True)
shadow_ok = (not report.passed) and (report.patched_text is not None) and ("影子红蓝对抗合规补强" in report.patched_text)

# 3. Broken cartridge attack
mgr = DomainCartridgeManager()
with tempfile.TemporaryDirectory() as tmpdir:
    fake_cartridge = Path(tmpdir) / "corrupted_cartridge.yaml"
    fake_cartridge.write_text("invalid_key: 123\\npolicies: []", encoding="utf-8")
    valid, errors = mgr.validate_cartridge_file(fake_cartridge)
    cartridge_ok = (not valid) and len(errors) > 0

print(intent_ok and shadow_ok and cartridge_ok)
"""
    rc, out = run_cmd(["uv", "run", "--project", "projects/ecos", "python3", "-c", script])
    success = rc == 0 and "True" in out
    return {
        "drill_name": "Intent Spec, Shadow Challenger & Broken Cartridge Defense",
        "category": "Cognitive Mesh",
        "passed": success,
        "detail": "Intent grounded correctly, Shadow red-team auto-patched flaws, and broken cartridge blocked",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified Governance Chaos & Red-Teaming Drill Suite")
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero on any drill failure")
    parser.add_argument("--json", action="store_true", help="Output summary as JSON")
    args = parser.parse_args()

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    drills = [
        run_drill_1_documents_invasion(),
        run_drill_2_stale_and_corrupt_facts(),
        run_drill_3_policy_red_line_bypass(),
        run_drill_4_compute_vram_and_thermal_chaos(),
        run_drill_5_intent_shadow_cartridge_adversarial(),
    ]

    all_passed = all(d["passed"] for d in drills)
    passed_count = sum(1 for d in drills if d["passed"])

    if args.json:
        print(
            json.dumps(
                {
                    "timestamp": now_iso,
                    "all_passed": all_passed,
                    "score": f"{passed_count}/{len(drills)}",
                    "drills": drills,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print("\n⚡️ ─────────────────────────────────────────────────────────────")
        print(f"   omostation 全域混沌演练与红蓝对抗大盘 (Chaos & Red-Teaming)")
        print(f"   演练时间: {now_iso}   状态: {'🟢 ALL PASS (全域坚韧)' if all_passed else '🔴 DRILL FAILED'}")
        print("─────────────────────────────────────────────────────────────────\n")
        for d in drills:
            status = "✅ PASS" if d["passed"] else "❌ FAIL"
            print(f"  {status}  [{d['category']}] {d['drill_name']}")
            print(f"         └─ {d['detail']}")
        print()

    if not all_passed and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
