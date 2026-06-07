# Graph Report - /Users/xiamingxing/Workspace/.omo/tests  (2026-06-03)

## Corpus Check
- Corpus is ~46,422 words - fits in a single context window. You may not need a graph.

## Summary
- 812 nodes · 1430 edges · 71 communities
- Extraction: 96% EXTRACTED · 4% INFERRED · 0% AMBIGUOUS · INFERRED: 59 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Automation Tests|Automation Tests]]
- [[_COMMUNITY_Debt CLI Tests|Debt CLI Tests]]
- [[_COMMUNITY_Promotion Approval Scripts|Promotion Approval Scripts]]
- [[_COMMUNITY_Discovery & Provider Plane|Discovery & Provider Plane]]
- [[_COMMUNITY_Debt Reporting Trend Tests|Debt Reporting Trend Tests]]
- [[_COMMUNITY_Phase Rules & Acceptance|Phase Rules & Acceptance]]
- [[_COMMUNITY_Worker Mechanism Tests|Worker Mechanism Tests]]
- [[_COMMUNITY_Governance Overlay & Rollout|Governance Overlay & Rollout]]
- [[_COMMUNITY_Cost Tracking & Experience|Cost Tracking & Experience]]
- [[_COMMUNITY_Debt Registry & Metrics|Debt Registry & Metrics]]
- [[_COMMUNITY_Debt Action Packet|Debt Action Packet]]
- [[_COMMUNITY_KOS Baseline & Repair|KOS Baseline & Repair]]
- [[_COMMUNITY_Phase Execution Tests|Phase Execution Tests]]
- [[_COMMUNITY_Debt Approval Tests|Debt Approval Tests]]
- [[_COMMUNITY_Governance Overlay Loop|Governance Overlay Loop]]
- [[_COMMUNITY_Spec & Schema Tests|Spec & Schema Tests]]
- [[_COMMUNITY_Debt Dispatch Tests|Debt Dispatch Tests]]
- [[_COMMUNITY_Integration & Fusion Tests|Integration & Fusion Tests]]
- [[_COMMUNITY_Admission & Verification|Admission & Verification]]
- [[_COMMUNITY_Test Suite Standards|Test Suite Standards]]
- [[_COMMUNITY_Debt Review Queue|Debt Review Queue]]
- [[_COMMUNITY_Phase Gate Docs Tests|Phase Gate Docs Tests]]
- [[_COMMUNITY_Promotion Readiness|Promotion Readiness]]
- [[_COMMUNITY_Debt Execution Tests|Debt Execution Tests]]
- [[_COMMUNITY_External OMO Tests|External OMO Tests]]
- [[_COMMUNITY_Promotion Request Tests|Promotion Request Tests]]
- [[_COMMUNITY_Promotion History Tests|Promotion History Tests]]
- [[_COMMUNITY_Skill Registration Tests|Skill Registration Tests]]
- [[_COMMUNITY_Promotion Approval Status|Promotion Approval Status]]
- [[_COMMUNITY_Architecture Baseline|Architecture Baseline]]
- [[_COMMUNITY_Promotion Approval History|Promotion Approval History]]
- [[_COMMUNITY_Promotion Approval Analytics|Promotion Approval Analytics]]
- [[_COMMUNITY_Debt Outputs Tests|Debt Outputs Tests]]
- [[_COMMUNITY_Governance Overlay Prep|Governance Overlay Prep]]
- [[_COMMUNITY_Debt Reporting Tests|Debt Reporting Tests]]
- [[_COMMUNITY_Phase9 Runtime Boundary|Phase9 Runtime Boundary]]
- [[_COMMUNITY_OCP & Operation Level Tests|OCP & Operation Level Tests]]
- [[_COMMUNITY_Governance Consistency Tests|Governance Consistency Tests]]
- [[_COMMUNITY_Phase9 Space Registry|Phase9 Space Registry]]
- [[_COMMUNITY_Debt Reporting Diff Tests|Debt Reporting Diff Tests]]
- [[_COMMUNITY_Debt Reporting History Tests|Debt Reporting History Tests]]
- [[_COMMUNITY_Debt Campaign Tests|Debt Campaign Tests]]
- [[_COMMUNITY_Phase8 Closeout Tests|Phase8 Closeout Tests]]
- [[_COMMUNITY_Phase6 Ratification Tests|Phase6 Ratification Tests]]
- [[_COMMUNITY_Phase11 Wave4 Governance CI|Phase11 Wave4 Governance CI]]
- [[_COMMUNITY_Phase10 Wave3 Matrix Tests|Phase10 Wave3 Matrix Tests]]
- [[_COMMUNITY_Phase11 Wave4 Absolute Paths|Phase11 Wave4 Absolute Paths]]
- [[_COMMUNITY_Phase10 Wave4 Cross Space|Phase10 Wave4 Cross Space]]
- [[_COMMUNITY_Phase11 Wave3 Docs Tests|Phase11 Wave3 Docs Tests]]
- [[_COMMUNITY_Phase11 Wave2 Path Debt|Phase11 Wave2 Path Debt]]
- [[_COMMUNITY_Debt Owner Routing Tests|Debt Owner Routing Tests]]
- [[_COMMUNITY_Phase10 Wave2 Normalization|Phase10 Wave2 Normalization]]
- [[_COMMUNITY_Phase7 Planning Gate Tests|Phase7 Planning Gate Tests]]
- [[_COMMUNITY_Phase8 Completion Tests|Phase8 Completion Tests]]
- [[_COMMUNITY_Automation Contract Tests|Automation Contract Tests]]
- [[_COMMUNITY_Phase6 Hardening Packet|Phase6 Hardening Packet]]
- [[_COMMUNITY_Phase6 Completion Tests|Phase6 Completion Tests]]
- [[_COMMUNITY_Phase10 Kickoff Tests|Phase10 Kickoff Tests]]
- [[_COMMUNITY_Phase7 Completion Tests|Phase7 Completion Tests]]
- [[_COMMUNITY_Phase5 Completion Tests|Phase5 Completion Tests]]
- [[_COMMUNITY_Phase11 Kickoff Tests|Phase11 Kickoff Tests]]
- [[_COMMUNITY_Phase4 Wave2 Docs Tests|Phase4 Wave2 Docs Tests]]
- [[_COMMUNITY_Phase8 Wave2 Closeout|Phase8 Wave2 Closeout]]

