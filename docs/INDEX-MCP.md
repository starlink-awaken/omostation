# MCP 服务器索引

> 自动生成于 1970-01-01T00:00:00Z
> 源: `docs/generated/capability-registry.yaml`

全生态共 **27** 个 MCP 服务器, **199** 个工具。

| 服务器 | 层 | 工具数 | 传输 | 端口 | 源文件 |
|--------|-----|--------|------|------|--------|
| `agora` | I0 | 110 | stdio/sse | — | `projects/agora/src/agora/server/mcp.py` |
| `ecos` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/mcp_server.py` |
| `ecos-ssot` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/l0/ssot/mcp_server.py` |
| `ecos-integration` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/services/integration/mcp_server.py` |
| `runtime` | L1 | 0 | stdio | — | `projects/runtime/src/runtime/mcp_server.py` |
| `gbrain` | L2 | 75 | stdio | — | `projects/knowledge/gbrain/src/core/operations/exports.ts` |
| `omo` | L2 | 0 | stdio | — | `projects/omo/src/omo/mcp_server.py` |
| `kos` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `kos-stdio` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/kos/src/kos/mcp/fastmcp_app.py` |
| `metaos` | L2 | 0 | stdio | — | `projects/metaos/src/metaos/mcp_server.py` |
| `iris` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/iris/src/iris/mcp_server.py` |
| `sophia` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/sophia/src/sophia/server/mcp_server.py` |
| `kronos` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/kronos/src/kronos/mcp_server.py` |
| `minerva` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/minerva/src/minerva/mcp_server/server.py` |
| `codeanalyze` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/codeanalyze/src/codeanalyze/mcp.py` |
| `forge` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/forge/src/mcp_server.py` |
| `ontoderive` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/ontoderive/src/ontoderive/mcp_server.py` |
| `toolforge` | L2 | 0 | stdio | — | `projects/knowledge/kairon/packages/ontoderive/src/ontoderive/toolforge/mcp_server.py` |
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

### agora (110 tools)

`a2a_cancel_task`, `a2a_get_task`, `a2a_list_tasks`, `a2a_send_task`, `add_route`, `agora_capability_discover`, `agora_execute`, `audit_query`, `audit_stats`, `bcos_evolve`, `bcos_north_star`, `bcos_signals`, `bos_documents_jobs`, `bos_documents_registry`, `bos_documents_state`, `bos_health`, `bos_inbox_archive`, `bos_inbox_draft`, `bos_inbox_pending`, `bos_inbox_search`, `bos_inbox_triage`, `bos_inbox_watch`, `bos_mail_draft`, `bos_mesh_dma_status`, `bos_metrics_status`, `bos_middleware_status`, `bos_reload_discovery`, `bos_reload_m1`, `bos_reload_routes`, `bos_spine_diff`, `bos_spine_distill`, `bos_spine_draft`, `bos_spine_replay`, `bos_spine_sign`, `bos_spine_status`, `cartridge_pack`, `check_health`, `create_api_key`, `daemon_bus_publish`, `debt_auto_seed_tool`, `entropy_cleanup_tool`, `get_agent_card`, `get_bos_schema`, `get_event_log`, `get_state_transitions`, `governance_auto_fix`, `health_check`, `lifecycle_load_all`, `lifecycle_start_watch`, `lifecycle_status`, `lifecycle_stop_watch`, `lifecycle_unload_all`, `list_agent_cards`, `list_api_keys`, `list_bos_domains`, `list_bos_resources`, `list_bos_tools`, `list_routes`, `list_services`, `mutate_resource`, `persona_bdsk_evaluate`, `proposal_triage`, `proxy_add_service`, `proxy_arch_health`, `proxy_backend_health`, `proxy_call`, `proxy_connect`, `proxy_governance_status`, `proxy_list_tools`, `proxy_omo_debt`, `proxy_remove_service`, `proxy_status`, `publish_event`, `read_resource`, `register_push_notification`, `register_service`, `registry_find_agent_tool`, `registry_health_tool`, `registry_heartbeat_tool`, `registry_list_agents_tool`, `registry_list_tasks_tool`, `registry_register_agent_tool`, `registry_submit_task_tool`, `repo_discover`, `repo_install`, `repo_load`, `repo_pipeline`, `repo_search`, `repo_status`, `repo_unload`, `resident_roles`, `resident_status`, `resolve_bos_uri`, `revoke_api_key`, `route_call`, `rules_lifecycle`, `subscribe_event`, `swarm_nodes`, `swarm_resolve`, `swarm_status`, `unwatch_resource`, `watch_resource`, `workflow_capability_health`, `workspace_audit_gitlink`, `workspace_audit_governance`, `workspace_audit_lint`, `workspace_audit_ops`, `workspace_audit_radar`, `workspace_audit_run`, `workspace_audit_ssot`

### gbrain (75 tools)

`add_link`, `add_tag`, `add_timeline_entry`, `cancel_job`, `code_blast`, `code_callees`, `code_callers`, `code_def`, `code_flow`, `code_refs`, `code_traversal_cache_clear`, `delete_page`, `extract_facts`, `file_list`, `file_upload`, `file_url`, `find_anomalies`, `find_contradictions`, `find_experts`, `find_orphans`, `find_trajectory`, `forget_fact`, `get_backlinks`, `get_brain_identity`, `get_calibration_profile`, `get_chunks`, `get_health`, `get_ingest_log`, `get_job`, `get_job_progress`, `get_links`, `get_page`, `get_raw_data`, `get_recent_salience`, `get_recent_transcripts`, `get_stats`, `get_tags`, `get_timeline`, `get_versions`, `list_jobs`, `list_pages`, `log_ingest`, `memory_tree`, `pause_job`, `purge_deleted_pages`, `put_page`, `put_raw_data`, `query`, `recall`, `remove_link`, `remove_tag`, `replay_job`, `resolve_slugs`, `restore_page`, `resume_job`, `retry_job`, `revert_version`, `run_doctor`, `search`, `search_by_image`, `send_job_message`, `sources_add`, `sources_list`, `sources_remove`, `sources_status`, `submit_agent`, `submit_job`, `sync_brain`, `takes_calibration`, `takes_list`, `takes_scorecard`, `takes_search`, `think`, `traverse_graph`, `whoami`

### agent-runtime (14 tools)

`cards_check`, `cards_status`, `chat`, `domain_context`, `domain_controller_shadow_status`, `domain_facts_audit`, `domain_facts_validation_status`, `domain_model_freshness_status`, `domain_project_status`, `domain_sanyi_status_consistency_status`, `domains_list`, `kems_status`, `run_task`, `workspace_context`

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*