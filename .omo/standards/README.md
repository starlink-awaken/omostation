# .omo Standards Registry

> `.omo/standards/` 的入口注册表。
> 当前只将 **跨阶段、持续生效、会被 workflow 直接引用** 的文档视为 active standards。

---

## Active standards

| 文件 | 角色 |
|------|------|
| `ARCHITECTURE_CONVERGENCE.md` | 架构边界与收敛原则 |
| `planning-blueprint-delivery-test-standard.md` | 规划 / 交付 / 测试统一标准 |
| `agent-cli-worker-collaboration.md` | 外部 worker 协作、dispatch、reclaim、handoff |
| `agent-registry-heartbeat.md` | registry heartbeat / liveness 契约 |
| `operation-levels.md` | L0-L3 操作分级定义 + rollout 基线 |
| `mcp-tool-and-transport-standard.md` | MCP 工具返回契约 + 传输约束 |
| `phase2-full-execution-go-no-go.md` | 当前 phase 执行门禁标准 |
| `ssot-7-domain-schema.md` | SSOT 7 域 schema 规范 |

## Supporting references

| 文件 | 说明 |
|------|------|
| `kos-baseline-drift-monitor.md` | KOS baseline 监控标准，偏专项运行规范 |
| `hardcoded-paths-inventory.md` | 历史硬编码路径清点，偏治理 inventory |

## Legacy / merged / historical

| 文件 | 当前状态 | 去向 |
|------|----------|------|
| `MCP_STANDARDS.md` | merged | `mcp-tool-and-transport-standard.md` |
| `mcp-transport.md` | merged | `mcp-tool-and-transport-standard.md` |
| `operation-level-rollout-plan.md` | merged | `operation-levels.md` |
| `post-phase1-governance-and-phase2-entry.md` | historical gate snapshot | `goals/current.yaml` + `phase2-full-execution-go-no-go.md` |

## Usage rules

1. `tasks/README.md` 与 `plans/README.md` 只能引用 active standards。
2. legacy / historical 文档可作为证据或背景，不再作为新的执行入口。
3. 若新增 standard，必须同时更新本注册表与 `.omo/INDEX.md`。
