# Phase 7 规划分析需求文档

> 类型: 需求分析 (standalone, 不替代现有 phase7-program-plan.md)
> 基线: Phase 6 已完成 (health 90, 85/87 tasks), Phase 7 当前 `in_progress`
> 基于: [Phase 1-6 全面 Review](../_knowledge/management/phase1-6-comprehensive-review.md)
> 现存程序计划: [phase7-program-plan.md](archive/phase7-program-plan.md) (简版, 3 Waves + sequencing)
> 现存任务: `P7-W1-USER-JOURNEY-ENABLEMENT` (execution-ready)

---

## 一、整体视角 — Phase 7 在 OMO 演化中的定位

### 1.1 演化脉络回顾

```
Phase 1:  基础设施补完  ─── "能不能跑"           → health 75
Phase 2:  知识能力深化  ─── "怎么受控地跑"       → health 80
Phase 3:  自我进化闭环  ─── "怎么证明跑完了"     → health 88
Phase 4:  Worker Ops   ─── "多 Worker 协同跑"     → health 90
Phase 5:  治理正式化    ─── "治理即架构"           → health 90
Phase 6:  运行时实现    ─── "治理即运行时"         → health 90
Phase 7:  ████████████ ─── "能力即体验"           → target 94
```

### 1.2 Phase 7 的核心矛盾

**已建 vs 已用**:
- 系统已交付 55+ 模块、6 个架构层级、3 个运行时机制（proposal/checkpoint/skill）
- 但实际用户旅程覆盖率低，D2 adoption 未量化
- 7 个跨阶段缺陷（D1-D7）未被系统性处理

**核心命题**: 把"能力可及"变成"体验连贯"——让已落地的工具、治理、运行时通过真实用户旅程被真正使用，同时清理积压的架构债务。

### 1.3 Phase 7 三大支柱

| 支柱 | 要解决的问题 | 对应 Wave |
|------|-------------|-----------|
| **体验贯通** | 工具已存在但未被端到端使用 | Wave 1: 用户旅程启用 |
| **成本可见** | 使用成本不可见、不可控 | Wave 2: 资源核算 |
| **新鲜度治理** | 知识老化不可感知、不可持续 | Wave 3: 新鲜度熵治理 |

---

## 二、架构维度 — Phase 7 的架构演进

### 2.1 当前架构快照 (Phase 6 终态)

```
                    ┌────────────────────────┐
                    │       控制面 _control/   │
                    │  (驾驶舱 · 状态 · 门禁)   │
                    └──────┬─────────┬───────┘
                           │         │
                    ┌──────▼──┐  ┌──▼──────────┐
                    │ 事实面    │  │  知识面       │
                    │ _truth/  │  │ _knowledge/  │
                    │ (SSOT)   │  │ (设计/过程/     │
                    │          │  │  管理/使用/参考)│
                    └──────┬──┘  └──┬──────────┘
                           │         │
                    ┌──────▼─────────▼──────────┐
                    │       交付面 _delivery/     │
                    │  (运行记录 · 证据 · 产出)   │
                    └────────────────────────────┘

    运行时机制: proposal-governed truth mutation
               checkpoint / lease / watchdog
               blueprint discovery registry
               skill manifest + skill-to-task bridge
```

**架构优势（保持）**:
- 四平面导航壳+SSOT 约束稳定
- Runtime 层已具备持久化、可回退、可审计
- Packet 模式已验证（Phase 5 → 6 连续成功）
- 技能联合机制已就绪

**架构缺口（Phase 7 填）**:
- 用户旅程层缺失（体验面 → 四平面的映射）
- 成本/用量可见性为零
- 知识新鲜度全凭手动
- KOS 存储耦合未解（D1）
- Hermes 调度断链（D6）
- 跨仓库治理不一致（D4）

### 2.2 Phase 7 目标架构

