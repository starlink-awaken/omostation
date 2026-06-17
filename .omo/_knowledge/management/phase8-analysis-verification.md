# Phase 8 分析与验证报告

> 类型: 阶段分析与验证
> 基线: Phase 8 已完成 (health 90, 93/95 tasks, phase_status: completed)
> 验证日期: 2026-05-31
> 前置文档: [Phase 1-6 全面 Review](phase1-6-comprehensive-review.md), [Phase 7 规划分析需求](../plans/phase7-planning-analysis-requirements.md)
> 历史阶段分析与验证 / reference only。本文记录 Phase 8 收口时的完成度、健康分和验证判断，不是当前任务状态、当前健康分或当前治理结论 SSOT。
> 当前事实请回看 `/.omo/state/system.yaml`、`/.omo/goals/current.yaml`、`/.omo/debt/` 与当前交付/审计证据。

---

## 一、Phase 8 概览

### 1.1 主题定位

```
Phase 7:  "能力即体验"  ─── 把可见性建出来
Phase 8:  "体验即控制"  ─── 把可见性变成控制闸门
```

### 1.2 Waves 结构

| Wave | 代号 | 主题 | 状态 | 核心产出 |
|:----:|------|------|:----:|---------|
| W0 | 规划闸门 | 确定 control-first 计划 | ✅ 已核定 | 只播种 Wave 1 |
| **W1** | **预算+新鲜度控制面** | 将 P7 的可见性升级为执行前控制闸门 | ✅ **GO** | `omo_experience.py` 控制闸门、`control/current.yaml`、allow/degrade/review/block |
| **W2** | **Hermes+存储收敛** | 移除 `.omo` 硬编码、Hermes 桥默认 wrapper-only | ✅ **GO** | 可配置 OMO 根、sync 派生引用不硬编码、wrapper-first 安装 |
| **W3** | **跨仓库治理** | 记录 repo 内治理边界 + blocked-surface 核定标准 | ✅ **GO** | `operation-levels.md`、Apple/WeChat/Family OS blocked 标准 |

### 1.3 关键数据

| 指标 | 值 |
|------|:---:|
| 完成任务 | 93 / 95 (97.9%) |
| 阻塞任务 | 2 |
| 活跃任务 | 0 |
| 健康分 | **90.0** |
| 漂移标记 | 0 |
| 最后一次 GO/NO-GO | Phase 8 GO |
| 下一个里程碑 | Phase 9 planning gate |

---

## 二、任务完成验证

### 2.1 任务完成度

```
total_tasks:    95
completed:      93  ████████████████████████████████ 97.9%
blocked:         2  ██                                2.1%
active:          0

完成率 97.9%，高于 Phase 6 的 85/87 (97.7%)。2 个 blocked tasks 是遗留项。
```

### 2.2 完成率趋势对比

| Phase | 完成率 | 状态 |
|:----:|:------:|:----:|
| Phase 5 | ~95% | 已完成 |
| Phase 6 | 87.4% (85/87) | 已完成 |
| Phase 7 | ~90% (未精确记录) | 已完成 |
| Phase 8 | **97.9% (93/95)** | **已完成** |

**Phase 8 是完成率最高的阶段之一**，仅 2 个任务被阻塞未被绕开。

---

## 三、各 Wave 交付验证

### 3.1 Wave 1 — 预算 + 新鲜度控制面

**声明的交付物**:
1. `scripts/omo_experience.py` — 执行前控制闸门评估
2. `_delivery/task-center/control/current.yaml` — 控制决策持久化
3. 受控路由返回 `allow / degrade / review / block`

**验证**:

| 验证项 | 证据 | 状态 |
|--------|------|:----:|
| 控制闸门脚本存在 | `scripts/omo_experience.py` | ✅ |
| 控制决策持久化 | `_delivery/task-center/control/current.yaml` (decision: degrade) | ✅ |
| 控制面输出可用 | `decision: degrade`, `reasons: [freshness_warning]` | ✅ |
| 预算限制生效 | `budget_limit_usd: 2.5`, `total_cost_usd: 0.0334` | ✅ |
| 新鲜度评分 | `freshness_score: 70`, `stale_items: [state_update_stale]` | ✅ |
| 测试验证 | `test_omo_experience.py -k control_gate` | ✅ |

