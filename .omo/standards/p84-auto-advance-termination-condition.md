---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: "2026-07-29"
type: ssot
---
# P84 自动推进终止条件 (Q1, ADV 传送带停)

> Status: MANDATORY | 上位: goal Q1 · P86 §B1' (P3 红线延伸)
> 🔴 红线 (Q1): 为构造场景补实现 = 违规 (P3 同族). 自动推进生成新场景类工作 = 须重新派单.
> 触发: W6+ ADV 传送带持续加对抗类 (wave8 到 double_spend/ghost_writer), 全部仅对抗集, 真实 0 发生.

## 1. 终止规则 (强制)

**任何自动进入的下一轮 (P84 自动推进 / 系统续跑 / linter 触发), 若产出物是以下之一,
且无真实发生证据 → 不得自动启动, 须重新派单 (人类确认):**

1. **构造场景** (collab-scenarios/ADV*.yaml, GEN-ADV-*) — 对抗场景, 非真实任务
2. **检测器实现** (scenario_lib._synthesize_* / _handle_*) — 为对抗场景补的检测逻辑
3. **新对抗类** (byzantine / replay / cross_key / split_brain / identity_spoof / supply_chain /
   sybil_flood / time_travel / quorum_eclipse / clock_skew / ghost_writer / double_spend / ...)

**真实发生证据** (任一):
- `.omo/_delivery/agent-workflows/runs/` 里真实 run 记录该冲突/失败
- `.omo/tasks/done/` 里真实任务 closure 涉及该类
- B1' 频率核查命中 (≥1 真实发生)

无证据 → 标注"协议不支持 X, 属已知边界" (B1' 标准), **不补实现**.

## 2. ADV25-47 边界标注 (不补实现, B1' 同标准)

已落地的 ADV25-47 (系统加的) **不回滚** (避免破坏性), 但 **不再新增**, 且按 B1' 标注边界:

| ADV wave | 类别 | 真实发生? | 处置 |
|---------|------|----------|------|
| wave5 (ADV19/21/23) | byzantine/replay/cross_key | ❌ 仅对抗 | 标注边界 (B1' 已记) |
| wave6 (ADV25/27/29) | split_brain/identity_spoof/supply_chain | ❌ 仅对抗 | 标注边界 |
| wave7 (ADV31/33/35) | sybil_flood/time_travel/quorum_eclipse | ❌ 仅对抗 | 标注边界 |
| wave8 (ADV37/39/41) | clock_skew/ghost_writer/double_spend | ❌ 仅对抗 | 标注边界 |

**全部"协议不支持, 属已知边界"** (真实任务 0 发生, runs 87 个 0 真实冲突).
不为它们补 _synthesize_* 实现 (P3 红线: 严禁为构造场景补实现 = 死代码同族违规).

## 3. 已落地检测器处置 (不回滚, 但标注)

scenario_lib 现有 _synthesize_* (byzantine/replay/cross_key/split_brain/.../double_spend):
- **不回滚** (避免破坏已 pass 的对抗集)
- **标注**: 这些检测器对应"仅对抗集"类别, **不算产能贡献** (B1' 标准)
- **不再扩展**: 不加新 _synthesize_* (Q1 传送带停)

## 4. 自动推进终止机制 (送卡 §F)

P84 自动推进 / 系统续跑 / linter 应在以下条件**停止**:
- 产出物属上述 3 类 (构造场景/检测器/新对抗类)
- 且无真实发生证据

**终止动作**: 不自动启动, 写入 needs-human 队列, 等人类派单.

实现建议 (送卡):
- pre-commit / agent-workflow start 前置检查: 若 diff 含 ADV*.yaml 新增 或 _synthesize_* 新增
  → 拒绝自动启动, 报 "Q1 终止条件触发, 须人类派单"
- 这是对 P3 红线的**可执行落地** (B1' 已证明标准可执行)

## 5. Q1 与 B1'/P3 的一致性

- P3 红线: 严禁为构造场景补实现 (死代码同族违规)
- B1': 仅对抗集类别 → 标注边界, 不补
- Q1: 自动推进生成构造场景/检测器 → 须重新派单 (强制人类确认)
- → 三者一脉相承: **真实频率驱动**, 不为对抗集 (无真实证据) 补实现.

## 6. 红线
❌ 为构造场景 (ADV) 补 _synthesize_* 实现 = 违规 (Q1/P3)
❌ 自动推进跳过终止条件 = 违规 (Q1)
❌ 拿"对抗消解率高"当产能成绩 = 违规 (B1': 仅对抗集不算产能)
✅ 真实发生 → 设计; 仅对抗集 → 标注边界

## References
- goal Q1 · P86 longplan §B1' · §熔断
- B1' 取舍 `.omo/_knowledge/audits/2026-07-29-p86-b1prime-conflict-triage.md`
- P3 红线 (P86 longplan §熔断)

## 7. 可执行冻结点 (ABCD close 2026-07-29)

- Gate: `python3 bin/gac/check-scenario-growth.py` (stock grace; **new** no-evidence ADV → blocking)
- Cap: `ADV_CAP` = stock max at freeze; detector count baseline frozen
- Meta: `check-baseline-growth.py` 守 baseline 行数不得静默扩大
- Closeout: `.omo/_knowledge/audits/2026-07-29-p86-abcd-closeout.md` · ADR-0287
- 🔴 ABCD 关闭后 **禁止** 无人类派单的 wave32+ 检测器/加硬传送带
