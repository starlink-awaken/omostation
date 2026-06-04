from __future__ import annotations

from pathlib import Path

import yaml
from scripts.omo_task_schema import validate_task_file


WORKSPACE = Path(__file__).resolve().parents[2]
OMO = WORKSPACE / ".omo"
TASKS = OMO / "tasks"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _task_files(group: str) -> list[Path]:
    return sorted((TASKS / group).glob("*.yaml"))


def test_state_counts_match_task_directories_and_do_not_use_active_extras_shadow_queue():
    state = _load_yaml(OMO / "state" / "system.yaml")

    active_count = len(_task_files("active"))
    planned_count = len(_task_files("planned"))
    blocked_count = len(_task_files("blocked"))
    done_count = len(_task_files("done"))

    assert state["active_tasks"] == active_count
    assert state["planned_tasks"] == planned_count
    assert state["blocked_tasks"] == blocked_count
    assert state["completed_tasks"] == done_count
    assert state["total_tasks"] == active_count + planned_count + blocked_count + done_count
    assert "active_extras" not in state


def test_active_task_schema_includes_worker_run_and_knowledge_links():
    required_fields = {
        "dispatch_id",
        "run_ref",
        "approval_ref",
        "review_ref",
        "knowledge_refs",
        "handoff_refs",
    }

    for task_file in _task_files("active"):
        task = _load_yaml(task_file)
        missing = required_fields - task.keys()
        assert not missing, f"{task_file.name} missing {sorted(missing)}"
        assert isinstance(task["knowledge_refs"], list)
        assert isinstance(task["handoff_refs"], list)


def test_active_l2_l3_tasks_carry_approval_ref():
    for task_file in _task_files("active"):
        task = _load_yaml(task_file)
        if task.get("allowed_operation_level") in {"L2", "L3"}:
            assert task.get("approval_ref"), f"{task_file.name} missing approval_ref"


def test_all_active_tasks_pass_current_task_schema():
    failures: dict[str, list[str]] = {}

    for task_file in _task_files("active"):
        errors = validate_task_file(task_file)
        if errors:
            failures[task_file.name] = errors

    assert not failures, failures


def test_future_phase_pending_packets_in_active_require_promotion_handoff_ref():
    goals = _load_yaml(OMO / "goals" / "current.yaml")
    current_phase = goals["phase"]
    failures = []

    for task_file in _task_files("active"):
        task = _load_yaml(task_file)
        if task.get("phase", 0) <= current_phase or task.get("status") != "pending":
            continue
        has_promotion_ref = any("-promotion-" in ref for ref in task.get("handoff_refs", []))
        if not has_promotion_ref:
            failures.append(task["id"])

    assert failures == [], failures


def test_planned_queue_contains_future_backlog_packets():
    planned_ids = [_load_yaml(path)["id"] for path in _task_files("planned")]

    assert "P18-W1-NEURAL-CENTER" in planned_ids
    assert "P25-W2-DOCS-DEBT-CLOSURE" in planned_ids


def test_coordinator_preclaims_worker_tasks_before_execution():
    tasks_readme = (TASKS / "README.md").read_text(encoding="utf-8")
    worker_standard = (
        OMO / "standards" / "agent-cli-worker-collaboration.md"
    ).read_text(encoding="utf-8")

    assert "coordinator 预占 lease" in tasks_readme
    assert "Coordinator preclaims the task lease before worker execution." in worker_standard
    assert "Worker claims the task by setting:" not in worker_standard


def test_worker_templates_include_approval_records_and_lease_terms():
    approval_template = OMO / "workers" / "templates" / "worker-approval-record.yaml"
    assert approval_template.exists()

    envelope = _load_yaml(OMO / "workers" / "templates" / "worker-task-envelope.yaml")
    dispatch = _load_yaml(OMO / "workers" / "templates" / "worker-dispatch-record.yaml")

    assert "approval_ref" in envelope["gates"]
    assert "run_ref" in envelope
    assert "knowledge_refs" in envelope
    assert "handoff_refs" in envelope

    assert "approval_ref" in dispatch["execution"]
    assert "run_ref" in dispatch
    assert "warning_after_seconds" in dispatch["lease"]
    assert "lease_expired_after_seconds" in dispatch["lease"]
    assert "stale_after_seconds" not in dispatch["lease"]
    assert "zombie_after_seconds" not in dispatch["lease"]