**结论**: ✅ **交付完成。** Phase 7 的可见性循环已升级为 Phase 8 的执行前控制闸门。不再是事后观察，而是执行前决策。

### 3.2 Wave 2 — Hermes + 存储收敛

**声明的交付物**:
1. `omo_worker.py` 支持可配置 OMO 存储根
2. `sync_omo_state.py` 从实际存储根派生引用
3. `install-all-bridges.sh` 默认 wrapper-only

**验证**:

| 验证项 | 证据 | 状态 |
|--------|------|:----:|
| 可配置存储根 | `omo_worker.py` 支持 `--omo-dir` 参数 | ✅ |
| 派生引用不硬编码 | `sync_omo_state.py` 使用实际根 | ✅ |
| 桥安装 wrapper-only | `install-all-bridges.sh` 默认无 legacy 安装器 | ✅ |
| legacy 为 opt-in | `--legacy-installers` 参数存在 | ✅ |
| 测试验证 | `test_omo_automation.py -k 'custom_omo_root or wrapper_only or legacy_installers'` | ✅ |

**结论**: ✅ **交付完成。** Hermes 安装已从"默认 legacy"切换为"默认 wrapper-only"，这是一个正确的长期收敛方向。

### 3.3 Wave 3 — 跨仓库治理

**声明的交付物**:
1. 核定 repo 内治理语言
2. `operation-levels.md` 记录 blocked-surface 核定标准
3. Apple / WeChat / Family OS 保持 blocked

**验证**:

| 验证项 | 证据 | 状态 |
|--------|------|:----:|
| 治理语言已核定 | `standards/operation-levels.md` | ✅ |
| blocked-surface 标准 | 明确 Apple/WeChat/Family OS 需满足 cross-repo governance sync 后才能解锁 | ✅ |
| 未来扩张边界 | 当前 repo 可治理，外部仓库需未来闸门 | ✅ |

**结论**: ✅ **交付完成。** Phase 8 不仅有了控制运行时，还明确了控制运行时如何（以及何时）扩展到其他仓库。

---

## 四、运行时证据验证

### 4.1 控制面证据

**文件**: `_delivery/task-center/control/current.yaml`

```yaml
generated_at: '2026-05-31T18:13:00Z'
decision: degrade                    # ← 实际决策: 降级
reasons:
- freshness_warning                  # ← 触发原因: 新鲜度警告
budget_limit_usd: 2.5               # ← 预算限制
total_cost_usd: 0.0334              # ← 当前成本
freshness_score: 70                 # ← 新鲜度评分
stale_items:
- state_update_stale                # ← 已识别的老化项
```

**解读**: 系统在执行前做出了 `degrade` 决策，原因是新鲜度警告。这是一个**真实的控制行为**——不是被动记录，而是主动决策。预算 $2.5/$0.0334 表示当前用量远低于阈值，但新鲜度 70 分触发了降级。

### 4.2 新鲜度证据

**文件**: `_delivery/task-center/freshness/current.yaml`

```yaml
freshness_score: 70
stale_items:
- state_update_stale
recommended_actions:
- refresh state summary
- resolve or tolerate divergence
```

**解读**: 新鲜度 70 是一个中等偏低的评分。建议的 action 是具体可操作的——这是 Phase 7 需求分析中 R3 红队所要求的"可操作报告"。

### 4.3 用量核算证据

**文件**: `_truth/task-center/usage-accounting.yaml`

```yaml
task_counts:
  active: 1
  blocked: 2
  completed: 90
dispatches:
  total: 9
  workers:
    codebuddy: 5
    reasonix: 4
cost_by_org:
- org: starlink-core
  calls: 2
  cost: 0.0334
  tokens: 800
```

**解读**: 用量数据是真实的，但粒度较粗（仅 1 个 org，9 次 dispatch）。成本可见性按 org 聚合的机制存在，但覆盖面窄。

