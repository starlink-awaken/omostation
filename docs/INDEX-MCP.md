# MCP 服务器索引

> 自动生成于 2026-08-02T10:17:40Z
> 源: `docs/generated/capability-registry.yaml`

全生态共 **24** 个 MCP 服务器, **541** 个工具。

| 服务器 | 层 | 工具数 | 传输 | 端口 | 源文件 |
|--------|-----|--------|------|------|--------|
| `agora` | I0 | 86 | stdio/sse | — | `projects/agora/src/agora/server/mcp.py` |
| `ecos` | L0 | 28 | stdio | — | `projects/ecos/src/ecos/mcp_server.py` |
| `ecos-integration` | L0 | 26 | stdio | — | `projects/ecos/src/ecos/services/integration/mcp_server.py` |
| `ecos-ssot` | L0 | 9 | stdio | — | `projects/ecos/src/ecos/l0/ssot/mcp_server.py` |
| `gbrain` | L2 | 75 | stdio | — | `projects/gbrain/src/core/operations/exports.ts` |
| `kos` | L2 | 44 | stdio | — | `projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `kos-stdio` | L2 | 44 | stdio | — | `projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `codeanalyze` | L2 | 25 | stdio | — | `projects/kairon/packages/codeanalyze/src/codeanalyze/mcp.py` |
| `metaos` | L2 | 24 | stdio | — | `projects/metaos/src/metaos/mcp_server.py` |
| `omo` | L2 | 19 | stdio | — | `projects/omo/src/omo/mcp_server.py` |
| `kronos` | L2 | 16 | stdio | — | `projects/kairon/packages/kronos/src/kronos/mcp_server.py` |
| `iris` | L2 | 8 | stdio | — | `projects/kairon/packages/iris/src/iris/mcp_server.py` |
| `sophia` | L2 | 8 | stdio | — | `projects/kairon/packages/sophia/src/sophia/server/mcp_server.py` |
| `minerva` | L2 | 8 | stdio | — | `projects/kairon/packages/minerva/src/minerva/mcp_server/server.py` |
| `forge` | L2 | 7 | stdio | — | `projects/kairon/packages/forge/src/mcp_server.py` |
| `ontoderive` | L2 | 7 | stdio | — | `projects/kairon/packages/ontoderive/src/ontoderive/mcp_server.py` |
| `toolforge` | L2 | 5 | stdio | — | `projects/kairon/packages/ontoderive/src/ontoderive/toolforge/mcp_server.py` |
| `agent-runtime` | L3 | 2 | stdio | — | `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py` |
| `l4-kernel` | L4 | 51 | stdio/http/sse | http:7455, sse:7456 | `projects/l4-kernel/src/l4_kernel/mcp_server.py` |
| `model-driven` | M0 | 28 | stdio | — | `projects/model-driven/src/model_driven/mcp_server.py` |
| `model-driven-fastmcp` | M0 | 2 | stdio | — | `projects/model-driven/src/model_driven/fastmcp_server.py` |
| `aetherforge` | X | 10 | stdio | — | `projects/aetherforge/src/aetherforge/mcp_server.py` |
| `family-hub` | X | 6 | stdio | — | `projects/family-hub/mcp_server.py` |
| `c2g` | X | 3 | stdio | — | `projects/c2g/src/c2g/mcp_server.py` |

## 工具清单

### agora (86 tools)