```
                    ┌────────────────────────┐
                    │       体验面 (新增)      │ ← Phase 7 核心新增
                    │  self-context 预载     │
                    │  TaskObject/task bridge│
                    │  共识标记 · 新鲜度报告   │
                    └──────────┬─────────────┘
                               │ 映射到
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
   │  控制面       │   │  事实面       │   │  知识面       │
   │ _control/    │   │ _truth/      │   │ _knowledge/  │
   │ cost/usage   │   │ usage-reg    │   │ freshness    │
   │ 仪表盘       │   │ cost-ledger  │   │ 报告         │
   └──────────────┘   └──────────────┘   └──────────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                        ┌──────▼──────┐
                        │  交付面       │
                        │ _delivery/   │
                        │ run records  │
                        └─────────────┘

    新增机制: self-context preload
              usage/cost registry
              freshness gauge + report
```

### 2.3 架构层级扩展

```
现有 6 层级                          Phase 7 新增
───────                             ───────────
项目级 (kairon/SharedBrain/...)      ─ (不变)
Mesh 级 (Agora)                      ─ (不变)
治理级 (goals/state/tasks/...)       ─ (不变)
运营级 (worker dispatch/reclaim)     ─ (不变)
治理正式级 (四平面)                   ─ (不变)
运行时级 (proposal/checkpoint/skill) ─ (不变)
+ 体验级 (用户旅程/成本可见/新鲜度)    ← Phase 7
```

---

## 三、战略 · 战术 · 执行

### 3.1 战略层 — 为什么做

| 维度 | 战略判断 |
|------|---------|
| **方向** | 从"构建模式"切换到"采用模式" |
| **核心指标** | D2 adoption rate、端到端用户旅程覆盖数、知识新鲜度评分 |
| **约束** | 一次一个 execution-ready Wave；不扩大架构层级，只在现有层级上加体验面 |
| **风险上限** | 如 Wave 1 未产生可验证的采用提升，Phase 7 不继续推进 Wave 2-3 |
| **成功标准** | 至少 1 条完整用户旅程走过 self-context → task → consensus → freshness 全链路 |

### 3.2 战术层 — 做什么

#### Wave 1: 用户旅程启用 (G7.1)

**目标**: 让 Hermes 和 OMO 使用现有工具表面做端到端执行

**已有 scope** (来自 phase7-program-plan.md / starter-packet-spec):
1. self-context preload into Hermes-style flows
2. TaskObject/task bridge for complex work
3. positive-confirmation consensus marking
4. first freshness report and D2 reassessment

**建议追加 scope**:
- D7 orphaned task 处置 (Wave 1 关闭前必须解决或明确容忍)
- Hermes 调度断链评估 (D6): 不修复，但评估断链对用户旅程的影响并记录

#### Wave 2: 资源核算可见 (G7.2)

**目标**: 消除 cost blindness

**已有 scope**:
1. token and cost accounting surfaces
2. usage registry or usage-db truth
3. summary CLI/report entry points

**建议追加 scope**:
- **D1 评估**: 检查 KOS 存储耦合对用量核算的影响范围
- **D3 处理**: eu-pricing 独立测试作为 Wave 2 的依赖任务

#### Wave 3: 新鲜度熵治理 (G7.3)

**目标**: 知识老化可测量、可持久化

**已有 scope**:
1. structured freshness output
2. writing reports into governed knowledge truth
3. D6 refresh scoring update

**建议追加 scope**:
- **D4 处理**: 跨仓库治理同步 — 至少对齐关键仓库的 AGENTS.md
- **D5 状态更新**: Apple/WeChat connector 阻塞状态复议

### 3.3 执行层 — 怎么做

#### Wave 1 执行路径

```
P7-W1-USER-JOURNEY-ENABLEMENT (已存在, execution-ready)
    │
    ├── Lane A: Self-context preload
    │   ├── 实现 Hermes-style context 预载接口
    │   └── 验证: 至少 1 条真实交互路径走通
    │
    ├── Lane B: TaskObject bridge
    │   ├── 实现复杂请求→TaskObject→task YAML 的桥接
    │   └── 验证: 桥接路径产生有效的 .omo/tasks/active/ 条目
    │
    ├── Lane C: Consensus marking
    │   ├── 实现 positive-confirmation → evidence 的写入
    │   └── 验证: consensus 记录出现在 _delivery/evidence/
    │
    ├── Lane D: Freshness report (first pass)
    │   ├── 产出第一份知识新鲜度报告
    │   └── 验证: 报告可读、可引用
    │
    └── Lane E: Debt cleanup (建议追加)
        ├── D7: orphaned task 处置
        └── D6: 断链影响评估记录
```

