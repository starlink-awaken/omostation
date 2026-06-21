# Health 指标语义统一 (产品走查 v3 #19 架构师)

4 个"健康"指标语义不同, 命名易混淆 (用户不知看哪个). 此文档澄清各指标含义 + 权威源.

## 指标矩阵

| 指标 | 实测值 | 语义 | 权威 | 位置 |
|------|:---:|------|:---:|------|
| **health_score** | 92 | 治理健康 (manual audit post-cleanup) | ✅ **SSOT** | `.omo/state/health.yaml` (system.yaml 引用) |
| health_score_raw | 88 | 原始自动计算 (未人工校准, 基线) | 子维度 | `.omo/state/system.yaml` |
| product-health | 30 | 产品/服务健康 (在线服务视角, 0/2 健康) | 子维度 | `cockpit product-health` 运行时 |
| audit 总分 | 96.8 | 6 维度综合审计 (governance/lint/radar/ssot/gitlink/ops) | 综合视图 | `cockpit audit` |

## 使用指南 (避免混淆)

- **看治理健康** → `health_score` (health.yaml, 人工校准的权威值)
- **看服务是否活着** → `product-health` (运行时在线服务)
- **看综合质量** → `cockpit audit` (6 维度)
- `health_score_raw` 是 health_score 的未校准基线, 不直接对用户暴露

## 根因 (为何 4 值)

各指标算法/视角不同, 非数据冲突:
- health_score = 人工审计治理面 (post-cleanup)
- health_score_raw = 自动算的原始分 (未校准)
- product-health = 只看在线服务数 (gateway/agora 等没全起 → 30)
- audit = 6 维度加权 (governance 100 + lint + radar + ssot + gitlink 6/7 + ops)

## 建议 (后续)

1. `cockpit status` 首页统一显示 `health_score` (SSOT), product-health/audit 作为子项
2. health_score_raw 内部用, 不对用户暴露 (减少混淆)
3. product-health 命名改 `service-health` (语义更准)

---

*产品走查 v3 架构师视角 #19 · 2026-06-19 · 澄清 4 健康指标语义, 定 health_score 为 SSOT*
