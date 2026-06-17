# OMO Governance Surfaces Standard

> 状态: active
> 版本: v1.1
> 日期: 2026-06-17
> 适用范围: `.omo/` 状态面、`projects/omo` 治理内核、`projects/c2g` 战略入口

## 1. 目的

`.omo/` 不是一个“什么都能塞”的目录。它只是 OMO 治理系统的状态承载面。

真正的治理必须拆成三层一起看：

| 层 | 位置 | 职责 |
|---|---|---|
| `state_plane` | `.omo/` | 承载状态、证据、知识、控制与交付产物 |
| `kernel_plane` | `projects/omo/` | 提供治理命令、Schema 校验、审计、promotion、overlay、sync |
| `ingress_plane` | `projects/c2g/` | 将 Pitch / OpenSpec / Fast-Track 转化为 OMO Planned Tasks |

红线：任何只改 `.omo/` 目录、不同时考虑 `projects/omo` 与 `projects/c2g` 的方案，都不算治理完成。

## 1.1 SSOT 链

| 类型 | 文件 |
|---|---|
| 解释性标准 | `.omo/standards/omo-governance-surfaces.md` |
| 机器可读注册表 | `.omo/_truth/registry/omo-governance-surfaces.yaml` |
| X1 审计/边界策略 | `.omo/_truth/x1-governance-policies.yaml` |
| X2 保鲜规则 | `.omo/_truth/x2-freshness-rules.yaml` |
| X3 价值归因 | `.omo/_truth/x3-value-stack.yaml` |
| X4 一致性规则 | `.omo/_truth/x4-consistency-rules.yaml` |
| L0 强制约束 | `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` |

上层入口文档如 `AGENTS.md`、`.omo/INDEX.md` 只能保留骨架与链接，不得再复制这些规则正文。

## 2. 分层契约

### 2.1 `.omo/` 只存状态，不存治理执行内核

- `.omo/` 可以存 YAML / JSON / Markdown / evidence / audit / registry / state。
- `.omo/` 不应成为 Python 运行时代码的长期宿主。
- `.omo/` 允许存在测试与历史残留，但必须被分类、限界并逐步出清，不能伪装为 active truth。

### 2.2 `projects/omo` 是唯一治理执行内核

- 负责 `.omo` 的任务校验、标准读取、truth mutation、audit、sync、promotion、overlay。
- 新的 `.omo` 目录治理规则，必须能被 `projects/omo` 引用，而不只是写在文档里。
- 任何对 `.omo/_truth/` 的高风险修改，都应优先走 `omo governance propose/approve/apply` 模式或等价审计链。
- `projects/omo/.omo/` 或其他子仓内部的 `.omo/` 只可视为测试夹具、历史影子或局部样例，不得作为运行时权威状态面。

### 2.3 `projects/c2g` 是唯一战略入口

- `projects/c2g` 负责把上游 Pitch / OpenSpec / Fast-Track 变成 `.omo/tasks/planned/*.yaml`。
- `c2g` 产物必须携带治理上下文，至少可追溯到：
  - `.omo` 目录治理标准
  - `.omo` 资产分类注册表
  - X1-X4 治理规则
- `c2g` 不得绕过 OMO task schema 直接制造不受治理约束的任务。

### 2.4 授权写入 broker

未来若需要修改 `.omo/`，只能通过下列 broker：

| broker | 允许范围 |
|---|---|
| `projects/omo/src/omo/*` | OMO 内核对 `.omo` 的治理写入 |
| `projects/c2g/src/c2g/adapters.py` | 仅写 `.omo/tasks/planned/` 与 `.omo/goals/current.yaml` 对应能力 |
| `projects/c2g/src/c2g/bridge_import.py` | 仅写 C2G 导入产物到 planned/ |
| `omo CLI` / `workspace compass` / `c2g` | 面向人类与 agent 的正式入口 |

禁止新增任何“顺手脚本”直接 `write_text/open(..., "w")/unlink/mkdir` 改 `.omo/`，除非该脚本本身被提升为受审计 broker。

## 3. `.omo/` 目录分类

