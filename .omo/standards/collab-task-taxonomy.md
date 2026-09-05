---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: "2026-07-29"
type: ssot
---

# 协作任务类型分类学 (P86 A1)

> Status: MANDATORY | Applied: P86 A 波 (分层归因的基础)
> 上位: P86 §A1 · 验收: 现有全部真实任务与场景可归类
> 目的: 回答"协作在哪类任务有效/有害", 为协作收益地图 (A2) + 产能目标分层 (C1) 提供维度

## 1. 核心问题

P84 "协作普遍正收益" 假设被四组测量 challenge:
- 批次1 (独立并行批量): 历史 **5.4x 已作废** (R1)；多 agent 真 dispatch **未闭环**
- 批次2 (简单分析归因): 协作 **劣 1.7x**
- 批次3 (对抗冲突消解): **4% 消解** (协议没设计)

不建立任务类型分类学, 任何"协作收益"结论都是空中楼阁 (混类型平均 = 掩盖分化).

## 2. 四维度分类 (P86 §A1)

### 维度 1: 并行度 (parallelism)
| 值 | 含义 | 协作预期 |
|----|------|---------|
| `independent` | 任务可拆成无依赖子任务, 各 agent 独立做 | **协作正收益** (并行加速) |
| `ordered` | 子任务有顺序依赖 (B 需 A 输出) | 协作收益存疑 (木桶效应) |
| `coupled` | 子任务强耦合 (需实时协商) | 协作可能负收益 (coordination overhead) |

### 维度 2: 冲突面 (conflict_surface)
| 值 | 含义 | 协作预期 |
|----|------|---------|
| `none` | 各 agent 产物隔离, 无共享 | **协作正收益** (无冲突) |
| `read_shared` | 共享只读 (都读同一 spec) | 协作正收益 (无写冲突) |
| `write_shared` | 共享可写 (都改同一 artifact) | **需冲突消解** (协作机制上限决定) |

### 维度 3: 确定性 (determinism)
| 值 | 含义 | 协作预期 |
|----|------|---------|
| `well_defined` | 判定准则明确 (测试/编译/格式) | 协作正收益 (可并行验证) |
| `negotiated` | 需协商定义 (设计/架构选择) | 协作收益存疑 (协商 overhead) |
| `open_ended` | 开放式 (创意/探索) | 协作可能负收益 (难收敛) |

### 维度 4: 规模 (scale)
| 值 | 含义 | 协作预期 |
|----|------|---------|
| `single_step` | 单步任务 | 单 agent 更快 (dispatch overhead 不值) |
| `few_step` | 少步 (<5) | 协作边界 (看并行度) |
| `long_chain` | 长链 (≥5 步) | 协作正收益 (若可并行) / 木桶 (若有序) |

## 3. 协作收益预测矩阵 (基于四维度组合)

| 组合 | 协作收益 | 典型任务 | 实测印证 |
|------|---------|---------|---------|
| independent + none/read + well_defined + few/long | **待多 agent 闭环** (D2 人类允许) | doc 修复 / 场景生成 / 批量 as_of | 5.4x 作废；非 batch5 线程池 |
| ordered + read + well_defined + few | **弱正/平** | 串行审查 / 归因 | 批次2 1.7x 劣 ⚠️ |
| coupled + write + negotiated + few | **负/需消解** | 多 agent 共写 / 设计协商 | 批次3 4% (协议没设计) 🔴 |
| any + write + any + any | **取决于消解** | 双写/抢占 | 批次3 暴露盲区 |

## 4. 现有资产归类

### 4.1 能力轨场景 (134)
| category | 并行度 | 冲突面 | 确定性 | 规模 | 协作预期 |
|----------|--------|--------|--------|------|---------|
| A_conflict (88) | coupled | write_shared | negotiated | few | 需消解 (实测 4% 对抗) |
| B_failure_injection (18) | ordered | read_shared | well_defined | few | 弱正 (容错重分派) |
| C_decomposition (13) | independent→ordered | none | well_defined | long | 正 (链式分解) |
| D_reuse_pair (13) | independent | read_shared | well_defined | few | 正 (复用对) |

### 4.2 真实任务 (11, 见 A3 归因)
| 任务 | 并行度 | 冲突面 | 确定性 | 规模 | 协作适用? |
|------|--------|--------|--------|------|----------|
| stage1-task1 doc-claims-scope (6 INTERFACE) | independent | none | well_defined | few | D2 允许；多 agent 墙钟未闭环 |
| stage1-task2 kairon-ruff | independent | none | well_defined | single | 边界 (单步) |
| stage1-task3 adr-index | independent | read | well_defined | few | ✅ |
| stage1-task4 adr-coverage | independent | read | well_defined | few | ✅ |
| stage1-task5 gbrain-dead-entry | independent | none | well_defined | single | 边界 |
| (planned 6 项, A3 归因中) | — | — | — | — | — |

## 5. A2 对照实验设计 (待跑, 真 dispatch 口径)

基于分类学, 每个协作收益档**各跑一批真 dispatch 对照** (禁平均, 禁混口径):
- 批次4: `independent + none + well_defined` (强正档, 复现批次1)
- 批次5: `ordered + read + well_defined` (弱正/平档, 复现批次2)
- 批次6: `coupled + write + negotiated` (负/需消解档, 验证 B2 修复后是否转正)
- 批次7: `independent + write` (混合档, 测 write 冲突在 independent 下是否可控)

**验收** (P86 §A2): ≥4 类型各有真 dispatch 对照数据 → 协作收益地图.

## 6. 反模式 (熔断红线)
❌ **只跑有利类型** (independent+none) 让协作数据好看 = 最高级违规 (P86 §熔断)
❌ **混口径** (真 dispatch vs 模拟) 平均 = 违规
❌ **不分类就平均** 协作收益 = 掩盖分化 (批次1/2/3 分化就是证据)
❌ A 波结论未出按 60 任务/月推 = 违规

## 7. References
- P86 longplan §A1 · §熔断
- 批次1/2/3 实测 (`.omo/_knowledge/audits/2026-07-2X-p84-*`)
- A3 归因 (`.omo/_knowledge/audits/2026-07-29-p86-a3-completion-rootcause.md`, 待写)

## 6. 下游 SSOT 指针 (ABCD 关闭)

- A2 协作收益地图定论: `.omo/_knowledge/audits/2026-07-29-p86-a2-collaboration-gain-map.md`
- A3 完成率归因: `.omo/_knowledge/audits/2026-07-29-p86-a3-completion-rootcause.md`
- B 协议边界: `.omo/standards/collab-conflict-protocol-boundary.md`
- C 目标 / BRIEF 产能节: `BRIEF.md` · ADR-0247 amend · ADR-0287
- §STOP: `.omo/standards/p84-auto-advance-termination-condition.md`
