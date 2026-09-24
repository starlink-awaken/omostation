# MCP 服务器索引

> 自动生成于 1970-01-01T00:00:00Z
> 源: `docs/generated/capability-registry.yaml`

全生态共 **27** 个 MCP 服务器, **135** 个工具。

| 服务器 | 层 | 工具数 | 传输 | 端口 | 源文件 |
|--------|-----|--------|------|------|--------|
| `agora` | I0 | 111 | stdio/sse | — | `projects/agora/src/agora/server/mcp.py` |
| `ecos` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/mcp_server.py` |
| `ecos-ssot` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/l0/ssot/mcp_server.py` |
| `ecos-integration` | L0 | 0 | stdio | — | `projects/ecos/src/ecos/services/integration/mcp_server.py` |
| `runtime` | L1 | 0 | stdio | — | `projects/runtime/src/runtime/mcp_server.py` |
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
| `gbrain` | L2 | 0 | stdio | — | `projects/knowledge/gbrain/src/core/operations/exports.ts` |
| `agent-runtime` | L3 | 0 | stdio | — | `projects/cockpit/src/cockpit/agent_runtime_mcp_server.py` |
| `l4-kernel` | L4 | 0 | stdio/http/sse | http:7455, sse:7456 | `projects/l4-kernel/src/l4_kernel/mcp_server.py` |
| `model-driven` | M0 | 0 | stdio | — | `projects/model-driven/src/model_driven/mcp_server.py` |
| `model-driven-fastmcp` | M0 | 0 | stdio | — | `projects/model-driven/src/model_driven/fastmcp_server.py` |
| `aetherforge` | X | 15 | stdio | — | `projects/aetherforge/src/aetherforge/mcp_server.py` |
| `aetherforge-mesh` | X | 6 | stdio | — | `projects/aetherforge/packages/mesh/src/compute_mesh/api/mcp_server.py` |
| `aetherforge-gateway` | X | 3 | stdio | — | `projects/aetherforge/packages/gateway/src/llm_gateway/mcp_server.py` |
| `c2g` | X | 0 | stdio | — | `projects/omo/src/omo/_vendored/c2g/mcp_server.py` |
| `family-hub` | X | 0 | stdio | — | `projects/family-hub/mcp_server.py` |

## 工具清单

### agora (111 tools)

`a2a_cancel_task`, `a2a_get_task`, `a2a_list_tasks`, `a2a_send_task`, `a2a_update_task`, `add_route`, `agora_capability_discover`, `agora_execute`, `audit_query`, `audit_stats`, `bcos_evolve`, `bcos_north_star`, `bcos_signals`, `bos_documents_jobs`, `bos_documents_registry`, `bos_documents_state`, `bos_health`, `bos_inbox_archive`, `bos_inbox_draft`, `bos_inbox_pending`, `bos_inbox_search`, `bos_inbox_triage`, `bos_inbox_watch`, `bos_mail_draft`, `bos_mesh_dma_status`, `bos_metrics_status`, `bos_middleware_status`, `bos_reload_discovery`, `bos_reload_m1`, `bos_reload_routes`, `bos_spine_diff`, `bos_spine_distill`, `bos_spine_draft`, `bos_spine_replay`, `bos_spine_sign`, `bos_spine_status`, `cartridge_pack`, `check_health`, `create_api_key`, `daemon_bus_publish`, `debt_auto_seed_tool`, `entropy_cleanup_tool`, `get_agent_card`, `get_bos_schema`, `get_event_log`, `get_state_transitions`, `governance_auto_fix`, `health_check`, `lifecycle_load_all`, `lifecycle_start_watch`, `lifecycle_status`, `lifecycle_stop_watch`, `lifecycle_unload_all`, `list_agent_cards`, `list_api_keys`, `list_bos_domains`, `list_bos_resources`, `list_bos_tools`, `list_routes`, `list_services`, `mutate_resource`, `persona_bdsk_evaluate`, `proposal_triage`, `proxy_add_service`, `proxy_arch_health`, `proxy_backend_health`, `proxy_call`, `proxy_connect`, `proxy_governance_status`, `proxy_list_tools`, `proxy_omo_debt`, `proxy_remove_service`, `proxy_status`, `publish_event`, `read_resource`, `register_push_notification`, `register_service`, `registry_find_agent_tool`, `registry_health_tool`, `registry_heartbeat_tool`, `registry_list_agents_tool`, `registry_list_tasks_tool`, `registry_register_agent_tool`, `registry_submit_task_tool`, `repo_discover`, `repo_install`, `repo_load`, `repo_pipeline`, `repo_search`, `repo_status`, `repo_unload`, `resident_roles`, `resident_status`, `resolve_bos_uri`, `revoke_api_key`, `route_call`, `rules_lifecycle`, `subscribe_event`, `swarm_nodes`, `swarm_resolve`, `swarm_status`, `unwatch_resource`, `watch_resource`, `workflow_capability_health`, `workspace_audit_gitlink`, `workspace_audit_governance`, `workspace_audit_lint`, `workspace_audit_ops`, `workspace_audit_radar`, `workspace_audit_run`, `workspace_audit_ssot`

### aetherforge (15 tools)

`forge_cost_report`, `forge_fabric_compact`, `forge_fabric_inspect`, `forge_fabric_vram`, `forge_fabric_warm`, `forge_generate`, `forge_generate_mesh`, `forge_health_check`, `forge_list_nodes`, `forge_mesh_status`, `forge_swarm_run`, `forge_triage`, `forge_triage_batch`, `forge_triage_consensus`, `forge_triage_status`

### aetherforge-mesh (6 tools)

`mesh_cost_report`, `mesh_generate`, `mesh_health_check`, `mesh_list_nodes`, `mesh_status`, `mesh_wakeup`

### aetherforge-gateway (3 tools)

`gateway_generate`, `gateway_health`, `llm_generate`

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*