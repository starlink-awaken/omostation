# 系统索引体系设计方案 — 全景调研 + 架构设计

> 调研日期: 2026-07-03 | 实施: 2026-07-03
> 状态: **已实施**（最终方案：1 个纯指针文件，0 个新数据源）
> 覆盖范围: Workspace 根 + 17 项目 + .omo + runtime + protocols + 所有 agent 配置
> 最终产出: `SYSTEM-INDEX.md`（~80 行，纯指针，不复制数据）

---

## 一、现状全景审计

### 1.1 信息资产清单

workspace 中共有 **284 个**结构化信息源：

| 类别 | 数量 | 位置 | 性质 |
|------|------|------|------|
| 项目目录 | 17 | `projects/` | 独立 git 仓库 |
| 根级工具 (bin/) | 105 | `bin/*.py` + `bin/*.sh` | 治理/审计/lint 工具 |
| 运维脚本 (scripts/) | 68 | `scripts/` | 同步/部署/检查 |
| 治理注册表 | 20 | `.omo/_truth/registry/*.yaml` | 机器可读 SSOT |
| 治理标准 | 41 | `.omo/standards/` | 人类可读契约 |
| ADR 决策记录 | 89 | `.omo/_knowledge/decisions/` | 历史决策 |
| 审计报告 | 84 | `.omo/_knowledge/audits/` | 审计证据 |
| 沉淀模式 | 4 | `.omo/_knowledge/patterns/` | 复用模式 |
| 任务 (done) | 129 | `.omo/tasks/done/` | 已完成任务 |
| 任务 (planned) | 9 | `.omo/tasks/planned/` | 计划任务 |
| 文档 (root docs) | 18 | `docs/*.md` | 架构/路线/能力图 |
| 生成文档 | 2 | `docs/generated/` | 机器生成 |
| 协议注册表 | 5 | `protocols/` | 端口/vault/x-axis |
| 项目级 Skills | 6 | `.agents/skills/` | 工作流技能 |
| Mimocode Skills | 1 | `.mimocode/skills/` | 分析模式 |
| Mimocode Commands | 2 | `.mimocode/commands/` | 命令模板 |
| 集成测试 | 11 | `tests/` | 根级测试 |
| 项目文档 (×17) | ~120 | `projects/*/` | 每项目 7 文件 |
| **合计** | **~700+** | | |

### 1.2 项目文档矩阵

每个项目（17 个）的标准文档：

| 文件 | 存在数 | 用途 |
|------|--------|------|
| `AGENTS.md` | 17/17 | 开发指南（操作层 OWN） |
| `CLAUDE.md` | 17/17 | AI 会话协议（操作层 OWN） |
| `README.md` | 17/17 | 项目入口（入口层 OWN） |
| `ARCHITECTURE.md` | 17/17 | 架构契约（架构层 OWN） |
| `BOUNDARY.md` | 17/17 | 边界定义（边界层 OWN） |
| `CALLCHAIN.md` | 17/17 | 调用链路 |
| `pyproject.toml` | 15/17 | Python 构建配置 |
| `Makefile` | 10/17 | 构建命令 |
| `.github/` | 16/17 | CI/CD |
| `.pre-commit-config.yaml` | 1/17 | 预提交钩子（仅 kairon） |

### 1.3 信息流向图

```
用户/Agent
    │
    ├─→ AGENTS.md ─→ CLAUDE.md ─→ ARCHITECTURE.md ─→ project-registry.yaml
    │       │              │              │
    │       │              │              ├─→ protocols/port-registry.yaml
    │       │              │              ├─→ protocols/vault-paths.yaml
    │       │              │              └─→ .omo/_truth/registry/*.yaml
    │       │              │
    │       │              └─→ .omo/state/system.yaml (运行时状态)
    │       │
    │       └─→ bin/agent-workflow.py (工作流执行器)
    │
    ├─→ project-registry.yaml ─→ docs/generated/project-layer-index.md
    │
    ├─→ .omo/_truth/registry/ ─→ bin/gac-validate.py (CI 门禁)
    │
    └─→ docs/*.md (架构图/路线图/能力图)
```

### 1.4 现有 SSOT 契约

`.omo/standards/doc-ssot-contract.md` 定义了 5 维正交原则：

| 维度 | Owner 文档 | 内容 |
|------|-----------|------|
| 事实层 | `project-registry.yaml`, `system.yaml` | 易变数字 |
| 架构层 | `ARCHITECTURE.md`, `PANORAMA.md` | 稳定原则 |
| 操作层 | `AGENTS.md`, `CLAUDE.md` | 开发命令 |
| 边界层 | `BOUNDARY.md` | 接口定义 |
| 入口层 | `README.md` | 快速开始 |

**CI 门禁**: `bin/doc-ssot-lint.py` 检测硬编码冲突。

---

## 二、核心问题诊断

### 问题 1：没有统一入口（导航断裂）

**现状**: Agent 进入 workspace 需要读 6+ 个文件才能理解全貌。

```
AGENTS.md → CLAUDE.md → ARCHITECTURE.md → project-registry.yaml → ...
```

