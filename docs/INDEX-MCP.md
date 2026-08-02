# MCP 服务器索引

> 自动生成于 2026-08-02T12:56:53Z
> 源: `docs/generated/capability-registry.yaml`

全生态共 **25** 个 MCP 服务器, **385** 个工具。

| 服务器 | 层 | 工具数 | 传输 | 端口 | 源文件 |
|--------|-----|--------|------|------|--------|
| `agora` | I0 | 31 | stdio/sse | — | `projects/agora/src/agora/server/mcp.py` |
| `ecos-integration` | L0 | 26 | stdio | — | `projects/ecos/src/ecos/services/integration/mcp_server.py` |
| `ecos-ssot` | L0 | 9 | stdio | — | `projects/ecos/src/ecos/l0/ssot/mcp_server.py` |
| `ecos` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/mcp_server.py` |
| `gbrain` | L2 | 75 | stdio | — | `projects/gbrain/src/core/operations/exports.ts` |
| `kos` | L2 | 44 | stdio | — | `projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `kos-stdio` | L2 | 44 | stdio | — | `projects/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `metaos` | L2 | 24 | stdio | — | `projects/metaos/src/metaos/mcp_server.py` |
| `kronos` | L2 | 7 | stdio | — | `projects/kairon/packages/kronos/src/kronos/mcp_server.py` |
| `ontoderive` | L2 | 7 | stdio | — | `projects/kairon/packages/ontoderive/src/ontoderive/mcp_server.py` |
| `toolforge` | L2 | 5 | stdio | — | `projects/kairon/packages/ontoderive/src/ontoderive/toolforge/mcp_server.py` |
| `omo` | L2 | 0 | stdio | — | `projects/omo/src/omo/mcp_server.py` |
| `iris` | L2 | 0 | stdio | — | `projects/kairon/packages/iris/src/iris/mcp_server.py` |
| `sophia` | L2 | 0 | stdio | — | `projects/kairon/packages/sophia/src/sophia/server/mcp_server.py` |
| `minerva` | L2 | 0 | stdio | — | `projects/kairon/packages/minerva/src/minerva/mcp_server/server.py` |
| `codeanalyze` | L2 | 0 | stdio | — | `projects/kairon/packages/codeanalyze/src/codeanalyze/mcp.py` |
| `forge` | L2 | 0 | stdio | — | `projects/kairon/packages/forge/src/mcp_server.py` |
| `cockpit-mcp` | L3 | 30 | stdio | — | `projects/cockpit/src/cockpit/scripts/cockpit_mcp.py` |
| `agent-runtime` | L3 | 0 | stdio | — | `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py` |
| `l4-kernel` | L4 | 45 | stdio/http/sse | http:7455, sse:7456 | `projects/l4-kernel/src/l4_kernel/mcp_server.py` |
| `model-driven` | M0 | 28 | stdio | — | `projects/model-driven/src/model_driven/mcp_server.py` |
| `model-driven-fastmcp` | M0 | 0 | stdio | — | `projects/model-driven/src/model_driven/fastmcp_server.py` |
| `aetherforge` | X | 10 | stdio | — | `projects/aetherforge/src/aetherforge/mcp_server.py` |
| `c2g` | X | 0 | stdio | — | `projects/c2g/src/c2g/mcp_server.py` |
| `family-hub` | X | 0 | stdio | — | `projects/family-hub/mcp_server.py` |

## 工具清单

### gbrain (75 tools)

`add_link`, `add_tag`, `add_timeline_entry`, `cancel_job`, `code_blast`, `code_callees`, `code_callers`, `code_def`, `code_flow`, `code_refs`, `code_traversal_cache_clear`, `delete_page`, `extract_facts`, `file_list`, `file_upload`, `file_url`, `find_anomalies`, `find_contradictions`, `find_experts`, `find_orphans`, `find_trajectory`, `forget_fact`, `get_backlinks`, `get_brain_identity`, `get_calibration_profile`, `get_chunks`, `get_health`, `get_ingest_log`, `get_job`, `get_job_progress`, `get_links`, `get_page`, `get_raw_data`, `get_recent_salience`, `get_recent_transcripts`, `get_stats`, `get_tags`, `get_timeline`, `get_versions`, `list_jobs`, `list_pages`, `log_ingest`, `memory_tree`, `pause_job`, `purge_deleted_pages`, `put_page`, `put_raw_data`, `query`, `recall`, `remove_link`, `remove_tag`, `replay_job`, `resolve_slugs`, `restore_page`, `resume_job`, `retry_job`, `revert_version`, `run_doctor`, `search`, `search_by_image`, `send_job_message`, `sources_add`, `sources_list`, `sources_remove`, `sources_status`, `submit_agent`, `submit_job`, `sync_brain`, `takes_calibration`, `takes_list`, `takes_scorecard`, `takes_search`, `think`, `traverse_graph`, `whoami`

### l4-kernel (45 tools)

`l4_cards_check`, `l4_cards_compliance`, `l4_cards_get`, `l4_cards_list`, `l4_cards_search`, `l4_claude_validate`, `l4_config_read`, `l4_cross_search`, `l4_dashboard`, `l4_domain_create`, `l4_domain_freeze`, `l4_domain_info`, `l4_domain_migrate`, `l4_domain_unfreeze`, `l4_domain_validate`, `l4_domains_list`, `l4_engine_check`, `l4_engine_logs`, `l4_entrypoint_read`, `l4_evolution_status`, `l4_evolution_tasks`, `l4_evolution_trigger`, `l4_files_list`, `l4_freshness`, `l4_health`, `l4_kems_validate`, `l4_memory_read`, `l4_models_list`, `l4_plugin_actions`, `l4_plugin_run_action`, `l4_plugin_run_mechanism`, `l4_plugin_specs`, `l4_plugin_workflows`, `l4_reload`, `l4_rules_read`, `l4_search`, `l4_signal_emit`, `l4_signal_patterns`, `l4_signals_list`, `l4_state_read`, `l4_status_read`, `l4_storage_usage`, `l4_timeline_list`, `l4_tools_list`, `l4_workspace_search`

### kos (44 tools)

`build_context`, `check_subscription`, `collab.add_artifact`, `collab.claim_subtask`, `collab.create_task`, `collab.get_task`, `collab.list_tasks`, `collab.update_task`, `consensus.create`, `consensus.get`, `consensus.list_expired`, `consensus.renew`, `consensus.trace`, `cross_domain_sync`, `db_vacuum`, `entity_explore`, `fact_check`, `full_sync`, `get_entity`, `get_entity_timeline`, `get_knowledge`, `get_stats`, `get_system_status`, `graph_search`, `knowledge_ask`, `list_domains`, `mcp_market_discover`, `memory_stats`, `ontology_graph`, `ontology_rebuild`, `research_now`, `research_pipeline`, `run_indexer`, `search_entity`, `search_knowledge`, `self.get_current_role`, `self.get_profile`, `self.get_vision_summary`, `semantic_scholar`, `semantic_search`, `subscribe_topic`, `sync_gbrain`, `verify_claim`, `viz_render`

### kos-stdio (44 tools)

`build_context`, `check_subscription`, `collab.add_artifact`, `collab.claim_subtask`, `collab.create_task`, `collab.get_task`, `collab.list_tasks`, `collab.update_task`, `consensus.create`, `consensus.get`, `consensus.list_expired`, `consensus.renew`, `consensus.trace`, `cross_domain_sync`, `db_vacuum`, `entity_explore`, `fact_check`, `full_sync`, `get_entity`, `get_entity_timeline`, `get_knowledge`, `get_stats`, `get_system_status`, `graph_search`, `knowledge_ask`, `list_domains`, `mcp_market_discover`, `memory_stats`, `ontology_graph`, `ontology_rebuild`, `research_now`, `research_pipeline`, `run_indexer`, `search_entity`, `search_knowledge`, `self.get_current_role`, `self.get_profile`, `self.get_vision_summary`, `semantic_scholar`, `semantic_search`, `subscribe_topic`, `sync_gbrain`, `verify_claim`, `viz_render`

### agora (31 tools)

`add_route`, `bos_inbox_draft`, `bos_inbox_pending`, `bos_inbox_search`, `bos_inbox_status`, `bos_inbox_triage`, `bos_inbox_watch`, `bos_metrics_status`, `bos_middleware_status`, `get_bos_schema`, `get_event_log`, `list_bos_domains`, `list_bos_resources`, `list_routes`, `list_services`, `mutate_resource`, `persona_bdsk_evaluate`, `publish_event`, `python`, `read_resource`, `register_service`, `repo_discover`, `repo_install`, `repo_load`, `repo_pipeline`, `repo_search`, `repo_status`, `repo_unload`, `resolve_bos_uri`, `route_call`, `subscribe_event`

### cockpit-mcp (30 tools)

`cards_check`, `cards_status`, `daily_summary`, `domains_list`, `github_pr_review`, `governance_check`, `governance_dashboard`, `governance_history`, `governance_leaderboard`, `governance_sla`, `governance_status`, `research_agent_list`, `research_archive`, `research_ask`, `research_create`, `research_dossier`, `research_half_life`, `research_list`, `research_open`, `research_rename`, `research_restore`, `research_search`, `research_tag`, `shared_context_list`, `shared_context_read`, `shared_context_write`, `status_json`, `status_summary`, `vault_search`, `workspace_context`

### model-driven (28 tools)

`adr-create`, `adr-list`, `audit-record`, `collab-assign`, `collab-create`, `collab-status`, `cross-stage-check`, `debt-register`, `lifecycle-advance`, `lifecycle-blockers`, `lifecycle-create`, `lifecycle-dashboard`, `lifecycle-status`, `model-execute`, `model-tools`, `okr-create`, `okr-progress`, `spec-create`, `spec-list`, `ssot-drift-check`, `task-create`, `trigger-dashboard`, `trigger-derive`, `trigger-drift`, `trigger-heal`, `trigger-list`, `trigger-status`, `value-roi`

### ecos-integration (26 tools)

`bos_routes`, `domain_list`, `domain_read`, `domain_resolve`, `domain_search`, `domain_stats`, `domain_tree`, `domain_validate`, `ecos_brief`, `ecos_health`, `handle_bos_routes`, `handle_domain_list`, `handle_domain_stats`, `handle_domain_tree`, `handle_domain_validate`, `handle_ecos_brief`, `handle_ecos_health`, `handle_read`, `handle_resolve`, `handle_search`, `handle_workflow_list`, `handle_workflow_relations`, `handle_workflow_show`, `workflow_list`, `workflow_relations`, `workflow_show`

### metaos (24 tools)

`handle_day`, `handle_device_orchestrator`, `handle_evening`, `handle_family_brief`, `handle_gate`, `handle_health`, `handle_morning`, `handle_request`, `handle_review`, `handle_ssot`, `handle_status`, `handle_trace`, `metaos-engine`, `metaos_day`, `metaos_device_orchestrator`, `metaos_evening`, `metaos_family_brief`, `metaos_gate`, `metaos_health`, `metaos_morning`, `metaos_review`, `metaos_ssot`, `metaos_status`, `metaos_trace`

### aetherforge (10 tools)

`forge_cost_report`, `forge_generate`, `forge_generate_mesh`, `forge_health_check`, `forge_list_nodes`, `forge_mesh_status`, `forge_triage`, `forge_triage_batch`, `forge_triage_consensus`, `forge_triage_status`

### ecos-ssot (9 tools)

`check`, `compile`, `derive`, `evolve`, `extract_from_file`, `handle_message`, `ssot-kernel`, `stats`, `sync`

### kronos (7 tools)

`cloakbrowser`, `eidos`, `kos`, `kronos`, `ollama`, `vault`, `wps_note`

### ontoderive (7 tools)

`derive`, `handle_mcp_request`, `list_entities`, `ontoderive`, `pipeline_status`, `trace`, `validate`

### toolforge (5 tools)

`handle_request`, `ontoderive-toolforge`, `toolforge_guide`, `toolforge_match`, `toolforge_select`

*由 `bin/cockpit/gen-help-docs.py` 于 2026-08-02T12:56:53Z 生成*