## God Nodes (most connected - your core abstractions)
1. `Path` - 97 edges
2. `_write_yaml()` - 91 edges
3. `Path` - 46 edges
4. `_load_yaml()` - 44 edges
5. `_history_entry()` - 36 edges
6. `_seed_legacy_dispatch_snapshot()` - 19 edges
7. `Debt Governance Tests` - 18 edges
8. `_owner_reporting_packet()` - 17 edges
9. `Integration Tests` - 17 edges
10. `_owner_entry()` - 14 edges

## Surprising Connections (you probably didn't know these)
- `test_omo_promotion_approval` --conceptually_related_to--> `Task Schema Validation`  [INFERRED]
  test_omo_promotion_approval.py → README.md
- `test_omo_admission` --conceptually_related_to--> `Agent Control Plane Tests`  [INFERRED]
  test_omo_admission.py → README.md
- `test_omo_debt_action_packet` --conceptually_related_to--> `Debt Governance Tests`  [INFERRED]
  test_omo_debt_action_packet.py → README.md
- `test_omo_debt_approval` --conceptually_related_to--> `Debt Governance Tests`  [INFERRED]
  test_omo_debt_approval.py → README.md
- `test_omo_debt_campaign` --conceptually_related_to--> `Debt Governance Tests`  [INFERRED]
  test_omo_debt_campaign.py → README.md