def test_index_covers_core_control_plane_entrypoints_and_has_no_broken_cli_mcp_doc_link():
    index_text = (OMO / "INDEX.md").read_text(encoding="utf-8")

    required_refs = [
        "[CONSISTENCY-CHECK.md](CONSISTENCY-CHECK.md)",
        "[MASTER-BLUEPRINT.md](MASTER-BLUEPRINT.md)",
        "[plans/README.md](plans/README.md)",
        "[workers/README.md](workers/README.md)",
        "[tasks/README.md](tasks/README.md)",
    ]

    for ref in required_refs:
        assert ref in index_text

    assert "[CLI-MCP-SPEC.md](standards/CLI-MCP-SPEC.md)" not in index_text


def test_state_document_is_positioned_as_architecture_history_not_live_status_source():
    index_text = (OMO / "INDEX.md").read_text(encoding="utf-8")
    state_text = (OMO / "STATE.md").read_text(encoding="utf-8")

    assert "架构历史与演进里程碑（legacy summary）" in index_text
    assert "当前运行状态请以 `.omo/state/system.yaml` 与 `.omo/goals/current.yaml` 为准。" in state_text
    assert "Phase 2 核心完成" not in state_text


def test_task_and_plan_docs_embed_required_standard_references():
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")
    plans_text = (OMO / "plans" / "README.md").read_text(encoding="utf-8")

    assert "planning-blueprint-delivery-test-standard.md" in tasks_text
    assert "agent-cli-worker-collaboration.md" in tasks_text
    assert "planning-blueprint-delivery-test-standard.md" in plans_text
    assert "phase2-full-execution-go-no-go.md" in plans_text


def test_task_docs_distinguish_active_and_planned_queues():
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    index_text = (OMO / "INDEX.md").read_text(encoding="utf-8")
    doc_arch_text = (OMO / "DOC-ARCH.md").read_text(encoding="utf-8")
    tests_text = (OMO / "tests" / "README.md").read_text(encoding="utf-8")

    assert "tasks/planned/" in tasks_text
    assert "strict-active-only" in agent_text
    assert "[tasks/planned/](tasks/planned/)" in index_text
    assert "planned/" in doc_arch_text
    assert "planned queue" in tests_text


def test_task_docs_describe_planned_to_active_promotion_workflow():
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    index_text = (OMO / "INDEX.md").read_text(encoding="utf-8")

    assert "promote-eval" in tasks_text
    assert "promote-apply" in tasks_text
    assert "handoff_refs" in tasks_text
    assert "promote-apply" in agent_text
    assert "planned packets become active only through promotion" in index_text


def test_worker_docs_describe_promotion_history_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")

    assert "promotion-history" in workers_text
    assert ".omo/workers/promotion/current.yaml" in workers_text
    assert "promotion/current.yaml" in agent_text


def test_worker_docs_describe_promotion_readiness_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-readiness" in workers_text
    assert ".omo/workers/promotion/readiness.yaml" in workers_text
    assert "promotion/readiness.yaml" in agent_text
    assert "promotion-readiness" in tasks_text


def test_worker_docs_distinguish_backlog_presence_approval_from_promotion_approval():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "worker-promotion-approval.yaml" in workers_text
    assert "does not authorize promotion" in agent_text
    assert "approval_invalid" in tasks_text


def test_worker_docs_describe_promotion_request_workflow():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-request-approval" in workers_text
    assert "promotion-request-approval" in agent_text
    assert "promotion-request-approval" in tasks_text


def test_worker_docs_describe_promotion_approval_closure_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-approval-status" in workers_text
    assert "promotion-approval-status" in agent_text
    assert "promotion-approval-status" in tasks_text
    assert "omo_governance.py approve" in workers_text


def test_worker_docs_describe_promotion_approval_history_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-approval-history" in workers_text
    assert "promotion/approvals/history/current.yaml" in workers_text
    assert "promotion-approval-history" in agent_text
    assert "promotion-approval-history" in tasks_text


def test_worker_docs_describe_promotion_approval_analytics_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "promotion-approval-analytics" in workers_text
    assert "promotion/approvals/analytics/current.yaml" in workers_text
    assert "promotion-approval-analytics" in agent_text
    assert "promotion-approval-analytics" in tasks_text


def test_worker_docs_describe_governance_overlay_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "governance-overlay-status" in workers_text
    assert "workers/governance-overlay/current.yaml" in workers_text
    assert "governance overlay" in agent_text.lower()
    assert "governance overlay" in tasks_text.lower()