---

## 五、架构演进分析

### 5.1 架构层级扩展

```
Phase 1-6:  项目级 → Mesh 级 → 治理级 → 运营级 → 正式治理级 → 运行时级
Phase 7:    + 体验级 (用户旅程/成本可见/新鲜度)
Phase 8:    + 控制闸门级 (执行前决策 allow/degrade/review/block)
```

### 5.2 Phase 8 架构快照

```
                    ┌─────────────────────────────┐
                    │        控制闸门级 (新增)       │ ← Phase 8 核心
                    │  omo_experience.py 评估决策   │
                    │  control/current.yaml 持久化  │
                    │  allow / degrade / review / block
                    └──────────┬──────────────────┘
                               │ 执行前判断
                    ┌──────────▼──────────────────┐
                    │        体验面 (Phase 7)       │
                    │  self-context · task bridge  │
                    │  共识标记 · 新鲜度报告         │
                    └──────────┬──────────────────┘
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
```

### 5.3 架构验证结论

| 维度 | 评估 | 状态 |
|------|------|:----:|
| 架构一致性 | 控制闸门级没有增加新的平面，只是体验面之上的一层决策机制 | ✅ |
| 四平面约束 | 所有数据仍然写入对应的平面（control→交付面、usage→事实面）| ✅ |
| SSOT 不漂移 | `usage-accounting.yaml` 作为唯一真实来源 | ✅ |
| Packet 模式 | W2/W3 仅在 W1 closeout GO 后才解锁 | ✅ |

---

## 六、D1-D7 在 Phase 8 中的处理情况

Phase 7 需求分析中识别了 7 个跨阶段缺陷。Phase 8 对这些缺陷的实际处理：

| 缺陷 | Phase 7 要求 | Phase 8 实际处理 | 状态 |
|:----:|-------------|-----------------|:----:|
| **D1**: KOS 存储耦合 | W1 评估 → W2 实施存储抽象 | **W2 实现了更通用的方案**: 可配置 OMO 根，移除 `.omo` 硬编码，比存储抽象层更轻量 | ⬤ 间接解决 |
| **D2**: CI 测试环境 | W1 容器化集群 | **未见处理** — CI 测试环境问题仍在 | ✗ 未解决 |
| **D3**: eu-pricing 测试 | W2 新增测试目录 | **未见处理** — eu-pricing 独立测试未覆盖 | ✗ 未解决 |
| **D4**: 跨仓库同步 | W3 对齐 10+ 仓库 | **W3 做了** — 记录了 repo 内治理姿态，但**未强制执行外部仓库**。标准有了，执行未做 | ⬤ 部分解决 |
| **D5**: Connector blocked | W3 复议状态 | **W3 做了** — Apple/WeChat/Family OS 保持 blocked，有核定标准 | ✅ 已处理 |
| **D6**: Hermes 179 断链 | W1 评估 → W2 修复 | **W2 做了关键收敛**: wrapper-first 安装、删除 `.omo` 硬编码，但**未完全消除 179 条断链** | ⬤ 部分解决 |
| **D7**: Orphaned task | W1 关闭前强制处置 | **未见明确提及** — system.yaml 中无相关记录，2 个 blocked tasks 可能包含它 | ? 不确定 |

### D1-D7 总体处理评估

```
D5  ✅ 已处理   (connector 阻塞状态已记录)
D1  ⬤ 间接解决   (通过可配置根而非存储抽象层)
D6  ⬤ 部分解决   (wrapper-first 方向正确，但 179 条未全清)
D4  ⬤ 部分解决   (治理标准已定义，但未强制执行)
D2  ✗ 未解决     (CI 测试环境)
D3  ✗ 未解决     (eu-pricing 测试)
D7  ? 不确定     (orphaned task 状态不明)

已处理/部分解决: 4/7 (57%)
明确未解决:     2/7 (29%)
不确定:         1/7 (14%)
```

---

## 七、健康分分析

### 7.1 健康分 90 意味着什么