## Import Cycles
- 1-file cycle: `test_omo_admission.py -> test_omo_admission.py`
- 1-file cycle: `test_omo_automation.py -> test_omo_automation.py`
- 1-file cycle: `test_omo_debt_action_packet.py -> test_omo_debt_action_packet.py`
- 1-file cycle: `test_omo_debt_approval.py -> test_omo_debt_approval.py`
- 1-file cycle: `test_omo_debt_campaign.py -> test_omo_debt_campaign.py`
- 1-file cycle: `test_omo_debt_dispatch.py -> test_omo_debt_dispatch.py`
- 1-file cycle: `test_omo_debt_execution.py -> test_omo_debt_execution.py`
- 1-file cycle: `test_omo_debt_metrics.py -> test_omo_debt_metrics.py`
- 1-file cycle: `test_omo_debt_owner_routing.py -> test_omo_debt_owner_routing.py`
- 1-file cycle: `test_omo_debt_reporting.py -> test_omo_debt_reporting.py`
- 1-file cycle: `test_omo_debt_reporting_diff.py -> test_omo_debt_reporting_diff.py`
- 1-file cycle: `test_omo_debt_reporting_history.py -> test_omo_debt_reporting_history.py`
- 1-file cycle: `test_omo_debt_reporting_trend.py -> test_omo_debt_reporting_trend.py`
- 1-file cycle: `test_omo_debt_review_queue.py -> test_omo_debt_review_queue.py`
- 1-file cycle: `test_omo_discovery.py -> test_omo_discovery.py`
- 1-file cycle: `test_omo_experience.py -> test_omo_experience.py`
- 1-file cycle: `test_omo_governance_overlay.py -> test_omo_governance_overlay.py`
- 1-file cycle: `test_omo_governance_overlay_approval_prep.py -> test_omo_governance_overlay_approval_prep.py`
- 1-file cycle: `test_omo_governance_overlay_loop.py -> test_omo_governance_overlay_loop.py`
- 1-file cycle: `test_omo_promotion_approval.py -> test_omo_promotion_approval.py`

## Communities (71 total, 0 thin omitted)

### Community 0 - "Automation Tests"
Cohesion: 0.07
Nodes (98): _load_yaml(), Path, test_contract_declaration_apply_advances_overlay_from_contract_gap_to_launch(), test_dispatch_prompt_includes_required_deliverables_when_task_declares_them(), test_dispatch_task_and_worker_status_use_custom_omo_root(), test_dispatch_task_creates_checkpoint_and_reclaim_artifacts(), test_dispatch_task_creates_packet_and_preclaims_task(), test_dispatch_task_launch_handles_quoted_prompt_without_shell_breakage() (+90 more)

### Community 1 - "Debt CLI Tests"
Cohesion: 0.09
Nodes (51): float, int, object, Path, str, _reset_generated_reporting_artifacts(), _seed_legacy_dispatch_snapshot(), test_debt_approve_rejects_non_gate_item_and_duplicate_record() (+43 more)

### Community 2 - "Promotion Approval Scripts"
Cohesion: 0.06
Nodes (31): scripts.omo_promotion_approval_analytics, scripts.omo_promotion_approval_history, scripts.omo_promotion_approval_status, scripts.omo_promotion_history, scripts.omo_promotion_readiness, scripts.omo_promotion_request, Path, test_build_promotion_approval_analytics_packet_assigns_age_buckets_for_open_requests() (+23 more)

### Community 3 - "Discovery & Provider Plane"
Cohesion: 0.06
Nodes (41): scripts.omo_discovery, scripts.omo_handoff_index, scripts.omo_io, scripts.omo_metrics, scripts.omo_provider_plane, scripts.omo_redaction, scripts.omo_skill, scripts.omo_task_schema (+33 more)

### Community 4 - "Debt Reporting Trend Tests"
Cohesion: 0.11
Nodes (38): _history_entry(), _owner_entry(), _owner_reporting_packet(), float, int, object, str, test_build_reporting_trend_packet_adds_execution_progress_from_oldest_selected_run() (+30 more)

### Community 5 - "Phase Rules & Acceptance"
Cohesion: 0.06
Nodes (29): scripts.omo_rules, scripts.phase3_acceptance, str, _read_yaml(), test_phase10_rule_registry_is_linked_from_system_space_surfaces(), Path, test_phase10_wave3_live_runtime_observe_bundle_uses_normalized_contracts(), test_phase10_wave3_project_dispatch_bundle_uses_normalized_contracts_without_wave2_task_prefix() (+21 more)

### Community 6 - "Worker Mechanism Tests"
Cohesion: 0.08
Nodes (12): _load_yaml(), Path, str, _task_files(), test_active_l2_l3_tasks_carry_approval_ref(), test_active_task_schema_includes_worker_run_and_knowledge_links(), test_all_active_tasks_pass_current_task_schema(), test_future_phase_pending_packets_in_active_require_promotion_handoff_ref() (+4 more)

