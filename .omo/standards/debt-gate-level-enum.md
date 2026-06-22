---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-22
---

# Debt Gate Level Enum (SSOT)

> 状态: active
> 版本: v1.0
> 日期: 2026-06-18
> 适用范围: omo debt item `gate_level` 字段

## 1. 目的

`gate_level` 是 omo debt item 的机器可读 severity-tier 字段。所有上游 (c2g pitch, agent register, broker proposal) 必须用合法值。

非法值会导致:

- `omo_debt_review_queue.GATE_ORDER` 排序乱序 (rank=99)
- `compute_debt_metrics` 不识别, watchlist/gate list 漏算
- `omo debt escalate` / `owner-routing` 走错路径
- `debt_health` 算法扣分失真

## 2. 合法值 (Authoritative Enum)

来源: `projects/omo/src/omo/omo_debt_review_queue.py:GATE_ORDER`

| 值 | 语义 | 优先级 (rank) | 适用场景 |
|---|---|---|---|
| `gate` | 必须先解决此 debt 才能 promote 任务/收口 phase | 0 (最高) | P0 / P1 严重 debt, 跨模块影响 |
| `watchlist` | 治理面持续监控, 每周 review | 1 | X1-X4 governance dimension 强相关 debt |
| `none` | 一般性 debt, 不需要 gate 拦截 | 2 (最低) | 低优 backlog, 已计划但未 start |

## 3. 非法值 → 合法值映射

注册 omo debt 时**必须**把上游 X1-X4 dimension 映射到上述 enum:

| 上游 dimension | 映射到 |
|---|---|
| `x1_audit` | `gate` (审计失败必拦) |
| `x2_freshness` | `watchlist` (保鲜监控) |
| `x3_value` | `watchlist` (价值归因) |
| `x4_consistency` | `watchlist` (一致性治理面, 大多是 watchlist 级别) |
| `unknown` / `other` | `none` (待评估) |

## 4. 治理面 L0 约束

L0 规则 `CR-DEBT-GATE-ENUM-01` (新增): 任何 omo debt register / governance proposal 修改 `gate_level` 字段, 必须从上述 enum 取值, 否则 reject。

实现位置: `projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml` 待补。

## 5. 验证

```bash
# 列出所有 debt item 的 gate_level
for f in .omo/debt/items/*.yaml; do
  python3 -c "import yaml; d=yaml.safe_load(open('$f')); print(d.get('id'), d.get('gate_level'))"
done | sort -u

# 验证 compute_debt_metrics 把所有 open debt 算入 watchlist/gate
python3 scripts/sync_omo_state.py --omo-dir .omo
python3 -c "import yaml; d=yaml.safe_load(open('.omo/state/system.yaml')); print('watchlist:', d.get('debt_watchlist_count'), 'gate:', d.get('debt_gate_count'))"
```

## 6. 历史违规修复

| 日期 | debt_id | 原 gate_level | 修后 | 路径 |
|---|---|---|---|---|
| 2026-06-18 | DEBT-CARDS-FRONTMATTER-PARSE | x4_consistency | watchlist | governance proposal DEBT-CARDS-FRONTMATTER-PARSE-gate-level-normalize-2026-06-18T15-21-00Z-proposal |

## 7. 参考

- `projects/omo/src/omo/omo_debt_review_queue.py:GATE_ORDER` — 合法 enum 定义
- `projects/omo/src/omo/omo_debt_metrics.py:compute_debt_metrics` — 算法消费方
- `.omo/_knowledge/management/2026-06-18-omo-drift-audit.md` §6 P1 — 触发本标准的 drift audit next-action
