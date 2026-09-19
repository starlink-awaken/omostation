---
schema_version: specification/v1
spec_version: 1.0.0
title: omostation 架构分析与需求收敛
bet_id: BET-Y1Q4-T10-03
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
type: ssot
last_updated: 2026-09-04
---

# omostation 架构分析与需求收敛（BET-Y1Q4-T10-03）

## 背景（Context）

`omostation` 作为根工作区，既有治理文档、SSOT 事实层，也有多项目子仓、多执行后端和长期工作流。当前系统已经具备显著的治理强度，但在“主线架构 / 执行适配层 / 多 Agent 协作机制 / 运行时边界”之间仍存在一定的收敛余量。

这一 bet 的目的不是做一次盲目的重构，而是先形成规范、可审计的架构分析结论和需求文档，作为后续治理收敛、统一控制面、执行后端收口、状态审计的基线。

## 目标（Goal）

1. 明确 `omostation` 的本体定位：它是治理驱动的 Agent OS，而不是传统单体应用。
2. 梳理主线架构、入口层、治理层、Resident Agent 层、BOS 路由和执行后端之间的真实关系。
3. 解释多 Agent 协作机制的核心设计：worktree 隔离、workflow start/claim/verify/closeout、resident roles 和统一控制面限制。
4. 识别 `multica` / `orca` / `pi-worker` / `local` 等适配层在整体系统中的真实角色。
5. 形成可执行的架构优化方案，覆盖短期、中期、长期路线和优先级排序。
6. 把以上结论固化为可审计的文档与 bet ledger，确保后续工程、审查和回滚都有事实来源。

## 非目标（Non-Goals）

- 不进行大范围生产代码重构；本 bet 以文档/需求/架构分析为主。
- 不制造第二控制面，不把专项 worker adapter 伪装成主线架构。
- 不扩展为对所有子模块执行统一大规模改造。
- 不绕过工作流/SSOT/审计机制。

## 关键输出（Deliverables）

1. 结构化分析文档：`docs/plans/2026-09-04-architecture-analysis-and-requirements-consolidation.md`
2. 该 bet 的 ledger 记录：`docs/plans/3y-bet-ledger.yaml`
3. 用于 binding 的 spec 文件：`docs/superpowers/specs/2026-09-04-architecture-analysis-requirements-spec.md`

## 完成标准（Done When）

1. 需求文档中已明确定义：主线架构、执行后端、治理边界、风险、验收标准和优化路线。
2. 结论清晰区分“主线架构”与“专项执行适配层”，并明确控制面与执行面边界。
3. `bet-ledger` 中已写入 `BET-Y1Q4-T10-03`，且拥有唯一 accepted specification binding。
4. 该 spec 文件的 digest 与 ledger 中记录的 `content_digest` 一致。
5. 所有文档结论均可追溯到 `README.md`、`AGENTS.md`、`CLAUDE.md`、`ARCHITECTURE.md`、内核代码和 registry 文件。

## 审核与验收（Verification）

- `python3 -c "import yaml, pathlib; ..."` 校验 ledger YAML 并可解析。
- `git diff --stat` 对交付物范围做审查。
- `make agent-workflow-bootstrap` / `agent-workflow start` / `claim` / `verify` / `closeout` 继续按 workflow 规则执行。
