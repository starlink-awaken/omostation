---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
last_updated: 2026-09-03
type: ssot
---
# ADR-0200: Y1Q4 年度门 code_loc 重基线（净值口径）

## Status
Accepted (BET-Y1Q3-T1-04 人类批示, 2026-08-18: 采纳情景 B 调门 1,100K + 净值口径 + 分项目观测)

## Context

Y1Q4 年度门 `code_loc <= 690000 AND adr_active <= 120 AND gac_rules <= 80` 的
690K 基线按 Y1 初制定，**未纳入两个变量**：

1. **gbrain 重写噪音** — gbrain 独立仓库在 Y1 期间整体重写（含 god-module
   SRP 拆分，见 BET-Y1Q3-T6-04），名义 churn +179K/-179K，净值仅 +360
   （纯对称改写，净贡献≈0）。
2. **新项目出生** — cockpit-ui / omlxc / runtime / ecos 等新项目在 Y1 期间
   落地，其代码量是"出生"而非"膨胀"。

实测（2026-08-18，`bet-ledger.py surface`）：

| 指标 | 当前 | 基线(2026-08) | 变化 |
|---|---|---|---|
| src_loc（总量口径，含子模块） | 1,663,966 | 726,412 | +937,554 (+129%) |
| test_loc | 803,823 | 350,854 | +452,969 (+129%) |

净值口径（T1-03，since 2026-08-01）显示真实业务增长 ≈ +145K
（cockpit-ui +30K / omo +29K / cockpit +26K / runtime +22K / omlxc +22K），
gbrain 重写净 +360，agora 净 +6.7K。

总量口径 1,663,966 中，子模块（gbrain/agora/cockpit 等）占大头；690K 基线
只锚定了主仓初态。守原门 = 刻舟求剑，会诱导 T3-01 式谎报。

## Decision

1. **门值重基线为 1,100,000**：

   ```yaml
   gates:
     Y1Q4:
       question: 表面积是否达标?
       pass: code_loc <= 1100000 AND adr_active <= 120 AND gac_rules <= 80
       on_fail: Y2 不启动扩展, 继续做 Y1
   ```

   论证：净值口径实测承载 ≈ 1,480K（剥离 gbrain 重写噪音），预留 20% 余量
   取 1,100K；或按"基线 726K + 净值增长 145K × 2"= 1,016K 取整 1,100K。
   该门允许 Y1 期间的项目出生与工具 churn，同时仍约束"净膨胀"。

2. **门检从总量口径切换为净值口径**：gbrain 重写噪音剥离，重写是维护成本
   而非表面扩张。

3. **新增分项目净增长观测**（季度报告，不设硬门，超预算需解释）。

4. **adr_active <= 120 / gac_rules <= 80 维持原值**（本 ADR 不改）。

## Consequences

- 守门从"不可能"变为"可达成且有意义"：约束净膨胀而非名义总量。
- 消除重写型变更对门检的失真（刻舟求剑 → 诚实口径）。
- 分项目观测为 Y2 年度门提供"出生 vs 膨胀"的分解依据。
- 需要人类批示后更新 `docs/plans/3y-bet-ledger.yaml` 的 Y1Q4 门值。

## References

- BET-Y1Q3-T1-04（年度门修订评审）
- BET-Y1Q3-T1-03（surface numstat 净值口径）
- docs/plans/annual-gate-rebaseline-2026Q4.md（三情景量化提案）