### Community 7 - "Governance Overlay & Rollout"
Cohesion: 0.10
Nodes (29): scripts.omo_governance, scripts.omo_governance_overlay, scripts.omo_governance_overlay_loop, scripts.omo_rollout, _load_yaml(), Path, test_plan_governance_overlay_cycle_blocks_unsupported_target_ref(), test_plan_governance_overlay_cycle_closes_done_active_item() (+21 more)

### Community 8 - "Cost Tracking & Experience"
Cohesion: 0.28
Nodes (17): scripts.cost_track_org, scripts.omo_experience, _load_yaml(), Path, str, test_bridge_request_to_task_creates_governed_blocked_packet(), test_build_session_bootstrap_reads_live_phase_and_active_packet(), test_control_gate_blocks_when_budget_is_exceeded() (+9 more)

### Community 9 - "Debt Registry & Metrics"
Cohesion: 0.18
Nodes (15): DebtItem, scripts.omo_debt_metrics, scripts.omo_debt_registry, scripts.omo_debt_review_queue, Path, test_compute_debt_metrics_flags_overdue_and_gate_items(), test_compute_debt_metrics_flags_stale_evidence_when_refs_are_newer_than_last_reviewed(), test_load_debt_ledger_returns_seed_items() (+7 more)

### Community 10 - "Debt Action Packet"
Cohesion: 0.26
Nodes (14): scripts.omo_debt_reporting_diff, _owner_packet(), float, int, object, str, _reporting_packet(), test_build_reporting_diff_packet_computes_summary_deltas() (+6 more)

### Community 11 - "KOS Baseline & Repair"
Cohesion: 0.29
Nodes (14): scripts.omo_governance_overlay_approval_prep, scripts.omo_governance_overlay_approval_prep_aging, scripts.omo_governance_overlay_approval_prep_analytics, scripts.omo_governance_overlay_approval_prep_diff, scripts.omo_governance_overlay_approval_prep_trend, Path, test_build_governance_overlay_approval_prep_aging_prioritizes_followups_and_escalations(), test_build_governance_overlay_approval_prep_analytics_summarizes_current_and_history() (+6 more)

### Community 12 - "Phase Execution Tests"
Cohesion: 0.37
Nodes (13): Path, test_build_governance_overlay_status_advances_phase_blocked_target_into_approval_prep(), test_build_governance_overlay_status_marks_missing_target_refs_invalid(), test_build_governance_overlay_status_prefers_verify_for_active_review_target(), test_build_governance_overlay_status_reports_active_roadmap_item_and_target_states(), test_build_governance_overlay_status_reports_candidate_and_blocked_items(), test_build_governance_overlay_status_requires_overlay_inputs(), test_build_governance_overlay_status_summarizes_monitor_blockers_for_active_phase_bridge() (+5 more)

### Community 13 - "Debt Approval Tests"
Cohesion: 0.17
Nodes (11): Phase 2 integration test: Eidos ↔ OntoDerive ↔ Minerva adapters., All adapters work when Eidos is NOT available., OntoDerive Entity -> Eidos OntologyNode., Eidos Fact -> OntoDerive FormalFact., Minerva research result -> Eidos KnowledgeCard., Eidos validator can validate the converted OntologyNode., test_adapters_graceful_fallback(), test_eidos_can_validate_ontoderive_output() (+3 more)

### Community 14 - "Governance Overlay Loop"
Cohesion: 0.33
Nodes (10): scripts.omo_promotion_approval, Path, str, test_evaluate_promotion_approval_accepts_valid_task_specific_yaml(), test_evaluate_promotion_approval_rejects_shared_markdown_baseline_ref(), test_evaluate_promotion_approval_rejects_yaml_for_different_task(), test_evaluate_promotion_approval_returns_missing_when_ref_absent(), _write_text() (+2 more)

### Community 15 - "Spec & Schema Tests"
Cohesion: 0.31
Nodes (9): _dispatch_runs(), float, int, object, str, _reporting_packet(), test_build_reporting_history_packet_marks_missing_reporting_artifacts_without_dropping_run(), test_build_reporting_history_packet_orders_runs_and_sets_latest_prior() (+1 more)

