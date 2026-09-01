# MCP 服务器索引

> 自动生成于 1970-01-01T00:00:00Z
> 源: `docs/generated/capability-registry.yaml`

全生态共 **27** 个 MCP 服务器, **290** 个工具。

| 服务器 | 层 | 工具数 | 传输 | 端口 | 源文件 |
|--------|-----|--------|------|------|--------|
| `agora` | I0 | 104 | stdio/sse | — | `projects/agora/src/agora/server/mcp.py` |
| `ecos` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/mcp_server.py` |
| `ecos-ssot` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/l0/ssot/mcp_server.py` |
| `ecos-integration` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/services/integration/mcp_server.py` |
| `runtime` | L1 | 0 | stdio | — | `projects/runtime/src/runtime/mcp_server.py` |
| `kos` | L2 | 44 | stdio | — | `projects/knowledge/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `kos-stdio` | L2 | 44 | stdio | — | `projects/knowledge/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `codeanalyze` | L2 | 25 | stdio | — | `projects/knowledge/kairon/packages/codeanalyze/src/codeanalyze/mcp.py` |
| `kronos` | L2 | 16 | stdio | — | `projects/knowledge/kairon/packages/kronos/src/kronos/mcp_server.py` |
| `iris` | L2 | 8 | stdio | — | `projects/knowledge/kairon/packages/iris/src/iris/mcp_server.py` |
| `sophia` | L2 | 8 | stdio | — | `projects/knowledge/kairon/packages/sophia/src/sophia/server/mcp_server.py` |
| `minerva` | L2 | 8 | stdio | — | `projects/knowledge/kairon/packages/minerva/src/minerva/mcp_server/server.py` |
| `forge` | L2 | 7 | stdio | — | `projects/knowledge/kairon/packages/forge/src/mcp_server.py` |
| `ontoderive` | L2 | 7 | stdio | — | `projects/knowledge/kairon/packages/ontoderive/src/ontoderive/mcp_server.py` |
| `toolforge` | L2 | 5 | stdio | — | `projects/knowledge/kairon/packages/ontoderive/src/ontoderive/toolforge/mcp_server.py` |
| `omo` | L2 | 0 | stdio | — | `projects/omo/src/omo/mcp_server.py` |
| `metaos` | L2 | 0 | stdio | — | `projects/metaos/src/metaos/mcp_server.py` |
| `gbrain` | L2 | 0 | stdio | — | `projects/knowledge/gbrain/src/core/operations/exports.ts` |
| `agent-runtime` | L3 | 14 | stdio | — | `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py` |
| `l4-kernel` | L4 | 0 | stdio/http/sse | http:7455, sse:7456 | `projects/l4-kernel/src/l4_kernel/mcp_server.py` |
| `model-driven` | M0 | 0 | stdio | — | `projects/model-driven/src/model_driven/mcp_server.py` |
| `model-driven-fastmcp` | M0 | 0 | stdio | — | `projects/model-driven/src/model_driven/fastmcp_server.py` |
| `aetherforge` | X | 0 | stdio | — | `projects/aetherforge/src/aetherforge/mcp_server.py` |
| `aetherforge-gateway` | X | 0 | stdio | — | `projects/aetherforge/packages/gateway/src/llm_gateway/mcp_server.py` |
| `aetherforge-mesh` | X | 0 | stdio | — | `projects/aetherforge/packages/mesh/src/compute_mesh/api/mcp_server.py` |
| `c2g` | X | 0 | stdio | — | `projects/omo/src/omo/_vendored/c2g/mcp_server.py` |
| `family-hub` | X | 0 | stdio | — | `projects/family-hub/mcp_server.py` |

## 工具清单

### agora (104 tools)

`a2a_cancel_task`, `a2a_get_task`, `a2a_list_tasks`, `a2a_send_task`, `add_route`, `agora_capability_discover`, `agora_execute`, `audit_query`, `audit_stats`, `bcos_evolve`, `bcos_north_star`, `bcos_signals`, `bos_health`, `bos_inbox_archive`, `bos_inbox_draft`, `bos_inbox_pending`, `bos_inbox_search`, `bos_inbox_triage`, `bos_inbox_watch`, `bos_mesh_dma_status`, `bos_metrics_status`, `bos_middleware_status`, `bos_reload_discovery`, `bos_reload_m1`, `bos_reload_routes`, `bos_spine_diff`, `bos_spine_draft`, `bos_spine_sign`, `bos_spine_status`, `cartridge_pack`, `check_health`, `create_api_key`, `daemon_bus_publish`, `debt_auto_seed_tool`, `entropy_cleanup_tool`, `get_agent_card`, `get_bos_schema`, `get_event_log`, `get_state_transitions`, `governance_auto_fix`, `health_check`, `lifecycle_load_all`, `lifecycle_start_watch`, `lifecycle_status`, `lifecycle_stop_watch`, `lifecycle_unload_all`, `list_agent_cards`, `list_api_keys`, `list_bos_domains`, `list_bos_resources`, `list_bos_tools`, `list_routes`, `list_services`, `mutate_resource`, `persona_bdsk_evaluate`, `proposal_triage`, `proxy_add_service`, `proxy_arch_health`, `proxy_backend_health`, `proxy_call`, `proxy_connect`, `proxy_governance_status`, `proxy_list_tools`, `proxy_omo_debt`, `proxy_remove_service`, `proxy_status`, `publish_event`, `read_resource`, `register_push_notification`, `register_service`, `registry_find_agent_tool`, `registry_health_tool`, `registry_heartbeat_tool`, `registry_list_agents_tool`, `registry_list_tasks_tool`, `registry_register_agent_tool`, `registry_submit_task_tool`, `repo_discover`, `repo_install`, `repo_load`, `repo_pipeline`, `repo_search`, `repo_status`, `repo_unload`, `resident_roles`, `resident_status`, `resolve_bos_uri`, `revoke_api_key`, `route_call`, `rules_lifecycle`, `subscribe_event`, `swarm_nodes`, `swarm_resolve`, `swarm_status`, `unwatch_resource`, `watch_resource`, `workflow_capability_health`, `workspace_audit_gitlink`, `workspace_audit_governance`, `workspace_audit_lint`, `workspace_audit_ops`, `workspace_audit_radar`, `workspace_audit_run`, `workspace_audit_ssot`

### kos (44 tools)

`build_context`, `check_subscription`, `collab.add_artifact`, `collab.claim_subtask`, `collab.create_task`, `collab.get_task`, `collab.list_tasks`, `collab.update_task`, `consensus.create`, `consensus.get`, `consensus.list_expired`, `consensus.renew`, `consensus.trace`, `cross_domain_sync`, `db_vacuum`, `entity_explore`, `fact_check`, `full_sync`, `get_entity`, `get_entity_timeline`, `get_knowledge`, `get_stats`, `get_system_status`, `graph_search`, `knowledge_ask`, `list_domains`, `mcp_market_discover`, `memory_stats`, `ontology_graph`, `ontology_rebuild`, `research_now`, `research_pipeline`, `run_indexer`, `search_entity`, `search_knowledge`, `self.get_current_role`, `self.get_profile`, `self.get_vision_summary`, `semantic_scholar`, `semantic_search`, `subscribe_topic`, `sync_gbrain`, `verify_claim`, `viz_render`

### kos-stdio (44 tools)

`build_context`, `check_subscription`, `collab.add_artifact`, `collab.claim_subtask`, `collab.create_task`, `collab.get_task`, `collab.list_tasks`, `collab.update_task`, `consensus.create`, `consensus.get`, `consensus.list_expired`, `consensus.renew`, `consensus.trace`, `cross_domain_sync`, `db_vacuum`, `entity_explore`, `fact_check`, `full_sync`, `get_entity`, `get_entity_timeline`, `get_knowledge`, `get_stats`, `get_system_status`, `graph_search`, `knowledge_ask`, `list_domains`, `mcp_market_discover`, `memory_stats`, `ontology_graph`, `ontology_rebuild`, `research_now`, `research_pipeline`, `run_indexer`, `search_entity`, `search_knowledge`, `self.get_current_role`, `self.get_profile`, `self.get_vision_summary`, `semantic_scholar`, `semantic_search`, `subscribe_topic`, `sync_gbrain`, `verify_claim`, `viz_render`

### codeanalyze (25 tools)

`analyze_project`, `architecture_generate_diagram`, `architecture_get_code_metrics`, `ast_search`, `audit_project`, `cgc_query`, `codegraph_callees`, `codegraph_callers`, `codegraph_context`, `codegraph_get_affected_tests`, `codegraph_get_impact_radius`, `codegraph_get_symbol_graph`, `codegraph_init`, `codegraph_search`, `codegraph_sync`, `crg_build`, `crg_status`, `export_graph`, `extract_policy_docs`, `pack_repo`, `rg_search`, `scan_directory`, `status`, `workflow_impact_analysis`, `workflow_onboarding`

### kronos (16 tools)

`cloakbrowser`, `eidos`, `kos`, `kronos`, `kronos_browser_fetch`, `kronos_extract`, `kronos_fetch`, `kronos_insight`, `kronos_pipelines`, `kronos_plan`, `kronos_route`, `kronos_status`, `kronos_tools`, `ollama`, `vault`, `wps_note`

### agent-runtime (14 tools)

`cards_check`, `cards_status`, `chat`, `domain_context`, `domain_controller_shadow_status`, `domain_facts_audit`, `domain_facts_validation_status`, `domain_model_freshness_status`, `domain_project_status`, `domain_sanyi_status_consistency_status`, `domains_list`, `kems_status`, `run_task`, `workspace_context`

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

### toolforge (5 tools)

`handle_request`, `ontoderive-toolforge`, `toolforge_guide`, `toolforge_match`, `toolforge_select`

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*