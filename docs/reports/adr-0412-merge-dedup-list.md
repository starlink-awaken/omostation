---
type: ephemeral
created: 2026-09-03
---

# ADR-0412 归并去重清单 (BET-Y1Q2-T1-01)

## 内包 (非删除 — 子模块条目移除, 代码进 omo._vendored)

| 来源 | 去向 | 文件数 | 说明 |
|---|---|---|---|
| projects/omo-debt/src/omo_debt/ | omo/_vendored/omo_debt_engine/ | 18 | 评分引擎 (core/honesty/legacy), cockpit 唯一消费者已改道 |
| projects/c2g/src/c2g/ | omo/_vendored/c2g/ | 27 | C2G 战略引擎, import 全限定改写 |

## 去重判定

- 主仓 omo.omo_debt* (P110 split 系列) 与子仓 omo_debt.core 为**功能互补非重复** (主仓=治理面 CLI, 子仓=评分引擎) — 内包后统一单仓
- c2g 无重复面 (独立域)
- src 下降量 = 子模块条目移除 (2 gitlink), 代码净迁入 ~4.5K 行; test_loc: omo+vendored 均在 (26 测试文件随内包可后续迁)

## CLI 兼容

- `omo-debt` 入口: 主仓 pyproject 已有 omo-debt = "omo.omo_debt:main" (原主仓入口, 不变)
- `c2g`/`c2g-mcp` 入口: 由 omo._vendored.c2g 提供 — pyproject scripts 补 c2g = "omo._vendored.c2g.cli:main"

## 消费者迁移

- cockpit debt_scoring.py → omo._vendored.omo_debt_engine.core (已改)
- CI ci-python-coverage pkg 列表、governance-check 等路径引用 → 随本 PR 同步
