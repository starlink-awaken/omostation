# `.omo/` 文档架构体系

> 基于 SSOT 本体建模思想的四平面文档架构。参考 [KEMS](https://github.com/user/kems) 方法论体系。

---

## 体系总览

### 四平面定义

| 平面 | 目录 | 隐喻 | 回答的问题 | 变动频率 | SSOT 原则 |
|------|------|------|-----------|---------|----------|
| **控制面** | `_control/` | 驾驶舱 | 我现在在哪？状态如何？下一步做什么？ | 会话级 | `state/system.yaml` 为唯一状态聚合快照 |
| **事实面** | `_truth/` | 黑匣子 | 什么是真的？唯一权威源在哪？ | 永久 | `tasks/` 任务SSOT / `standards/` 标准SSOT |
| **知识面** | `_knowledge/` | 手册库 | 我们知道了什么？有哪些可以复用的知识？ | 30天级 | 设计/过程/管理/使用/参考 五类 |
| **交付面** | `_delivery/` | 货架 | 我们交付了什么？可验证的证据在哪？ | 持续 | 运行记录为唯一执行证据 |

### 四平面关系

```
                  ┌─────────────────────────────────┐
                  │          控制面 _control/          │
                  │   (设定目标 → 观测状态 → 触发行动)    │
                  └──────┬────────────┬─────────────┘
                         │            │
                  ┌──────▼──┐   ┌────▼─────────┐
                  │ 事实面   │   │   知识面       │
                  │ _truth/ │   │ _knowledge/   │
                  │ (SSOT)  │   │ (WIKI)        │
                  └──────┬──┘   └────┬─────────┘
                         │            │
                  ┌──────▼────────────▼─────────┐
                  │         交付面 _delivery/       │
                  │   (执行证据 → 运行记录 → 产出)    │
                  └─────────────────────────────────┘

    采集链（进）──── 推导链（想）──── 输出链（出）
```

---

## 融合原则（与现有 `.omo` 机制共存）

四平面不是要把 `.omo` 现有机制重新搬家，而是给现有机制加一层**稳定的语义入口**：

1. **控制面入口化**：`_control/INDEX.md` 聚合 `goals/`、`state/`、一致性门禁，但真正可写的控制信号仍在 `goals/current.yaml` 与 `state/system.yaml`。
2. **事实面索引化**：`_truth/INDEX.md` 只负责说明 SSOT 在哪；`tasks/`、`standards/`、`workers/registry.yaml`、`PROJECTS.yaml` 继续是唯一真相源。
3. **知识面编目化**：`_knowledge/` 不复制事实或运行记录，只给顶层散落文档建立稳定分类与阅读路径。
4. **交付面证据化**：`_delivery/INDEX.md` 负责串联 `workers/runs/`、`tests/`、`summaries/`、`evidence/`；执行证据仍写回这些原位置。

补充约束：

- **默认保持“导航壳”模型**：新机制优先落在既有根目录，再由平面 INDEX 编目。
- **允许 plane-native domain**：如果新域天然只有单一 owner plane（例如 truth-only registry、delivery-only runs），允许直接落在对应平面目录下，但不得在其他平面再复制一份镜像实体。
- **实时事实禁止在索引页硬编码复制**：Phase、任务数、健康分、active queue 等易变数据必须链接 live source，而不是在 INDEX 中维护静态数字。

因此，**四平面目录是“导航壳 + 约束层”**，底层 `.omo` 任务系统、状态系统、worker 协同机制和验收机制不变。

---

## 平面详述

### 1. 控制面 — `_control/`

**角色**: 系统的传感器与调节器。回答"我现在在哪？下一步该做什么？"

| 组件 | 实现 | SSOT 原则 |
|------|------|----------|
| **战略参考信号** | `goals/current.yaml` | 人类设定 Phase 目标的唯一源 |
| **系统状态仪表盘** | `state/system.yaml` | Agent 可读的系统全局状态快照 |
| **质量门禁** | `CONSISTENCY-CHECK.md` | 跨平面一致性规则与检查结果 |
| **控制历史文档** | `_control/*.md` (legacy 控制文档) | 历史快照，不再作为执行源 |

**核心流程**: `goals/` 设定目标 → Agent 执行 → `state/system.yaml` 聚合状态 → `CONSISTENCY-CHECK.md` 验证一致性 → 反馈修正目标

### 2. 事实面 — `_truth/`

**角色**: 系统的唯一真相源。回答"什么是真的？权威信息在哪？"

| SSOT 实体 | 实现位置 | 内容 |
|-----------|---------|------|
| **任务 SSOT** | `tasks/` | 14字段 YAML schema 的任务生命周期管理；其中 `active/` 是 current executable queue，`planned/` 是 future backlog / not-yet-promoted packet surface |
| **标准 SSOT** | `standards/` | 8 Active + 5 Legacy 治理标准 |
| **项目注册表** | `PROJECTS.yaml` | 5 项目 + 1 归档的注册信息 |
| **Worker 注册表** | `workers/registry.yaml` | 外部 Agent 注册与能力声明 |
| **资产清单** | `INVENTORY.md` | 全系统资产枚举 |
| **巨石分解配置** | `boulder.json` | 巨石任务分解结构 |

**SSOT 铁律**: 同一事实不在多处重复写。知识面文档引用事实面时使用指针而非副本。

### 3. 知识面 — `_knowledge/`

**角色**: 系统的长期记忆与知识复用库。回答"我们知道了什么？有哪些可以复用的知识？"

| 子分类 | 目录 | 包含内容 |
|--------|------|---------|
| **设计文档** | `_knowledge/design/` | 架构设计、蓝图、路线图、规格书 |
| **过程文档** | `_knowledge/process/` | 复盘总结、SOP、工作流记录 |
| **管理文档** | `_knowledge/management/` | 审计报告、评审记录、影响分析 |
| **使用文档** | `_knowledge/usage/` | 上手指南、CLI 规范、使用说明 |
| **参考文档** | `_knowledge/reference/` | 术语表、经验教训、基准测试 |

### 4. 交付面 — `_delivery/`

**角色**: 系统的产出货架。回答"我们交付了什么？可验证的证据在哪？"

| 组件 | 实现位置 | 内容 |
|------|---------|------|
| **Worker 运行记录** | `workers/runs/` | 外部 Worker 的执行证据 |
| **测试记录** | `tests/` | 治理一致性 + Schema 测试 |
| **执行证据** | `evidence/` | 交付证据归档 |
| **会话续接** | `../runtime/run-continuation/` | 工作区运行时会话续接记录 |
| **产出报告** | `summaries/` (部分) | 交付总结报告 |

**交付面规则**: 运行记录不可删除，仅可归档。每条记录包含可重现的上下文。

---

## 文件规范

### Frontmatter 字段

所有文档建议使用以下 frontmatter 元数据：

```yaml
---
plane: control          # control | truth | knowledge | delivery
type: state             # 见下方类型枚举
status: active          # active | legacy | draft | archived
freshness: 2026-05-31   # 最后验证/更新日期 (YYYY-MM-DD)
maintainer: auto        # human | agent | auto
supersedes:             # (可选) 被取代的文件路径
superseded_by:          # (可选) 取代此文件的新文件路径
---
```

### 类型枚举

| 平面 | 允许的类型值 |
|------|-------------|
| control | `state`, `goal`, `gate`, `signal`, `timeline`, `strategy`, `blueprint`, `command` |
| truth | `task`, `standard`, `entity`, `registry`, `inventory`, `schema`, `config` |
| knowledge | `design`, `process`, `management`, `usage`, `reference`, `case`, `retro`, `audit`, `diagram` |
| delivery | `run`, `evidence`, `report`, `artifact`, `test`, `session` |

### 命名规范

| 规范 | 规则 |
|------|------|
| **平面目录前缀** | 体系目录以 `_` 开头: `_control/`, `_truth/` 等 |
| **文件名格式** | kebab-case: `CONSISTENCY-CHECK.md`, `system.yaml` |
| **知识面编号** | 子分类内使用 `NN-` 前缀表阅读顺序 |
| **实体 ID** | `{type}-{kebab-case}` 格式: `task-M2.5-knowledge-closed-loop` |
| **已有文件** | 保持原名不重命名，通过平面 INDEX 定位 |

### 交叉引用规范

| 引用类型 | 格式 | 示例 |
|---------|------|------|
| 同平面引用 | 直接相对路径 | `[STATE](state/system.yaml)` |
| 跨平面引用 | 格式: `[平面名:文件名]` + `(相对路径)`  | `[事实面:tasks](tasks/README.md)` |
| 外部引用 | 完整相对路径 | `<KEMS 四平面>` 参考资源 |
| 文档元引用 | `^^` 前缀 | `^^ 参见 DOC-ARCH.md §3` |

---

## 一致性规则

1. **状态对齐**: `state/system.yaml.phase` 必须与 `goals/current.yaml.phase` 一致
2. **目标覆盖**: 每个 active goal 必须有对应任务 YAML
3. **指针优于副本**: 事实面（SSOT）数据在知识面文档中只能引用，不得复制
4. **新鲜度标记**: 知识面文档必须标注 `freshness` 日期，超过 90 天标记为 `⚠️ stale`
5. **交付不可逆**: 交付面运行记录一旦写入不可删除，仅可标记 `archived`
6. **平面入口**: 每个平面必须有 `INDEX.md` 作为该平面唯一入口

---

## 文件映射总览

### 控制面文件映射

```
现有位置                        → 控制面类别
─────────────────────────────────────────────────
goals/current.yaml              → 战略参考信号
goals/history/                  → 历史目标归档
state/system.yaml               → 系统状态仪表盘
state/provider-plane.yaml       → Provider 状态
MASTER-BLUEPRINT.md             → 战略蓝图
CONSISTENCY-CHECK.md            → 质量门禁
GOVERNANCE_PLAN.md              → 历史控制文档 (legacy)
HEALTH_DASHBOARD.md             → 历史健康看板 (legacy)
STATE.md                        → 架构历史演进 (legacy)
P1_PROJECT_HEALTH.md            → 历史健康分析 (legacy)
TASK_POOL.md                    → 历史任务池 (legacy)
```

### 事实面文件映射

```
现有位置                        → 事实面类别
─────────────────────────────────────────────────
tasks/                          → 任务 SSOT（含 active/ current executable queue 与 planned/ future backlog）
standards/                      → 标准 SSOT
workers/registry.yaml           → Worker 注册表
PROJECTS.yaml                   → 项目注册表
INVENTORY.md                    → 资产清单
boulder.json                    → 巨石分解配置
```

### 知识面文件映射

```
现有位置                        → 知识面子分类
─────────────────────────────────────────────────
plans/                          → design (设计文档)
MASTER-BLUEPRINT.md             → design (蓝图)
INSIGHTS-AND-ROADMAP.md         → design (路线图)
task-center-requirements.md     → design (需求规格书)
_knowledge/design/reviews/      → design (审阅报告)
ARC-ONTOLOGY-RECOMMEND.md       → reference (本体论)
ARC-ONTOLOGY-TOOLKIT.md         → reference (工具包)
diagrams/                       → reference (架构图)
summaries/                      → process/management
audits/                         → management
AUDIT.md                        → management
ARCH-AUDIT-*.md                 → management
ARCH-REVIEW.md                  → management
KOS_MIGRATION_IMPACT.md         → management
DEBT-ANALYSIS.md                → management
CLEANUP.md                      → management
_knowledge/management/           → management (清理/运维记录)
RETRO-*.md / retro-*.md / wave-*.md → process (复盘)
LESSONS.md                      → reference (经验教训)
MODEL-BENCHMARK.md              → reference (基准测试)
KNOWLEDGE_ARCH.md               → reference (知识架构)
PRODUCT-ARCH-JOURNEY.md         → reference (演进史)
ONBOARDING.md                   → usage (上手指南)
CLI-MCP-SPEC.md                 → usage (CLI 规范)
drafts/                         → management (草稿)
task-prompts/                   → reference (Agent 提示词)
```

### 交付面文件映射

```
现有位置                        → 交付面类别
─────────────────────────────────────────────────
workers/runs/                   → Worker 运行记录
tests/                          → 测试记录
evidence/                       → 交付证据
../runtime/run-continuation/    → 工作区会话续接记录（运行时根）
summaries/phase3-acceptance-report.md → 验收报告
summaries/p3-full-execution-retrospective.md → 最终复盘
```

---

## 使用指南

### Agent 使用约定

1. 新创建文档时，根据内容选择对应平面和子分类放置
2. 引用事实面数据时使用相对路径指针，不复制内容
3. 控制面 INDEX = `.omo/INDEX.md` 是 Agent 启动入口
4. 事实面 INDEX = `_truth/INDEX.md` 是查找 SSOT 的入口
5. 四平面 INDEX 只做导航；写入仍落到原始 SSOT / 证据目录

### 阅读路径

| 目标 | 入口 |
|------|------|
| 快速了解整体状态 | `INDEX.md` → `_control/` |
| 查找权威数据 | `INDEX.md` → `_truth/` |
| 查阅知识文档 | `INDEX.md` → `_knowledge/` |
| 验证交付证据 | `INDEX.md` → `_delivery/` |

---

## 参考

- KEMS 四平面定义: `../../../Documents/学习进化/经验积累/KEMS/.kems/_planes/`
- KEMS Schema Contract: `../../../Documents/学习进化/经验积累/KEMS/.kems/_protocol/03-schema-contract.md`
- KEMS Write Contract: `../../../Documents/学习进化/经验积累/KEMS/.kems/_protocol/01-write-contract.md`

---

*创建: 2026-05-31 · 基于 KEMS v3.4.1 四平面本体建模方法论*
