# INDEX-AGENTS.md — Agent 能力索引

> **维护规则**
> - owner: governance-team
> - trigger: Agent CLI 升级 / 新增 skill / 配置变更
> - method: 脚本生成 (bin/ssot/gen-agents-index.py)
> - validation: skill 数与实际目录一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: 2026-08-04T11:04:27.246873+00:00

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
| `bdsk-virtual-board` | B.D.S.K. 虚拟董事会 (Mode-A 深度辩论 / Mode-B 快速决策) 4角共识执行与本地 LLM 接入指南。当任意 Agent 面临架构设计、核心技术选型、重大代码修改或风险 ROI 决策时调用。 | B |
| `bos-contract-fix` | bos contract fix | bos contract fix |
| `bos-service-discovery` | Browse and call BOS URI services in the omostation workspace. Lists available domains, services, and transports. Use ... | Browse and call BOS URI services in the omostation workspace |
| `ci-red-triage` | Diagnose & fix omostation CI red via 6-layer recursive triage (P75). Use when gh pr checks fail, main CI red, or gac-... | Diagnose & fix omostation CI red via 6-layer recursive triage (P75) |
| `ecos-test-cycle` | Edit→test→commit cycle for the ecos project. Run full test suite after code changes, verify results, commit on pass, ... | Edit→test→commit cycle for the ecos project |
| `external-agent-attach` | Attach an external AI agent (Claude Code, Codex, Cursor, custom MCP host) to omostation via Agora MCP + BOS + agent-w... | Attach an external AI agent (Claude Code, Codex, Cursor, custom MCP host) to omo |
| `governance-phase-orchestrator` | governance phase orchestrator | governance phase orchestrator |
| `governance-ssot-edit` | Edit governance SSOT (governance-checks.yaml / gac-*.py / write-owners / x*-rules / mutation-surfaces) safely in a co... | Edit governance SSOT (governance-checks |
| `omo-audit-baseline` | Governance audit baseline workflow for the omostation workspace. Run omo audit, check results, commit governance data... | Governance audit baseline workflow for the omostation workspace |
| `project-governance` | Use when an agent changes this workspace or a child project and needs executable governance workflow routing instead ... | Use when an agent changes this workspace or a child project and needs executable |
| `system-index-distill` | Deep workspace analysis to find information silos and create unified navigation. Use when the workspace has many proj... | Deep workspace analysis to find information silos and create unified navigation |
| `workflow-silence-detection` | Detect silent agent workflows (registered in agent-workflows.yaml but with no recent activity). Use when running gove... | Detect silent agent workflows (registered in agent-workflows |
| `worktree-ci-isolate` | Create isolated git worktrees for CI fixes and parallel development. Init submodules, work in isolation, clean up whe... | Create isolated git worktrees for CI fixes and parallel development |

### 外部 Agent 推荐包

见 [`docs/operations/external-agent-attach-card.md`](operations/external-agent-attach-card.md)：
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
