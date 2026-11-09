---
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-11-09
---

# INDEX-AGENTS.md — Agent 能力索引

> **维护规则**
> - owner: governance-team
> - trigger: Agent CLI 升级 / 新增 skill / 配置变更
> - method: 脚本生成 (bin/ssot/gen-agents-index.py)
> - validation: skill 数与实际目录一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: 2026-11-03T08:51:31.893893+00:00

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
| `Browser` | Visual verification and browser automation via Playwright. Headless or headed Chrome. USE WHEN browser, screenshot, d... | Visual verification and browser automation via Playwright |
| `ContentAnalysis` | Content extraction and analysis — wisdom extraction from videos, podcasts, articles, and YouTube. USE WHEN extract wi... | Content extraction and analysis — wisdom extraction from videos, podcasts, artic |
| `Investigation` | OSINT and people-finding — structured investigations, company intel, due diligence, and ethical people search across ... | OSINT and people-finding — structured investigations, company intel, due diligen |
| `Scraping` | Web scraping via progressive escalation (Bright Data proxy) and social media platform actors (Apify). USE WHEN scrapi... | Web scraping via progressive escalation (Bright Data proxy) and social media pla |
| `Thinking` | Multi-mode analytical and creative thinking — first principles decomposition, iterative depth analysis, creative brai... | Multi-mode analytical and creative thinking — first principles decomposition, it |
| `a2a-coordination` | Coordinate tasks between multiple AI agents using the A2A (Agent-to-Agent) protocol via Agora MCP. Covers Agent Card ... | Coordinate tasks between multiple AI agents using the A2A (Agent-to-Agent) proto |
| `agent-browser` | Browser automation CLI for AI agents. Use when the user needs to interact with websites, including navigating pages, ... | Browser automation CLI for AI agents |
| `agent-onboarding` | Onboard a new AI agent into the omostation workspace. Covers agent profile registration, MCP connection setup, BOS UR... | Onboard a new AI agent into the omostation workspace |
| `agent-quickstart` | Minimal 5-minute quickstart for AI agents working in the omostation workspace. Covers: run a gate, claim a path, edit... | Minimal 5-minute quickstart for AI agents working in the omostation workspace |
| `architecture-perception` | Agent 感知当前架构状态，检查架构合规性 | Agent 感知当前架构状态，检查架构合规性 |
| `autoresearch-agent` | Autonomous experiment loop that optimizes any file by a measurable metric. Inspired by Karpathy's autoresearch. The a... | Autonomous experiment loop that optimizes any file by a measurable metric |
| `bailian-cli` | 阿里云百炼 / Aliyun Bailian / DashScope 资源管理与 `bl` CLI hub： 应用调用（bl app）、应用记忆、知识库检索、模型目录/模型列表、用量/额度/配额、免费额度、 工作空间、MCP 市场、p... | 阿里云百炼 / Aliyun Bailian / DashScope 资源管理与 `bl` CLI hub： 应用调用（bl app）、应用记忆、知识库检索、模 |
| `bailian-docs-llm-wiki` | 阿里云百炼平台技术文档知识库（LLM Wiki）。当用户查询百炼模型列表、API 参数、错误码、 应用开发（智能体/RAG/知识库/记忆/插件）、模型对比与定价、SDK/OpenAI 兼容接口、 多模态能力（语音/图片/视频）、Tok... | 阿里云百炼平台技术文档知识库（LLM Wiki） |
| `bailian-finetune` | 阿里云百炼模型精调训练入口：用户要精调、微调、训练自己的模型（fine-tune，支持 SFT / SFT-LoRA / DPO / DPO-LoRA / CPT， 覆盖文本、语音、图像）、校验或上传训练数据集、看训练进度和日志、挑 ... | 阿里云百炼模型精调训练入口：用户要精调、微调、训练自己的模型（fine-tune，支持 SFT / SFT-LoRA / DPO / DPO-LoRA / CP |
| `bailian-gen` | 阿里云百炼图片/视频/语音生成与理解入口：用户要生图、画图、生成照片、生成图片、AI 绘画、海报、头像、插画、 文生图（text-to-image）、图生图、改图、修图、多图合成、生成视频、文生视频、图生视频、参考生视频、视频编辑、风... | 阿里云百炼图片/视频/语音生成与理解入口：用户要生图、画图、生成照片、生成图片、AI 绘画、海报、头像、插画、 文生图（text-to-image）、图生图、改 |
| `bailian-managed-agent` | 阿里云百炼托管 Agent 声明式基础设施与 API 命令入口：用户要创建agent、初始化 agents.yaml、校验或预览配置变更、 创建/更新/销毁托管 Agent 或 Deployment、在 Workbench 编辑和调试... | 阿里云百炼托管 Agent 声明式基础设施与 API 命令入口：用户要创建agent、初始化 agents |
| `bailian-model-recommend` | 阿里云百炼模型选型与推荐。当用户需要"选择、推荐、对比"模型，或描述一个 AI 场景/功能需求（隐含需要帮其决策用哪个模型）时激活。核心意图是帮用户做决策， 不是单纯查资料。触发词：推荐模型、选哪个、哪个适合、对比、做一个XX、实现X... | 阿里云百炼模型选型与推荐 |
| `bailian-protocol` | 阿里云百炼 `bl` 家族共享执行协议（consent 确认、版本预检、鉴权/安装、错误上报、本地文件与输出约定）。 不是面向用户意图的业务入口；当任一 bailian-* 业务 skill（bailian-cli / bailian... | 阿里云百炼 `bl` 家族共享执行协议（consent 确认、版本预检、鉴权/安装、错误上报、本地文件与输出约定） |
| `bailian-sandbox` | 阿里云百炼 Sandbox 沙箱实例与模版生命周期管理入口：用户要创建、查询、连接、暂停、恢复或释放百炼沙箱， 或查看内置基础镜像、上传模版挂载文件、创建、更新、查询、删除沙箱模版、查看模版构建状态时，使用 `bl sandbox`。... | 阿里云百炼 Sandbox 沙箱实例与模版生命周期管理入口：用户要创建、查询、连接、暂停、恢复或释放百炼沙箱， 或查看内置基础镜像、上传模版挂载文件、创建、更新 |
| `bailian-train-deploy` | 用百炼 CLI (`bl`) 走完"数据→微调训练→导出→部署→调用"的完整闭环，或跳过训练直接部署基座模型。支持文本模型（SFT/DPO/CPT）、音频 TTS 模型（CosyVoice）、图像生成模型（Wan2.7）和视频生成模型... | 用百炼 CLI (`bl`) 走完"数据→微调训练→导出→部署→调用"的完整闭环，或跳过训练直接部署基座模型 |
| `bailian-web-search` | 阿里云百炼联网搜索（web search）入口：为联网搜索 / 网页搜索 / 查最新资讯做路径分发。 先识别当前连接身份：Token Plan（profile `token-plan` 或 base_url host 为 `token... | 阿里云百炼联网搜索（web search）入口：为联网搜索 / 网页搜索 / 查最新资讯做路径分发 |
| `bdsk-virtual-board` | B.D.S.K. 虚拟董事会 4 角架构审议与真实 BOS/AetherForge 本地算力接入。用于高风险架构、技术取舍、跨仓协作和合规决策。 | B |
| `bet-closeout-chain` | BET 完成闭环全链路 skill：从 spec binding 到 ledger complete 的 8 步 checklist（spec 规范/start 绑定/交付 PR/evidence matrix/complete/re... | BET 完成闭环全链路 skill：从 spec binding 到 ledger complete 的 8 步 checklist（spec 规范/start |
| `bet-execution` | 认领并执行三年规划台账（3Y-BET-LEDGER）里的 bet。当你要开始一项工程/治理任务、需要知道现在该做什么、或被要求「领一个 bet」时使用。Triggers on: bet, 台账, ledger, BET-Y1Q1, b... | 认领并执行三年规划台账（3Y-BET-LEDGER）里的 bet |
| `bos-contract-fix` | Use when user says 'fix this BOS contract error' / '帮我修复 BOS 契约错误' / 'mof contract-lint failed'. Triggers on keywords... | Use when user says 'fix this BOS contract error' / '帮我修复 BOS 契约错误' / 'mof contra |
| `bos-service-discovery` | Browse and call BOS URI services in the omostation workspace. Lists available domains, services, and transports. Use ... | Browse and call BOS URI services in the omostation workspace |
| `brainstorming` | You MUST use this before any creative work - creating features, building components, adding functionality, or modifyi... | You MUST use this before any creative work - creating features, building compone |
| `ci-red-triage` | Diagnose & fix omostation CI red via 6-layer recursive triage (P75). Use when gh pr checks fail, main CI red, or gac-... | Diagnose & fix omostation CI red via 6-layer recursive triage (P75) |
| `closeout-retro` | 关闭与回溯 skill：负责 workflow 收尾、retro 归档、evidence 记录和 closeout 报告生成 | 关闭与回溯 skill：负责 workflow 收尾、retro 归档、evidence 记录和 closeout 报告生成 |
| `codebase-memory` | Use the codebase knowledge graph for structural code queries. Triggers on: explore the codebase, understand the archi... | Use the codebase knowledge graph for structural code queries |
| `cognitive-governance` | V2.0 Cognitive OS & Sovereign Governance Skill. Enables agents to deconstruct vague human intents into structured exe... | V2 |
| `dashboard-component-evolution` | 全景驾驶舱与治理大屏组件开发、TS 契约映射、WAI-ARIA 1.2 无障碍规范与双模供给层演进指南。 | 全景驾驶舱与治理大屏组件开发、TS 契约映射、WAI-ARIA 1 |
| `dashboard-governance-patrol` | 全景驾驶舱与治理大屏日常巡检、端口导流守护、数据新鲜度与门禁探针自愈技能包。 | 全景驾驶舱与治理大屏日常巡检、端口导流守护、数据新鲜度与门禁探针自愈技能包 |
| `delegation-guardrails` | 委托机制加固的两条硬规则：①「只叙述不落盘」是模型路由故障信号（不是 worker 偷懒）——只叙述不改文件 = 错误/不可达模型端点返回空内容，禁止 blind retry，必须跑 5 步诊断序列；② 终验波次子代理结论矛盾时，编排... | 委托机制加固的两条硬规则：①「只叙述不落盘」是模型路由故障信号（不是 worker 偷懒）——只叙述不改文件 = 错误/不可达模型端点返回空内容，禁止 blin |
| `dispatching-parallel-agents` | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies | Use when facing 2+ independent tasks that can be worked on without shared state  |
| `document-generation` | 通用文档生成方案 — Word/PDF/图表/流程图/架构图/PPT/Excel/Markdown 一站式产出 | 通用文档生成方案 — Word/PDF/图表/流程图/架构图/PPT/Excel/Markdown 一站式产出 |
| `docx` | Use this skill whenever the user wants to create, read, edit, or manipulate Word documents (.docx files). Triggers in... | Use this skill whenever the user wants to create, read, edit, or manipulate Word |
| `domain-cartridge-governance` | Master governance and execution skill for domain-specific .cartridge capsules (ADR-0203). Guides packaging, cryptogra... | Master governance and execution skill for domain-specific  |
| `ecos-test-cycle` | Edit→test→commit cycle for the ecos project. Run full test suite after code changes, verify results, commit on pass, ... | Edit→test→commit cycle for the ecos project |
| `executing-plans` | Use when you have a written implementation plan to execute in a separate session with review checkpoints | Use when you have a written implementation plan to execute in a separate session |
| `external-agent-attach` | Attach an external AI agent (Claude Code, Codex, Cursor, custom MCP host) to omostation via Agora MCP + BOS + agent-w... | Attach an external AI agent (Claude Code, Codex, Cursor, custom MCP host) to omo |
| `find-skills` | Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is... | Helps users discover and install agent skills when they ask questions like "how  |
| `finishing-a-development-branch` | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work - guides comple... | Use when implementation is complete, all tests pass, and you need to decide how  |
| `frontend-design` | Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aes... | Guidance for distinctive, intentional visual design when building new UI or resh |
| `git-commit` | 仅用 Git 分析改动并自动生成 conventional commit 信息（可选 emoji）；必要时建议拆分提交，默认运行本地 Git 钩子（可 --no-verify 跳过） | 仅用 Git 分析改动并自动生成 conventional commit 信息（可选 emoji）；必要时建议拆分提交，默认运行本地 Git 钩子（可 --no |
| `git-discipline` | 多 agent 并行下的 git 纪律：隔离工作树、交付三段式（add/commit/tag）、逃生口、子模块、僵尸锁、合并型交付补 claim、agent 自身 git 写能力自检。当你要提交代码、切换分支、碰子模块、做分支合并、遇... | 多 agent 并行下的 git 纪律：隔离工作树、交付三段式（add/commit/tag）、逃生口、子模块、僵尸锁、合并型交付补 claim、agent 自 |
| `git-guardrails-claude-code` | Set up Claude Code hooks to block dangerous git commands (push, reset --hard, clean, branch -D, etc.) before they exe... | Set up Claude Code hooks to block dangerous git commands (push, reset --hard, cl |
| `git-safety-check` | git 安全检查 skill：高危 git 操作（reset/push/子模块指针）前置校验与守门 | git 安全检查 skill：高危 git 操作（reset/push/子模块指针）前置校验与守门 |
| `governance-phase-orchestrator` | Use when the user requests a governance-related task, P-phase closure, doc-lifecycle audit, frontmatter remediation, ... | Use when the user requests a governance-related task, P-phase closure, doc-lifec |
| `governance-ssot-edit` | Edit governance SSOT (governance-checks.yaml / gac-*.py / write-owners / x*-rules / mutation-surfaces) safely in a co... | Edit governance SSOT (governance-checks |
| `grilling` | Grill the user relentlessly about a plan, decision, or idea. Use when the user wants to stress-test their thinking, o... | Grill the user relentlessly about a plan, decision, or idea |
| `handoff` | Compact the current conversation into a handoff document for another agent to pick up. | Compact the current conversation into a handoff document for another agent to pi |
| `harness-compliance` | Harness 全生命周期合规检查 — 12 章节完整性 + MOF 约束联动 + OMO 状态同步 | Harness 全生命周期合规检查 — 12 章节完整性 + MOF 约束联动 + OMO 状态同步 |
| `host-check` | 诊断远程主机（如 mini）上的工具、凭证、配置问题。判断 gh/某命令"缺失"、token"失效"、钥匙串、非交互 SSH 环境差异、"改了配置没生效"时使用。先复现真实执行环境，再下结论。 | 诊断远程主机（如 mini）上的工具、凭证、配置问题 |
| `kos-cold-start` | KOS 冷启动 skill：会话启动时从 KOS 加载状态/检索知识/实体，对齐历史决策（v1.1 实测校准） | KOS 冷启动 skill：会话启动时从 KOS 加载状态/检索知识/实体，对齐历史决策（v1 |
| `lifeos-core` | 共享 LifeOS 核心入口。用于跨 agent 读取同一 USER、MEMORY 与固定 runtime，解释 setup、interview、update；保持当前系统、用户及仓库指令的优先级。 | 共享 LifeOS 核心入口 |
| `magpie-quota` | Check how much is left of the user's AI subscriptions, coding plans and API key balances through magpie (usemagpie.ai... | Check how much is left of the user's AI subscriptions, coding plans and API key  |
| `mcp-builder` | Guide for creating high-quality MCP (Model Context Protocol) servers that enable LLMs to interact with external servi... | Guide for creating high-quality MCP (Model Context Protocol) servers that enable |
| `memory-recall` | Unified memory recall/write routing for omostation agents (Memory OS). Use when searching knowledge, recalling user p... | Unified memory recall/write routing for omostation agents (Memory OS) |
| `multica-squad-ops` | 用 multica CLI 落地日常工程协作 4 个 squad（交付流水线/架构评审/研究情报/运维监控）+ 配额动态分派台账。与 R3-executor 的 multica 后端物理隔离，不替代 ADR-0203 workflow。 | 用 multica CLI 落地日常工程协作 4 个 squad（交付流水线/架构评审/研究情报/运维监控）+ 配额动态分派台账 |
| `nextgen-cognitive-mesh` | Master governance skill for OMOStation Next-Gen Cognitive Mesh V3.0 (ADR-0200~0203). Guides memory self-distillation,... | Master governance skill for OMOStation Next-Gen Cognitive Mesh V3 |
| `omlxc-compute-fabric` | omlxc 异构算力织网、DFlash 2 块扩散投机解码、Radix 前缀树与 Paged KV 块内存、双区自适应量化与 75% 阶梯显存治理操作指南。当 Agent 需要执行本地大模型推理、预估长上下文显存、分析 Prompt ... | omlxc 异构算力织网、DFlash 2 块扩散投机解码、Radix 前缀树与 Paged KV 块内存、双区自适应量化与 75% 阶梯显存治理操作指南 |
| `omo-audit-baseline` | Governance audit baseline workflow for the omostation workspace. Run omo audit, check results, commit governance data... | Governance audit baseline workflow for the omostation workspace |
| `opencontext-context` | Load relevant OpenContext docs for the current task (safe, no index build) | Load relevant OpenContext docs for the current task (safe, no index build) |
| `opencontext-create` | Create a new idea or problem statement inside OpenContext | Create a new idea or problem statement inside OpenContext |
| `opencontext-help` | Start here — choose the right OpenContext command (beginner-friendly) | Start here — choose the right OpenContext command (beginner-friendly) |
| `opencontext-iterate` | Enrich an existing idea with additional context from OpenContext | Enrich an existing idea with additional context from OpenContext |
| `opencontext-search` | Search OpenContext to find the right docs (safe, no index build by default) | Search OpenContext to find the right docs (safe, no index build by default) |
| `orca-cli` | Use the public `orca` CLI to operate Orca-managed worktrees, folder contexts, terminals, repos, automations, artifact... | Use the public `orca` CLI to operate Orca-managed worktrees, folder contexts, te |
| `orca-per-workspace-env` | Set up, review, debug, or validate Orca per-workspace environment recipes — on-demand, disposable runtimes (cloud san... | Set up, review, debug, or validate Orca per-workspace environment recipes — on-d |
| `orchestration` | Use Orca orchestration for structured multi-agent coordination: threaded messages, blocking ask/reply flows, task dis... | Use Orca orchestration for structured multi-agent coordination: threaded message |
| `pdf` | Use this skill whenever the user wants to do anything with PDF files. This includes reading or extracting text/tables... | Use this skill whenever the user wants to do anything with PDF files |
| `pptx` | Use this skill any time a .pptx file is involved in any way — as input, output, or both. This includes: creating slid... | Use this skill any time a  |
| `proj-status` | 项目或会话状态汇报。用户问"看看项目状态""进度怎么样""做个总结/复盘""另一个会话进展如何"时使用。给出带证据的简短状态表，不靠猜。 | 项目或会话状态汇报 |
| `project-governance` | Use when an agent changes this workspace or a child project and needs executable governance workflow routing instead ... | Use when an agent changes this workspace or a child project and needs executable |
| `receiving-code-review` | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or tec... | Use when receiving code review feedback, before implementing suggestions, especi |
| `refactoring` | 代码重构专家，优化代码结构、提升可读性和可维护性 | 代码重构专家，优化代码结构、提升可读性和可维护性 |
| `requesting-code-review` | Use when completing tasks, implementing major features, or before merging to verify work meets requirements | Use when completing tasks, implementing major features, or before merging to ver |
| `resolving-merge-conflicts` | Use when you need to resolve an in-progress git merge/rebase conflict. | Use when you need to resolve an in-progress git merge/rebase conflict |
| `round-gate-check` | 回合门禁检查 skill：回合制执行的 gate 结果核验与放行判定 | 回合门禁检查 skill：回合制执行的 gate 结果核验与放行判定 |
| `round-workflow` | 回合工作流 skill：回合制任务的状态机管理与轮次推进 | 回合工作流 skill：回合制任务的状态机管理与轮次推进 |
| `scene-shadow-activate` | 场景影子激活 skill：将 scene card 从 draft/shadow 阶段推进到 assisted/supervised 生命周期 | 场景影子激活 skill：将 scene card 从 draft/shadow 阶段推进到 assisted/supervised 生命周期 |
| `security-review` | Use this skill when adding authentication, handling user input, working with secrets, creating API endpoints, or impl... | Use this skill when adding authentication, handling user input, working with sec |
| `setup-pre-commit` | Set up Husky pre-commit hooks with lint-staged (Prettier), type checking, and tests in the current repo. Use when use... | Set up Husky pre-commit hooks with lint-staged (Prettier), type checking, and te |
| `simplify` | Simplifies code for clarity without changing behavior. Use for readability, maintainability, and complexity reduction... | Simplifies code for clarity without changing behavior |
| `source-command-opencontext-context` | Migrated source command `opencontext-context` | Migrated source command `opencontext-context` |
| `source-command-opencontext-create` | Migrated source command `opencontext-create` | Migrated source command `opencontext-create` |
| `source-command-opencontext-help` | Migrated source command `opencontext-help` | Migrated source command `opencontext-help` |
| `source-command-opencontext-iterate` | Migrated source command `opencontext-iterate` | Migrated source command `opencontext-iterate` |
| `source-command-opencontext-search` | Migrated source command `opencontext-search` | Migrated source command `opencontext-search` |
| `spine-value-pipeline` | omostation (eCOS v6) 主干真值流与署名自进化技能包。指导 AI Agent 如何通过标准 bos:// 服务感知外部信号、驱动 Journey 状态机、调用本地主权算力生成草稿、在 Cockpit 呈递待办并捕获夏... | omostation (eCOS v6) 主干真值流与署名自进化技能包 |
| `subagent-driven-development` | Use when executing implementation plans with independent tasks in the current session | Use when executing implementation plans with independent tasks in the current se |
| `swarm-escape` | 蜂群逃生 skill：多 agent 冲突/死锁时的逃生阀与冲突升级路径 | 蜂群逃生 skill：多 agent 冲突/死锁时的逃生阀与冲突升级路径 |
| `system-index-distill` | Deep workspace analysis to find information silos and create unified navigation. Use when the workspace has many proj... | Deep workspace analysis to find information silos and create unified navigation |
| `systematic-debugging` | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes | Use when encountering any bug, test failure, or unexpected behavior, before prop |
| `test-driven-development` | Use when implementing any feature or bugfix, before writing implementation code | Use when implementing any feature or bugfix, before writing implementation code |
| `using-git-worktrees` | Use when starting feature work that needs isolation from current workspace or before executing implementation plans -... | Use when starting feature work that needs isolation from current workspace or be |
| `using-superpowers` | Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY re... | Use when starting any conversation - establishes how to find and use skills, req |
| `verification-before-completion` | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running ver... | Use when about to claim work is complete, fixed, or passing, before committing o |
| `web-access` | 所有联网操作必须通过此 skill 处理，包括：搜索、网页抓取、登录后操作、网络交互等。 触发场景：用户要求搜索信息、查看网页内容、访问需要登录的网站、操作网页界面、抓取社交媒体内容（小红书、微博、推特等）、读取动态渲染页面、以及任何... | 所有联网操作必须通过此 skill 处理，包括：搜索、网页抓取、登录后操作、网络交互等 |
| `workflow-silence-detection` | Use when governance audits report silent workflows, P74 or p74_solidification warnings, compliance drift, or when pla... | Use when governance audits report silent workflows, P74 or p74_solidification wa |
| `workflow:bet-execution` | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 |
| `workflow:governance-state-mutation` | SEMA 自动结晶技能包 — 基于 5 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 5 条 MOS 踩坑信念反向萃取 |
| `workflow:mini` | SEMA 自动结晶技能包 — 基于 2 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 2 条 MOS 踩坑信念反向萃取 |
| `workflow:project-code-change` | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 |
| `workflow:project-doc-change` | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 | SEMA 自动结晶技能包 — 基于 3 条 MOS 踩坑信念反向萃取 |
| `worktree-ci-isolate` | Create isolated git worktrees for CI fixes and parallel development. Init submodules, work in isolation, clean up whe... | Create isolated git worktrees for CI fixes and parallel development |
| `writing-for-agents` | Writing documents for agents. Use when creating or editing skills, or modifying AGENTS.md or CLAUDE.md. | Writing documents for agents |
| `writing-plans` | Use when you have a spec or requirements for a multi-step task, before touching code | Use when you have a spec or requirements for a multi-step task, before touching  |
| `writing-skills` | Use when creating new skills, editing existing skills, or verifying skills work before deployment | Use when creating new skills, editing existing skills, or verifying skills work  |
| `xlsx` | Use this skill any time a spreadsheet file is the primary input or output. This means any task where the user wants t... | Use this skill any time a spreadsheet file is the primary input or output |
| `zsh-split-audit` | 事后审计会话转写，量化 Agent 是否违反 zsh 分词纪律（`VAR="a b c"; for x in $VAR` 在 zsh 下只迭代 1 次且 $x 是整串）。含假零断言与噪声判别，把「无法事前拦截」的教训变成可测指标。 | 事后审计会话转写，量化 Agent 是否违反 zsh 分词纪律（`VAR="a b c"; for x in $VAR` 在 zsh 下只迭代 1 次且 $x  |

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