#### Packet 链

```
Phase 7 Program Map (phase7-program-plan.md, 已存在)
    → 已批准: phase7-planning-gate.md (已存在)
    │
    → execution-ready: phase7-starter-packet-spec.md (已存在)
        → P7-W1-USER-JOURNEY-ENABLEMENT (active/ 中)
    │
    → gated: Wave 2 Execution Plan (待创建)
        → 建议包含 D1 评估 + D3 处理
    │
    → gated: Wave 3 Execution Plan (待创建)
        → 建议包含 D4 处理 + D5 复议
```

---

## 四、核心方案 — 必须做的事

### 4.1 必须修复的缺陷 (P0/P1)

| 缺陷 | 优先级 | 方案 | 关系 Wave |
|------|:------:|------|:---------:|
| **D2**: E2E 测试需运行中服务 | P0 | 在 Wave 1 中增加 CI 测试环境搭建子任务；优先容器化 Agora + SharedBrain | Wave 1 |
| **D1**: KOS 存储耦合 | P0 | 在 Wave 1 完成影响评估，Wave 2 实施存储抽象层 | Wave 1 (评估) → Wave 2 (实施) |
| **D7**: Orphaned task | P0 | Wave 1 关闭前必须处置（resolve 或 正式容忍） | Wave 1 |
| **D6**: Hermes 179 断链 | P1 | Wave 1 评估影响，Wave 2 按 Direction A 收敛 | Wave 1 (评估) → Wave 2 (实施) |
| **D4**: 跨仓库治理同步 | P1 | Wave 3 对齐关键仓库 AGENTS.md | Wave 3 |
| **D3**: eu-pricing 无独立测试 | P2 | Wave 2 添加 | Wave 2 |
| **D5**: Blocked connector | P2 | Wave 3 复议外部阻塞状态 | Wave 3 |

### 4.2 必须交付的能力

| 能力 | 交付标准 | Wave |
|------|---------|:----:|
| Self-context preload | Hermes 第一条交互路径走通 | W1 |
| Task bridge | 复杂请求 → 合法 task YAML | W1 |
| Consensus marking | evidence 可追踪、可审计 | W1 |
| Freshness report | 可读、可引用、可治理 | W1 |
| Cost accounting | token/cost 可见 (CLI + report) | W2 |
| Usage registry | 用量 SSOT | W2 |
| Freshness automation | 周期性刷新、报告写入 knowledge | W3 |

### 4.3 建议保持的模式

参考 [Phase 1-6 Review](../_knowledge/management/phase1-6-comprehensive-review.md):
1. 先验证再推进
2. 渐进式交付
3. Packet 模式
4. 四平面写入约束
5. 跨阶段验收
6. SSOT 不漂移

---

## 五、交叉分析 (Cross Analysis)

### 5.1 与 Phase 1-6 Review 的交叉引用

| Review 发现 | Phase 7 应对 | 状态 |
|------------|-------------|:----:|
| 健康 90 → 目标 94 | 每个 Wave 关闭后重新评估健康分 | 跟踪 |
| KOS 存储耦合 (D1) | Wave 1 评估 → Wave 2 实施 | 规划中 |
| CI 测试环境 (D2) | Wave 1 子任务：容器化集群 | 规划中 |
| eu-pricing 测试 (D3) | Wave 2 新增测试目录 | 规划中 |
| 跨仓库同步 (D4) | Wave 3 对齐 | 规划中 |
| Connector blocked (D5) | Wave 3 复议 | 规划中 |
| Hermes 断链 (D6) | Wave 1 评估 → Wave 2 修复 | 规划中 |
| Orphaned task (D7) | Wave 1 关闭前处置 | 必做 |
| "不要急于 Phase 7" | 已有足够基础 (Phase 6 85/87) BUT 需在 W1 清理 D7 | 已采纳 |