def test_worker_docs_describe_governance_overlay_run_next_surface():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "governance-overlay-run-next" in workers_text
    assert "governance-overlay-run-next" in agent_text
    assert "governance-overlay-run-next" in tasks_text


def test_worker_docs_describe_governance_overlay_active_item_continuation():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")

    assert "continue_active" in workers_text
    assert "close a finished roadmap item and advance control state" in workers_text
    assert "current active roadmap item" in agent_text


def test_worker_docs_describe_governance_overlay_dispatch_and_verify_actions():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "dispatch:<TASK_ID>" in workers_text
    assert "verify:<TASK_ID>" in workers_text
    assert "dispatch or verify the current active roadmap item" in agent_text
    assert "dispatch:<TASK_ID>" in tasks_text


def test_worker_docs_describe_governance_overlay_launch_contract_actions():
    workers_text = (OMO / "workers" / "README.md").read_text(encoding="utf-8")
    agent_text = (OMO / "_knowledge/usage/AGENT.md").read_text(encoding="utf-8")
    tasks_text = (OMO / "tasks" / "README.md").read_text(encoding="utf-8")

    assert "contract:<TASK_ID>" in workers_text
    assert "launch:<TASK_ID>" in workers_text
    assert "autonomous launch requires explicit task deliverables" in agent_text
    assert "contract:<TASK_ID>" in tasks_text
    assert "contract-declare-deliverables" in workers_text
    assert "contract-declare-deliverables" in agent_text
    assert "contract-declare-deliverables" in tasks_text


def test_standards_registry_tracks_active_and_legacy_merged_docs():
    standards_readme = (OMO / "standards" / "README.md").read_text(encoding="utf-8")

    assert "mcp-tool-and-transport-standard.md" in standards_readme
    assert "operation-levels.md" in standards_readme
    assert "MCP_STANDARDS.md" in standards_readme
    assert "mcp-transport.md" in standards_readme
    assert "operation-level-rollout-plan.md" in standards_readme
    assert "post-phase1-governance-and-phase2-entry.md" in standards_readme


def test_legacy_standard_docs_redirect_to_consolidated_sources():
    mcp_standard = (OMO / "standards" / "MCP_STANDARDS.md").read_text(encoding="utf-8")
    mcp_transport = (OMO / "standards" / "mcp-transport.md").read_text(encoding="utf-8")
    operation_rollout = (OMO / "standards" / "operation-level-rollout-plan.md").read_text(encoding="utf-8")

    assert "已合并至 `.omo/standards/mcp-tool-and-transport-standard.md`" in mcp_standard
    assert "已合并至 `.omo/standards/mcp-tool-and-transport-standard.md`" in mcp_transport
    assert "已合并至 `.omo/standards/operation-levels.md`" in operation_rollout


def test_legacy_governance_docs_are_marked_as_historical_references():
    governance_plan = (OMO / "GOVERNANCE_PLAN.md").read_text(encoding="utf-8")
    task_pool = (OMO / "TASK_POOL.md").read_text(encoding="utf-8")

    assert "历史战略快照，不再作为当前治理执行源" in governance_plan
    assert "不再作为 Agent 认领入口" in task_pool


def test_state_exposes_divergence_detail_refs_and_promotion_blockers():
    state = _load_yaml(OMO / "state" / "system.yaml")
    assert "divergence_detail_refs" in state
    assert "promotion_blockers" in state


def test_diagram_index_lists_control_plane_state_flow():
    diagrams_index = (OMO / "diagrams" / "INDEX.md").read_text(encoding="utf-8")

    assert "control-plane-state-flow.md" in diagrams_index


def test_llm_convergence_requirements_are_folded_into_future_planning():
    plans_readme = (OMO / "plans" / "README.md").read_text(encoding="utf-8")
    blueprint = (OMO / "MASTER-BLUEPRINT.md").read_text(encoding="utf-8")
    phase3_specs = (OMO / "plans" / "phase3-task-specs-v2.md").read_text(encoding="utf-8")
    llm_packet = (OMO / "plans" / "llm-convergence-planning-packet.md").read_text(encoding="utf-8")

    assert "llm-convergence-requirements.md" in plans_readme
    assert "llm-convergence-requirements.md" in blueprint
    assert "llm-convergence-planning-packet.md" in plans_readme
    assert "llm-convergence-planning-packet.md" in blueprint
    assert "llm-convergence-planning-packet.md" in phase3_specs
    assert "dual_track" in llm_packet
