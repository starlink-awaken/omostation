---
lifecycle: history
owner: governance-team
last_updated: "2026-07-29"
---
# Z1-Z4: baseline 冻回 + baseline 受保护 + 观察窗 + 产能如实

> 上位: goal Z1-Z4 (治本: baseline 冻回叫停前 + 守门配置)
> 🔴 Z2 根因: 第四次门被绕过, 共同点"门守代码没人守门配置" → 本轮守 baseline 本身

## Z1 · baseline 冻回 B1' 划线 ✅ (验收 exit ≠ 0)

**冻结点**: B1' 划线 (cycle/deadlock/broken_chain 已实现保留; ADV19/21/23 标边界 grace).

**baseline-scenario-growth.txt 冻后** (7 行含注释, 3 个 ADV grace):
- ADV19-byzantine-quorum (标边界 grace)
- ADV21-replay-attack (标边界 grace)
- ADV23-cross-key-collusion (标边界 grace)
- ADV25-107 **一律不进 baseline** (叫停后产出, blocking)

**验收** (Z1 要求 exit ≠ 0):
- `check-scenario-growth`: **FAIL**, blocking=133, **exit 1** ✅ (有火力)
- ADV25-107 全 blocking (无 evidence + 非 baseline)

**取消 grace 的逻辑**: ADV25-107 是明令停止后产出, 不是"存量". 之前误当存量 grace = 让违规产物合法化. Z1 纠正.

## Z2 · baseline 受保护 ✅ (治本, 守门配置)

**check-baseline-growth.py** (新, sgf-policy gate + redline baseline-growth-protected):
- baseline 文件条目扩大 (current > meta) → **blocking** (须人类批准)
- 缩小 (清偿存量) → 自由 (PASS)
- 不变 → PASS

**元 baseline** (`baseline-baseline.txt`, Z2 冻结点):
- baseline-perf-budget.txt: 38
- baseline-scenario-detectors.txt: 1
- baseline-scenario-growth.txt: 3
- baseline-work-landed.txt: 0

**验收** (Z2 模拟加行):
- baseline-scenario-growth 加 1 行 (3→4) → **FAIL blocking=1, exit 1** ✅
- 恢复后 PASS

**治本意义**: 门守代码 (check-scenario-growth 拦 ADV), 本 check 守门配置 (baseline 文件). 第四次绕过根因 = 没人守配置 → Z2 补.

## Z3 · 观察窗重置 (今天起 + baseline 增长判据)

**起点重置**: 2026-07-29 (今天, 不从旧观察算).
**判据** (加一条):
1. 有无新 W 波 merge (required check 拦)
2. **baseline 有无再次增长** (Z2 守 baseline, 增长 = 违规)

**一周观察** (2026-07-29 ~ 08-05):
- 无新 W 波 merge + baseline 无增长 → 传送带真停
- 任一发生 → 还有没找到的路径, 如实报告不猜

## Z4 · 产能如实 (月 15 保守不达标, 不调口径)

**数据** (92 done):
- 真实有 PR: **9** (从第一次量到现在没变, T1 去污标准)
- 月 15 目标保守口径: **9 < 15 不达标**
- 🔴 **如实记录, 不调口径** (Z4 红线)
- 宽松 (30 含疑似): 达标, 但疑似未验证 (不报喜)

**export-dualtrack 报 103/98.1% 不可信** (含 62 自产 W 波, 67% 污染). 真实 9.

## 🔴 红线
- Z1 baseline 冻回 B1' 划线 (ADV25-107 不 grace)
- Z2 baseline 受保护 (扩大 blocking, 守门配置)
- Z3 观察窗今天起 + baseline 增长判据
- Z4 产能 9 如实 (月 15 保守不达标, 不调口径)

## References
- B1' 划线 (cycle/deadlock/broken_chain + ADV19/21/23 标边界)
- Z2 第四次绕过根因 (门守代码没人守配置)
- T1 去污标准 (真实有 PR 9)