### 5.2 与 Hermes 收敛策略的交叉引用

参考 [_knowledge/design/hermes-convergence-strategy.md](_knowledge/design/hermes-convergence-strategy.md)

| Hermes 收敛策略 (Direction A) | Phase 7 对应 | 优先级 |
|-----------------------------|-------------|:------:|
| Priority 0: 修复 179 断链 | Wave 1 评估断链影响 → Wave 2 修复 | P1 |
| Priority 1: 收敛调度到 cron-service | Wave 2-3 范围 | P1 |
| Priority 2: 长期计划 | Phase 7 结束后评估 | P2 |

### 5.3 与四平面架构的交叉引用

| 平面 | Wave 1 影响 | Wave 2 影响 | Wave 3 影响 |
|------|:----------:|:----------:|:----------:|
| `_control/` | 新增 cost/usage 仪表盘入口 | 仪表盘数据化 | 新鲜度评分入仪表盘 |
| `_truth/` | task bridge 写 task YAML | usage-registry SSOT | freshness SSOT |
| `_knowledge/` | freshness report 入 management | — | 自动刷新报告 |
| `_delivery/` | consensus evidence 写入 | cost evidence | freshness evidence |

### 5.4 与 Phase ∞ 愿景的交叉引用

参考 [beyond-phase4-vision.md](beyond-phase4-vision.md)

| Phase ∞ 门槛 | Phase 7 贡献 | 差距 |
|-------------|-------------|:----:|
| KOS 推荐准确率 >= 90% | D1 解耦推进 | 当前 KOS 仍耦合 gbrain SQLite |
| 自愈成功率 >= 95% | checkpoint/watchdog 已就绪 | 无需额外工作 |
| 辅助研究质量 >= 85% | Hermes 用户旅程推进 | Wave 1 可提供测试数据 |
| HITL 超时机制 | proposal governance 已就绪 | 无需额外工作 |
| 级联保护 | skill federation 已就绪 | 无需额外工作 |
| RBAC 执行 | 现有 Agent Registry (Ed25519) | 无需额外工作 |

---

## 六、红队分析 (Red Team Analysis)

### R1: "用户旅程是假的"

**攻击描述**: Wave 1 的"走通一条用户旅程"可能变成人工编排的演示，而不是真实的自发使用。self-context preload 如果没有真实用户触发，就只是一个框架验证。

**严重性**: 🟠 Major

**缓解方案**:
1. Wave 1 验收条件必须包含**至少一条不需要人工编排的自动化路径**
2. self-context preload 必须在 Hermes 或 CLI 的真实触发场景下验证
3. 旅程证据必须包含 `_delivery/evidence/` 中的 non-trivial 运行记录

### R2: "成本可见 ≠ 成本控制"

**攻击描述**: Wave 2 做的 usage registry 和 cost accounting 可能只是多了一张仪表盘，而没有实际的成本控制机制（如预算阈值、自动降级）。系统可能陷入"看到问题但无法处理"的状态。

**严重性**: 🟠 Major

**缓解方案**:
1. Wave 2 必须包含至少一个**成本控制网关**（如：超过预算阈值时自动阻止 dispatch）
2. cost/usage 数据必须写入 `_truth/` 的可治理 SSOT，而非只存在于仪表盘

### R3: "新鲜度治理变成噪声"

**攻击描述**: Wave 3 的新鲜度熵治理可能生成大量低价值报告，导致用户忽略真正重要的老化信号（Goodhart's Law：被测量的东西会被游戏化）

**严重性**: 🟡 Minor

**缓解方案**:
1. 新鲜度报告必须分级（critical / warning / info），只有 critical 才进入控制面
2. 报告必须可操作（含具体的 refresh action），否则只是噪声

### R4: "债务清理被 Wave 1 的体验工作挤掉"

**攻击描述**: D7 (orphaned task)、D6 (Hermes 断链) 这些债务清理任务是"不讨好的工作"，在追赶 Wave 1 的用户旅程交付时最容易被牺牲。结果 Phase 7 结束时 D1-D7 仍在。

