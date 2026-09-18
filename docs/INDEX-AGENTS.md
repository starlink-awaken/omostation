---
type: ssot
owner: governance-team
last_updated: 2026-09-17
---

# INDEX-AGENTS.md — Agent 能力索引

> **维护规则**
> - owner: governance-team
> - trigger: Agent CLI 升级 / 新增 skill / 配置变更
> - method: 脚本生成 (bin/ssot/gen-agents-index.py)
> - validation: skill 数与实际目录一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: 2026-09-17T01:02:46.379929+00:00

---

## 本地 Agent CLI

| CLI | 配置位置 | 说明 |
|-----|---------|------|
| Claude Code | `~/.claude/` | 主要开发 Agent |
| Codex | `~/.codex/` | 代码专家 Agent |
| OpenCode | `~/.opencode/` | 开源协作 Agent |
| OMO | `projects/omo/` | 治理 Agent (项目级) |


---

## 技能分布

| 位置 | 性质 |
|------|------|
| `.agents/skills/` | 项目级 Skills (工作区通用) |


---

## 项目级 Skills (.agents/skills/)

| Skill | 用途 | 触发场景 |
|-------|------|---------|
| `a2a-coordination` | Coordinate tasks between multiple AI agents using the A2A (Agent-to-Agent) protocol via Agora MCP. Covers Agent Card ... | Coordinate tasks between multiple AI agents using the A2A (Agent-to-Agent) proto |
| `agent-onboarding` | Onboard a new AI agent into the omostation workspace. Covers agent profile registration, MCP connection setup, BOS UR... | Onboard a new AI agent into the omostation workspace |
| `agent-quickstart` | Minimal 5-minute quickstart for AI agents working in the omostation workspace. Covers: run a gate, claim a path, edit... | Minimal 5-minute quickstart for AI agents working in the omostation workspace |
| `architecture-perception` | Agent 感知当前架构状态，检查架构合规性 | Agent 感知当前架构状态，检查架构合规性 |
| `bdsk-virtual-board` | B.D.S.K. 虚拟董事会 4 角架构审议与真实 BOS/AetherForge 本地算力接入。用于高风险架构、技术取舍、跨仓协作和合规决策。 | B |
| `bet-closeout-chain` | BET 完成闭环全链路 skill：从 spec binding 到 ledger complete 的 8 步 checklist（spec 规范/start 绑定/交付 PR/evidence matrix/complete/re... | BET 完成闭环全链路 skill：从 spec binding 到 ledger complete 的 8 步 checklist（spec 规范/start |
| `bet-execution` | 认领并执行三年规划台账（3Y-BET-LEDGER）里的 bet。当你要开始一项工程/治理任务、需要知道现在该做什么、或被要求「领一个 bet」时使用。Triggers on: bet, 台账, ledger, BET-Y1Q1, b... | 认领并执行三年规划台账（3Y-BET-LEDGER）里的 bet |
| `bos-contract-fix` | Use when user says 'fix this BOS contract error' / '帮我修复 BOS 契约错误' / 'mof contract-lint failed'. Triggers on keywords... | Use when user says 'fix this BOS contract error' / '帮我修复 BOS 契约错误' / 'mof contra |
| `bos-service-discovery` | Browse and call BOS URI services in the omostation workspace. Lists available domains, services, and transports. Use ... | Browse and call BOS URI services in the omostation workspace |
| `ci-red-triage` | Diagnose & fix omostation CI red via 6-layer recursive triage (P75). Use when gh pr checks fail, main CI red, or gac-... | Diagnose & fix omostation CI red via 6-layer recursive triage (P75) |
| `closeout-retro` | 关闭与回溯 skill：负责 workflow 收尾、retro 归档、evidence 记录和 closeout 报告生成 | 关闭与回溯 skill：负责 workflow 收尾、retro 归档、evidence 记录和 closeout 报告生成 |
| `cognitive-governance` | V2.0 Cognitive OS & Sovereign Governance Skill. Enables agents to deconstruct vague human intents into structured exe... | V2 |
| `delegation-guardrails` | 委托机制加固的两条硬规则：①「只叙述不落盘」是模型路由故障信号（不是 worker 偷懒）——只叙述不改文件 = 错误/不可达模型端点返回空内容，禁止 blind retry，必须跑 5 步诊断序列；② 终验波次子代理结论矛盾时，编排... | 委托机制加固的两条硬规则：①「只叙述不落盘」是模型路由故障信号（不是 worker 偷懒）——只叙述不改文件 = 错误/不可达模型端点返回空内容，禁止 blin |
| `domain-cartridge-governance` | Master governance and execution skill for domain-specific .cartridge capsules (ADR-0203). Guides packaging, cryptogra... | Master governance and execution skill for domain-specific  |
| `ecos-test-cycle` | Edit→test→commit cycle for the ecos project. Run full test suite after code changes, verify results, commit on pass, ... | Edit→test→commit cycle for the ecos project |
| `external-agent-attach` | Attach an external AI agent (Claude Code, Codex, Cursor, custom MCP host) to omostation via Agora MCP + BOS + agent-w... | Attach an external AI agent (Claude Code, Codex, Cursor, custom MCP host) to omo |
| `git-discipline` | 多 agent 并行下的 git 纪律：隔离工作树、交付三段式（add/commit/tag）、逃生口、子模块、僵尸锁、合并型交付补 claim、agent 自身 git 写能力自检。当你要提交代码、切换分支、碰子模块、做分支合并、遇... | 多 agent 并行下的 git 纪律：隔离工作树、交付三段式（add/commit/tag）、逃生口、子模块、僵尸锁、合并型交付补 claim、agent 自 |
| `git-safety-check` | git 安全检查 skill：高危 git 操作（reset/push/子模块指针）前置校验与守门 | git 安全检查 skill：高危 git 操作（reset/push/子模块指针）前置校验与守门 |
| `governance-phase-orchestrator` | Use when the user requests a governance-related task, P-phase closure, doc-lifecycle audit, frontmatter remediation, ... | Use when the user requests a governance-related task, P-phase closure, doc-lifec |
| `governance-ssot-edit` | Edit governance SSOT (governance-checks.yaml / gac-*.py / write-owners / x*-rules / mutation-surfaces) safely in a co... | Edit governance SSOT (governance-checks |
| `harness-compliance` | Harness 全生命周期合规检查 — 12 章节完整性 + MOF 约束联动 + OMO 状态同步 | Harness 全生命周期合规检查 — 12 章节完整性 + MOF 约束联动 + OMO 状态同步 |
| `kos-cold-start` | KOS 冷启动 skill：会话启动时从 KOS 加载 BRIEF/ADR/实体，对齐历史架构决策 | KOS 冷启动 skill：会话启动时从 KOS 加载 BRIEF/ADR/实体，对齐历史架构决策 |
| `memory-recall` | Unified memory recall/write routing for omostation agents (Memory OS). Use when searching knowledge, recalling user p... | Unified memory recall/write routing for omostation agents (Memory OS) |
| `multica-squad-ops` | 用 multica CLI 落地日常工程协作 4 个 squad（交付流水线/架构评审/研究情报/运维监控）+ 配额动态分派台账。与 R3-executor 的 multica 后端物理隔离，不替代 ADR-0203 workflow。 | 用 multica CLI 落地日常工程协作 4 个 squad（交付流水线/架构评审/研究情报/运维监控）+ 配额动态分派台账 |
| `nextgen-cognitive-mesh` | Master governance skill for OMOStation Next-Gen Cognitive Mesh V3.0 (ADR-0200~0203). Guides memory self-distillation,... | Master governance skill for OMOStation Next-Gen Cognitive Mesh V3 |
| `omlxc-compute-fabric` | omlxc 异构算力织网、DFlash 2 块扩散投机解码、Radix 前缀树与 Paged KV 块内存、双区自适应量化与 75% 阶梯显存治理操作指南。当 Agent 需要执行本地大模型推理、预估长上下文显存、分析 Prompt ... | omlxc 异构算力织网、DFlash 2 块扩散投机解码、Radix 前缀树与 Paged KV 块内存、双区自适应量化与 75% 阶梯显存治理操作指南 |
| `omo-audit-baseline` | Governance audit baseline workflow for the omostation workspace. Run omo audit, check results, commit governance data... | Governance audit baseline workflow for the omostation workspace |
| `project-governance` | Use when an agent changes this workspace or a child project and needs executable governance workflow routing instead ... | Use when an agent changes this workspace or a child project and needs executable |
| `round-gate-check` | 回合门禁检查 skill：回合制执行的 gate 结果核验与放行判定 | 回合门禁检查 skill：回合制执行的 gate 结果核验与放行判定 |
| `round-workflow` | 回合工作流 skill：回合制任务的状态机管理与轮次推进 | 回合工作流 skill：回合制任务的状态机管理与轮次推进 |
| `scene-shadow-activate` | 场景影子激活 skill：将 scene card 从 draft/shadow 阶段推进到 assisted/supervised 生命周期 | 场景影子激活 skill：将 scene card 从 draft/shadow 阶段推进到 assisted/supervised 生命周期 |
| `spine-value-pipeline` | omostation (eCOS v6) 主干真值流与署名自进化技能包。指导 AI Agent 如何通过标准 bos:// 服务感知外部信号、驱动 Journey 状态机、调用本地主权算力生成草稿、在 Cockpit 呈递待办并捕获夏... | omostation (eCOS v6) 主干真值流与署名自进化技能包 |
| `swarm-escape` | 蜂群逃生 skill：多 agent 冲突/死锁时的逃生阀与冲突升级路径 | 蜂群逃生 skill：多 agent 冲突/死锁时的逃生阀与冲突升级路径 |
| `system-index-distill` | Deep workspace analysis to find information silos and create unified navigation. Use when the workspace has many proj... | Deep workspace analysis to find information silos and create unified navigation |
| `workflow-silence-detection` | Use when governance audits report silent workflows, P74 or p74_solidification warnings, compliance drift, or when pla... | Use when governance audits report silent workflows, P74 or p74_solidification wa |
| `workflow:bet-execution` | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 |
| `workflow:governance-state-mutation` | SEMA 自动结晶技能包 — 基于 5 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 5 条 MOS 踩坑信念反向萃取 |
| `workflow:mini` | SEMA 自动结晶技能包 — 基于 2 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 2 条 MOS 踩坑信念反向萃取 |
| `workflow:project-code-change` | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 |
| `workflow:project-doc-change` | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 |
| `worktree-ci-isolate` | Create isolated git worktrees for CI fixes and parallel development. Init submodules, work in isolation, clean up whe... | Create isolated git worktrees for CI fixes and parallel development |

### 外部 Agent 推荐包

见 [`external-agent-attach` skill](../.agents/skills/external-agent-attach/SKILL.md)：
`external-agent-attach` · `agent-onboarding` · `bos-service-discovery` · `project-governance` · `a2a-coordination`。


---

## Agent 入门指南

### 新 Agent 设置步骤

1. **阅读入口文档**: `README.md` → `SYSTEM-INDEX.md`
2. **了解架构**: `ARCHITECTURE.md` → `PANORAMA.md`
3. **学习操作**: `AGENTS.md` → `CLAUDE.md`
4. **查看项目**: `INDEX-PROJECTS.md` → 目标项目文档
5. **查找工具**: `INDEX-TOOLS.md` → 可用工具目录
6. **查询历史**: `INDEX-KNOWLEDGE.md` → ADR/审计/模式

### 常见任务路径

| 任务 | 路径 |
|------|------|
| 开发新功能 | 项目 `AGENTS.md` → `INDEX-TOOLS.md` → 项目 `README.md` |
| 修复 bug | `AGENTS.md` §5 → 项目 `Makefile` → `INDEX-KNOWLEDGE.md` |
| 治理操作 | `CLAUDE.md` §0 → `agent-workflow.py` → `omo` CLI |
| 架构决策 | `ARCHITECTURE.md` → `INDEX-KNOWLEDGE.md` → ADR 目录 |


---

## 说明

> Agent 配置和能力清单由脚本自动生成
> 
> 项目级 Skill 定义见 `.agents/skills/*/SKILL.md`
> 
> Agent 工作流使用见 `bin/agent-workflow.py --help`
