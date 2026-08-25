#!/usr/bin/env python3
"""
Real-World Domain Scenario Runner (ADR-0427 / Phase 8)
======================================================
Executes end-to-end domain business scenarios, validates Policy-as-Code red lines,
publishes structured A2A events to Agora Bus, and writes real resident decision proposals.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, NoReturn

# Add workspace environment via env-resolver
_BIN_DIR = Path(__file__).resolve().parents[1]
_RESOLVER_PATH = _BIN_DIR / "cockpit" / "env-resolver.py"
_spec = importlib.util.spec_from_file_location("env_resolver", _RESOLVER_PATH)
_env_resolver = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_env_resolver)
_ROOT = _env_resolver.setup_workspace_paths()

BUS_URL = "http://127.0.0.1:7432/publish"
_REFUSAL_MESSAGE = (
    "Mesh successor is pending; Cockpit PR #78 is retirement evidence only, "
    "never the delivered successor."
)


def _refuse_retired_surface(command: str) -> NoReturn:
    print(
        json.dumps(
            {
                "ok": False,
                "status": "retired",
                "successor": "Mesh-bound capability admission",
                "successor_status": "pending",
                "retirement_evidence": "Cockpit PR #78",
                "value_indicator_policy": False,
                "command": command,
                "message": _REFUSAL_MESSAGE,
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(2)


def load_scenario(scenario_file: Path) -> dict[str, Any]:
    import yaml

    with open(scenario_file, encoding="utf-8") as f:
        return yaml.safe_load(f)


def evaluate_weijian_scenario(manifest: dict[str, Any]) -> dict[str, Any]:
    """Evaluates E-POL-WJ-001 and E-POL-WJ-002 on the health scenario."""
    meta = manifest.get("project_metadata", {})
    experts = manifest.get("expert_committee", {})

    results = []

    # Check E-POL-WJ-001: 预算>=500万需5位以上专家论证
    budget = meta.get("budget_total_wan", 0)
    committee_size = experts.get("committee_size", 0)
    consensus = experts.get("consensus_verdict")

    if budget >= 500:
        if committee_size >= 5 and consensus == "CONSENSUS_PASSED":
            results.append({
                "rule_id": "E-POL-WJ-001",
                "name": "重大信息化项目预算与专家论证门禁",
                "verdict": "PASS",
                "detail": f"项目预算 {budget} 万元 (>=500万)，经由 {committee_size} 位高级职称专家委员会严谨论证并达成 CONSENSUS_PASSED 一致通过决议。",
            })
        else:
            results.append({
                "rule_id": "E-POL-WJ-001",
                "name": "重大信息化项目预算与专家论证门禁",
                "verdict": "BLOCK",
                "detail": f"专家人数 ({committee_size}) 不足 5 人或决议未达成一致通过。",
            })

    # Check E-POL-WJ-002: 等保三级与互联互通四级甲等
    sec_level = meta.get("security_level", "")
    sec_rep = meta.get("security_evaluation_report", "")
    interop = meta.get("interoperability_standard", "")

    if "三级" in sec_level and sec_rep and "四级甲等" in interop:
        results.append({
            "rule_id": "E-POL-WJ-002",
            "name": "医疗卫生网络安全三级等保与互联互通标准合规",
            "verdict": "PASS",
            "detail": f"已完备具备等保三级评测 ({sec_rep}) 并在方案中固化国家互联互通标准化成熟度四级甲等数据接口。",
        })
    else:
        results.append({
            "rule_id": "E-POL-WJ-002",
            "name": "医疗卫生网络安全三级等保与互联互通标准合规",
            "verdict": "BLOCK",
            "detail": "缺少等保三级评测报告或未达到互联互通四级甲等标准。",
        })

    all_passed = all(r["verdict"] == "PASS" for r in results)
    return {
        "scenario_id": manifest.get("scenario_id"),
        "domain": manifest.get("domain"),
        "title": manifest.get("title"),
        "status": "APPROVED" if all_passed else "REJECTED",
        "evaluations": results,
    }


def evaluate_transfer_scenario(manifest: dict[str, Any]) -> dict[str, Any]:
    """Evaluates E-POL-TF-001 and E-POL-TF-002 on the tech transfer scenario."""
    meta = manifest.get("project_metadata", {})
    alloc = manifest.get("revenue_allocation_plan", {})

    results = []

    # Check E-POL-TF-001: 团队奖励不得低于 70%
    ratio = alloc.get("team_incentive_ratio", 0.0)
    if ratio >= 0.70:
        results.append({
            "rule_id": "E-POL-TF-001",
            "name": "科技成果转化科研团队收益分配红线",
            "verdict": "PASS",
            "detail": f"科研团队收益分配比例达到 {int(ratio * 100)}% (法定红线 >= 70%)，合法合规保障科学家权益。",
        })
    else:
        results.append({
            "rule_id": "E-POL-TF-001",
            "name": "科技成果转化科研团队收益分配红线",
            "verdict": "BLOCK",
            "detail": f"团队分配比例 {int(ratio * 100)}% 低于法定红线 70%。",
        })

    # Check E-POL-TF-002: TRL >= 6
    trl = meta.get("trl_level", 0)
    if trl >= 6:
        results.append({
            "rule_id": "E-POL-TF-002",
            "name": "产业化项目技术成熟度 (TRL) 准入审查",
            "verdict": "PASS",
            "detail": f"项目技术成熟度评估达到 TRL {trl} (准入要求 >= 6)，具备原型在真实环境中的有效性验证。",
        })
    else:
        results.append({
            "rule_id": "E-POL-TF-002",
            "name": "产业化项目技术成熟度 (TRL) 准入审查",
            "verdict": "WARN",
            "detail": f"项目技术成熟度 TRL {trl} 偏低，建议增加中试验证。",
        })

    all_passed = all(r["verdict"] in ("PASS", "WARN") for r in results)
    return {
        "scenario_id": manifest.get("scenario_id"),
        "domain": manifest.get("domain"),
        "title": manifest.get("title"),
        "status": "APPROVED" if all_passed else "REJECTED",
        "evaluations": results,
    }


def publish_to_bus(event_payload: dict[str, Any]):
    """Attempts to publish scenario evaluation event to Agora 2.0 Bus."""
    _refuse_retired_surface("real-scenario-runner.publish_to_bus")
    try:
        req = urllib.request.Request(
            BUS_URL,
            data=json.dumps(event_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def record_resident_decision(scenario_eval: dict[str, Any]) -> tuple[Path, Path]:
    """Generates both JSON evolution proposal and Markdown decision proposal."""
    _refuse_retired_surface("real-scenario-runner.record_resident_decision")
    ts_compact = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sc_id = scenario_eval["scenario_id"]

    # 1. JSON Proposal
    json_dir = _ROOT / ".omo" / "_knowledge" / "evolution-proposals"
    json_dir.mkdir(parents=True, exist_ok=True)
    slug = f"scenario-{sc_id.lower()}"
    json_file = json_dir / f"decision-{ts_compact}-{slug}.json"

    proposal_data = {
        "schema_version": "resident-decision/v1",
        "proposal_id": f"prop-{ts_compact}-{sc_id}",
        "proposal_count": len(scenario_eval["evaluations"]),
        "trigger_event": {
            "event_type": "DomainScenarioEvaluated",
            "trace_id": f"trace-{sc_id}",
            "scenario_id": sc_id,
            "domain": scenario_eval["domain"],
            "occurred_at": ts_iso,
        },
        "proposals": [
            {
                "level": "L3_STRATEGIC",
                "type": "domain_policy_compliance",
                "action": "AUTHORIZE_WORKFLOW_EXECUTION" if scenario_eval["status"] == "APPROVED" else "REQUIRE_REVISION",
                "severity": "info" if scenario_eval["status"] == "APPROVED" else "high",
                "proposal": f"Domain policy evaluation for {scenario_eval['title']}: {scenario_eval['status']}",
            }
        ],
        "evaluations": scenario_eval["evaluations"],
    }

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(proposal_data, f, indent=2, ensure_ascii=False)

    # 2. Markdown View
    md_dir = _ROOT / ".omo" / "_knowledge" / "decision-proposals"
    md_dir.mkdir(parents=True, exist_ok=True)
    md_file = md_dir / f"decision-{ts_compact}-{sc_id}.md"

    md_content = f"""---