`a2a_cancel_task`, `a2a_get_task`, `a2a_list_tasks`, `a2a_send_task`, `add_route`, `agora_execute`, `audit_query`, `audit_stats`, `bos_health`, `bos_inbox_archive`, `bos_inbox_draft`, `bos_inbox_pending`, `bos_inbox_search`, `bos_inbox_status`, `bos_inbox_triage`, `bos_inbox_watch`, `bos_metrics_status`, `bos_middleware_status`, `bos_reload_discovery`, `bos_reload_m1`, `bos_reload_routes`, `create_api_key`, `debt_auto_seed_tool`, `entropy_cleanup_tool`, `get_agent_card`, `get_bos_schema`, `get_event_log`, `get_state_transitions`, `health_check`, `lifecycle_load_all`, `lifecycle_start_watch`, `lifecycle_status`, `lifecycle_stop_watch`, `lifecycle_unload_all`, `list_agent_cards`, `list_api_keys`, `list_bos_domains`, `list_bos_resources`, `list_bos_tools`, `list_routes`, `list_services`, `mutate_resource`, `persona_bdsk_evaluate`, `proxy_add_service`, `proxy_arch_health`, `proxy_backend_health`, `proxy_connect`, `proxy_governance_status`, `proxy_list_tools`, `proxy_omo_debt`, `publish_event`, `python`, `read_resource`, `register_push_notification`, `register_service`, `registry_find_agent_tool`, `registry_health_tool`, `registry_heartbeat_tool`, `registry_list_agents_tool`, `registry_list_tasks_tool`, `registry_register_agent_tool`, `registry_submit_task_tool`, `repo_discover`, `repo_install`, `repo_load`, `repo_pipeline`, `repo_search`, `repo_status`, `repo_unload`, `resolve_bos_uri`, `revoke_api_key`, `route_call`, `subscribe_event`, `swarm_nodes`, `swarm_resolve`, `swarm_status`, `unwatch_resource`, `watch_resource`, `workflow_capability_health`, `workspace_audit_gitlink`, `workspace_audit_governance`, `workspace_audit_lint`, `workspace_audit_ops`, `workspace_audit_radar`, `workspace_audit_run`, `workspace_audit_ssot`

### gbrain (75 tools)

`add_link`, `add_tag`, `add_timeline_entry`, `cancel_job`, `code_blast`, `code_callees`, `code_callers`, `code_def`, `code_flow`, `code_refs`, `code_traversal_cache_clear`, `delete_page`, `extract_facts`, `file_list`, `file_upload`, `file_url`, `find_anomalies`, `find_contradictions`, `find_experts`, `find_orphans`, `find_trajectory`, `forget_fact`, `get_backlinks`, `get_brain_identity`, `get_calibration_profile`, `get_chunks`, `get_health`, `get_ingest_log`, `get_job`, `get_job_progress`, `get_links`, `get_page`, `get_raw_data`, `get_recent_salience`, `get_recent_transcripts`, `get_stats`, `get_tags`, `get_timeline`, `get_versions`, `list_jobs`, `list_pages`, `log_ingest`, `memory_tree`, `pause_job`, `purge_deleted_pages`, `put_page`, `put_raw_data`, `query`, `recall`, `remove_link`, `remove_tag`, `replay_job`, `resolve_slugs`, `restore_page`, `resume_job`, `retry_job`, `revert_version`, `run_doctor`, `search`, `search_by_image`, `send_job_message`, `sources_add`, `sources_list`, `sources_remove`, `sources_status`, `submit_agent`, `submit_job`, `sync_brain`, `takes_calibration`, `takes_list`, `takes_scorecard`, `takes_search`, `think`, `traverse_graph`, `whoami`

### l4-kernel (51 tools)

`l4_cards_check`, `l4_cards_compliance`, `l4_cards_get`, `l4_cards_list`, `l4_cards_search`, `l4_claude_validate`, `l4_config_read`, `l4_cross_search`, `l4_dashboard`, `l4_domain_create`, `l4_domain_freeze`, `l4_domain_info`, `l4_domain_migrate`, `l4_domain_sync`, `l4_domain_unfreeze`, `l4_domain_validate`, `l4_domains_list`, `l4_engine_check`, `l4_engine_logs`, `l4_entrypoint_read`, `l4_evolution_status`, `l4_evolution_tasks`, `l4_evolution_trigger`, `l4_file_delete`, `l4_file_move`, `l4_files_list`, `l4_freshness`, `l4_health`, `l4_health_detail`, `l4_kems_plane_scan`, `l4_kems_validate`, `l4_memory_read`, `l4_models_list`, `l4_plugin_actions`, `l4_plugin_run_action`, `l4_plugin_run_mechanism`, `l4_plugin_specs`, `l4_plugin_workflows`, `l4_project_check`, `l4_reload`, `l4_rules_read`, `l4_search`, `l4_signal_emit`, `l4_signal_patterns`, `l4_signals_list`, `l4_state_read`, `l4_status_read`, `l4_storage_usage`, `l4_timeline_list`, `l4_tools_list`, `l4_workspace_search`

