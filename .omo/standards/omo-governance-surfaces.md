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
| `projects/omo/src/omo/omo_ingress.py` | C2G / 其他 ingress 对 goal/task/debt 的受审计持久化写入 |
| `omo CLI` / `workspace governance` / `workspace compass` / `c2g` | 面向人类与 agent 的正式入口 |

`projects/c2g` 不再直接写 `.omo/`，而是必须调用 `projects/omo/src/omo/omo_ingress.py` 等受审计 broker。
禁止新增任何“顺手脚本”直接 `write_text/open(..., "w")/unlink/mkdir` 改 `.omo/`，除非该脚本本身被提升为受审计 broker。

运行时也一样。凡是会改变 `tasks/planned|active|done|archived|remediation` 生命周期状态的链路，即使调用方是 worker/runtime，也必须优先走 ingress broker，而不是在 worker 内部直接 `replace/unlink/write_yaml` 搬运任务文件。当前已收敛的最小集合至少包括：

- `yield_task()` -> `omo_ingress.yield_task_to_planned()`
- `promote-apply` -> `omo_ingress.promote_task_to_active()`
- promotion rollback -> `omo_ingress.revert_task_to_planned()`
- fast-track compaction archive -> `omo_ingress.archive_done_task()`
- self-evolution review lane -> `omo_ingress.route_self_evolution_to_remediation()`
- complex request bridge / user confirmation / task-center accounting-control -> `omo_ingress.create_blocked_task()` / `record_task_consensus()` / `write_usage_accounting()` / `write_task_center_freshness()` / `write_task_center_control_decision()`
- governance overlay roadmap/control mutation -> `omo_ingress.update_governance_overlay_state()`
- task-center truth helper outputs（例如 skill manifest / discovery registry）-> `omo_ingress.create_skill_manifest()` / `write_discovery_registry()`
- self-healing 自动 debt 登记 -> `omo_self_healing.SelfHealingEngine._create_debt()` 必须走 `omo_ingress.upsert_debt_item()`

任何 helper/factory（例如 skill packet / discovery blueprint instantiation）如果要生成 `.omo/tasks/blocked/*.yaml`，也必须复用 `omo_ingress.create_blocked_task()`，不能各写一套 `write_yaml_atomic()`。

允许继续直写的仅限 runtime scratch / dispatch lease / checkpoint / analytics snapshot 这类非 workflow truth 面，不包括任务主状态迁移。

补充边界约束：

- `projects/c2g` 业务模块不得散弹式直接 import `omo.omo_ingress`、`omo.omo_task_schema` 等内核模块。
- `projects/c2g` 必须通过本地单一 facade（当前为 `projects/c2g/src/c2g/omo_client.py`）接入 OMO。
- 这个约束必须由 `omo lint c2g-omo-boundary` 和 pre-commit gate 持续拦截，而不是靠 reviewer 肉眼记忆。

`_delivery/ingress/*` 的 artifact 也不是“写了就算”。至少必须满足：

- registry `artifact_ref` 指向真实文件
- artifact `kind / created_at / source_ref / ingress_plane` 与 registry 对齐
- artifact 必须带回指 carrier 的字段（如 `goal_ref / task_ref / debt_ref`）
- 新生成 artifact 应携带 `broker_ref / retention_mode / lifecycle_state`，让生命周期可追溯

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

### 3.1 顶层资产持久化语义

每个登记到 `/.omo/_truth/registry/omo-governance-surfaces.yaml:assets` 的 state-plane 资产，必须额外声明两类机器字段：

| 字段 | 含义 | 允许值 |
|---|---|---|
| `persistence_mode` | 资产在状态面上的持久化角色 | `authoritative` / `durable` / `operational` / `append_only` / `archival` / `compatibility_alias` |
| `retention_mode` | 资产保留与清理方式 | `until_replaced` / `manual_cleanup` / `rolling_window` / `append_forever` / `manual_archive` / `alias_only` |

最小约束：

- `authority` / `root_registry` / `goal_state` 必须是 `authoritative + until_replaced`
- `delivery_state` / `change_history` / `runtime_logs` 必须显式说明是否 `append_only`
- `archived_state` 必须是 `archival + manual_archive`
- `compatibility_alias` 必须是 `compatibility_alias + alias_only`，并带 `alias_target`
- `capability_market` 若承载 capability registry，现行写入路径必须是 `.omo/capabilities/*.yaml`，且写入必须通过 `projects/omo/src/omo/omo_ingress.py:write_capability_registry_bundle` / `write_manual_capabilities`；历史 `.omo/registry/*.yaml` 仅允许读兼容，不再新增写入
- `runtime_ssot` 若存在投影/缓存回写入口，必须在 mutation surface registry 显式登记为 projection/cache 写面；当前 `omo state sync-tasks` 只允许刷新 task counters 与 `next_*` 投影，不得扩成任意字段写口

这不是说明文案字段，而是 lint gate 会检查的治理契约。没有这两个字段，就说明“这个目录要留多久、能不能覆盖、什么时候归档”根本没定义清楚。

## 4. 红线

