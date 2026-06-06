# 差距分析：架构方案 vs 当前实现

> 依据: WF-2 差距分析流程 | 对比源: phase1-架构工程/ 9 篇文档
> 时间: 2026-05-27

---

## 总览

| 层 | 方案要求 | 当前实现 | 完成度 | 差距等级 |
|:--|---------|---------|:-----:|:-------:|
| **P0** | workspace CLI + profile + dashboard | CLI ✅, profile JSON ✅, dashboard ❌ | **85%** | 🟡 |
| **L1** | 5核心契约 + Schema版本化 | 8schemas ✅, 版本化策略 ✅, 缺2个schema | **90%** | 🟢 |
| **L2** | Agora/KOS/agentmesh/Forge/gbrain | 全部存在, ResourceAccounting ✅, build ✅ | **98%** | 🟢 |
| **L3** | TaskObject + Agora降级模式 | TaskObject ✅, **降级模式❌** | **70%** | 🔴 |
| **L4** | 身份/愿景/原则/框架 MCP | 全部存在, profile.json ✅ | **90%** | 🟡 |
| **X1** | 审计/授权/信任/免疫 | arcnode ✅, SSOT ✅, 信任模型部分实现 | **85%** | 🟢 |
| **X2** | 保鲜管线+统一守护进程 | 5个脚本✅, **无统一守护进程❌** | **60%** | 🔴 |
| **X3** | 价值层级+共识+半衰期 | KOS有字段✅, **未跨项目覆盖❌** | **75%** | 🟡 |

**加权完成度: ~84%**

---

## 🔴 严重差距（需近期处理）

### G1: L3 Agora 降级模式缺失

| 维度 | 内容 |
|------|------|
| **架构要求** | pat-09 §3.3: "Agora不可用时, Agent之间通过A2A直接通信" |
| **实际状态** | Agora是全系统MCP路由单点。Agora进程crash → 所有Agent之间无法发现/调用 |
| **影响范围** | 所有cron任务、Agent协作、MCP服务调用 |
| **建议修复** | ① Agora的Router加本地缓存(服务列表) ② Agent端加fallback: Agora不可用→直连已知服务 ③ 混沌测试验证 |

### G2: X2 无统一守护进程

| 维度 | 内容 |
|------|------|
| **架构要求** | pat-09 §7: 抗熵系统持续运行, 自回收, 不自膨胀 |
| **实际状态** | 5个独立脚本(freshness-watch/health-monitor/dual-baseline/auto-archive/freshness_check)各有cron, 无统一协调者 |
| **影响范围** | 保鲜策略碎片化, 无法做全局熵检测 → 系统自然退化 |
| **建议修复** | ① 当前x2-pipeline-runner是好的起点 ② 升级为常驻守护进程, 按schedule跑管线 ③ 加状态检查: `x2 status` 查看各环节健康度 |

---

## 🟡 中度差距（可规划）

### G3: X3 value_tier 未跨项目覆盖

| 维度 | 内容 |
|------|------|
| **架构要求** | pat-42: 7个价值层级需要跨项目一致 |
| **实际状态** | KOS ontology 有 value_tier/half_life/freshness 字段, 但 MetaOS/SSOT 无这些字段 |
| **影响范围** | 跨项目实体无法统一做保鲜管理 |
| **建议修复** | ① L1 Schema补充value_tier字段 ② MetaOS/SSOT 新增字段 ③ 治理检查: value_tier全覆盖 |

### G4: P0 profile 非 DB 持久化

| 维度 | 内容 |
|------|------|
| **架构要求** | pat-09 §2: 身份系统可版本化、可迁移 |
| **实际状态** | ~/.kos/self/profile.json 文件存储, 无版本历史, 无事务保护 |
| **建议修复** | ① 迁移到 SQLite (复用KOS SQLite机制) ② 保留JSON兼容读 ③ 自动迁移脚本 |

### G5: L4 profile 无版本历史

| 维度 | 内容 |
|------|------|
| **架构要求** | 身份变更可追溯 |
| **实际状态** | update_profile 直接覆写 profile.json, 无changelog |
| **建议修复** | ① update_profile 加变更日志到 SQLite ② CLI `profile history` 查看变更记录 |

---

## 🟢 轻度差距（监控即可）

### G6: L1 缺2个Schema文件

| 维度 | 内容 |
|------|------|
| **架构要求** | 5个核心契约: WorkspaceObject/IdentityEnvelope/CapabilityGrant/EventEnvelope + Principle/Decision |
| **实际状态** | 8个Schema, 涵盖identity-envelope/capability-grant/task-object/consensus/value-principle等. principle-decision 和 event-envelope 无独立文件, 但内容已分散在其他schema中 |
| **影响** | 低 — 核心契约已有, 只是命名/文件组织未完全对齐 |
| **建议** | ① 检查identity-envelope是否够用 ② 如缺则新增principle-decision.schema.json |

### G7: X1 信任模型部分实现

| 维度 | 内容 |
|------|------|
| **架构要求** | 3种信任模型: CA/PGP/WoT |
| **实际状态** | CA模型已实践(IdentityEnvelope + CapabilityGrant), PGP/WoT未实现 |
| **影响** | 低 — 个人环境CA模型够用, WoT在多人组织才需要 |
| **建议** | 暂缓, 进入多人阶段再实现 |

---

## 修复时间估计

| 差距 | 层 | 估时 | 复杂度 |
|:----:|:--:|:----:|:------:|
| G1 Agora降级模式 | L3 | **3h** | ⭐⭐⭐ (需要改Router+Agent两端) |
| G2 X2统一守护进程 | X2 | **2h** | ⭐⭐ (升级pipeline-runner) |
| G3 X3跨项目value_tier | X3 | **1h** | ⭐ (加L1 Schema字段) |
| G4 P0 profile DB持久化 | P0 | **1h** | ⭐⭐ (迁移+兼容读) |
| G5 L4 profile版本历史 | L4 | **30min** | ⭐ (加changelog) |
| G6 L1补充schema | L1 | **30min** | ⭐ (检查+补文件) |

**合计: ~8h**

---

## 优先级建议

```
Phase 7:
  Wave 7.1: G1 Agora降级模式 (3h) — 🔴 单点故障
  Wave 7.2: G2 X2守护进程 (2h) — 🔴 系统退化

Phase 8:
  Wave 8.1: G3+G4+G5 (2.5h) — 🟡 质量提升
  Wave 8.2: G6 (30min) — 🟢 完善

合计: 8h, 2个Phase, 4个Wave
```