id: DEC-{ts_compact}-{sc_id}
status: accepted
lifecycle: proposal
owner: resident
created: '{ts_iso[:10]}'
last-reviewed: '{ts_iso[:10]}'
scenario_id: {sc_id}
domain: {scenario_eval['domain']}
verdict: {scenario_eval['status']}
---

# 决策提案: {scenario_eval['title']}

> 提案 ID: `DEC-{ts_compact}-{sc_id}`  
> 领域: `{scenario_eval['domain']}`  
> 审查时间: `{ts_iso}`  
> 裁决结论: **{scenario_eval['status']}**

## 1. 业务场景概述
- **场景标识**: `{sc_id}`
- **业务事项**: {scenario_eval['title']}

## 2. Policy-as-Code 规则审查明细
"""
    for e in scenario_eval["evaluations"]:
        badge = "✅ PASS" if e["verdict"] == "PASS" else ("⚠️ WARN" if e["verdict"] == "WARN" else "❌ BLOCK")
        md_content += f"""
### {badge} [{e['rule_id']}] {e['name']}
- **审查意见**: {e['detail']}
"""

    md_content += f"""
## 3. 自治决策建议
- **执行动作**: `{proposal_data['proposals'][0]['action']}`
- **置信度**: 100% (基于确定性策略引擎评估)
"""

    with open(md_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    return json_file, md_file


def run_all_scenarios(scenario_dir: Path) -> int:
    _refuse_retired_surface("real-scenario-runner.run_all_scenarios")
    scenario_files = list(scenario_dir.glob("*.yaml")) + list(scenario_dir.glob("*.yml"))
    if not scenario_files:
        print(f"No scenario files found in {scenario_dir}")
        return 1

    print(f"\n🚀 正在执行真实业务场景全链路审查 (共 {len(scenario_files)} 个场景)...\n")

    for sf in scenario_files:
        manifest = load_scenario(sf)
        domain = manifest.get("domain", "")

        if domain == "work-weijian":
            eval_res = evaluate_weijian_scenario(manifest)
        elif domain == "work-transfer":
            eval_res = evaluate_transfer_scenario(manifest)
        else:
            print(f"⏭️ 跳过未支持领域的场景: {sf.name} ({domain})")
            continue

        # Publish to Agora bus
        event_payload = {
            "topic": "domain.scenario.evaluated",
            "sender": "scenario-runner",
            "scenario_id": eval_res["scenario_id"],
            "status": eval_res["status"],
            "timestamp": time.time(),
        }
        bus_ok = publish_to_bus(event_payload)
        bus_tag = "📡 Bus Published" if bus_ok else "⚠️ Bus Offline"

        # Record Resident Decision
        json_p, md_p = record_resident_decision(eval_res)

        print(f"╭─ 🏢 业务场景审查: {eval_res['title']} ───────────────")
        print(f"│ 场景 ID: {eval_res['scenario_id']}   领域: {eval_res['domain']}   [{bus_tag}]")
        print(f"│ 终审裁决: 【{eval_res['status']}】")
        for e in eval_res["evaluations"]:
            icon = "✅" if e["verdict"] == "PASS" else ("⚠️" if e["verdict"] == "WARN" else "❌")
            print(f"│   {icon} [{e['rule_id']}] {e['name']}: {e['detail']}")
        print(f"│ 决策落盘: {md_p.relative_to(_ROOT)}")
        print("╰─────────────────────────────────────────────────────────────────\n")

    return 0


def main():
    _refuse_retired_surface("real-scenario-runner")
    parser = argparse.ArgumentParser(description="Real-World Domain Scenario Runner (ADR-0427)")
    parser.add_argument(
        "--dir",
        type=Path,
        default=_ROOT / "spaces" / "domain-scenarios",
        help="Directory containing domain scenario YAML manifests",
    )
    args = parser.parse_args()

    sys.exit(run_all_scenarios(args.dir))


if __name__ == "__main__":
    main()
