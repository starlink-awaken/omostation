---
lifecycle: history
owner: governance-team
last_updated: 2026-07-28
---
# P84 W2 能力轨基线报告（134 场景全量跑批）

> 上位: strat-p84-scenario-driven-longplan.md W2.1
> 🔴 红线: 构造场景只计能力轨, 绝不计产能轨 (P84 §0)

## 场景库构成（134）
| 类别 | 手写 | 生成 | 小计 |
|------|------|------|------|
| 良构 (A/B/C/D) | 4 (A01/B01/C01/D01) | 100 (GEN-A60/B16/C12/D12) | 104 |
| 对抗 (red-team) | 6 (ADV01/03/05/07/09/11) | 24 (GEN-ADV 6缺陷×4) | 30 |
| **合计** | 10 | 124 | **134** |

## 跑批结果（能力基线）
- **总**: 107 passed + 27 failed
- **良构**: 104/104 = **100%** (管线正确处理正常任务)
- **对抗**: 3/30 过 (10%)
  - ✅ 过: ADV01/03/05 (W2.2 修后 cycle/deadlock/broken_chain 检测实现)
  - ❌ 失败: ADV07/09/11 + 24 GEN-ADV (runner 未实现 double_claim/partial/starvation 等)

## 失败归因（27 failed）
**全 27 失败 = 协作机制缺陷 (runner 模拟层未实现真实协作管线该有的检测), 非场景设计不合理**:
- `double_claim_detected` (认领去重) — ADV07 + 4 GEN-ADV
- `partial_failure_handled` (部分失败处理) — ADV09 + 4 GEN-ADV
- `starvation_resolved` (公平调度) — ADV11 + 4 GEN-ADV
- `orphan_detected` / `unauthorized_detected` / `audit_reject_handled` — 12 GEN-ADV

## 回归集（W2.2 闭环机制）
- ADV01/03/05 已修 → 入回归集**永久防复发**
- 未修 27 → W2.2 后续每修一个 → 对应 ADV/GEN-ADV 转 ✅ → 入回归集
- 回归集接 cron (W5 常态化, 每日跑防协作机制退化)

## 对抗集有效性（P84 W1.2 验收）
- 对抗 30/134 = **22% ≥ 20%** ✅
- 失败 27 **≥ 3** ✅ (对抗有效, 非全过, 不需上报加强)
- 6 手写 ADV: 3 过 3 失败 (修一批+加一批, 场景法自我校正)

## 双轨红线
- 🔴 构造场景只计能力轨 (本报告), 绝不计产能轨
- 🔴 silent_loss = 0 硬红线 (全 134 场景)
- 🔴 对抗场景行为准则 (events_contain) 非预设答案 — J1 核实通过
