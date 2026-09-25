---
type: ssot
status: active
lifecycle: design
owner: governance-team
last-reviewed: 2026-09-25
bet_id: __unassigned__
created: 2026-09-25
supersedes: __none__
schema_version: design/v1
---

# 根因分析与治本路径 (2026-09-25)

> **基线**: `.omo/_knowledge/reports/diag-2026-09-25.md` (#4310) — 31 个发现已落地。
>
> **目的**: 不修表面，按"症状 → 机制 → 根因"3 层重组，提出治本战略 + 建 BET。

---

## 0. 核心判断 (TL;DR)

**omostation 当前 maturity 高（截面状态好），但 sustainability 弱（长期不漂移能力缺）**。31 个发现是这一根本张力的不同投影：

```
截面 (maturity):              长期 (sustainability):
gates 11/11 pass     ≠       drift 30 天后必再积累
P74 0 沉默 workflow  ≠       ritual 断供 32 天
lint 0 冲突         ≠       retros 64% 缺字段
30 PR 全 MERGED     ≠       #4291 修了 46/数百
BET 99.8% done       ≠       4 open debt 全 owner-decision
```

**战略命题**: 不能继续"打地鼠式"修 drift。必须**建立自我修复闭环**。

---

## 1. 31 个发现的 3 层重组

### 1.1 现象层 (Symptoms, 31 项)

完整的 31 个发现在 #4310 报告。这里按**机制归类**重新组织。

### 1.2 机制层 (Mechanisms, 5 类)

| 机制 | 描述 | 涉及发现 | 复发模式 |
|---|---|---|---|
| **M1. 写后忘** (Write-and-Forget) | 一次性写完后无人续保；信号/状态/产物依赖"记得跑" | #1 debt-dashboard 9d, #4 13 ephemeral, #24 brief 22h, #26 weekly-review 32d, #15-#16 stale runs | 每 7-30 天必发 |
| **M2. 范围漂移** (Path-Coverage Drift) | 修复覆盖 A 路径，同类问题在 B 路径复发 | #2 5 子仓无 fm, #3 8 GOVERNANCE.md 重复, #25 342 retros 缺 fm, #30 42 rule 零引用 | 每次"路径 X 治理"触发 |
| **M3. 物理-逻辑不一致** (Physical-Logical Asynchrony) | gitlink/launchd/asset 声明面存在，实际面无对应物 | #6-#7 launchd zombie, #9 5 OMO zombie, #20 3 gitlink unreachable | 每次子仓合入或 cron 漂移 |
| **M4. 注册表多源无别名** (Multi-Source Registry Without Aliases) | governance-checks / L0-constraints / hook-manifest 三套 id 词汇不统一 | #30 规则接线率 49% | 每次新增规则 |
| **M5. Ritual 未运营化** (Ritual Not Operationalized) | "周检视"等治理动作只在文件层有定义，无强运营机制 | #26 weekly-review 32d 断供 | owner 任务漂移即发 |

### 1.3 根因层 (Root Causes, 3 个)

#### R1. 系统缺乏"持续守护"机制 (No Continuous Guardian)

**症状**: M1 + M5 都源自此。
**描述**: 所有治理动作（cron 跑、gitlink sync、ritual 触发、状态刷新）依赖**人记得**或**单次 commit 触发**。一旦间隔超 7-30 天，必然漂移。
**证据**:
- `debt-dashboard` 是生成产物，需要周期重生成 —— 但没有自动 cron（meta-doctor 知道，但没人接）
- `weekly-review` 是 ritual —— 32 天未跑
- `brief` 是 hour-cadence 产物 —— 22h 未刷（cron 应挂了）
- ephemeral reports 归档 —— doc-lifecycle audit 已识别，但无自动 archive cron
**根因本质**: 系统是 **passive**（事件触发）+ **人驱动**（owner 记得），不是 **active**（自动）+ **自驱动**（信号闭环）。

#### R2. 修复是事件式、不是面式 (Patched, Not Faced)

**症状**: M2 直接来自此。
**描述**: PR #4291 修了 46 个文档 frontmatter，但**只覆盖 `.agents/` 和 `docs/`**，没扫 `.omo/_knowledge/retros/` —— 结果 342/530 retros 仍缺 schema/status 字段。
**根因本质**: **修一个具体 drift ≠ 修一类 drift**。omostation 的工具是 "find/fix one issue" 而非 "find/fix all instances of issue"。
**证据**: 31 个发现中至少 5 个是"同类问题在不同路径"的复发：
- #2 + #25: frontmatter 缺 schema 字段
- #3 + #30: 重复模板/零引用
- #1 + #24 + #26: 信号/状态/ritual 漂移
- #9 + #6-#7 + #20: 物理-逻辑不一致
- #15-#16 + #1: stale 状态未自动 prune

#### R3. 物理-逻辑映射手工维护 (Manual Physical-Logical Mapping)

**症状**: M3 + M4 来自此。
**描述**: gitlink / launchd / OMO asset / governance-checks ID 都是**逻辑声明**，但需要物理存在（commit reachable、launchd plist installed、文件存在、rule id in code）。当前**双向同步靠人 commit**，无自动 sync 验证。
**证据**:
- #20: 主仓 gitlink 指向 74c3c77 (ecos)，但 origin/main HEAD 是 fa27e16 (子仓 PR #79 已合入)
- #6-#7: 声明 `cron-service` launchd 但 `launchctl list` 找不到
- #9: 5 个 OMO asset 声明但文件系统无对应物
- #30: governance-checks 86 条声明，但 check-l0-constraints.py 用 X2-C05 等不同命名（同一规则 3 个名）
**根因本质**: **声明 ≠ 物理存在 ≠ 实际可达**。每个声明都需要 3 个验证，目前只有第一个有自动 lint，物理存在/可达都是**事后**人工发现。

---

## 2. 战略层分析 — 为什么治标无效

### 2.1 历史趋势

回顾 #4310 的执行摘要，**31 个发现里至少 20 个是"已多次复发"**：

- PR #4128 (a02f54d30): "真复核 26 篇过期 SSOT 文档" —— 4 天后 11 篇再次过期
- PR #4291: "frontmatter 全覆盖 + superpowers 镜像归档" —— 64% retros 仍缺
- PR #4275 (#4282 后续): "reachability gate 的 network work" —— 3 submodule gitlink 仍 unreachable
- P74 0 沉默 + 文档治理 13 临时归档 + meta-doctor ritual_lapsed=1

**所有"修复 X 类 drift"的 PR 都很快被同类新 drift 抵消**。这不是执行问题，是**架构问题**。

### 2.2 系统架构性原因

参考 `ARCHITECTURE.md` + `AGENTS.md` 第 9 节"道法术器 (DFSQ/v1)" + "脊面运行模式 (SFOP)"，omostation 当前架构是：

```
┌──────────────────────────┐
│  L4 文档 / 协议           │  (静态, manual update)
├──────────────────────────┤
│  L3 入口 (cockpit)        │  (事件触发, 单点)
├──────────────────────────┤
│  L2 内核 (omo/agent-workflow) │  (drift 探测器)
├──────────────────────────┤
│  L1 运行时 (panorama/cron)  │  (依赖 owner)
├──────────────────────────┤
│  L0 协议 (BOS/MOF)         │  (注册表, manual sync)
└──────────────────────────┘
```

**缺一层**: **`L2.5 Self-Healing Layer`** —— 介于"探测器"和"人工修复"之间，自动闭环 (detect → diff → patch → verify)。

### 2.3 当前系统缺什么（按 DFSQ 框架）

| DFSQ 维度 | 当前 | 治本后 |
|---|---|---|
| **道 (Dao)** 原则 | "SSOT 是真理、SSOT 唯一"——原则已有 | 不变 |
| **法 (Fa)** 方法 | `lint → human patch → commit` | `lint → auto-detect-face → auto-bulk-patch → verify → commit` |
| **术 (Shu)** 技能 | gac-local-gate (单点)、doc-lifecycle audit (单次)、state-freshness (单点) | gac-local-gate + **drift-face-detector** (全路径)、**auto-pruner** (stale runs/dashboards)、**alias-resolver** (跨注册表) |
| **器 (Qi)** 工具 | 现有 489 个 bin scripts | 新增 3-5 个 self-healing 工具（下面 BET 列表）|

**核心缺**: 术层的 **face-wide detection** + 器层的 **auto-patch + verify**。

---

## 3. 治本路径 — 4 个新 BET

### BET 序列设计原则

按"先修根因 → 再修机制 → 最后修现象"递进：

```
治本根因 (R1+R2) → 治机制 (M1+M2+M5) → 治现象 (S1/S2/S3)
```

### BET 1: Self-Healing Drifts Foundation (P0, 2 weeks)

**目标**: 在 L2.5 新增 `drift-face-detector` + `auto-pruner` + cron 触发；建立"信号 → 自动检测 → 自动修复"闭环
**根因对应**: R1 (持续守护缺)
**机制覆盖**: M1 (写后忘) + M5 (ritual 未运营)
**修的现象**: #1, #4, #15-#16, #24, #26
**done_when**:
- `bin/ssot/drift-face-detector.py` 存在且 5 类 drift 全覆盖（dashboard, brief, ephemeral, runs, ritual）
- `bin/ssot/auto-pruner.py` 存在且能自动 prune stale runs / regenerate dashboards / archive ephemeral
- 接入 cron（`.omo/cron/registry.yaml`）每日跑一次 + 周跑一次
- `make drift-face-clean` 一键全跑
**风险**: 自动修改可能破坏声明面；circuit_breaker: 仅 pruner，**不**改 SSOT 文档 / 不改 gitlink
**appetite**: 2 weeks (P0)
**优先级**: P0 (治本)

### BET 2: Face-Wide Frontmatter Coverage (P0, 1 week)

**目标**: 把 #4291 "frontmatter 覆盖率" 从单路径扩展到全路径，**未来同类修复不再需手动扩路径**
**根因对应**: R2 (修复事件式 vs 面式)
**机制覆盖**: M2 (范围漂移)
**修的现象**: #2, #3, #25
**done_when**:
- `bin/ssot/frontmatter-coverage.py --face-wide` 扫 6 个 frontmatter 必填字段（schema/status/lifecycle/owner/last-reviewed/type），覆盖 7 类路径（docs/, .agents/, .omo/_knowledge/retros/, .omo/_knowledge/reports/, .omo/standards/, projects/*/AGENTS.md, projects/*/README.md）
- 输出覆盖率 matrix（path × field）
- 与 #4291 工具组合: 增量自动 patch（仅补缺字段，不动现有值）
- test fixtures 至少 10 个 path × field case
**风险**: 大量 frontmatter 自动 patch 可能改错；circuit_breaker: dry-run 默认，`--apply` 才动文件，且要求 git tracked
**appetite**: 1 week (P0)
**依赖**: 无（独立）

### BET 3: Physical-Logical Mapping Audit (P1, 2 weeks)

**目标**: 系统化保证"逻辑声明 ↔ 物理存在"同步
**根因对应**: R3 (物理-逻辑映射手工)
**机制覆盖**: M3 (物理-逻辑不一致)
**修的现象**: #6, #7, #9, #20
**done_when**:
- `bin/ssot/physical-logical-audit.py` 扫三类映射:
  1. **gitlink**: 主仓 .gitmodules ↔ origin/<sub>/main HEAD（自动 diff + PR）
  2. **launchd**: `.omo/cron/*.plist` ↔ `launchctl list` 实际运行（detect zombie / missing）
  3. **OMO assets**: `.omo/_truth/registry/omo-governance-surfaces.yaml` ↔ 文件系统（detect 真 zombie vs gitignored 运行时面）
- 每个发现给: drift 原因 + 修复路径（自动 PR / 建议 owner 决策）
- 接入 cron 每日跑 + 报告到 panorama health
- 与 `bin/ssot/submodule-reachability-gate.py` 集成（reachability 是其子集）
**风险**: 自动 PR gitlink bump 可能跨仓乱序；circuit_breaker: gitlink bump 限本地不直接 push，需 PR review
**appetite**: 2 weeks (P1)
**依赖**: BET 1 (drift-face-detector 共用 cron 触发)

### BET 4: Multi-Registry Alias Resolver (P1, 1.5 weeks)

**目标**: 解决 governance-checks / L0-constraints / hook-manifest 三套 id 词汇不统一
**根因对应**: R3
**机制覆盖**: M4 (注册表多源无别名)
**修的现象**: #30
**done_when**:
- `bin/gac/registry-alias-map.yaml` 列出三套注册表 id 的等价映射
- `bin/gac/check-rule-wiring-coverage.py` 升级为 `--strict` 模式，使用 alias map 把跨注册表 id 统一
- 49% 零引用降为 ≤ 15%
- 真零引用 vs alias 命名区分
**风险**: alias map 错误会让 gate 误判；circuit_breaker: alias 必须 anchor 到 4 处证据（governance-checks.yaml + L0-constraints.yaml + hook-manifest.yaml + bin executors 实际引用）
**appetite**: 1.5 weeks (P1)
**依赖**: 无

---

## 4. 与已有 bets 的关系

### 重叠 / supersede

- **`BET-Y2Q3-T10-OMLXC-01` (P0 dead-refs) 已 done via #4283** —— 无冲突
- **`DEBT-20260920-RULE-WIRING-DECL-EXEC-GAP`** —— 是 BET 4 的子债，建议 BET 4 完成后 close
- **`OMO-SURFACES-ZOMBIE-ASSETS`** —— 是 BET 3 的子债，建议 BET 3 完成后 close
- **`DEBT-20260921-X2-UNIMPLEMENTED-LEDGER`** —— **不在本批治本范围**（属于实现层，非 drift 治理）

### 优先级对照

| BET | 优先级 | appetite | 总投入 |
|---|---|---|---|
| BET 1 Self-Healing Foundation | P0 | 2 weeks | **2 weeks** |
| BET 2 Face-Wide Frontmatter | P0 | 1 week | 1 week |
| BET 3 Physical-Logical Audit | P1 | 2 weeks | 2 weeks |
| BET 4 Multi-Registry Alias | P1 | 1.5 weeks | 1.5 weeks |
| **合计** | | **6.5 weeks** | **6.5 weeks** |

### 与 FORWARD-PLAN v2 对齐

FORWARD-PLAN v2 (`docs/OMOSTATION-FORWARD-PLAN-v2.md`) 主线已 done。本 BET 集合是 **v3 路线图**：
- v2 主线 (BET 落地) → v3 主题 (系统自维持)
- 6.5 周可完成，是可持续的小周期

---

## 5. 不在本批治本范围

- **CI 修复**: 30 PR 全 MERGED，无 red（健康）
- **Gate 注册**: 86 条已稳定
- **doc-ssot-lint**: 0 冲突
- **P74**: 0 沉默 workflow（已有机制有效）
- **OOM-cells / Resident Agent**: 健康

---

## 6. 实施顺序建议

```
Week 1-2:   BET 1 (Self-Healing Foundation)
Week 2-3:   BET 2 (Face-Wide Frontmatter)  ← 可与 BET 1 后半并行
Week 3-5:   BET 3 (Physical-Logical Audit)  ← 依赖 BET 1
Week 4-5.5: BET 4 (Multi-Registry Alias)    ← 可与 BET 3 并行
```

**最大并行度**: BET 1 + BET 4 可先开；BET 2 等 BET 1 完成接入；BET 3 等 BET 1 cron 触发就绪。

---

## 7. 关键决策点（待 owner 决定）

本报告**不替 owner 决策**，但以下 4 点需 owner 拍板：

1. **SELF-HEALING 自动 PR vs 仅报告**：BET 1 默认 pruner 不推 PR；如果 owner 接受自动开 PR（限定的低风险 drift），可扩大自动面。
2. **face-wide frontmatter 自动 patch**：BET 2 默认 dry-run；自动 patch 是否接受？
3. **OMO 真 zombie 处置策略**：BET 3 找到 zombie 后，default 是 (a) 自动摘除声明 / (b) 建议 owner 决策。
4. **registry alias 权威源**：BET 4 哪个注册表作为权威，其他向其映射？

这 4 点需要在 BET 启动前明确，否则 done_when 会模糊。

---

## 8. 总结

**根本问题**: omostation 是 **passive + manual** 的治理系统 —— 任何"治理动作"都依赖**人记得**或**单次 commit 触发**。这不是执行力问题，是**架构缺一层 L2.5 Self-Healing Layer**。

**治本方案**: 4 个 BET，6.5 周，建立 `drift-face-detector + auto-pruner + face-wide-coverage + physical-logical-audit + alias-resolver` 五件套。

**预期收益**:
- 31 个发现一次性清零（含治本）
- 同类 drift 复发率从"每次都发"降到"季度级"
- omostation 治理从 maturity → sustainability 转型

**回归保障**:
- 所有新工具有 dry-run 默认
- 所有 auto-patch 限本地（不直接 push）
- cron 触发有 circuit_breaker
- 接入 cron 前需 spec 批准（ADR-0203）