1. 不得在 `.omo` 顶层新增未登记资产。
2. 不得把日志、tmp、stderr/stdout 转储长期混入 `_truth/` 或 `standards/`。
3. 不得把 `projects/omo` 的执行逻辑回灌进 `.omo/` 作为“临时脚本常驻”。
4. `projects/c2g` 只能把任务物化到 `.omo/tasks/planned/`，不得直接写 `active/`、`done/`。
5. 嵌套 `.omo/.omo/*` 视为遗留异常路径，发现即归档并删除，不得重新生成。
6. `.omo/evidence` 若仍存在，只允许作为指向 `_delivery/*` 的兼容别名，不得再作为独立真实目录扩写。
7. 非 broker Python 代码不得直接改写 `.omo/` 或 `spaces/`；pre-commit 与 `omo lint direct-omo-io` 必须拦截。
7.1 已知历史直写若暂时无法一轮消灭，必须登记到 `.omo/_truth/registry/direct-io-baseline.yaml`，只允许“冻结存量”，不得掩护新增违规。
7.2 一旦历史直写清零，`.omo/_truth/registry/direct-io-baseline.yaml` 必须保持 `entries: []`；`omo lint direct-omo-io` / CI / pre-commit 必须把任何新增 baseline entry 视为失败。
8. `.omo/_delivery/ingress/registry.yaml` 若存在，必须保持 `by_id` / `by_source_ref` 双向一致，并且 artifact/task/goal/debt 引用可落到真实状态面。
9. `/.omo/goals` 必须保持为指向 `/.omo/_truth/goals` 的运行时入口符号链接；文档与 broker 一律引用 `/.omo/goals/current.yaml`，不得发明第二写入目标。

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
- CI / 本地治理门禁必须显式执行 `omo.cli governance surfaces --workspace-root . --json`
- `omo lint ingress-registry` 能校验 ingress registry 的结构与反向映射
- `omo lint mutation-surfaces` 能把 broker 写入入口清单从“解释性文档”提升为可执行门禁
- `omo lint internal-write-profiles` 能把 worker/internal 运行时写面从“可观察报表”提升为正式 registry 门禁
- `omo lint state-plane-assets` 能校验 `.omo` 顶层资产是否带完整的持久化/保留语义，防止 state/control/delivery/knowledge 再次混写
- `omo lint c2g-omo-boundary` 能校验 `projects/c2g` 只通过单一 facade 接入 OMO，防止跨仓调用再次散开
- `omo lint ingress-artifacts` 能校验 ingress registry 指向的 artifact 文件存在且元数据与 registry / carrier 对齐
- `omo lint self-evolution-approval` 能拦截 OPC P6 self-evolution task 的审批字段漂移与 active 泄漏
- `omo lint task-policy <name>` 能承载后续更多特殊任务红线，而不把规则散落到单独脚本
- `task-policy` 既要有运行时代码注册表，也要有 `.omo/_truth/registry/task-policies.yaml` 机器可读注册表
- `task-policy` 注册表新增规则后，必须同时纳入 pre-commit 或 CI，避免只在文档层声明
- OMO 的人类/桥接 mutation surfaces 必须维护运行时快照与 `.omo/_truth/registry/mutation-surfaces.yaml` 对齐，防“入口已收口但没有资产清单”
- OMO 的 worker/internal 写路径必须维护 `.omo/_truth/registry/internal-write-profiles.yaml`，明确哪些写面属于运行时 scratch、哪些带 promotion 风险
- `omo governance ingress-goal/task/debt` 与 `projects/c2g` 的持久化适配器都属于正式 mutation surface，不得只登记终端 CLI 而漏掉治理入口/桥接入口
- `.omo/state/system.yaml` 的投影刷新也必须登记正式 mutation surface；`omo state sync-tasks` 与 `omo_audit_sync --apply` 只能通过 `write_system_projection_fields` 白名单 broker 落盘
- `omo governance surfaces --json` 必须暴露 mutation surface registry 漂移，作为 reviewer 判断“还有哪些 mutation 没收口”的机器依据
- pre-commit / CI / `workspace governance verify` 必须显式执行 `omo lint mutation-surfaces`、`omo lint internal-write-profiles`、`omo lint state-plane-assets`、`omo lint c2g-omo-boundary` 与 `omo lint ingress-artifacts`，避免只有 reviewer 看 `surfaces --json` 时才发现 drift
- 目录语义必须可固化为 policy；例如 `done/` 中的 packet 不得再出现 `status: review/completed`
- done 态治理要先从“新式 packet”做窄约束，再逐步覆盖历史存量，避免一刀切误伤老票
- review 态也优先走窄约束；例如 remediation review 先要求审查笔记存在，再逐步补更强的 lifecycle 字段
- 对新式 done packet，`evidence_paths` 采用“声明即强制存在”的方式落地，先不倒逼所有历史 packet 补齐
- active review 与 remediation review 分开治理：前者强调 `review_ref` 工件存在，后者强调 `review_note` 收口证据存在
- `projects/c2g` 产出的 planned task 携带治理引用
- `omo lint direct-omo-io` 与 pre-commit hook 能拦截非 broker 直接写 `.omo`
- `omo lint sensitive-governed-writes` 必须继续守住 `system.yaml / goals/current.yaml / tasks/* / capabilities/*` 的 broker-only 落盘约束，但仅针对人类/桥接敏感写面；已登记的 worker/internal 生命周期写口仍由 `internal-write-profiles` registry 单独治理
- `contract_gatekeeper.py` 若启用 baseline，只能压住已登记的历史 path+line；任何新违规必须仍然 fail
- `direct-io-baseline.yaml` 清零后必须持续为空；新增 grandfather entry 本身就应触发 lint fail
- X1/X2/X3/X4 与 L0/M1 治理模型中存在对应映射