**影响**: 每次新 session 都要重复这个链式跳转，且不知道还有哪些信息源存在。

**根因**: 没有"全景导航页"——一个文件说清楚"有什么、在哪里、怎么找"。

### 问题 2：工具目录不透明（工具孤岛）

**现状**: `bin/` 有 105 个工具，`scripts/` 有 68 个脚本，无统一目录。

**影响**: 不知道有哪些工具可用，不知道某个功能该用哪个工具。

**根因**: 工具是逐步添加的，没有回过头做统一编目。

### 问题 3：知识资产碎片化（知识孤岛）

**现状**: 89 ADR + 84 审计 + 4 模式 + 118 行 MEMORY.md，分散在不同目录。

**影响**: 找一个决策记录要翻多个目录；不知道某个主题有哪些相关 ADR。

**根因**: 知识按"类型"组织（decisions/audits/patterns），缺少按"主题"和"项目"的交叉索引。

### 问题 4：Agent 配置分散（能力不透明）

**现状**: `.claude/settings.json`（98 skills）、`.codex/config.toml`（34 skills）、`.agents/skills/`（6 项目级）三处配置。

**影响**: 不知道当前 agent 有哪些能力，不知道哪些 skill 是项目级的、哪些是全局的。

**根因**: 不同 agent CLI 有自己的配置目录，没有统一视图。

### 问题 5：文档引用链断裂风险

**现状**: `AGENTS.md` §2 列了 16 个 SSOT 源，但：
- 没有验证它们之间的引用完整性
- 生成文件（`project-layer-index.md`、`agent-gac-rules.md`）的触发条件不透明
- 部分文档可能引用了不存在的文件

**影响**: 文档漂移难以发现，直到 agent 读到断裂的引用才暴露。

### 问题 6：维护责任不清（维护孤岛）

**现状**: 谁负责更新什么文档？更新频率？触发条件？没有明确定义。

**影响**: 文档过期后无人更新，直到 CI 门禁报错或 agent 读到过期数据。

---

## 三、设计原则

### 原则 1：索引不复制，只指针

索引文件**绝不包含绝对数值**（包数、测试数、工具数、Phase、健康分）。只包含：
- 指向 SSOT 的路径指针
- 分类标签（项目名、用途、主题）
- 最后更新时间戳（由生成脚本自动填充）

### 原则 2：动态内容机器生成，静态内容人工维护

| 内容类型 | 生成方式 | 示例 |
|----------|---------|------|
| 动态（易变） | 脚本生成 | 工具列表、ADR 索引、任务统计 |
| 静态（稳定） | 人工维护 | 设计原则、分类规则、维护流程 |
| 混合 | 模板 + 数据 | SYSTEM-INDEX.md（模板人工写，数据脚本填） |

### 原则 3：维护责任显式声明

每个索引文件头部声明：
- `owner`: 谁负责维护
- `trigger`: 什么事件触发更新
- `method`: 怎么更新（手动生成/脚本生成/CI 自动生成）
- `validation`: 怎么验证正确性

### 原则 4：渐进式实施，不破坏现有 SSOT

- 不修改现有 SSOT 文件的内容
- 不改变现有文档的职责维度
- 只新增"导航层"文件，作为现有 SSOT 的地图

---

## 四、系统索引架构

### 4.1 层次结构

```
SYSTEM-INDEX.md                    ← 统一入口（根）
    │
    ├── docs/INDEX-PROJECTS.md     ← 项目索引（按层/按栈/按状态）
    ├── docs/INDEX-TOOLS.md        ← 工具索引（bin/ + scripts/ + skills/）
    ├── docs/INDEX-KNOWLEDGE.md    ← 知识索引（ADR + 审计 + 模式 + MEMORY）
    └── docs/INDEX-AGENTS.md       ← Agent 能力索引（配置 + 技能 + 权限）
```

### 4.2 文件职责定义

| 文件 | 维度 | Owner | 更新频率 | 生成方式 |
|------|------|-------|---------|---------|
| `SYSTEM-INDEX.md` | 入口层 | governance-team | 月度/重大变更 | 人工维护框架 + 脚本填充数据 |
| `docs/INDEX-PROJECTS.md` | 入口层 | governance-team | 项目增减时 | 脚本生成（扫描 project-registry.yaml） |
| `docs/INDEX-TOOLS.md` | 入口层 | governance-team | 工具增减时 | 脚本生成（扫描 bin/ + scripts/ + skills/） |
| `docs/INDEX-KNOWLEDGE.md` | 入口层 | governance-team | 季度 | 脚本生成（扫描 .omo/_knowledge/） |
| `docs/INDEX-AGENTS.md` | 入口层 | governance-team | Agent 配置变更时 | 脚本生成（扫描配置文件） |

### 4.3 与现有 SSOT 的关系

