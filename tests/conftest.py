"""Root test configuration with auto-registered domain markers."""

from __future__ import annotations

import pytest

MARKER_MAP = {
    "governance": [
        "test_gac_", "test_adr_", "test_governance_", "test_swarm_",
        "test_worktree_", "test_delegation_", "test_bet_ledger_",
        "test_chain_bind", "test_ci_surfaces", "test_classify_",
        "test_collab_", "test_commit_assist", "test_compass_",
        "test_convergence_", "test_cron_", "test_cross_package_",
        "test_current_state_", "test_delivery_g_del", "test_doc_claims",
        "test_doc_governance_", "test_e2_sweep_", "test_event_loop_",
        "test_feedback_loop_", "test_fix_", "test_generate_brief",
        "test_god_module_", "test_hardcoded_", "test_ingest_",
        "test_journey_", "test_kandev_", "test_m1_closeout",
        "test_meta_doctor", "test_mof_", "test_network_path_",
        "test_north_star_", "test_omo_", "test_p76_", "test_p86_",
        "test_personal_space_", "test_phase_gate_", "test_physical_",
        "test_provider_conformance", "test_requirement_iteration_",
        "test_role_framework_", "test_root_directory_", "test_rule_vitality",
        "test_scene_card_", "test_shared_context", "test_skill_",
        "test_skills_coverage", "test_spec_binding_", "test_ssot_",
        "test_state_goals_alignment", "test_submodule_", "test_sweep_",
        "test_sync_", "test_validate_human_gate", "test_worktree_",
        "test_yaml_bypass_", "test_batch1_", "test_batch2_",
        "test_bos_deprecated_", "test_capability_sync", "test_affected_graph",
        "test_agent_clone_reinstall", "test_agent_pool_observe",
        "test_alert_router", "test_anomaly_detector", "test_bdsk_",
        "test_check_submodule_", "test_check_", "test_ci_local_fast",
        "test_codex_worker_", "test_cross_domain_", "test_debt_predictor",
        "test_gac_hygiene_", "test_gac_local_gate_", "test_gac_worktree_",
        "test_gconv_", "test_god_module_", "test_governance_dashboard",
        "test_governance_ratio", "test_governance_summarizer",
        "test_governance_workflow_", "test_hook_tempfile_", "test_immutable_writer_",
        "test_mof_capabilities_", "test_omp_worker_", "test_orca_",
        "test_pi_worker_", "test_predictive_governance", "test_risk_profile",
        "test_rule_vitality_retention", "test_signal_", "test_submodule_reachability_",
    ],
    "workflow": ["test_agent_workflow", "test_agt_integration"],
    "documents": ["test_documents_"],
    "cross": [
        "test_cross_repo_", "test_external_", "test_gbrain_collab_",
    ],
    "cli": ["test_bin_scripts_", "test_gac_worktree_trap", "test_submodule_autobump"],
    "mof": ["test_mof_"],
}

DOMAIN_MARKERS = {name: pytest.mark.domain(name) for name in MARKER_MAP}


def pytest_collection_modifyitems(config, items):
    for item in items:
        name = item.name
        for domain, prefixes in MARKER_MAP.items():
            if any(name.startswith(prefix) for prefix in prefixes):
                item.add_marker(DOMAIN_MARKERS[domain])
                break