### kos (44 tools)

`build_context`, `check_subscription`, `collab.add_artifact`, `collab.claim_subtask`, `collab.create_task`, `collab.get_task`, `collab.list_tasks`, `collab.update_task`, `consensus.create`, `consensus.get`, `consensus.list_expired`, `consensus.renew`, `consensus.trace`, `cross_domain_sync`, `db_vacuum`, `entity_explore`, `fact_check`, `full_sync`, `get_entity`, `get_entity_timeline`, `get_knowledge`, `get_stats`, `get_system_status`, `graph_search`, `knowledge_ask`, `list_domains`, `mcp_market_discover`, `memory_stats`, `ontology_graph`, `ontology_rebuild`, `research_now`, `research_pipeline`, `run_indexer`, `search_entity`, `search_knowledge`, `self.get_current_role`, `self.get_profile`, `self.get_vision_summary`, `semantic_scholar`, `semantic_search`, `subscribe_topic`, `sync_gbrain`, `verify_claim`, `viz_render`

### kos-stdio (44 tools)

`build_context`, `check_subscription`, `collab.add_artifact`, `collab.claim_subtask`, `collab.create_task`, `collab.get_task`, `collab.list_tasks`, `collab.update_task`, `consensus.create`, `consensus.get`, `consensus.list_expired`, `consensus.renew`, `consensus.trace`, `cross_domain_sync`, `db_vacuum`, `entity_explore`, `fact_check`, `full_sync`, `get_entity`, `get_entity_timeline`, `get_knowledge`, `get_stats`, `get_system_status`, `graph_search`, `knowledge_ask`, `list_domains`, `mcp_market_discover`, `memory_stats`, `ontology_graph`, `ontology_rebuild`, `research_now`, `research_pipeline`, `run_indexer`, `search_entity`, `search_knowledge`, `self.get_current_role`, `self.get_profile`, `self.get_vision_summary`, `semantic_scholar`, `semantic_search`, `subscribe_topic`, `sync_gbrain`, `verify_claim`, `viz_render`

### ecos (28 tools)

`domain_list`, `domain_read`, `domain_resolve`, `domain_search`, `domain_stats`, `domain_tree`, `domain_validate`, `ecos_brief`, `ecos_health`, `ssot_check`, `ssot_compile`, `ssot_derive`, `ssot_evolve`, `ssot_extract`, `ssot_stats`, `ssot_sync`, `workflow_actions`, `workflow_backends`, `workflow_cache_invalidate`, `workflow_cache_status`, `workflow_circuit_breaker_reset`, `workflow_circuit_breaker_status`, `workflow_list`, `workflow_logs`, `workflow_run`, `workflow_show`, `workflow_test`, `workflow_validate`

### model-driven (28 tools)

`adr-create`, `adr-list`, `audit-record`, `collab-assign`, `collab-create`, `collab-status`, `cross-stage-check`, `debt-register`, `lifecycle-advance`, `lifecycle-blockers`, `lifecycle-create`, `lifecycle-dashboard`, `lifecycle-status`, `model-execute`, `model-tools`, `okr-create`, `okr-progress`, `spec-create`, `spec-list`, `ssot-drift-check`, `task-create`, `trigger-dashboard`, `trigger-derive`, `trigger-drift`, `trigger-heal`, `trigger-list`, `trigger-status`, `value-roi`

### ecos-integration (26 tools)

`bos_routes`, `domain_list`, `domain_read`, `domain_resolve`, `domain_search`, `domain_stats`, `domain_tree`, `domain_validate`, `ecos_brief`, `ecos_health`, `handle_bos_routes`, `handle_domain_list`, `handle_domain_stats`, `handle_domain_tree`, `handle_domain_validate`, `handle_ecos_brief`, `handle_ecos_health`, `handle_read`, `handle_resolve`, `handle_search`, `handle_workflow_list`, `handle_workflow_relations`, `handle_workflow_show`, `workflow_list`, `workflow_relations`, `workflow_show`