**严重性**: 🔴 Critical

**缓解方案**:
1. **Wave 1 关闭条件必须包含 D7 处置** — 不允许在 D7 unresolved 的情况下推进 Wave 2
2. D6 评估必须是 Wave 1 的可交付物（即使在 Wave 2 才修复）
3. 每个 Wave 关闭复盘必须检查 D1-D7 状态并记录变化

### R5: "Hermes 收敛永远被延期"

**攻击描述**: Direction A 的 Hermes 调度收敛从 Phase 5 就开始规划，Phase 6 没做，Phase 7 如果没有强制执行还会再延。179 条断链如果持续存在，最终会成为真实故障的根因。

**严重性**: 🟠 Major

**缓解方案**:
1. Wave 1 必须完成断链影响评估（写评估报告）
2. Wave 2 必须包含断链修复（这是 Phase 7 中修复 D6 的最后机会）
3. 如 Wave 2 也不做 → 升级为 Critical，强制在 Phase 7 关闭前完成

### 红队修订总结

| # | 发现 | 严重性 | 修订措施 |
|---|------|:-----:|---------|
| R1 | 用户旅程可能是假演示 | 🟠 | 验收条件增加"无人工编排的自动化路径"要求 |
| R2 | 成本可见不等于成本控制 | 🟠 | Wave 2 增加成本控制网关 |
| R3 | 新鲜度治理变噪声 | 🟡 | 分级报告 + 可操作 refresh action |
| R4 | 债务清理被挤出 | 🔴 | Wave 1 关闭强制包含 D7 处置 |
| R5 | Hermes 收敛被延期 | 🟠 | Wave 1 评估 + Wave 2 修复硬约束 |

---

## 七、Wave 详细结构（建议）

### Wave 1 — 用户旅程启用 (G7.1)

**状态**: execution-ready (已有 `P7-W1-USER-JOURNEY-ENABLEMENT`)

**目标**: 让 Hermes 和 OMO 使用现有工具表面端到端执行至少 1 条用户旅程

**执行 Lane**:
- Lane A: Self-context preload
- Lane B: TaskObject bridge
- Lane C: Consensus marking
- Lane D: Freshness report (first pass)
- Lane E: Debt cleanup — D7 处置 + D6 评估

**建议 Exit Criteria**:
1. 至少 1 条用户旅程走通 self-context → task → consensus → freshness 全链路
2. D7 orphaned task resolved 或 正式容忍声明写入 `_truth/`
3. D6 断链影响评估报告完成
4. `python3 -m pytest .omo/tests -q` 通过
5. `python3 scripts/sync_omo_state.py --omo-dir .omo` 无 divergence 异常（除已容忍的）

**Verification**:
1. `python3 scripts/omo_worker.py task validate --all-active`
2. `python3 scripts/sync_omo_state.py --omo-dir .omo`
3. `python3 -m pytest .omo/tests -q`

---

### Wave 2 — 资源核算可见 (G7.2)（建议）

**状态**: gated (等待 Wave 1 GO)

**目标**: 消除 cost blindness + 推进 D1/D6/D3

**建议 Scope**:
1. token and cost accounting surfaces
2. usage registry or usage-db truth
3. summary CLI/report entry points
4. **D1**: KOS 存储抽象层实施 (P0)
5. **D6**: Hermes 调度断链修复 (P1)
6. **D3**: eu-pricing 独立测试目录 (P2)

**Gate to Enter**:
1. Wave 1 关闭且 GO
2. D1 评估报告可用
3. D6 评估报告可用

**建议 Exit Criteria**:
1. cost/usage SSOT 可查询
2. CLI `omo cost summary` 可用
3. KOS 存储抽象接口定义完成 + 至少一种适配器实现验证
4. Hermes 调度断链修复且验证通过
5. eu-pricing 测试通过 >= 80%
6. 全量单元测试无回归

---

### Wave 3 — 新鲜度熵治理 (G7.3)（建议）

**状态**: gated (等待 Wave 2 GO)