| 目录/载体 | 分类 | 说明 | 写入者 |
|---|---|---|---|
| `_truth/` | authority | 唯一真相源、注册表、目标、规则 | governance / human-reviewed automation |
| `_control/` | control_state | 控制状态、overlay、evolution loop、dashboard | omo kernel / approved automation |
| `_knowledge/` | knowledge_state | 设计、决策、复盘、审计、说明 | agents / humans |
| `_delivery/` | delivery_state | release、phase-gate、scenario、audit rollout 等交付证据 | omo kernel / agents |
| `_archive/` | archived_state | 已降级历史，不参与当前 SSOT 计算 | humans / approved automation |
| `tasks/` | workflow_state | planned / active / blocked / done / archived 等任务状态 | omo kernel / c2g ingress |
| `state/` | runtime_ssot | phase、health、model-driven snapshots | aggregator / omo kernel |
| `debt/` | governance_program | 债务登记、派发、报表、评审 | omo kernel / debt pipeline |
| `workers/` | execution_runtime | dispatch / reclaim / prompt / runbook 运行态 | omo kernel |
| `cron/` | control_contract | 定时触发契约与入口定义 | humans / governance |
| `standards/` | rule_docs | 持续生效标准，供 kernel/agent/workflow 引用 | governance |
| `_log/` | runtime_logs | 原始日志、观测底稿、临时运行轨迹 | automation / kernel |
| `goals/` | goal_state | 当前目标、历史目标、战略收口状态 | governance / c2g |
| `pitches/` | strategic_input | 战略提案与投前材料的持久锚点 | c2g / humans |
| `tests/` | governance_test_surface | 工作区级治理与门禁测试资产 | test agents / humans |
| `capabilities/` | capability_market | 治理面能力/市场清单等轻量注册物 | governance |
| `change-log/` | change_history | 紧凑型变更历史摘要 | governance / automation |
| `PROJECTS.yaml` | root_registry | 全系统项目注册表（只记录稳定身份/状态/路径，不记录运行时计数） | governance |
| `INDEX.md` | root_index | `.omo` 根导航文档 | governance |
| `evidence/` | compatibility_alias | 兼容别名，真实存储应落 `_delivery/evidence-legacy/` 或 `_delivery/evidence/` | agents / humans |

## 4. 红线

1. 不得在 `.omo` 顶层新增未登记资产。
2. 不得把日志、tmp、stderr/stdout 转储长期混入 `_truth/` 或 `standards/`。
3. 不得把 `projects/omo` 的执行逻辑回灌进 `.omo/` 作为“临时脚本常驻”。
4. `projects/c2g` 只能把任务物化到 `.omo/tasks/planned/`，不得直接写 `active/`、`done/`。
5. 嵌套 `.omo/.omo/*` 视为遗留异常路径，发现即归档并删除，不得重新生成。
6. `.omo/evidence` 若仍存在，只允许作为指向 `_delivery/*` 的兼容别名，不得再作为独立真实目录扩写。
7. 非 broker Python 代码不得直接改写 `.omo/` 或 `spaces/`；pre-commit 与 `omo lint direct-omo-io` 必须拦截。

## 5. X1-X4 联动

| 维度 | 在本标准中的落点 |
|---|---|
| X1 | 哪些目录属于权威面、哪些写入路径被允许 |
| X2 | 目录治理标准、注册表、入口约束必须定期保鲜 |
| X3 | `.omo` 状态面、`omo` 内核、`c2g` 入口的治理成本与价值归因必须可分层说明 |
| X4 | 文档、注册表、kernel 常量、c2g 产物元数据必须保持一致 |

## 6. 验收标准

- 存在机器可读注册表：`.omo/_truth/registry/omo-governance-surfaces.yaml`
- `projects/omo` 能引用该标准或对应 registry 常量
- `projects/c2g` 产出的 planned task 携带治理引用
- `omo lint direct-omo-io` 与 pre-commit hook 能拦截非 broker 直接写 `.omo`
- X1/X2/X3/X4 与 L0/M1 治理模型中存在对应映射