```
                    ┌─────────────────────┐
                    │   SYSTEM-INDEX.md   │  ← 新增：导航层入口
                    │   (不持有任何数据)   │
                    └─────────┬───────────┘
                              │ 指针
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    ┌─────┴─────┐     ┌──────┴──────┐     ┌──────┴──────┐
    │INDEX-     │     │INDEX-       │     │INDEX-       │
    │PROJECTS   │     │TOOLS        │     │KNOWLEDGE    │
    └─────┬─────┘     └──────┬──────┘     └──────┬──────┘
          │ 指针              │ 指针              │ 指针
    ┌─────┴─────┐     ┌──────┴──────┐     ┌──────┴──────┐
    │project-   │     │bin/ +       │     │decisions/   │
    │registry   │     │scripts/ +   │     │audits/ +    │
    │.yaml      │     │.agents/     │     │patterns/    │
    │(SSOT)     │     │(SSOT)       │     │(SSOT)       │
    └───────────┘     └─────────────┘     └─────────────┘
```

**关键约束**: 索引文件**不持有数据**，只持有指向 SSOT 的指针。数据变了，索引不用改（因为指针不变）。

---

## 五、各文件详细规格

### 5.1 `SYSTEM-INDEX.md`（根入口）

```markdown
# SYSTEM-INDEX.md — Workspace 全景导航

> **维护规则**
> - owner: governance-team
> - trigger: 重大架构变更、新项目加入、工具链变更
> - method: 人工维护框架结构，具体内容指向各索引
> - validation: 所有指针路径必须存在（doc-ssot-lint 扩展检测）

## 快速开始

1. 读本文 → 了解全局结构
2. 读目标项目 `AGENTS.md` → 了解操作规则
3. 查 `INDEX-TOOLS.md` → 找可用工具
4. 查 `INDEX-KNOWLEDGE.md` → 查历史决策

## 层模型

见 `ARCHITECTURE.md` §2 和 `docs/project-registry.yaml::layers`。

## SSOT 导航

| 需要什么 | 去哪里读 | 维度 |
|----------|---------|------|
| 项目元数据 | `docs/project-registry.yaml` | 事实层 |
| 运行时状态 | `.omo/state/system.yaml` | 事实层 |
| 架构契约 | `ARCHITECTURE.md` | 架构层 |
| 端口分配 | `protocols/port-registry.yaml` | 边界层 |
| 治理规则 | `.omo/_truth/registry/governance-checks.yaml` | 事实层 |
| ADR 决策 | `.omo/_knowledge/decisions/INDEX.md` | 知识层 |
| ... | ... | ... |

## 分类索引

- → [项目索引](docs/INDEX-PROJECTS.md) — 17 项目按层/栈/状态分类
- → [工具索引](docs/INDEX-TOOLS.md) — 105 bin/ + 68 scripts/ + 9 skills/ 统一目录
- → [知识索引](docs/INDEX-KNOWLEDGE.md) — 89 ADR + 84 审计 + 4 模式交叉索引
- → [Agent 能力索引](docs/INDEX-AGENTS.md) — 当前 agent 配置 + 技能清单

## 文档维护生命周期

见下方 §维护管理。
```

### 5.2 `docs/INDEX-PROJECTS.md`（项目索引）