### Community 16 - "Debt Dispatch Tests"
Cohesion: 0.33
Nodes (9): str, _read(), _read_yaml(), test_phase15_dashboard_includes_projects_and_user_value_not_only_omo(), test_phase15_governance_evidence_ledger_is_complete_and_traceable(), test_phase15_policy_report_blocks_governance_invariant_violations(), test_phase15_proposal_compiler_outputs_inactive_task_drafts_only(), test_phase15_recovery_and_user_value_evidence_are_rehearsed() (+1 more)

### Community 17 - "Integration & Fusion Tests"
Cohesion: 0.31
Nodes (8): str, _read(), _read_yaml(), test_phase16_baseline_and_walkthrough_tie_omo_back_to_projects_and_user_value(), test_phase16_closeout_and_live_state_are_completed_with_only_authorized_active_tasks(), test_phase16_plan_promotes_knowledge_capture_search_scope(), test_phase16_recovery_and_policy_keep_phase15_guardrails(), test_phase16_scenario_shell_defines_user_contract_and_boundaries()

### Community 18 - "Admission & Verification"
Cohesion: 0.24
Nodes (9): bool, scripts.omo_debt_action_packet, _entry(), int, object, str, test_build_action_packet_keeps_revalidate_above_escalate_for_stale_items(), test_build_action_packet_routes_entries_into_primary_lanes() (+1 more)

### Community 19 - "Test Suite Standards"
Cohesion: 0.20
Nodes (10): scripts.omo_debt_reporting_history, scripts.omo_debt_reporting_trend, Debt Governance Tests, test_omo_debt_cli, test_omo_debt_docs, test_omo_debt_outputs, test_omo_debt_registry, test_omo_debt_reporting_history (+2 more)

### Community 20 - "Debt Review Queue"
Cohesion: 0.38
Nodes (9): str, _read_omo(), _read_workspace(), test_phase9_first_migration_baseline_is_indexed(), test_phase9_remaining_program_and_wave2_packet_are_seeded(), test_phase9_wave2_closeout_is_recorded_and_archived(), test_phase9_wave3_closeout_is_recorded_and_archived(), test_phase9_wave3_packet_is_seeded_with_membership_anchor() (+1 more)

### Community 21 - "Phase Gate Docs Tests"
Cohesion: 0.25
Nodes (6): scripts.omo_debt_approval, _dispatch_packet(), object, str, test_dispatch_entry_requires_approval_only_for_gate_revalidate_items(), test_omo_debt_approval

### Community 22 - "Promotion Readiness"
Cohesion: 0.31
Nodes (8): scripts.omo_debt_dispatch, _owner_routing(), object, str, test_build_dispatch_packet_freezes_commands_and_adds_run_ref(), test_build_dispatch_packet_rejects_missing_or_unresolved_command_metadata(), test_build_dispatch_packet_uses_shell_command_for_non_revalidate_lanes(), test_omo_debt_dispatch

### Community 23 - "Debt Execution Tests"
Cohesion: 0.28
Nodes (8): scripts.omo_debt_owner_routing, _entry(), int, object, str, test_build_owner_routing_groups_entries_by_owner_and_sets_flags(), test_build_owner_routing_normalizes_ownerless_entries_and_rejects_unknown_lanes(), test_omo_debt_owner_routing

### Community 24 - "External OMO Tests"
Cohesion: 0.28
Nodes (7): scripts.omo_debt_reporting, _campaign_packet(), object, str, test_build_reporting_packet_summarizes_counts_and_rates(), test_render_reporting_markdown_shows_summary_and_owner_rollups(), test_omo_debt_reporting

### Community 25 - "Promotion Request Tests"
Cohesion: 0.43
Nodes (7): scripts.omo_admission, Path, test_evaluate_worker_envelope_denies_when_membership_lacks_required_capability(), test_evaluate_worker_envelope_returns_conditional_approval_for_wave3_dispatch(), test_request_conditional_approval_creates_approval_record_and_governance_proposal(), _write_yaml(), test_omo_admission

### Community 26 - "Promotion History Tests"
Cohesion: 0.32
Nodes (7): scripts.omo_debt_campaign, _dispatch_run(), object, str, test_build_campaign_packet_classifies_pending_ready_and_executed(), test_render_campaign_markdown_groups_entries_by_state(), test_omo_debt_campaign