Phase 8 结束时 health_score = 90.0，与 Phase 5、6、7 相同。

```
Phase 1: 75  →  P2: 80  →  P3: 88  →  P4: 91  →  P5: 90  →  P6: 90  →  P7: 90  →  P8: 90
```

**健康分从 Phase 5 开始停滞在 90 未变。**

### 7.2 停滞原因分析

| 原因 | 说明 |
|------|------|
| **D2/D3 未解决** | CI 测试环境和 eu-pricing 测试未被修复，影响测试基础设施维度得分 |
| **D6 仅部分解决** | Hermes 179 断链未完全消除 |
| **cross-repo rollout 未执行** | 治理标准已定义但未落地到其他仓库 |
| **2 个 blocked tasks** | 阻止了 100% 完成率 |
| **健康评分体系可能饱和** | 90 分可能已经是当前的系统上限——现有指标可能无法区分 90 和 94 的差异 |

### 7.3 建议

- **健康评分指标需要重新校准**: 如果 Phase 5→8 的四个阶段都无法突破 90，说明现有的评分体系可能已经达到天花板
- **增加采用率指标**: 当前的健康评分可能只反映"构建质量"而非"采用质量"
- **D2 和 D3 是突破 90 的关键瓶颈**: CI 测试环境和测试覆盖是最明显的未解决问题

---

## 八、遗留风险

### 8.1 已记录的风险（来自复盘文档）

1. **Cross-repo rollout 仍是未来闸门** — 当前 repo 定义了治理姿态，但未强制执行其他仓库
2. **Hermes 收敛是 follow-on work** — wrapper-first 模式正确但更广泛的生态清理未做
3. **Apple / WeChat / Family OS 仍 blocked** — 需独立 planning gate 才能解锁

### 8.2 新识别的风险

4. **健康分 90 停滞风险** — 4 个阶段健康分不变，可能掩盖了实际问题，或评分体系已失效
5. **D2/D3 持续未解决风险** — 这两个缺陷从 Phase 5 就在，经过 Phase 6/7/8 仍未处理
6. **控制闸门覆盖范围窄** — 当前只有 cost 和 freshness 两个维度，覆盖面有限
7. **运行数据量太小** — 仅 9 次 dispatch、1 个 org，不足以验证控制闸门的真实有效性

### 8.3 风险优先级

| 风险 | 严重性 | 建议处理阶段 |
|:----:|:-----:|:-----------:|
| 健康分 90 停滞 | 🟠 高 | Phase 9 前置 |
| D2/D3 持续未解决 | 🟠 高 | Phase 9 |
| Cross-repo rollout 未执行 | 🟡 中 | Phase 9 |
| Hermes 收敛未完成 | 🟡 中 | Phase 9 |
| 控制闸门覆盖窄 | 🟢 低 | Phase ∞ |
| 运行数据量小 | 🟢 低 | Phase 9 继续积累 |

---

## 九、与 Phase 7 需求分析的交叉检查

Phase 7 需求分析中提到的 5 个红队风险在 Phase 8 中的处理情况：

| 红队 # | Phase 7 风险 | Phase 8 应对 | 状态 |
|:------:|-------------|-------------|:----:|
| **R1** | 用户旅程可能是假演示 | Phase 8 不做用户旅程验证，而是把可见性升级为控制——绕过了问题 | ⬤ 未验证 |
| **R2** | 成本可见≠成本控制 | **这是 Phase 8 W1 的核心贡献**——add `degrade/review/block` 决策控制 | ✅ 已解决 |
| **R3** | 新鲜度治理变噪声 | W1 实现了可操作的新鲜度报告（含 refresh action），且新鲜度触发了实 | ✅ 已解决 |
| **R4** | 债务清理被挤掉 | D6 部分解决，D2/D3 未解决——R4 在 Phase 8 仍然部分成立 | ⬤ 部分验证 |
| **R5** | Hermes 收敛被延期 | W2 做了 wrapper-first 收敛，但 179 条断链未全清 | ⬤ 部分处理 |

