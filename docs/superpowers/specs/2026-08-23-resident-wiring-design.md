---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-08-24



bet_id: BET-Y1Q3-T1-10
type: ssot
last_updated: 2026-09-03
---

# Resident 体系全面接线 — 配置/文档/治理/CI/MCP/BOS URI 感知

> Status: accepted
> Date: 2026-08-23
> BET: BET-Y1Q3-T1-10
> Track: T1-TRUTH · Window: Y1Q3 · Priority: P1 · Appetite: 2 days

## Problem

resident 常驻 agent 体系（WP-A~I / ADR-0396）运行时已就绪（`projects/omo/src/omo/resident/`
11 模块 + 路由表 + 角色 + 测试），但**感知面存在系统性缺口**，agent 无法从治理/工具/
CI 平面感知并调用 resident：

1. **Agora MCP 工具缺失**：`projects/agora/src/agora/mcp/tools/` 仅 5 个工具
   （bos_capability_lifecycle / bos_resolve / bos_yaml_lint / fabric / forge），无
   `resident_status` / `resident_roles`。而 `docs/architecture/resident-agent-system-v1.md` §3
   声称「Agora MCP 工具已接线」→ **文档声明与实际漂移**。
2. **L0 enforcement 悬空**：`L0-constraints.yaml` 三条 CR-RESIDENT-*（STATUS-01 / MOF-SYNC-01 /
   BOS-01）的 `enforcement` 字段引用了不存在的 check 工具（`CR-RESIDENT (check 工具) +
   gac-local-gate`），违反 D0「声明必须有实体」。
3. **governance-checks.yaml 无 CR-RESIDENT 条目**：40+ 条 CR-* 均无 resident 覆盖，L0 约束
   未在治理检查层登记。
4. **ci-surfaces.yaml 无 resident 平面**：CI 平面登记表（ADR-0379）无 resident 相关 surface。
5. **agent-workflows registry 无 resident 感知**：`.omo/_truth/registry/agent-workflows/`
   （workflows/adapters/profiles/_root.yaml）无任何 resident 覆盖。
6. **sgf-policy.yaml 无 resident gate**：62 个 MOF gates 无 resident 活性/角色/BOS 路由 gate。

## Architecture

接线原则：**不新增 resident 运行时能力**（载体/规则路由/角色/契约修复均已 done），只补感知面
声明与可执行检查。所有 check 工具走既有 `bin/gac/` 单前缀命名（ADR-0115），登记进
`governance-checks.yaml`（`type: python` + `module` + `class` + `severity` + `enabled`）。

### 分面设计

**F1 — CR-RESIDENT check 工具（3 个）**

| 工具 | 校验内容 | 对应 L0 约束 |
|------|----------|--------------|
| `bin/gac/check-resident-status.py` | daemon byte_offset 水位新鲜度（stale 30min） | CR-RESIDENT-STATUS-01 |
| `bin/gac/check-resident-mof-sync.py` | roles.py 与 MOF AGENT-RESIDENT-ROLES 双份对齐，drift=0 | CR-RESIDENT-MOF-SYNC-01 |
| `bin/gac/check-resident-bos.py` | bos-services.yaml + bos-registry.json 含 `bos://resident/*` 4 条，且 BOS_URI_DOMAINS 含 resident | CR-RESIDENT-BOS-01 |

三个工具 exit 0=通过 / exit 1=违规（fail-closed），独立可跑 + 可被 gac-local-gate 聚合。

**F2 — 治理检查登记**：`governance-checks.yaml` 追加 3 条 CR-RESIDENT-*（dimension 对齐
L0：X2 / X4 / X1），enforcement 指向 F1 工具，消除 L0 悬空引用。

**F3 — CI 平面登记**：`ci-surfaces.yaml` 追加 resident 平面（omo resident 测试 + 三个
CR-RESIDENT checks），使 CI 可观测性（ADR-0379）覆盖 resident。

**F4 — agent-workflows 感知**：`agent-workflows/` registry 补 resident workflow
（如 `resident-runtime-observe`）+ adapter/profile 引用，让 agent 从 workflow 层可感知
resident 运维动作（status / roles / promote）。

**F5 — Agora MCP 工具**：`projects/agora/src/agora/mcp/tools/` 新增 `resident_status.py` /
`resident_roles.py`，经 `resolver/services.py` 声明式路由到 `bos://resident/core/status` /
`bos://resident/core/roles`（bus-foundation stdio 传输），补齐文档声明的接线。

**F6 — sgf-policy gate**：`sgf-policy.yaml` 追加 resident 活性/角色/BOS 路由 gate（若
F1/F2 已覆盖则由 CR-RESIDENT 条目满足，避免重复登记——实现时以 gac-local-gate 聚合为准）。

**F7 — 文档对齐**：`docs/architecture/resident-agent-system-v1.md` §3 的 Agora MCP 声明在
F5 落地后由「已接线」保持为真实；AGENTS.md/CLAUDE.md resident 章节路径已核实准确
（`bin/ssot/*` 兼容脚本全部存在），无需修正。

## done_when

- [ ] `bin/gac/check-resident-{status,mof-sync,bos}.py` 三工具存在且 exit 0（独立可跑）
- [ ] `governance-checks.yaml` 登记 3 条 CR-RESIDENT-*，L0 enforcement 悬空消除
- [ ] `ci-surfaces.yaml` 登记 resident 平面
- [ ] `agent-workflows/` registry 补 resident 感知（workflow + adapter/profile）
- [ ] agora MCP 新增 `resident_status` / `resident_roles` 工具并经 BOS 路由可调
- [ ] `resident-agent-system-v1.md` §3 Agora MCP 声明与实际一致（非空声明）
- [ ] `bet-ledger.py lint` + `agent-workflow.py lint` exit 0

## Non-goals

- 不新开发 resident 运行时能力（execute 契约修复已完成）
- 不改 `projects/omo/src/omo/resident/` 核心逻辑
- 不新增台账治理以外的子项目 / 不扩 sink 渠道（ALERT_SLACK_WEBHOOK 待用户提供，另行处理）
