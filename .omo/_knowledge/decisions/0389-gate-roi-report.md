---
id: ADR-0389
title: M5 gate ROI 治理价值报告 — 量化 gate 价值的减法决策输入
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-07
type: ssot
---

# ADR-0389 Decision: M5 gate ROI 治理价值报告

> 承接 ADR-0386 roadmap 的 M5 (C3) 与 ADR-0384 的 gate-effectiveness (D3).
> ADR-0384 首测揭示 5/7 gates WEAK → 系统到投资收益递减点 → 未来该做减法.
> 但"砍谁"一直靠人工判断. 本 ADR 把减法决策变成**数据驱动**:
> 产出量化价值报告, 让"下轮砍谁"有依据.

## 一、背景 (实测数据, 693 events / 7 gates / 2026-06-06→08-06)

| gate | fires | fail | 30d fire | 全期 fire | 趋势 | 估算节省 |
|------|-------|------|----------|-----------|------|---------|
| agora health | 94 | 0 | 0% | 19% | ↓ 衰减 | 23.5h |
| ruff lint | 91 | 0 | 31% | 14% | ↑ | 12.1h |
| debt integrity | 31 | 0 | 69% | 2% | ↑↑ | 10.3h |
| task consistency | 55 | 0 | 0% | 11% | ↓ 衰减 | 9.2h |
| test coverage | 23 | 0 | 50% | 1% | ↑↑ | 5.8h |
| doc lifecycle | 13 | 0 | 0% | 9% | ↓ 衰减 | 2.2h |
| adr links | 27 | 0 | 25% | 5% | ↑ | 2.2h |

**关键洞察**:
1. **7 个 gate 全部 warn-only, 0 fail** — 无 CI 阻断级拦截, 全是提醒型.
   这意味着 gate 的价值 = 提醒密度 × 人工处理时间, 而非"抓到了必须修的错".
2. **趋势分化**: debt integrity 2%→69%↑↑ (治理债务恶化被持续捕获),
   agora health 19%→0%↓ (健康已修复或检测失效 — 需人工核查),
   task consistency/doc lifecycle 归零 ↓ (可能已收敛或检测失效).
3. **估算总节省 65.3h** — 若这些 warn 无人消费, 则接近 0; 若被消费, 则价值真实.
   报告必须标注"经验估计, 用于相对排序".

## 二、决策

### 决策 1: 新增 `bin/_archive/2026-08-conv3/gate-roi-report.py`

复用 gate-effectiveness 的 governance-history.jsonl 加载, 新增:

- **trend**: 近 30d fire_rate vs 全期 → up/down/flat (减法判断核心)
- **est_hours_saved**: warn×warn_min + fail×fail_min (COST_MODEL 经验值)
- **verdict 建议**: RETIRE (0 fires 大样本) / NOISY (warn-only 高密度, 降级去噪)
  / PRUNE (30d 衰减) / KEEP (有 fail 拦截) / NEW (样本不足)
- 输出: 人类表格 / --json / --markdown (季度报告)

### 决策 2: 生成季度报告产物 `docs/reports/gate-roi-2026-08.md`

消费时刻 = 季度 bet review. 报告给出下一轮减法的量化候选:
- **PRUNE agora health / task consistency / doc lifecycle**: 30d 归零,
  需人工核查是"已修复"还是"检测失效" (二者处置不同)
- **NOISY ruff lint / debt integrity**: warn 高密度 0 fail,
  降级 warn→info 或聚合去噪, 避免提醒疲劳

### 决策 3: 报告建议不自动执行

ROI 报告是**决策输入**, 不是自动执行器. 每条建议需人工确认后
再落地为 workflow/SSOT 变更 (遵循"减法也要先验证"原则).

## 三、与既有工具的边界

| 工具 | 职责 |
|------|------|
| gate-effectiveness.py (ADR-0384) | 单门 effectiveness 评分 (fire 密度) |
| gate-roi-report.py (本 ADR) | 门价值报告 (trend + 时间估算 + 减法建议) |
| workflow-health.py (ADR-0386) | workflow 结构健康 (unpathed/idle/COE) |
| check-ci-surfaces.py (ADR-0379) | CI 平面 SSOT 接线漂移 |

gate-effectiveness 保留 (评分视角), ROI 报告在其上叠加决策层, 不重复.

## 四、验证

```bash
python3 bin/_archive/2026-08-conv3/gate-roi-report.py             # 表格 + 减法建议
python3 bin/_archive/2026-08-conv3/gate-roi-report.py --json      # 结构化 (仪表盘可消费)
python3 bin/_archive/2026-08-conv3/gate-roi-report.py --markdown  # 季度报告文本
```

## 五、后续 (下一轮减法的量化候选)

1. **agora health / task consistency / doc lifecycle 30d 归零核查**:
   是真修复 (gate 使命完成 → 降频) 还是检测失效 (→ 修 detector)
2. **ruff lint / debt integrity warn 降级**: 高密度 warn → info,
   或聚合为周报一条, 防提醒疲劳
3. M3 (drift 预测) / M4 (ADR 生成器) 按 roadmap 顺序推进
