---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
migrated_to: governance-mechanism.md
deprecated-since: 2026-06-23

---

# OMO 治理体系 — 全流程机制

> 2026-06-06 | 版本: v1.0 (治理首次运行完成)
> 本文说明治理机制，不维护当前 Phase、下次审查时间、服务数量、债务数量、交付物数量等运行时快照。
> 当前运行时事实请回看 `/.omo/state/system.yaml`、`/.omo/goals/current.yaml`、`/.omo/debt/`、`/.omo/_delivery/`。

---

## 一、治理总览

OMO 治理体系是一个**数据驱动**的闭环系统，围绕"观测 → 决策 → 执行 → 验证"四个阶段循环运转。

```
                    ┌──────────────┐
                    │   观测 (O)    │ ← state show / health / i0 status
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   决策 (D)    │ ← goal / debt review
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   执行 (E)    │ ← omo-debt dispatch / goal create
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   验证 (V)    │ ← delivery archive / governance report
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  归档到交付面  │ → _delivery/
                    └──────────────┘
```

---

## 二、治理周期

### 标准周期 (每周)

```
周一: 观测 — state show → health → i0 status
周三: 决策 — goal status → debt review → knowledge list
周五: 执行 — debt dispatch → goal progress → delivery report
      验证 — governance report → commit → archive
```

### 当前周期状态

> 当前 Phase、上次治理时间、下次审查节奏属于运行时事实，
> 不在本文手工维护；以 `/.omo/state/system.yaml`、`/.omo/goals/current.yaml`
> 和自动化调度/审计证据为准。

---

## 三、工具链

### 观测工具

```bash
omo state show          # 系统状态: Phase / Health / Agents
omo state health        # 服务健康聚合
omo goal list           # Phase 目标列表
omo goal status --json  # 完成度 JSON
omo knowledge list      # 知识面文档总览
omo delivery list       # 交付物列表
omo standard list       # 标准文件列表
omo i0 status           # Agora Hub 状态
omo i0 routes           # Agora 路由与入口状态
```

### 决策工具

```bash
omo goal create --id G29.1 --desc "..."    # 创建新目标
omo goal progress --id G29.1 --pct 50       # 更新目标进度
omo-debt register --id ...                  # 注册新债务
omo-debt reclassify --id ...                # 重分类债务
```

### 执行工具

```bash
omo-debt dispatch --now 2026-06-13          # 分发债务到负责人
omo-debt report                             # 生成债务报告
omo-debt report-trend                       # 债务趋势分析
omo state refresh                           # 刷新系统状态
omo knowledge add --plane management ...     # 添加知识文档
```

### 验证工具

```bash
omo delivery list --phase phase28           # 检查交付物
omo delivery archive --phase phase27        # 归档旧交付物
omo standard add --title "..." --content... # 添加标准
```

---

## 四、数据流

### 数据从哪里来

```
外部系统                       →  OMO CLI             →  .omo/ 存储
─────────────────────────────────────────────────────────────────────
Agora (HTTP :7430)            →  omo i0 status        →  (查询, 不存储)
Runtime Matrix (subprocess)   →  omo state refresh    →  state/system_health.yaml
KEI Audit (kei_audit.jsonl)   →  omo kei dashboard    →  (查询, 不存储)
开发者/治理者 (键盘)            →  omo goal create      →  goals/current.yaml
开发者/治理者 (键盘)            →  omo-debt register    →  debt/items/*.yaml
开发者/治理者 (键盘)            →  omo knowledge add    →  _knowledge/*/
开发者/治理者 (键盘)            →  omo delivery archive →  _archive/delivery/
```

### 数据存在哪里

```
.omo/ 目录 (单一数据源 SSOT)
├── state/system.yaml           ← 系统状态 (Health/Phase/Agents)
├── state/system_health.yaml    ← 服务健康（实时聚合状态）
├── goals/current.yaml          ← Phase 目标（权威目标状态）
├── debt/registry.yaml          ← 债务台账索引
├── debt/items/*.yaml           ← 每项债务的详情
├── debt/reviews/current.md     ← 审查队列 (Due/Unscheduled/Identified)
├── debt/review-queue/*.yaml    ← 分发队列 (owner/schedule/approve)
├── debt/dispatch/current.yaml  ← 分发记录 (18 项 schedule_now)
├── debt/reporting/current.yaml ← 债务报告
├── debt/dashboard/current.yaml ← 债务仪表盘数据
├── standards/                  ← 架构与治理标准
├── _knowledge/                 ← 知识文档
├── _delivery/                  ← 交付物
└── _archive/                   ← 历史归档
```

---

## 五、决策流程

### 债务生命周期

```
发现 → 注册 → 排期 → 分发 → 执行 → 审查 → 关闭 → 归档
  │        │       │       │       │       │       │
  ├ omo-   ├ omo-  ├ omo-  ├ omo-  ├ 代码  ├ omo-  ├ delivery
  │ debt   │ debt  │ debt  │ debt  │ 实现  │ debt  │ archive
  │ register│report │schedule│dispatch│       │review │
  │        │       │       │       │       │       │
  │        │       │       │       │       │       │
  └ 全景   └ 从    └ 设定  └ 分配  └ 修复  └ 确认  └ 归档到
    分析      review      next_     owner     已解决    _archive/
             queue       review    (omo-              delivery/
                         at       governance)
```

### 审查队列

```
review-queue/ 按优先级排序:
  due_now:       排期已到期的项
  upcoming:      即将到期的项
  unscheduled:   从未排期的项
  watch_only:    仅监控项

当前状态:
  以 `/.omo/debt/` 下的 registry/items/reviews/dispatch/reporting/dashboard 为准，
  不在本文静态维护 open/resolved 数量。
```

---

## 六、角色与职责

| 角色 | 职责 | 工具 |
|------|------|------|
| **人类治理者** | 制定 Phase 目标、审批重大决策、审查报告 | `omo goal create`, `omo-debt approve` |
| **OMO CLI** | 执行治理操作、读写 .omo/ 数据 | `omo *` 命令族 |
| **AI Agent** | 发现债务、实施修复、更新状态 | `omo-debt register`, `omo goal progress` |
| **治理系统** | 维持审查节奏、追踪债务趋势、生成报告 | 每周五 9:17 自动审查 |

---

## 七、治理成熟度

| 指标 | 当前 | 目标 |
|------|------|------|
| CLI 覆盖 | 以治理检查与接口注册表实测为准 | 全平面覆盖 |
| 债务追踪 | 以 `/.omo/debt/` 实际状态为准 | 0 open 或合理 backlog |
| 审查节奏 | 每周五 9:17 | 已建立 |
| 状态刷新 | 手动运行 `omo state refresh` | 自动化 cron |
| Phase 目标 | 以 `/.omo/goals/current.yaml` 为准 | 每个 Phase 有活跃目标 |
| 交付报告 | 以 `/.omo/_delivery/` 为准 | 每周 1 份 |

---

## 八、一句话总结

> **OMO 治理 = 观测 → 决策 → 执行 → 验证**
>
> 数据在 `.omo/` 中流转；覆盖率、数量与实时进度一律回看 control/truth/delivery SSOT。
