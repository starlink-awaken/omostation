---
type: ephemeral
created: 2026-09-03
---

# 算力路由双 Owner 收敛决策 — BET-Y1Q3-T1-06

> 日期: 2026-08-16 · Owner: governance-team · Status: accepted

## 背景

两周架构分析发现算力路由存在**双 owner 职责重叠**：
- **aetherforge**（projects/aetherforge，omostation-aetherforge 仓）：算力网关，活跃（08-15 #37 MBP intents 定向本地模型）
- **gac-mesh-router**（bin/_archive/2026-08-conv3/gac-mesh-router.py）：独立 mesh 流式路由代理（HTTP server port 7437）

## 证据对比

| 维度 | aetherforge | gac-mesh-router |
|---|---|---|
| BOS 服务登记 | ✅ `bos://memory/aetherforge/mcp-server` + `forge_list_nodes`/`forge_n_status`/`forge_health_check` 等 tools | ❌ 无 BOS 登记 |
| 主仓引用 | ✅ 9 处（AGENTS.md / registry / ci-architecture / external-connection-fabric 等） | ❌ 零引用（仅自身文件） |
| governance-checks 接线 | ✅ 有 | ❌ 未接线 |
| 活跃度 | 活跃（08-15 #37） | 无近期提交证据 |
| 端口 | 7422/7431 体系 | 7437 孤立端口 |

## 决策

**算力路由单一 owner = aetherforge**。理由：
1. aetherforge 已承担实际算力网关职责（BOS 服务 + forge_* tools + 活跃开发），是生态实际消费方
2. gac-mesh-router 主仓零引用、未接 BOS/governance，是**孤立实现**（无消费者）
3. 收敛到 aetherforge 符合"能力市场"方向（BOS 是唯一能力入口，mesh 路由应作为 aetherforge 内部能力而非独立二进制）

## 落地

1. **gac-mesh-router → deprecated**（`docs/project-registry.yaml` status: implemented-in-bin → deprecated）
   - 保留文件不删除（可能仍被历史文档/端口引用，待归档评估）
   - 不在 governance-checks 新接线
2. **aetherforge 指针同步**：agora 内嵌副本 b9a299f → 905195b（已完成，agora aabe4a9e）
3. **影响面**：7437 端口保留声明（protocols/port-registry.yaml 不动），mesh 路由能力迁移责任由 aetherforge 后续版本承担

## 待办（后续 bet）
- gac-mesh-router 归档评估（确认 7437 端口无消费者后移 _archive/）
- aetherforge 承接 mesh 路由能力的排期（若确需独立 mesh 层）

## 关联
- BET: BET-Y1Q3-T1-06
- Debt: D-2（算力路由双 owner）
- Registry: docs/project-registry.yaml::mesh-router
