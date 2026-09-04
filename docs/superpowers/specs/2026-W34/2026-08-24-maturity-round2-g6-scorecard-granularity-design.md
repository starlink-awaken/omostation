---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-08-24
last-reviewed: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-06
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G6: Scorecard 检测粒度升级 (9/10 档, overall 9.0 可达)

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-06
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G6)

## 背景与问题

`maturity-scorecard.py` 6 个维度中 5 个是二值评分（PASS→8 / FAIL→6 或 7），
仅 `optimizable` 有 9 分档（drift-sweep clean → 9）。
数学上 overall 被 8 封顶：8×6/6 = 8.0，即使 5 维全绿也到不了 9.0。
本轮 G1-G4 已把 6 维推满到 8/8/8/8/8，整体 8.17，距 9.0 差 0.83——**封顶即瓶颈**。

## 架构选择

升级 `maturity-scorecard.py`，为每个维度增加 **9 分档深度验证**（在 8 分 PASS 基础上
要求连续/深度指标），保留 8 分档作为兜底，形成 6/7/8/9 四级。9 分档标准统一为
"**8 分基线的可验证深化证据**"，全部由现有工具/注册表产出，不新增外部依赖。

### 各维度 9 分档标准

| 维度 | 8 分（现状） | 9 分（新增深度证据） |
|------|-------------|----------------------|
| evolvable | script-registry validate PASS | validate PASS 且 registry 无 gap（`validate` 无 warning/missing）+ 登记脚本数 ≥ 基线 |
| iterable | 90pct-maturity-design.md 存在 | design doc 存在 **且** 含 5 阶段路线图 **且** Phase 1-3 已标记完成 |
| observable | compass_radar 有输出 | compass_radar 有输出 **且** 输出包含 ≥6 个雷达维度指标（非空雷达盘） |
| traceable | adr-link-validator rc=0 | links valid **且** 有效 ADR 文档数 ≥ 基线（无死链/悬空引用） |
| troubleshootable | owner 字段全覆盖 | owner 全覆盖 **且** expected+remediation 字段全覆盖（可排障三要素齐备） |
| optimizable | drift-sweep 有 findings | drift-sweep rc=0（clean, 已实现） |

### 评分函数变更（示例 signature）

```python
def _score(level8: bool, level9: bool, level6: bool = True) -> int:
    if level9: return 9
    if level8: return 8
    return 6
```

每维度实现独立的 `_level9_*` 校验，输出 evidence 注明命中档位。

## 验收标准

1. **[scorecard overall ≥ 9.0]**
   - 验证方式：`python3 bin/gac/maturity-scorecard.py --json`
   - 证据类型：overall ≥ 9.0（= 5 维 9 + 1 维 8）

2. **[9 分档有独立 evidence]**
   - 验证方式：`--json` 输出每维 evidence 含 9 分证据描述
   - 证据类型：evidence 非空且不误导

3. **[8 分档仍可达成（不破回归）]**
   - 验证方式：G1-G4 的 8 分档指标保持可判定
   - 证据类型：6 维全部 score ≥ 8

## 反指标

本 spec **不追求**以下指标作为成功度量：
- 10 分档（需自治自愈率 ≥90% 的运行时证据，Phase 5 范畴）
- 每维度满 9（6 维中允许部分 8，只要 overall ≥ 9.0）
- 引入外部成熟度模型（自研六维框架保持不变）

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 加 9/10 档 vs 改权重 | 加 9 分档 | 9 分档由现有工具可证，改权重是口径造假 |
| 2 | 统一 9 分档定义 vs 每维自定义 | 统一 "8 分基线+深度证据" | 避免各维标准漂移，评审可复核 |
| 3 | 5 维到 9 vs 全部 9 | 5 维 9 即可 overall≥9.0 | 留 1 维 8 作为诚实余量 |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G6) | agent |