### Community 27 - "Skill Registration Tests"
Cohesion: 0.48
Nodes (6): str, _read(), test_convergence_audit_is_indexed_and_live_indexes_do_not_copy_stale_counts(), test_fusion_optimization_blueprint_covers_strategy_tactics_and_execution(), test_index_links_blueprint_and_meta_retrospective(), test_meta_retrospective_covers_mechanism_and_phase1_to_phase3()

### Community 28 - "Promotion Approval Status"
Cohesion: 0.48
Nodes (6): _load_yaml(), str, test_debt_registry_campaign_and_reporting_refs_exist(), test_debt_registry_lists_seed_items_and_outputs(), test_new_seed_items_stay_pointer_based(), test_seed_items_keep_refs_to_existing_governance_surfaces()

### Community 29 - "Architecture Baseline"
Cohesion: 0.48
Nodes (6): str, _read(), test_canonical_runner_exists_and_keeps_stage_order(), test_governance_workflow_uses_canonical_runner(), test_makefile_delegates_to_canonical_runner(), test_omo_agent_documents_canonical_verification_command()

### Community 30 - "Promotion Approval History"
Cohesion: 0.76
Nodes (6): Path, _seed_active_task(), test_check_system_consistency_script_fails_when_plans_readme_misses_current_wave(), test_check_system_consistency_script_recomputes_state_before_alignment(), test_check_system_consistency_script_refreshes_freshness_and_control(), _write_yaml()

### Community 31 - "Promotion Approval Analytics"
Cohesion: 0.48
Nodes (6): str, _read(), _read_yaml(), test_phase13_closeout_and_tasks_are_recorded(), test_phase13_metacognition_outputs_are_supervised_and_read_only(), test_phase13_remains_completed_after_phase16_completion_allowing_only_authorized_active_tasks()

### Community 32 - "Debt Outputs Tests"
Cohesion: 0.48
Nodes (6): str, _read(), _read_yaml(), test_phase14_closeout_and_tasks_are_recorded(), test_phase14_evidence_completes_deferred_ecosystem_scope(), test_phase14_remains_completed_after_phase16_completion_allowing_only_authorized_active_tasks()

### Community 33 - "Governance Overlay Prep"
Cohesion: 0.48
Nodes (6): _load_workspace_yaml(), str, test_identity_admission_schema_declares_actor_membership_anchor(), test_system_space_identity_contract_is_linked_and_concrete(), test_system_space_identity_contract_links_taxonomy_and_matrix(), test_worker_envelope_binds_action_and_membership_to_admission_contract()

### Community 34 - "Debt Reporting Tests"
Cohesion: 0.33
Nodes (4): scripts.omo_debt_execution, Path, test_execution_record_helpers_build_run_scoped_paths(), test_omo_debt_execution

### Community 35 - "Phase9 Runtime Boundary"
Cohesion: 0.53
Nodes (5): str, _read(), test_architecture_baseline_registers_canonical_framework_and_boundaries(), test_indexes_and_plan_registry_include_baseline_and_phase16(), test_phase15_and_phase16_docs_preserve_sequence_and_non_goals()

### Community 36 - "OCP & Operation Level Tests"
Cohesion: 0.40
Nodes (3): str, _read_yaml(), test_phase12_registry_and_scenario_evidence_are_complete()

### Community 37 - "Governance Consistency Tests"
Cohesion: 0.53
Nodes (5): str, _read(), test_phase4_roadmap_exists_with_worker_collab_focus(), test_phase4_wave1_closure_is_recorded(), test_worker_collaboration_review_records_strengths_gaps_and_verdict()

### Community 38 - "Phase9 Space Registry"
Cohesion: 0.53
Nodes (5): _load_workspace_yaml(), str, test_space_registry_declares_system_space_manifest(), test_space_registry_entry_carries_boundary_metadata(), test_system_space_manifest_matches_schema_contract()

### Community 40 - "Debt Reporting Diff Tests"
Cohesion: 0.60
Nodes (4): str, _read(), test_phase4_wave2_closure_recorded_in_goals_state_and_indexes(), test_wave2_docs_define_canonical_status_vs_gate_facts()

### Community 41 - "Debt Reporting History Tests"
Cohesion: 0.50
Nodes (3): str, _read(), test_phase7_completion_remains_recorded_as_historical_baseline()

