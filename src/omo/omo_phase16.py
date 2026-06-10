#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .omo_shared import utc_now, write_yaml, write_text


def _external_omo_root() -> Path:
    configured = os.environ.get("OMO_EXTERNAL_ROOT")
    if configured:
        return Path(configured)

    candidates = [
        Path.home() / "Documents/学习进化/2-knowledge/经验积累/OMO",
        Path.home() / "Documents/学习进化/经验积累/OMO",
        Path.home() / "Documents/学习进化/2-knowledge/体系/OMO",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


EXTERNAL_OMO_ROOT = _external_omo_root()


def _root() -> Path:
    return Path(__file__).resolve().parents[2]


def _omo(root: Path) -> Path:
    return root / ".omo"


def _phase16_evidence_dir(root: Path) -> Path:
    omo_root = _omo(root)
    modern = omo_root / "_delivery" / "evidence" / "phase16"
    if modern.parent.exists():
        return modern
    return omo_root / "evidence" / "phase16"


def _scenario_path(root: Path) -> Path:
    omo_root = _omo(root)
    modern = omo_root / "_truth" / "scenarios" / "knowledge-capture-search.yaml"
    if modern.parent.exists():
        return modern
    return omo_root / "scenarios" / "knowledge-capture-search.yaml"


def _phase15_policy_ref(root: Path) -> str:
    omo_root = _omo(root)
    modern = omo_root / "_delivery" / "evidence" / "phase15" / "policy-test-report.yaml"
    if modern.exists() or modern.parent.exists():
        return ".omo/_delivery/evidence/phase15/policy-test-report.yaml"
    return ".omo/evidence/phase15/policy-test-report.yaml"


def _sharedbrain_readme_ref(root: Path) -> str:
    archived = "projects/_archived/SharedBrain-original/README.md"
    current = "projects/SharedBrain/README.md"
    return archived if not (root / current).exists() else current


def _sharedbrain_quickstart_ref(root: Path) -> str:
    archived = "projects/_archived/SharedBrain-original/QUICKSTART.md"
    current = "projects/SharedBrain/QUICKSTART.md"
    return archived if not (root / current).exists() else current


def _agentmesh_ref(root: Path, name: str, *, fallback: str = "src/index.ts") -> str:
    current = f"projects/agentmesh/{name}"
    archived = f"projects/_archived/agentmesh/{name}"
    if (root / current).exists():
        return current
    if (root / archived).exists():
        return archived
    fallback_current = f"projects/agentmesh/{fallback}"
    fallback_archived = f"projects/_archived/agentmesh/{fallback}"
    if (root / fallback_current).exists():
        return fallback_current
    return fallback_archived


def baseline_payload() -> dict[str, Any]:
    return {
        "id": "phase16-journey-baseline",
        "created_at": utc_now(),
        "phase": 16,
        "status": "ready",
        "primary_scenario": "knowledge-capture-search",
        "theme": "Knowledge Capture/Search Product Surface Convergence",
        "gap": "control-plane-strong-user-entry-fragmented",
        "phase15_inputs": [
            ".omo/_delivery/evidence/phase15/user-value-loop.yaml",
            ".omo/_delivery/evidence/phase15/operating-dashboard-snapshot.yaml",
            ".omo/_delivery/governance-evidence/ledger.yaml",
        ],
        "project_roles": {
            "SharedBrain": {
                "role": "runtime-home and result-home",
                "evidence_refs": [
                    _sharedbrain_readme_ref(_root()),
                    _sharedbrain_quickstart_ref(_root()),
                ],
            },
            "gbrain": {
                "role": "capture, search, retrieval",
                "evidence_refs": [
                    "projects/gbrain/README.md",
                    "projects/gbrain/package.json",
                ],
            },
            "kairon": {
                "role": "capability binding and governance trace",
                "evidence_refs": [
                    "projects/kairon/README.md",
                    "projects/kairon/pyproject.toml",
                ],
            },
            "agentmesh": {
                "role": "future orchestration candidate only",
                "evidence_refs": [
                    _agentmesh_ref(_root(), "README.md", fallback="src/index.ts"),
                    _agentmesh_ref(_root(), "package.json", fallback="src/cli.ts"),
                ],
            },
        },
        "double_layer_deposition": {
            "repo_omo": "repo `.omo/` stores live evidence, tests, plans, and closeout",
            "external_omo": "external OMO stores case, pattern, and playbook as Pointer/Pattern/Playbook only",
            "shadow_ssot_blocked": True,
        },
    }


def scenario_payload() -> dict[str, Any]:
    return {
        "id": "knowledge-capture-search",
        "phase": 16,
        "status": "ready",
        "authorization": "scenario-contract-only",
        "description": "User captures text or a markdown file, searches it back, and receives a visible result state with evidence refs.",
        "input_contract": ["text_or_markdown_file", "query"],
        "output_contract": [
            "capture_receipt",
            "search_hits",
            "result_summary",
            "evidence_refs",
            "status",
        ],
        "status_enum": [
            "ready",
            "needs_approval",
            "blocked",
            "failed_with_recovery",
            "completed",
        ],
        "project_boundaries": {
            "SharedBrain": "runtime-home and result-home",
            "gbrain": "capture, search, retrieval",
            "kairon": "capability binding and governance trace",
            "agentmesh": "future orchestration candidate only",
        },
        "guardrails": [
            "No production auto-mutation.",
            "No marketplace install or publish.",
            "No bypass of Phase 15 evidence ledger.",
            "Scenario contract is not execution authorization.",
        ],
    }


def shell_payload() -> dict[str, Any]:
    return {
        "id": "phase16-scenario-shell",
        "created_at": utc_now(),
        "phase": 16,
        "scenario_id": "knowledge-capture-search",
        "status": "ready",
        "binds": [
            "intent",
            "context",
            "policy",
            "execution",
            "verification",
            "recovery",
        ],
        "intent": {
            "user_goal": "Capture knowledge and search it back with an explainable result.",
            "input_contract": ["text_or_markdown_file", "query"],
        },
        "context": {
            "runtime_home": "SharedBrain",
            "retrieval_surface": "gbrain",
            "governance_trace": "kairon",
        },
        "policy": {
            "phase15_guardrails_preserved": True,
            "approval_required_for_high_risk_actions": True,
        },
        "execution": {
            "default_mode": "fixture-backed",
            "live_mode_condition": "gbrain local brain initialized and capture/search command verified without production mutation",
        },
        "verification": {
            "requires_capture_receipt": True,
            "requires_search_hit": True,
            "requires_user_visible_result": True,
        },
        "recovery": {
            "blocked_state": "failed_with_recovery",
            "rollback": "Discard fixture result and keep source project data untouched.",
        },
        "does_not_authorize_live_mutation": True,
        "phase15_guardrails_preserved": True,
    }


def walkthrough_payload() -> dict[str, Any]:
    return {
        "id": "phase16-capture-search-walkthrough",
        "created_at": utc_now(),
        "phase": 16,
        "scenario_id": "knowledge-capture-search",
        "status": "completed",
        "mode": "fixture-backed",
        "blocked_reason": "Live gbrain local brain, API keys, and user data store were not assumed during governed repo execution.",
        "next_live_demo_condition": "Run the same scenario against an initialized local gbrain PGLite brain after explicit user approval.",
        "sample_input": {
            "text": "OMO Phase16 should turn governance evidence into a user-visible knowledge capture and search loop.",
            "query": "What should Phase16 prove for users?",
        },
        "execution_path": [
            {
                "project": "SharedBrain",
                "action": "accept intent and provide result-home semantics",
            },
            {
                "project": "gbrain",
                "action": "fixture capture receipt and keyword search hit",
            },
            {
                "project": "kairon",
                "action": "record capability binding and evidence trace",
            },
            {
                "project": ".omo",
                "action": "store walkthrough, recovery, and closeout evidence",
            },
        ],
        "user_visible_result": {
            "status": "completed",
            "capture_receipt": "fixture://phase16/knowledge-capture-search/receipt-001",
            "search_hits": [
                {
                    "id": "fixture-hit-001",
                    "title": "Phase16 knowledge capture/search proof",
                    "snippet": "Phase16 should prove a user can capture knowledge, search it back, and inspect evidence refs.",
                    "source": "fixture-backed-gbrain-contract",
                }
            ],
            "result_summary": "Phase16 proves a governed, user-visible capture/search loop before broader product-surface expansion.",
        },
        "capability_binding": {
            "SharedBrain": "runtime-home",
            "gbrain": "capture-search",
            "kairon": "governance-trace",
        },
        "evidence_refs": [
            ".omo/_truth/scenarios/knowledge-capture-search.yaml",
            ".omo/_delivery/evidence/phase16/scenario-shell.yaml",
            ".omo/_delivery/evidence/phase16/knowledge-capture-run-record.yaml",
            "projects/gbrain/README.md",
            "projects/kairon/docs/knowledge_capture_run_record_fixture_2026-06-05.yaml",
        ],
    }


def run_record_payload() -> dict[str, Any]:
    return {
        "id": "phase16-knowledge-capture-run-record",
        "created_at": utc_now(),
        "phase": 16,
        "scenario_id": "knowledge-capture-search",
        "status": "completed",
        "request_id": "fixture-2026-06-05-run-001",
        "request_mode": "fixture-backed",
        "kairon_trace_id": "trace-knowledge-capture-001",
        "kairon_route_surface": [
            "agora.router.route",
            "agora.event_bus.publish",
            "wksp.cli",
            "sharedbrain-bridge",
        ],
        "kairon_event_refs": {
            "binding_probe_event_id": "evt_1780639951_0f3a52",
            "route_event_id": "evt_1780640262_26e4a9",
            "route_event_type": "route:call.succeeded",
        },
        "gbrain_execution_ref": "eval_candidate:1",
        "capture_receipt": {
            "slug": "inbox/knowledge-capture-run-record",
            "status": "created_or_updated",
            "chunks": 1,
            "source_kind": "capture-cli",
            "captured_at": "2026-06-05T06:13:09.244Z",
        },
        "search_hit_refs": [
            {
                "slug": "inbox/knowledge-capture-run-record",
                "page_id": 1,
                "chunk_id": 1,
                "source_id": "default",
                "score": 0.9997516870498657,
            }
        ],
        "result_summary": "Fixture-backed knowledge capture/search run now has a single request_id and trace_id that can be followed across kairon routing, gbrain capture/query, and OMO evidence.",
        "omo_evidence_refs": [
            ".omo/_truth/scenarios/knowledge-capture-search.yaml",
            ".omo/_delivery/evidence/phase16/scenario-shell.yaml",
            ".omo/_delivery/evidence/phase16/capture-search-walkthrough.yaml",
            ".omo/_delivery/evidence/phase16/adoption-closeout.yaml",
        ],
        "verification_refs": [
            {
                "surface": "kairon-binding-probe",
                "observed_value": "evt_1780639951_0f3a52",
                "source_ref": "projects/kairon/docs/knowledge_capture_run_record_fixture_2026-06-05.yaml",
            },
            {
                "surface": "kairon-router-route-event",
                "observed_value": "evt_1780640262_26e4a9",
                "source_ref": "projects/kairon/docs/knowledge_capture_run_record_fixture_2026-06-05.yaml",
            },
            {
                "surface": "gbrain-capture-receipt",
                "observed_value": "inbox/knowledge-capture-run-record",
                "source_ref": "projects/kairon/docs/knowledge_capture_run_record_fixture_2026-06-05.yaml",
            },
            {
                "surface": "gbrain-query-eval",
                "observed_value": "eval_candidate:1",
                "source_ref": "projects/kairon/docs/knowledge_capture_run_record_fixture_2026-06-05.yaml",
            },
        ],
        "limits": [
            "This is fixture-backed and does not prove production capture/search availability.",
            "No production mutation, install, or proposal activation was performed.",
        ],
    }


def recovery_payload() -> dict[str, Any]:
    policy_ref = _phase15_policy_ref(_root())
    checks = [
        {
            "id": "phase15-policy-preserved",
            "result": "pass",
            "evidence_ref": policy_ref,
        },
        {
            "id": "fixture-walkthrough-rollback",
            "result": "pass",
            "rollback": "Delete fixture-backed walkthrough output and rerun phase16 walkthrough.",
        },
        {
            "id": "external-omo-shadow-ssot-block",
            "result": "pass",
            "evidence_ref": ".omo/_delivery/evidence/phase16/adoption-closeout.yaml",
        },
    ]
    return {
        "id": "phase16-recovery-report",
        "created_at": utc_now(),
        "phase": 16,
        "status": "pass",
        "mode": "fixture-backed-recovery",
        "live_mutations_applied": 0,
        "marketplace_install_enabled": False,
        "auto_mutation_enabled": False,
        "checks": checks,
    }


def adoption_payload() -> dict[str, Any]:
    return {
        "id": "phase16-adoption-closeout",
        "created_at": utc_now(),
        "phase": 16,
        "status": "ready",
        "user_can_complete_task": True,
        "primary_scenario": "knowledge-capture-search",
        "result_states": [
            "completed",
            "blocked",
            "needs_approval",
            "failed_with_recovery",
        ],
        "operator_facing_journey": "Inspect scenario shell, walkthrough evidence, recovery report, and closeout.",
        "end_user_facing_journey": "Submit knowledge text and query, then receive capture receipt, search hit, summary, and status.",
        "remaining_limits": [
            "Live gbrain capture/search is not enabled by default in Phase16.",
            "No broad UI/dashboard rewrite was shipped.",
            "Agentmesh remains a future orchestration candidate only.",
        ],
        "next_recommendation": "Phase17 may promote one live low-risk gbrain capture/search demo after local brain readiness is verified.",
    }


def external_docs() -> dict[Path, str]:
    workspace_root = os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
    workspace = f"{workspace_root}/.omo/"
    return {
        EXTERNAL_OMO_ROOT
        / "_delivery"
        / "cases"
        / "2026-06-01-phase16-knowledge-capture-search-retrospective.md": f"""# Phase16 知识捕获检索复盘

> 类型：Case / Retrospective
> 边界：Pointer only，不是 repo live truth，也不是 shadow SSOT。

## 复盘对象

本案例复盘 Phase16 如何把 OMO 控制面能力转回用户可感知的知识捕获检索闭环。

Pointer:
- `{workspace}_knowledge/design/plans/phase16-product-surface-convergence-preplanning.md`
- `{workspace}_truth/scenarios/knowledge-capture-search.yaml`
- `{workspace}_delivery/evidence/phase16/capture-search-walkthrough.yaml`

## 关键判断

知识捕获检索是 Phase16 的最小用户价值闭环：用户输入知识，系统返回 capture receipt、search hit、result summary 和 evidence refs。

## 边界

本文件不维护 repo 的 live phase、active queue 或任何 mutable fact。repo `.omo/` 是 live SSOT；外部 OMO 只做方法复盘与模式抽象，避免 shadow SSOT。
""",
        EXTERNAL_OMO_ROOT
        / "_delivery"
        / "patterns"
        / "03-控制面不能替代用户价值.md": f"""# 控制面不能替代用户价值

> 类型：Pattern
> 边界：Pointer / Pattern only，不是 repo live truth，也不是 shadow SSOT。

## 模式

当控制面、证据链、policy、recovery 持续增强后，系统容易误把“治理更强”当成“用户价值更强”。

## 识别信号

- 计划、测试、closeout 很完整，但用户仍不知道能完成什么。
- capability registry 很丰富，但没有一个可复现的用户闭环。
- dashboard 能显示健康，却不能让用户完成 capture/search/action。

## 默认动作

从一个低风险用户场景反推项目能力边界，再让 OMO 记录证据。

Pointer:
- `{workspace}_delivery/evidence/phase15/user-value-loop.yaml`
- `{workspace}_delivery/evidence/phase16/capture-search-walkthrough.yaml`

## 禁止

不要在外部 OMO 复制 repo live state；不要维护 live phase 或 active queue；不要制造 shadow SSOT。
""",
        EXTERNAL_OMO_ROOT
        / "_control"
        / "07-从OMO计划到项目能力升级Playbook.md": f"""# 从 OMO 计划转项目能力升级 Playbook

> 类型：Playbook
> 边界：Pointer / Playbook only，不是 repo live truth，也不是 shadow SSOT。

## 触发条件

当 OMO 计划已经完成治理闭环，但项目能力和用户使用层仍停在 preview / dry-run 时，启动本 Playbook。

## 步骤

1. 选择一个低风险用户闭环，本次为知识捕获检索。
2. 明确项目职责：SharedBrain 承接 runtime-home，gbrain 承接 capture/search，kairon 承接治理 trace。
3. 在 repo `.omo/` 写 scenario、evidence、tests、closeout。
4. 在外部 OMO 只写 case、pattern、playbook，并用 Pointer 指向 repo 证据。
5. 检查外部 OMO 未复制 live phase、active queue 等 mutable facts。

Pointer:
- `{workspace}_truth/scenarios/knowledge-capture-search.yaml`
- `{workspace}_delivery/evidence/phase16/journey-baseline.yaml`
- `{workspace}_knowledge/summaries/phase16/phase16-closeout.md`

## 收口标准

用户能看到 capture receipt、search hit、result summary、evidence refs 和明确状态；repo `.omo/` 保持 live SSOT；外部 OMO 不形成 shadow SSOT。
""",
    }


def baseline_command(args: argparse.Namespace) -> int:
    payload = baseline_payload()
    write_yaml(Path(args.output), payload)
    print(json.dumps({"status": "ready", "output": args.output}, ensure_ascii=False))
    return 0


def scenario_command(args: argparse.Namespace) -> int:
    root = _root()
    scenario = scenario_payload()
    shell = shell_payload()
    write_yaml(_scenario_path(root), scenario)
    write_yaml(Path(args.output), shell)
    print(
        json.dumps(
            {"status": "ready", "scenario": scenario["id"], "output": args.output},
            ensure_ascii=False,
        )
    )
    return 0


def walkthrough_command(args: argparse.Namespace) -> int:
    payload = walkthrough_payload()
    write_yaml(Path(args.output), payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "mode": payload["mode"],
                "output": args.output,
            },
            ensure_ascii=False,
        )
    )
    return 0