**目标**: 知识老化可测量、可持久化 + 治理对齐

**建议 Scope**:
1. structured freshness output
2. writing reports into governed knowledge truth
3. D6 refresh scoring update
4. **D4**: 跨仓库治理同步 (P1) — 至少对齐 10 个关键仓库
5. **D5**: Blocked connector 状态复议 (P2)

**Gate to Enter**:
1. Wave 2 关闭且 GO
2. cost/usage 基础设施稳定运行至少 1 个周期

**建议 Exit Criteria**:
1. 新鲜度报告自动生成并写入 `_knowledge/management/`
2. 关键仓库 AGENTS.md/CI 配置统一
3. D5 connector 阻塞状态更新记录
4. 健康评分 >= 92

---

## 八、Program-Level Go/No-Go 规则（建议）

### Go (允许推进)

1. 一次只有一个 execution-ready packet
2. 只有 G7.1 可以在 `tasks/active/` 中作为 Phase 7 起始点
3. 每个 Wave 必须通过 verification + retrospective + explicit GO/NO-GO 后才能关闭
4. Wave 1 关闭前必须处置 D7 (resolve 或 正式容忍)
5. 每个 Wave 关闭时更新 D1-D7 状态矩阵

### No-Go (禁止做的事)

1. 不要在 Wave 1 unresolved 时引入 G7.2 或 G7.3
2. 不要让用量/成本数据只存在于仪表盘而不写入 SSOT
3. 不要让新鲜度报告变成无操作的噪声（必须分级 + 可操作）
4. 不要让 Hermes 收敛继续被延期（Wave 2 必须修复 D6）
5. 不要让 D7 orphaned task 无处置地进入 Wave 2

---

## 九、验证基线（建议）

```bash
# 每个 Wave 关闭前必须通过
python3 scripts/omo_worker.py task validate --all-active
python3 scripts/sync_omo_state.py --omo-dir .omo
python3 -m pytest .omo/tests -q

# Wave 1 追加验证
python3 scripts/check_user_journey.py  # 用户旅程验证脚本 (待创建)

# Wave 2 追加验证
python3 scripts/omo cost summary --verify  # 成本核算验证

# Wave 3 追加验证
python3 scripts/omo freshness report --verify  # 新鲜度报告验证
```

---

## 十、文档关系

```
现有 Phase 7 文档 (不变)
├── phase7-planning-gate.md         ← 入口门禁 (已批准)
├── phase7-program-plan.md          ← 程序地图 (简版, 3 Waves + sequencing)
├── phase7-starter-packet-spec.md   ← Wave 1 规范 (已有)
├── P7-W1-USER-JOURNEY-ENABLEMENT   ← 执行中任务 (已有)

本需求分析文档
└── phase7-planning-analysis-requirements.md  ← 独立分析, 不替代以上文件

待创建 (建议)
├── phase7-wave2-execution-plan.md  ← Wave 2 执行计划
├── phase7-wave3-execution-plan.md  ← Wave 3 执行计划
├── phase7-redteam-findings.md      ← 红队发现独立文件 (可选)
├── phase7-cross-analysis.md        ← 交叉分析独立文件 (可选)
```

---

## 附录: D1-D7 状态追踪矩阵

| 缺陷 | Phase 7 前 | Wave 1 后 | Wave 2 后 | Wave 3 后 |
|------|:----------:|:---------:|:---------:|:---------:|
| D1: KOS 存储耦合 | 未修复 | 评估完成 | 抽象层实施 | 稳定运行 |
| D2: CI 测试环境 | 未解决 | 容器化启动 | 可用 | 稳定运行 |
| D3: eu-pricing 测试 | 无独立测试 | — | 测试通过 | 回归通过 |
| D4: 跨仓库同步 | 43 仓库未对齐 | — | — | 10+ 仓库对齐 |
| D5: Connector blocked | 外部阻塞 | — | — | 状态复议 |
| D6: Hermes 断链 | 179 条 | 评估报告 | 修复完成 | 验证通过 |
| D7: Orphaned task | 1 个 | 已处置 | 无复发 | 无复发 |