**交叉检查结论**: Phase 8 有效回应了 R2 和 R3（控制面+可操作报告），但对 R4 和 R5 只是部分处理，R1 未被验证。

---

## 十、总体评价

### 10.1 做得好的

1. **范围控制优秀** — 每个 Wave 有清晰的工作边界，没有 scope creep
2. **从可见性到控制的升级** — Phase 7 看到问题 → Phase 8 阻止问题，是正向的架构进化
3. **运行时证据完整** — `control/current.yaml` 和 `freshness/current.yaml` 是真实的、可审计的运行记录
4. **W2 存储收敛方向正确** — 移除 `.omo` 硬编码比存储抽象层更实用
5. **W3 治理标准定义明确** — 为未来 cross-repo 扩张铺好了路
6. **完成率 97.9%** — 属于 OMO 机制执行以来的最高水平

### 10.2 可以更好的

1. **健康分未提升** — 90→90，4 个阶段没突破
2. **D2/D3 跨越 3 个阶段未被处理** — CI 测试和 eu-pricing 测试从 Phase 5 遗留至今
3. **Cross-repo rollout 只做了标准定义，未执行落地**
4. **运行样本量太小** — 9 次 dispatch 不足以验证控制闸门的有效性
5. **控制闸门仅覆盖 2 个维度** — 预算和新鲜度是好的开始，但覆盖面有限

### 10.3 最终判定

```
Phase 8 总体评分: 8.5 / 10

交付质量:     🟢 9/10 — 3 个 Wave 按计划交付，运行时证据完整
范围控制:     🟢 9/10 — 没有 scope creep，每个 Wave 聚焦
架构演进:     🟢 8/10 — 控制闸门级是有价值的架构新增
债务清理:     🟡 6/10 — D5 解决，D1/D6 部分解决，D2/D3 未解决
健康分提升:   🔴 5/10 — 90→90 停滞，评分体系可能需要重新审视
遗留处理:     🟡 6/10 — 明确了遗留项但没有完整解决它们
```

**总结**: Phase 8 在"把可见性变成控制"这个主题上做得非常出色，范围控制和交付质量都是最高水平。但健康分停滞和 D2/D3 跨越 3 个阶段未被处理是两个需要认真面对的问题——它们将是 Phase 9 规划的关键输入。

---

## 附录: 数据来源清单

| 来源 | 路径 | 用途 |
|------|------|------|
| 系统状态 | `state/system.yaml` | Phase 8 状态、健康分、任务计数 |
| 程序计划 | `plans/archive/phase8-program-plan.md` | Wave 结构定义 |
| W1 规范 | `plans/archive/phase8-starter-packet-spec.md` | Wave 1 范围 |
| W2 计划 | `plans/archive/phase8-wave2-execution-plan.md` | Wave 2 范围 |
| W3 计划 | `plans/archive/phase8-wave3-execution-plan.md` | Wave 3 范围 |
| 规划核定 | `summaries/phase8-planning-ratification.md` | 入口门禁记录 |
| W1 关闭 | `summaries/phase8-wave1-closeout.md` | Wave 1 交付物 |
| W2 关闭 | `summaries/phase8-wave2-closeout.md` | Wave 2 交付物 |
| W3 关闭 | `summaries/phase8-wave3-closeout.md` | Wave 3 交付物 |
| 总复盘 | `summaries/phase8-closeout-retrospective.md` | 总体判断 |
| 回顾 | `summaries/phase8-review.md` | 优势与风险 |
| 控制证据 | `_delivery/task-center/control/current.yaml` | 运行时控制决策 |
| 新鲜度证据 | `_delivery/task-center/freshness/current.yaml` | 运行时新鲜度 |
| 用量核算 | `_truth/task-center/usage-accounting.yaml` | 用量 SSOT |
| 治理标准 | `standards/operation-levels.md` | 跨仓库治理边界 |
| 计划索引 | `plans/README.md` | 文档状态分类 |
| P7 需求分析 | `plans/phase7-planning-analysis-requirements.md` | 交叉检查依据 |
