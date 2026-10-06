---
schema: md/v1
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-10-04
type: ssot
---

# ONBOARDING — 阅读顺序与路由

本文是一张给新人的**阅读顺序与路由表**：告诉你先读哪些文件、每份解决什么问题、按什么顺序读。操作性的 onboarding 指令已经完整存在于两份活跃 skill 中——[`.agents/skills/agent-onboarding/SKILL.md`](../.agents/skills/agent-onboarding/SKILL.md)（全量 onboarding）与 [`.agents/skills/agent-quickstart/SKILL.md`](../.agents/skills/agent-quickstart/SKILL.md)（5 分钟快速开始）——本文**不重复**它们的内容，只负责指路。

## 从哪开始：路由表

| 我想… | 去读 | 为什么是这份 |
|---|---|---|
| 理解系统是什么 | [ARCHITECTURE.md](../ARCHITECTURE.md) | 稳定架构契约的唯一权威 |
| 找到我的路 | [SYSTEM-INDEX.md](SYSTEM-INDEX.md) | 导航枢纽，按层索引全仓（根级另有一份 [SYSTEM-INDEX.md](../SYSTEM-INDEX.md)） |
| 知道操作规则 | [AGENTS.md](../AGENTS.md) | 工作区运行规则与红线 |
| 加载运行时事实 / SSOT | [agent-workflow bootstrap](../bin/agent-workflow.py) | 单一入口把当前运行态与 SSOT 注入会话 |
| 做第一次受管改动 | [agent-quickstart/SKILL.md](../.agents/skills/agent-quickstart/SKILL.md) | 5 分钟跑通 gate → claim → edit → PR |
| 完整 onboarding 一个 agent | [agent-onboarding/SKILL.md](../.agents/skills/agent-onboarding/SKILL.md) | 注册、MCP、BOS、第一次 workflow 运行 |
| 深入理解架构与运维 | [PROJECT-COMPLETE-GUIDE.md](PROJECT-COMPLETE-GUIDE.md) | 全景长文，含操作细节 |
| 理解一个历史决策 | [decisions/INDEX.md](../.omo/_knowledge/decisions/INDEX.md) | ADR 索引，决策记录按编号可查 |
| 认领计划中的工作 | [plans/3Y-BET-LEDGER.md](plans/3Y-BET-LEDGER.md) | 三年 bet 台账 |
| 起隔离工作环境 | [AGENTS.md](../AGENTS.md) §0 | 主工作区只读，改动一律从 worktree 开始 |

## 两份 skill 怎么选

- 只想尽快跑通第一个受管改动（gate → claim → edit → test → PR）：读 [agent-quickstart/SKILL.md](../.agents/skills/agent-quickstart/SKILL.md)。
- 需要完整能力（agent profile 注册、MCP 接线、BOS URI 发现、cockpit CLI、第一个 workflow 生命周期）：读 [agent-onboarding/SKILL.md](../.agents/skills/agent-onboarding/SKILL.md)。
- 二者是同一体系的两档：quickstart 是进入路径，onboarding 是完整流程。本文不展开任何细节。

## 建议阅读顺序

第一轮不需要读完全部，按这个顺序推进：

1. [ARCHITECTURE.md](../ARCHITECTURE.md) —— 先知道系统是什么
2. [SYSTEM-INDEX.md](SYSTEM-INDEX.md) —— 再知道文件都放在哪里
3. [AGENTS.md](../AGENTS.md) —— 然后读操作规则
4. [CLAUDE.md](../CLAUDE.md) §6.6 —— 开始干活前建立「声明 ≠ 执行」的心智前提
5. [agent-workflow bootstrap](../bin/agent-workflow.py) —— 让会话加载真实运行态事实
6. [agent-quickstart/SKILL.md](../.agents/skills/agent-quickstart/SKILL.md) —— 做第一个受管改动
7. [agent-onboarding/SKILL.md](../.agents/skills/agent-onboarding/SKILL.md) —— 需要完整能力时再深入

过程中任何「某文件存在 / 某规则已接线」的说法，先按下面的第 4 条校验再相信。

## 在相信任何声明之前

这可能是整个仓库最重要的一条心智前提：**「文档或规则声称它存在」不是证据**。文件里写着「这个检查已接线」、台账里列着「这个门禁已落地」，都不能说明它在真实执行。判据在 [CLAUDE.md](../CLAUDE.md) §6.6（Declaration vs Execution vs Verification）：把声明锚到真实可读的文件或函数，再在可执行体语料（`bin/**`、hooks、workflows、hook-manifest）里确认该锚可查——否则是 DECL_EXEC_GAP，不是「执行了却叫不出名字」。完整的验证命令清单在该节，本文不重复。

## 已知陷阱（只指路，不解释）

下面每个主题都有完整记录；这里只让你知道「存在这些坑、去对应章节读」，不展开：

| 陷阱主题 | 记录位置 |
|---|---|
| zsh 分词 / 多值列表迭代塌缩 | [AGENTS.md](../AGENTS.md) §7 |
| 管道计数命令零匹配断链 | [AGENTS.md](../AGENTS.md) §11 |
| 并发 agent 争用与分支隔离 | [AGENTS.md](../AGENTS.md) §6（分支隔离）、§7（争用） |
| 子模块指针 / 浅历史可达性 | [AGENTS.md](../AGENTS.md) §6 |
| 运行时快照陈旧 / legacy 兜底 | [AGENTS.md](../AGENTS.md) §7 |
| 生成态弄脏提交 | [AGENTS.md](../AGENTS.md) §7 |
| 修复目标可能已被别人合入（PITFALL-GAT-006） | [AGENTS.md](../AGENTS.md) §11 |
| 声明 vs 执行 vs 验证 | [CLAUDE.md](../CLAUDE.md) §6.6 |

## 本文刻意不包含什么

- 不写任何**计数**（项目数、包数、ADR 数、健康分、端口、阶段号）——它们各有权威 owner 与注册表，写进这里必然过期。
- 不写任何**规则表 / workflow 列表 / agent-profile 列表 / 适配器列表**——它们由各自的 registry 持有。
- 不复制两份 skill 的操作指令，也不复制 [CLAUDE.md](../CLAUDE.md) §6.6 的验证命令清单。

需要这些事实时，从上面的路由表找到 owner 读原文。权威注册表总览见 [SYSTEM-INDEX.md](SYSTEM-INDEX.md) 与 [AGENTS.md](../AGENTS.md) §2。