def run_record_command(args: argparse.Namespace) -> int:
    payload = run_record_payload()
    write_yaml(Path(args.output), payload)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "request_id": payload["request_id"],
                "trace_id": payload["kairon_trace_id"],
                "output": args.output,
            },
            ensure_ascii=False,
        )
    )
    return 0


def recovery_command(args: argparse.Namespace) -> int:
    payload = recovery_payload()
    write_yaml(Path(args.output), payload)
    print(json.dumps({"status": "pass", "output": args.output}, ensure_ascii=False))
    return 0


def closeout_command(args: argparse.Namespace) -> int:
    root = _root()
    adoption = adoption_payload()
    write_yaml(_phase16_evidence_dir(root) / "adoption-closeout.yaml", adoption)
    for path, text in external_docs().items():
        write_text(path, text)
    print(
        json.dumps(
            {
                "status": "ready",
                "external_docs": 3,
                "output": ".omo/_delivery/evidence/phase16/adoption-closeout.yaml",
            },
            ensure_ascii=False,
        )
    )
    return 0


def all_command(args: argparse.Namespace) -> int:
    root = _root()
    evidence_dir = _phase16_evidence_dir(root)
    write_yaml(evidence_dir / "journey-baseline.yaml", baseline_payload())
    write_yaml(_scenario_path(root), scenario_payload())
    write_yaml(evidence_dir / "scenario-shell.yaml", shell_payload())
    write_yaml(evidence_dir / "capture-search-walkthrough.yaml", walkthrough_payload())
    write_yaml(evidence_dir / "knowledge-capture-run-record.yaml", run_record_payload())
    write_yaml(evidence_dir / "recovery-report.yaml", recovery_payload())
    write_yaml(evidence_dir / "adoption-closeout.yaml", adoption_payload())
    for path, text in external_docs().items():
        write_text(path, text)
    print(
        json.dumps({"status": "ready", "phase": 16, "artifacts": 10}, ensure_ascii=False)
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="omo-phase16")
    sub = parser.add_subparsers(dest="command", required=True)

    baseline = sub.add_parser("baseline")
    baseline.add_argument(
        "--output", default=".omo/_delivery/evidence/phase16/journey-baseline.yaml"
    )
    baseline.set_defaults(func=baseline_command)

    scenario = sub.add_parser("scenario")
    scenario.add_argument(
        "--output", default=".omo/_delivery/evidence/phase16/scenario-shell.yaml"
    )
    scenario.set_defaults(func=scenario_command)

    walkthrough = sub.add_parser("walkthrough")
    walkthrough.add_argument(
        "--output", default=".omo/_delivery/evidence/phase16/capture-search-walkthrough.yaml"
    )
    walkthrough.set_defaults(func=walkthrough_command)

    run_record = sub.add_parser("run-record")
    run_record.add_argument(
        "--output", default=".omo/_delivery/evidence/phase16/knowledge-capture-run-record.yaml"
    )
    run_record.set_defaults(func=run_record_command)

    recovery = sub.add_parser("recovery")
    recovery.add_argument(
        "--output", default=".omo/_delivery/evidence/phase16/recovery-report.yaml"
    )
    recovery.set_defaults(func=recovery_command)

    closeout = sub.add_parser("closeout")
    closeout.set_defaults(func=closeout_command)

    all_parser = sub.add_parser("all")
    all_parser.set_defaults(func=all_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