### codeanalyze (25 tools)

`analyze_project`, `architecture_generate_diagram`, `architecture_get_code_metrics`, `ast_search`, `audit_project`, `cgc_query`, `codegraph_callees`, `codegraph_callers`, `codegraph_context`, `codegraph_get_affected_tests`, `codegraph_get_impact_radius`, `codegraph_get_symbol_graph`, `codegraph_init`, `codegraph_search`, `codegraph_sync`, `crg_build`, `crg_status`, `export_graph`, `extract_policy_docs`, `pack_repo`, `rg_search`, `scan_directory`, `status`, `workflow_impact_analysis`, `workflow_onboarding`

### metaos (24 tools)

`handle_day`, `handle_device_orchestrator`, `handle_evening`, `handle_family_brief`, `handle_gate`, `handle_health`, `handle_morning`, `handle_request`, `handle_review`, `handle_ssot`, `handle_status`, `handle_trace`, `metaos-engine`, `metaos_day`, `metaos_device_orchestrator`, `metaos_evening`, `metaos_family_brief`, `metaos_gate`, `metaos_health`, `metaos_morning`, `metaos_review`, `metaos_ssot`, `metaos_status`, `metaos_trace`

### omo (19 tools)

`acquire_lock`, `cards_check`, `cards_create`, `cards_search`, `cards_status`, `cards_update`, `check_gac_rule`, `check_lock`, `list_locks`, `omo_bridge`, `omo_debt_list`, `omo_debt_summary`, `omo_gc`, `omo_metacognition`, `omo_worker_dispatch`, `omo_worker_reclaim`, `omo_yield_task`, `release_lock`, `validate_task`

### kronos (16 tools)

`cloakbrowser`, `eidos`, `kos`, `kronos`, `kronos_browser_fetch`, `kronos_extract`, `kronos_fetch`, `kronos_insight`, `kronos_pipelines`, `kronos_plan`, `kronos_route`, `kronos_status`, `kronos_tools`, `ollama`, `vault`, `wps_note`

### aetherforge (10 tools)

`forge_cost_report`, `forge_generate`, `forge_generate_mesh`, `forge_health_check`, `forge_list_nodes`, `forge_mesh_status`, `forge_triage`, `forge_triage_batch`, `forge_triage_consensus`, `forge_triage_status`

### ecos-ssot (9 tools)

`check`, `compile`, `derive`, `evolve`, `extract_from_file`, `handle_message`, `ssot-kernel`, `stats`, `sync`

### iris (8 tools)

`iris_connector_status`, `iris_get_item`, `iris_list_connectors`, `iris_list_items`, `iris_search`, `iris_sync`, `iris_sync_bidirectional`, `iris_validate`

### sophia (8 tools)

`compile_paradigm`, `get_effective_ops`, `get_transitions`, `list_operations`, `list_states`, `record_trace`, `suggest_ops`, `suggest_paradigm`

### minerva (8 tools)

`cross_domain_research`, `knowledge_closed_loop`, `knowledge_ingest`, `knowledge_search`, `minerva_bfs_search`, `research_now`, `research_schedule`, `research_watch`

### forge (7 tools)

`get_project_status`, `get_tool_info`, `list_tools`, `market_install`, `market_list`, `market_remove`, `search_tools`

### ontoderive (7 tools)

`derive`, `handle_mcp_request`, `list_entities`, `ontoderive`, `pipeline_status`, `trace`, `validate`

### family-hub (6 tools)

`complete_quest`, `create_quest`, `generate_smart_quests`, `get_active_quests`, `get_health`, `get_profiles`

### toolforge (5 tools)

`handle_request`, `ontoderive-toolforge`, `toolforge_guide`, `toolforge_match`, `toolforge_select`

### c2g (3 tools)

`c2g_bet`, `c2g_gc`, `c2g_radar`

### model-driven-fastmcp (2 tools)

`model_tool_execute`, `model_tools_list`

### agent-runtime (2 tools)

`chat`, `run_task`

*由 `bin/cockpit/gen-help-docs.py` 于 2026-08-02T10:17:40Z 生成*