```markdown
# INDEX-PROJECTS.md — 项目索引

> **维护规则**
> - owner: governance-team
> - trigger: 新项目加入 / 项目归档 / 层级变更
> - method: 脚本生成 (`python3 bin/gen-projects-index.py`)
> - validation: 与 project-registry.yaml 项目数一致

## 按层分类

| 层 | 项目 | 栈 | 入口文档 |
|----|------|-----|---------|
| L0 | ecos | Python/uv | `projects/ecos/AGENTS.md` |
| L1 | runtime | Python/uv | `projects/runtime/AGENTS.md` |
| L2 | kairon, gbrain, omo, metaos | 混合 | 各项目 `AGENTS.md` |
| L3 | cockpit, cockpit-ui | Python + TS | 各项目 `AGENTS.md` |
| L4 | l4-kernel | Python/uv | `projects/l4-kernel/AGENTS.md` |
| I0 | agora | Python/uv | `projects/agora/AGENTS.md` |
| M0 | model-driven | Python/uv | `projects/model-driven/AGENTS.md` |
| X | aetherforge, c2g, bus-foundation, omo-debt, observability, family-hub | 混合 | 各项目 `AGENTS.md` |

## 按栈分类

| 栈 | 项目 |
|----|------|
| Python (uv) | ecos, runtime, kairon, omo, metaos, cockpit, l4-kernel, model-driven, aetherforge, c2g, bus-foundation, omo-debt, family-hub |
| TypeScript (bun) | gbrain, cockpit-ui |
| Docker | observability |

## 项目文档矩阵

| 项目 | AGENTS | CLAUDE | README | ARCH | BOUNDARY | CALLCHAIN | Makefile | CI |
|------|--------|--------|--------|------|----------|-----------|----------|-----|
| ecos | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| ... | ... | ... | ... | ... | ... | ... | ... | ... |

> 数据来源: 扫描 `projects/*/` 目录。脚本自动生成，不手写。
```

### 5.3 `docs/INDEX-TOOLS.md`（工具索引）

```markdown
# INDEX-TOOLS.md — 治理工具统一目录

> **维护规则**
> - owner: governance-team
> - trigger: 新增 bin/ 工具 / 新增脚本 / 新增 skill
> - method: 脚本生成 (`python3 bin/gen-tools-index.py`)
> - validation: 工具数与 `ls bin/*.py | wc -l` 一致

## 治理门禁 (bin/gac-*)

| 工具 | 用途 | 调用方式 | 来源 |
|------|------|---------|------|
| gac-local-gate.py | 本地 GaC 检查 | `make gac-local-gate` | bin/ |
| gac-validate.py | 规则验证 | `python3 bin/gac-validate.py --gate` | bin/ |
| gac-drift.py | 漂移检测 | `python3 bin/gac-drift.py` | bin/ |
| ... | ... | ... | ... |

## MOF 工具 (bin/mof-*)

| 工具 | 用途 | 调用方式 |
|------|------|---------|
| mof-enforce | Agent 约束执行 | `bin/mof-enforce pre-check <id>` |
| mof-reason.py | 推理引擎 | `bin/mof-reason.py impact <id>` |
| ... | ... | ... |

## Agent 工作流 (bin/agent-workflow.py)

| 子命令 | 用途 |
|--------|------|
| bootstrap | 初始化全局状态 |
| start | 创建运行记录 |
| claim | 认领编辑面 |
| verify | 验证变更 |
| closeout | 关闭运行 |
| compliance | 合规检查 |

## 运维脚本 (scripts/)

| 脚本 | 用途 |
|------|------|
| sync_omo_state.py | OMO 状态同步 |
| ... | ... |

## 项目级 Skills (.agents/skills/)

| Skill | 用途 | 行数 | 来源 session |
|-------|------|------|-------------|
| ecos-test-cycle | ecos 测试循环 | 112 | ses_0dda6a245ffe |
| omo-audit-baseline | 治理审计同步 | 110 | ses_0dda6a245ffe |
| worktree-ci-isolate | 隔离开发 | 148 | ses_0dda6a245ffe |
| project-governance | 治理工作流路由 | 182 | 历史 |
| bos-contract-fix | BOS 契约修复 | 179 | 历史 |
| governance-phase-orchestrator | RISE 循环 | 194 | 历史 |

## Mimocode Skills (.mimocode/skills/)

| Skill | 用途 |
|-------|------|
| analyze-mode | 并行上下文收集 + 深度分析 |

## Mimocode Commands (.mimocode/commands/)

| Command | 用途 |
|---------|------|
| omo-review.md | OMO 治理状态审查 |
| workspace-health.md | Git 仓库健康扫描 |
```

### 5.4 `docs/INDEX-KNOWLEDGE.md`（知识索引）

```markdown
# INDEX-KNOWLEDGE.md — 知识资产统一索引

> **维护规则**
> - owner: governance-team
> - trigger: 新增 ADR / 新增审计 / 新增模式
> - method: 脚本生成 (`python3 bin/gen-knowledge-index.py`)
> - validation: ADR 数与 `ls .omo/_knowledge/decisions/*.md | wc -l` 一致

## 按项目索引

### ecos
| 类型 | 文件 | 主题 | 日期 |
|------|------|------|------|
| ADR | 0105-bos-contract-linter.md | BOS 契约 linter | 2026-06-25 |
| 审计 | 2026-06-29-l0-ssot-m0-mof-alignment.md | L0/SSOT 对齐 | 2026-06-29 |
| 模式 | p71-baseline-recovery-pattern.md | 基线恢复 | 2026-07-02 |

### cockpit
...

## 按时间索引

| 月 | ADR | 审计 | 模式 |
|----|-----|------|------|
| 2026-05 | 0100-0104 | ... | ... |
| 2026-06 | 0105-0120 | ... | ... |
| 2026-07 | 0121-0125 | ... | ... |

## 按主题索引

| 主题 | ADR | 审计 | 模式 |
|------|-----|------|------|
| 治理 | 0106, 0107, ... | ... | p43, p71 |
| 架构 | ... | ... | ... |
| CI/CD | ... | ... | ... |
| MOF | ... | ... | ... |

## MEMORY 跨 session 知识

> 来源: `MEMORY.md` (118 行) + `MEMORY-infrastructure-mof.md` (46 行) + `MEMORY-spillover-convergence.md` (45 行)

| 类别 | 条目数 | 最近更新 |
|------|--------|---------|
| Rules | 7 | 2026-06-30 |
| Architecture decisions | 20+ | 2026-06-30 |
| Discovered durable knowledge | 30+ | 2026-07-02 |
| Patterns | 7 | 2026-06-25 |
| Gotchas | 15+ | 2026-06-25 |
```

### 5.5 `docs/INDEX-AGENTS.md`（Agent 能力索引）

```markdown
# INDEX-AGENTS.md — Agent 配置能力清单

> **维护规则**
> - owner: governance-team
> - trigger: Agent CLI 升级 / 新增 skill / 配置变更
> - method: 脚本生成 (`python3 bin/gen-agents-index.py`)
> - validation: skill 数与实际目录一致

## 本地 Agent CLI

| CLI | 版本 | 模型 | 配置位置 |
|-----|------|------|---------|
| claude | 2.1.198 | DeepSeek-V4-pro | `~/.claude/settings.json` |
| codex | latest | gpt-5.5 | `~/.codex/config.toml` |
| opencode | latest | — | `~/.opencode/` |
| omc | latest | — | `~/.config/omc/` |
| agent-cli | latest | — | `~/.local/bin/agent-cli` |
| serena | latest | — | `~/.local/bin/serena` |

## 技能分布

| 位置 | 数量 | 性质 |
|------|------|------|
| `~/.claude/skills/` | 98 | 全局（Claude Code） |
| `~/.codex/skills/` | 34 | 全局（Codex） |
| `.agents/skills/` | 6 | 项目级（多 agent 通用） |
| `.mimocode/skills/` | 1 | 项目级（mimocode） |
| `.mimocode/commands/` | 2 | 项目级（命令模板） |

## 项目级 Skills 详情

| Skill | 文件 | 行数 | 触发词 |
|-------|------|------|--------|
| ecos-test-cycle | `.agents/skills/ecos-test-cycle/SKILL.md` | 112 | ecos 测试 |
| omo-audit-baseline | `.agents/skills/omo-audit-baseline/SKILL.md` | 110 | omo 审计 |
| worktree-ci-isolate | `.agents/skills/worktree-ci-isolate/SKILL.md` | 148 | worktree 隔离 |
| project-governance | `.agents/skills/project-governance/SKILL.md` | 182 | 治理工作流 |
| bos-contract-fix | `.agents/skills/bos-contract-fix/SKILL.md` | 179 | BOS 契约修复 |
| governance-phase-orchestrator | `.agents/skills/governance-phase-orchestrator/SKILL.md` | 194 | RISE 循环 |
```

---

## 六、动态化设计

### 6.1 什么内容是动态的

| 内容 | 漂移频率 | 生成方式 |
|------|---------|---------|
| 项目数/包数/工具数 | 低（月级） | 脚本扫描 |
| ADR 列表 | 中（周级） | 脚本扫描 `.omo/_knowledge/decisions/` |
| 审计报告列表 | 中（周级） | 脚本扫描 `.omo/_knowledge/audits/` |
| 工具列表 | 中（周级） | 脚本扫描 `bin/` + `scripts/` |
| 任务统计 | 高（日级） | 脚本扫描 `.omo/tasks/` |
| Agent skill 列表 | 低（月级） | 脚本扫描 `.agents/skills/` |

### 6.2 什么内容是静态的

| 内容 | 变化频率 | 维护方式 |
|------|---------|---------|
| 层模型定义 | 极低（架构级） | 人工维护 |
| 分类规则 | 低 | 人工维护 |
| 维护流程 | 低 | 人工维护 |
| SSOT 指针路径 | 极低 | 人工维护 |

### 6.3 动态内容的生成策略

```
索引文件 = 静态模板（人工维护） + 动态数据块（脚本生成）

示例:
# INDEX-PROJECTS.md
> 人工维护的说明文字...

## 按层分类
<!-- AUTO-GENERATED by bin/gen-projects-index.py -->
| 层 | 项目 | 栈 | ... |
| L0 | ecos | Python/uv | ... |
<!-- END AUTO-GENERATED -->
```

**好处**: 模板人工维护保证可读性，数据块机器生成保证准确性。

---

## 七、维护生命周期

### 7.1 维护角色

| 角色 | 职责 | 触发条件 |
|------|------|---------|
| **human operator** | 架构级变更、分类规则调整 | 手动触发 |
| **agent (CI)** | 检测漂移、生成索引 | commit/push 时自动触发 |
| **agent (session)** | 创建新 ADR/审计时同步索引 | 会话结束时 |

### 7.2 更新触发矩阵

| 事件 | 影响的索引 | 更新方式 | 优先级 |
|------|-----------|---------|--------|
| 新项目加入 | INDEX-PROJECTS | 脚本重新生成 | P1 |
| 项目归档 | INDEX-PROJECTS | 脚本重新生成 | P1 |
| 新增 bin/ 工具 | INDEX-TOOLS | 脚本重新生成 | P2 |
| 新增 ADR | INDEX-KNOWLEDGE | 脚本重新生成 | P2 |
| 新增审计 | INDEX-KNOWLEDGE | 脚本重新生成 | P2 |
| 新增 skill | INDEX-AGENTS | 脚本重新生成 | P2 |
| Agent CLI 升级 | INDEX-AGENTS | 脚本重新生成 | P3 |
| 架构层变更 | SYSTEM-INDEX | 人工更新 | P1 |

### 7.3 维护流程

#### 场景 1：新项目加入

```bash
# 1. 在 projects/ 下创建项目（或 git submodule add）
# 2. 更新 project-registry.yaml（SSOT）
python3 bin/gen-project-registry.py --write
# 3. 重新生成索引
python3 bin/gen-projects-index.py --write
# 4. 重新生成 SYSTEM-INDEX（如果层模型变了）
python3 bin/gen-system-index.py --write
# 5. CI 验证
make gac-local-gate
```

#### 场景 2：新增 ADR

```bash
# 1. 创建 ADR 文件
# 2. 更新 INDEX.md（.omo/_knowledge/decisions/INDEX.md）
# 3. 重新生成知识索引
python3 bin/gen-knowledge-index.py --write
# 4. 如果是架构级决策，更新 SYSTEM-INDEX 的 SSOT 导航表
```

#### 场景 3：新增工具

```bash
# 1. 在 bin/ 下创建工具
# 2. 重新生成工具索引
python3 bin/gen-tools-index.py --write
# 3. 如果工具改变了工作流，更新 SYSTEM-INDEX 的分类索引
```

### 7.4 CI 门禁集成

```bash
# 在 .pre-commit-config.yaml 或 CI 中添加:
- id: index-drift-check
  name: Check index drift
  entry: python3 bin/check-index-drift.py
  language: python
  pass_filenames: false
```

`check-index-drift.py` 检测：
1. `INDEX-PROJECTS.md` 中的项目数与 `project-registry.yaml` 一致
2. `INDEX-TOOLS.md` 中的工具数与 `ls bin/*.py | wc -l` 一致
3. `INDEX-KNOWLEDGE.md` 中的 ADR 数与 `ls .omo/_knowledge/decisions/*.md | wc -l` 一致
4. `INDEX-AGENTS.md` 中的 skill 数与 `ls .agents/skills/ | wc -l` 一致

---

## 八、阅读指南

### 8.1 新 Agent 进入 Workspace

```
第 1 步: 读 SYSTEM-INDEX.md（了解全局）
第 2 步: 读目标项目 AGENTS.md（了解操作规则）
第 3 步: 按需查 INDEX-TOOLS.md（找工具）
第 4 步: 按需查 INDEX-KNOWLEDGE.md（查历史决策）
```

### 8.2 查找特定信息

| 我想找什么 | 去哪里 |
|-----------|--------|
| 某个项目在哪个层 | INDEX-PROJECTS.md → 按层分类 |
| 某个工具怎么用 | INDEX-TOOLS.md → 按用途分类 |
| 某个主题有哪些决策 | INDEX-KNOWLEDGE.md → 按主题索引 |
| 当前 agent 有哪些技能 | INDEX-AGENTS.md → 技能分布 |
| 端口号是多少 | protocols/port-registry.yaml（不经过索引） |
| 当前 Phase 是多少 | .omo/state/system.yaml（不经过索引） |

### 8.3 查找链路

```
问题: "ecos 的 L0 约束规则在哪里？"

查找链:
1. INDEX-PROJECTS.md → ecos → L0 层
2. ecos/AGENTS.md → Key Files → src/ecos/ssot/registry/L0-constraints.yaml
3. 直接读取 L0-constraints.yaml
```

---

## 九、生成脚本设计

### 9.1 脚本清单

| 脚本 | 输入 | 输出 | 触发 |
|------|------|------|------|
| `bin/gen-system-index.py` | 各索引文件 | SYSTEM-INDEX.md | 架构变更时 |
| `bin/gen-projects-index.py` | project-registry.yaml | INDEX-PROJECTS.md | 项目变更时 |
| `bin/gen-tools-index.py` | bin/ + scripts/ + .agents/ | INDEX-TOOLS.md | 工具变更时 |
| `bin/gen-knowledge-index.py` | .omo/_knowledge/ | INDEX-KNOWLEDGE.md | 知识变更时 |
| `bin/gen-agents-index.py` | .claude/ + .codex/ + .agents/ | INDEX-AGENTS.md | Agent 变更时 |
| `bin/check-index-drift.py` | 各索引 + 各 SSOT | exit code | CI 门禁 |

### 9.2 实施优先级

| 阶段 | 内容 | 工作量 | 价值 |
|------|------|--------|------|
| P0 | SYSTEM-INDEX.md（人工框架） | 2h | 高 — 统一入口 |
| P1 | INDEX-PROJECTS.md + gen 脚本 | 3h | 高 — 项目导航 |
| P1 | INDEX-TOOLS.md + gen 脚本 | 4h | 高 — 工具导航 |
| P2 | INDEX-KNOWLEDGE.md + gen 脚本 | 3h | 中 — 知识导航 |
| P2 | INDEX-AGENTS.md + gen 脚本 | 2h | 中 — 能力导航 |
| P3 | check-index-drift.py | 2h | 中 — CI 门禁 |
| P3 | gen-system-index.py | 1h | 低 — 自动化 |

---

## 十、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 索引文件过期 | Agent 读到过期信息 | CI 门禁检测漂移 |
| 生成脚本 bug | 索引内容错误 | 脚本本身有测试 |
| 维护责任无人接 | 索引逐渐腐化 | 写入 pre-commit hook |
| 索引文件太多 | 导航反而更复杂 | 控制在 5 个文件内 |
| 与 doc-ssot-contract 冲突 | 违反正交原则 | 索引只做指针，不持有数据 |

---

## 十一、验证清单

实施后需验证：

- [ ] 所有索引中的指针路径存在
- [ ] `make gac-local-gate` 通过
- [ ] `doc-ssot-lint.py` 通过
- [ ] 新 agent 读 `SYSTEM-INDEX.md` 后能理解全局
- [ ] 生成脚本能正确重新生成索引
- [ ] CI 门禁能检测索引漂移
- [ ] 索引文件不包含任何硬编码数值

---

## 十二、GaC 体系集成

### 12.1 核心思路：索引即 GaC 规则

系统索引不是"额外的文档维护工作"，而是 **GaC 体系的自然延伸**：

- 索引漂移 = GaC 检测的 drift 类型之一
- 索引生成 = GaC 注册的 executor 之一
- 索引验证 = GaC gate 的检查项之一

### 12.2 GaC 规则注册

在 `governance-checks.yaml` 中新增规则：

```yaml
# ── 系统索引 GaC 规则 ──

- id: CR-INDEX-SYSTEM-SSOT
  dimension: X4
  layer: meta
  name: "系统索引 SSOT 一致"
  description: |
    系统索引文件 (SYSTEM-INDEX.md, INDEX-PROJECTS.md, INDEX-TOOLS.md,
    INDEX-KNOWLEDGE.md, INDEX-AGENTS.md) 必须与对应 SSOT 源保持一致。
    检测: 索引中声明的项目数/工具数/ADR 数与实际扫描结果的偏差。
  check_type: index_consistency
  executor: [ci_gate, doc_ssot_lint]
  lifecycle: active
  version: 1
  created_at: "2026-07-03"
  source_ref: "docs/SYSTEM-INDEX-DESIGN.md"

- id: CR-INDEX-GENERATION-FRESH
  dimension: X2
  layer: meta
  name: "系统索引生成新鲜度"
  description: |
    生成型索引文件 (INDEX-PROJECTS/TOOLS/KNOWLEDGE/AGENTS) 的 generated_at
    时间戳不得超过 7 天。超过 = 索引过期，需要重新生成。
    静态型索引 (SYSTEM-INDEX.md) 不受此约束。
  check_type: freshness
  executor: [ci_gate, state_freshness_check]
  lifecycle: active
  version: 1
  created_at: "2026-07-03"
  source_ref: "docs/SYSTEM-INDEX-DESIGN.md"

- id: CR-INDEX-NO-HARDCODED
  dimension: X4
  layer: meta
  name: "系统索引禁止硬编码数值"
  description: |
    系统索引文件中不得包含绝对数值 (项目数、工具数、ADR 数、测试数等)。
    数值必须通过指针引用 SSOT 源 (project-registry.yaml, system.yaml 等)。
    生成型索引的数据块由脚本填充，不受此约束（脚本保证准确性）。
  check_type: doc_ssot
  executor: [ci_gate, doc_ssot_lint]
  lifecycle: active
  version: 1
  created_at: "2026-07-03"
  source_ref: "docs/SYSTEM-INDEX-DESIGN.md"
```

### 12.3 与现有 GaC 机制的对接

| GaC 机制 | 索引如何对接 |
|----------|------------|
| **声明式规则** (机制 1) | 索引规则登记到 `governance-checks.yaml`，不硬编码在 lint 脚本中 |
| **schema 校验** (机制 2) | `gac-validate.py` 校验索引规则的必填字段 |
| **泛化执行器** (机制 3) | 索引漂移检测通过 `doc-ssot-lint.py` 执行（已有 executor） |
| **drift 检测** (机制 4) | `gac-drift.py` 检测索引规则 vs 实际执行的偏差 |
| **矛盾检测** (机制 5) | 索引规则与现有 `CR-X4-DOC-SSOT` 不矛盾（索引是 SSOT 的导航层，不是替代） |
| **lifecycle 管理** (机制 6) | 索引规则有 `lifecycle: active`，废弃时改为 `deprecated` |
| **元治理自检** (机制 7) | `gac-healthcheck.py` 的 `doc_ssot` 块检测索引健康度 |

### 12.4 CI 门禁集成

在 `bin/gac-local-gate.py` 的 `CHECKS` 中新增：

```python
# 系统索引漂移检测 (X4 一致性)
("index-drift-check", ["bin/check-index-drift.py", "--json"]),
```

`check-index-drift.py` 检测：
1. `INDEX-PROJECTS.md` 中声明的项目数与 `project-registry.yaml` 一致
2. `INDEX-TOOLS.md` 中声明的工具数与 `ls bin/*.py | wc -l` 一致
3. `INDEX-KNOWLEDGE.md` 中声明的 ADR 数与 `ls .omo/_knowledge/decisions/*.md | wc -l` 一致
4. `INDEX-AGENTS.md` 中声明的 skill 数与 `ls .agents/skills/ | wc -l` 一致
5. 所有索引文件的 `generated_at` 时间戳不超过 7 天

### 12.5 生成脚本作为 GaC executor

索引生成脚本不是"一次性工具"，而是 **GaC 注册的 executor**：

| 脚本 | GaC 角色 | 触发方式 |
|------|---------|---------|
| `bin/gen-projects-index.py` | executor for `CR-INDEX-SYSTEM-SSOT` | CI 门禁 / 手动 |
| `bin/gen-tools-index.py` | executor for `CR-INDEX-SYSTEM-SSOT` | CI 门禁 / 手动 |
| `bin/gen-knowledge-index.py` | executor for `CR-INDEX-SYSTEM-SSOT` | CI 门禁 / 手动 |
| `bin/gen-agents-index.py` | executor for `CR-INDEX-SYSTEM-SSOT` | CI 门禁 / 手动 |
| `bin/check-index-drift.py` | executor for `CR-INDEX-GENERATION-FRESH` | CI 门禁 |

### 12.6 与 NORTH-STAR.md 的对齐

GaC 北极星的 5 个不变量，索引体系全部满足：

| 不变量 | 索引体系如何满足 |
|--------|----------------|
| **规则 SSOT** | 索引规则登记在 `governance-checks.yaml`，不散落 |
| **声明式** | 规则是 YAML 数据，不是硬编码检查逻辑 |
| **执行通道统一** | 通过 `doc-ssot-lint.py` + `check-index-drift.py` 执行 |
| **drift 必检** | `gac-drift.py` 定期检测索引 vs 实际偏差 |
| **元模型约束** | 索引规则上 MOF M1，元模型派生保证结构一致 |

### 12.7 与 doc-ssot-contract.md 的扩展

在 `.omo/standards/doc-ssot-contract.md` 的 SSOT 映射表中新增：

```markdown
| 事实类型 | 唯一读源 | 禁止出现在 |
|---------|---------|-----------|
| ... 现有条目 ... | ... | ... |
| 系统索引 (导航层) | `docs/INDEX-*.md` (生成型) | 不持有数据，只做指针 |
| 索引漂移状态 | `bin/check-index-drift.py --json` | 所有 markdown |
```

在文档类型职责矩阵中新增：

```markdown
| 文档 | 事实层 | 架构层 | 操作层 | 边界层 | 入口层 | 导航层 |
|------|:------:|:------:|:------:|:------:|:------:|:------:|
| ... 现有行 ... | ... | ... | ... | ... | ... | ... |
| SYSTEM-INDEX.md | — | ref | ref | — | **OWN** | **OWN** |
| INDEX-PROJECTS.md | ref | — | — | — | ref | **OWN** |
| INDEX-TOOLS.md | ref | — | ref | — | ref | **OWN** |
| INDEX-KNOWLEDGE.md | ref | — | — | — | ref | **OWN** |
| INDEX-AGENTS.md | ref | — | ref | — | ref | **OWN** |
```

### 12.8 维护责任矩阵（GaC 版）

| 事件 | GaC 规则 | executor | 谁执行 | 频率 |
|------|---------|----------|--------|------|
| 新项目加入 | `CR-INDEX-SYSTEM-SSOT` | `gen-projects-index.py` | CI 自动 | push 时 |
| 新增 bin/ 工具 | `CR-INDEX-SYSTEM-SSOT` | `gen-tools-index.py` | CI 自动 | push 时 |
| 新增 ADR | `CR-INDEX-SYSTEM-SSOT` | `gen-knowledge-index.py` | CI 自动 | push 时 |
| 新增 skill | `CR-INDEX-SYSTEM-SSOT` | `gen-agents-index.py` | CI 自动 | push 时 |
| 索引过期 (>7d) | `CR-INDEX-GENERATION-FRESH` | `check-index-drift.py` | CI 门禁 | 每日 |
| 索引含硬编码 | `CR-INDEX-NO-HARDCODED` | `doc-ssot-lint.py` | pre-commit | 每次 commit |
| 架构层变更 | `CR-INDEX-SYSTEM-SSOT` | 人工更新 | governance-team | 手动 |

---

## 十三、总结

### 核心设计

| 维度 | 设计 |
|------|------|
| 架构 | 4 索引 + 1 入口（SYSTEM-INDEX → 4 分类索引 → SSOT） |
| SSOT | 索引只做指针，不复制数据 |
| GaC 集成 | 索引即 GaC 规则 — 3 条规则注册到 governance-checks.yaml |
| 动态化 | 模板人工维护 + 数据块脚本生成 |
| 维护 | GaC executor 自动触发 + CI 门禁漂移检测 |
| 阅读 | 分层导航（入口 → 分类 → SSOT） |

### GaC 集成要点

| GaC 机制 | 索引如何对接 |
|----------|------------|
| 声明式规则 | 3 条规则登记到 governance-checks.yaml |
| schema 校验 | gac-validate.py 校验规则字段 |
| 泛化执行器 | doc-ssot-lint.py + check-index-drift.py |
| drift 检测 | gac-drift.py 定期检测 |
| lifecycle | active → deprecated → removed |

### 实施路径

| 阶段 | 产出 | 工作量 |
|------|------|--------|
| 本次 | 方案确认 + SYSTEM-INDEX.md | 2h |
| 后续 P1 | 4 个分类索引 + 5 个生成脚本 + GaC 规则注册 | 19h |
| 后续 P2 | check-index-drift.py + CI 门禁集成 | 3h |
| 长期 | 季度维护 + GaC healthcheck | 持续 |