### Community 42 - "Debt Campaign Tests"
Cohesion: 0.67
Nodes (3): Path, test_debt_dispatch_writes_current_and_immutable_run_artifacts(), test_debt_refresh_writes_dashboard_review_queue_and_action_packet()

### Community 43 - "Phase8 Closeout Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase10_completion_is_recorded_with_wave4_closeout_and_retrospective()

### Community 44 - "Phase6 Ratification Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase10_wave1_kickoff_is_recorded_as_history()

### Community 45 - "Phase11 Wave4 Governance CI"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase10_wave2_is_recorded_as_history_after_phase10_completion()

### Community 46 - "Phase10 Wave3 Matrix Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase10_wave3_is_recorded_as_history_after_phase10_completion()

### Community 47 - "Phase11 Wave4 Absolute Paths"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase11_wave1_kickoff_is_preserved_as_history()

### Community 48 - "Phase10 Wave4 Cross Space"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase11_wave2_is_preserved_as_history()

### Community 49 - "Phase11 Wave3 Docs Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_wave2_scripts_drop_user_specific_workspace_literals()

### Community 50 - "Phase11 Wave2 Path Debt"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase11_wave3_is_recorded_as_history_after_phase16_completion()

### Community 51 - "Debt Owner Routing Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase11_wave4_is_preserved_after_phase16_completion()

### Community 52 - "Phase10 Wave2 Normalization"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase12_completion_and_phase13_plus_backlog_boundaries_are_registered()

### Community 53 - "Phase7 Planning Gate Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase5_completion_is_recorded()

### Community 54 - "Phase8 Completion Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase5_wave0_kickoff_is_recorded()

### Community 55 - "Automation Contract Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase6_completion_is_recorded()

### Community 56 - "Phase6 Hardening Packet"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase6_ratification_is_recorded()

### Community 57 - "Phase6 Completion Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase7_planning_gate_remains_recorded_as_historical_artifact()

### Community 58 - "Phase10 Kickoff Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase8_completion_is_recorded_with_retrospective_and_review()

### Community 59 - "Phase7 Completion Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase8_planning_gate_remains_recorded_as_historical_artifact()

### Community 60 - "Phase5 Completion Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase8_wave1_closeout_remains_recorded_as_historical_baseline()

### Community 61 - "Phase11 Kickoff Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase8_wave2_closeout_remains_recorded_as_historical_baseline()

### Community 62 - "Phase4 Wave2 Docs Tests"
Cohesion: 0.67
Nodes (3): str, _read(), test_phase9_completion_is_recorded_with_wave4_closeout_and_retrospective()

### Community 63 - "Phase8 Wave2 Closeout"
Cohesion: 0.67
Nodes (3): str, _read_workspace(), test_run_continuation_moves_to_runtime_root()

## Knowledge Gaps
- **84 isolated node(s):** `str`, `str`, `str`, `bool`, `int` (+79 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `.omo Test Suite Standards` connect `Discovery & Provider Plane` to `Promotion Approval Scripts`, `Test Suite Standards`, `Phase Rules & Acceptance`, `Governance Overlay & Rollout`?**
  _High betweenness centrality (0.278) - this node is a cross-community bridge._
- **Why does `Debt Governance Tests` connect `Test Suite Standards` to `Debt Reporting Tests`, `Discovery & Provider Plane`, `Debt Registry & Metrics`, `Debt Action Packet`, `Admission & Verification`, `Phase Gate Docs Tests`, `Promotion Readiness`, `Debt Execution Tests`, `External OMO Tests`, `Promotion History Tests`?**
  _High betweenness centrality (0.205) - this node is a cross-community bridge._
- **Why does `scripts.omo_task_schema` connect `Discovery & Provider Plane` to `Automation Tests`, `Cost Tracking & Experience`, `Worker Mechanism Tests`?**
  _High betweenness centrality (0.118) - this node is a cross-community bridge._
- **What connects `str`, `str`, `str` to the rest of the system?**
  _90 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Automation Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.06574257425742575 - nodes in this community are weakly interconnected._
- **Should `Debt CLI Tests` be split into smaller, more focused modules?**
  _Cohesion score 0.09351432880844646 - nodes in this community are weakly interconnected._
- **Should `Promotion Approval Scripts` be split into smaller, more focused modules?**
  _Cohesion score 0.06376811594202898 - nodes in this community are weakly interconnected._