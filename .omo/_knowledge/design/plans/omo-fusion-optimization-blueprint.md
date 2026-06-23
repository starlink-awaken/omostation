---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 历史设计/历史/评审/图表批量归档, 当前活跃设计以 design/INDEX.md + PANORAMA.md 为准"
---
# OMO fusion optimization blueprint

> 日期: 2026-05-31
> 范围: `.omo` 四平面机制的进一步融合升级
> 基线: Phase 3 completed / acceptance green / four-plane indexes already landed

## Goal

让 `.omo` 从“已经融合的文档治理层”继续升级为**可持续演进的治理操作系统**：

1. **战略上**：把四平面从静态导航，升级成长期稳定的治理 operating model。
2. **战术上**：让 control / truth / knowledge / delivery 四平面的职责、写入边界、验证方式更清晰。
3. **执行上**：把计划、任务、dispatch、验证、复盘串成固定闭环，避免 Phase 1-3 那种“做完了但要靠人工重新解释”的成本。

---

## Strategic upgrades

### 1. 从“文档分层”升级到“治理分层”

四平面的真正价值不是目录更整齐，而是把 `.omo` 的治理动作分成四种稳定语义：

- `_control`：定义方向、阶段状态、门禁、go/no-go。
- `_truth`：维护唯一真相源，承载任务、标准、注册表、状态机引用。
- `_knowledge`：沉淀可复用认知，把计划、复盘、审计、指南变成组织记忆。
- `_delivery`：沉淀可重放证据，让运行记录、测试、验收报告进入可验证链路。

这意味着未来 `.omo` 的演进不应再围绕“再加一个目录”，而应围绕“新增内容属于哪一个平面、写回哪个底层 SSOT、如何被验证”。

### 2. 从“阶段项目”升级到“持续经营”

Phase 1-3 已完成，但它们的产出不能停留在历史成果；应转成持续经营机制：

- **Phase 1** 贡献基础设施与测试纪律。
- **Phase 2** 贡献 provider plane、route seam、治理门禁。
- **Phase 3** 贡献统一 LLM contract、capability slice、acceptance baseline。

下一步不是重开旧 phase，而是让这些成果成为 `.omo` 的**默认运行方式**。

### 3. 从“人工理解”升级到“机器可验证”

四平面要长期稳定，核心不是写更多文档，而是让关键约束进入自动验证：

- 入口文档必须持续指向真实 SSOT。
- 关键验收命令必须可执行、可复用。
- Phase 复盘必须能回指证据，而不是仅有结论。

---

## Tactical operating model

### Control / Truth / Knowledge / Delivery 的战术边界

| 平面 | 只做什么 | 不做什么 | 主要写入点 |
| --- | --- | --- | --- |
| `_control` | 聚合阶段状态、目标、门禁、决策快照 | 不直接承载任务明细和运行证据 | `goals/current.yaml`, `state/system.yaml` |
| `_truth` | 维护任务/标准/注册表等 SSOT | 不复制总结性叙述 | `tasks/`, `standards/`, `workers/registry.yaml` |
| `_knowledge` | 归档计划、复盘、审计、指南、参考 | 不存放事实副本或运行日志 | `plans/`, `summaries/`, `audits/`, `_archive/ONBOARDING.md` |
| `_delivery` | 编目测试、运行记录、验收证据 | 不改写战略状态 | `workers/runs/`, `tests/`, `evidence/`, acceptance reports |

### 推荐的战术动作

1. **每次新增 `.omo` 文档先判平面，再落底层位置**：先判断语义归属，再决定写到哪个真实目录。
2. **每次重大交付都要有 delivery + process 双记录**：一份是证据，一份是复盘。
3. **控制面只保留当前态，不做历史堆积**：历史进入 knowledge/process 或 archive。
4. **事实面优先字段化**：能进 YAML / registry / schema 的，不写成自由文本。

---

## Execution loop

建议把 `.omo` 的执行闭环固定为下面 7 步：

1. **Control**：目标或阶段门禁更新到 `goals/` / `state/`
2. **Truth**：任务进入 `tasks/active/`，补齐 dispatch / evidence / review 引用
3. **Delivery**：执行时写 `workers/runs/`、测试结果、验收报告
4. **Knowledge**：产出 plan / retro / audit / usage 更新
5. **Validation**：跑 `.omo/tests/` + 关键 acceptance 命令
6. **Control refresh**：回写 `state/system.yaml`、go/no-go、完成态
7. **Retrospective**：把阶段经验写入 knowledge/process，反哺下一轮

这套 loop 的关键不是“每步都做很多”，而是**每一步都只改它该改的平面**。

---

## Verification model

这套升级后的机制建议固定三层验证：

### 1. 文档结构验证

- `.omo/tests/test_worker_mechanism_consistency.py`
- `.omo/tests/test_omo_automation.py`
- `.omo/tests/test_fusion_optimization_docs.py`

### 2. 机制级验收

- `python3 scripts/phase3_acceptance.py --write-report`
- `.omo/summaries/phase3-acceptance-report.md`

### 3. 回写一致性

- `INDEX.md` / plane indexes / `DOC-ARCH.md` 必须能回指当前真实状态
- 新 retro / plan 必须能回指对应 evidence / task / acceptance report

---

## Immediate execution priorities

1. **把四平面作为默认入口固定下来**，以后不再并行引入新的顶层“半治理入口”。
2. **继续提升自动验证覆盖**，优先检查 plane indexes、当前 phase 快照、关键命令引用。
3. **把 Phase 1-3 的成果转成 Phase 4 operating baseline**，而不是仅保留为历史说明。

---

## Success criteria

- 四平面入口继续与真实 SSOT 保持一致。
- 新增蓝图和总复盘进入 design / process 索引。
- `.omo` 相关测试继续通过。
- 后续新增治理文档时，不再出现“新目录/新文档与现有机制脱节”的漂移。
