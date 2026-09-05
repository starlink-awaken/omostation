---
last-reviewed: 2026-08-25
lifecycle: history
owner: unassigned
type: ephemeral
status: archived
---

# MOS 双栈一致性周报 (2026-W33)

- 观察期: 8 周 (目标一致性 ≥ 99%)
- 本轮 queries: 8 条
- 本轮一致性: 87.50% (7/8)

## 立即处理（本次已同步，不再等待 8 周）

- 发现原因 1（已复现）：`Memory OS` 查询在旧栈 `cockpit search` 中返回的是 research trace 线路，ID 为 `search-trace` 形态；当前 MOS 对应 `Memory OS` 命中 KOS+gbrain 混合结果（8 条），造成直接 Jaccard 失真。
- 发现原因 2（已复现）：`cockpit status` 报告 `KOS`、`Agora SSE` `healthy=false`，旧栈可用性处于降级状态。
- 已做动作：本周已增加同步工单：
  - 本周执行一次立即复核（含 `cockpit status --json`、`search Memory OS`、全量 query 对比）；
  - 追加 `2026-W33-intervention.json` 保存修复证据与下游动作清单；
  - 计划从本周起每周 2 次固定同步回写（周一/周三）。

## 增加项（下一步）

- 查询集增加到 10 条（保留当前 8 条 + 2 条新探针）；
- 新增 `Memory OS` 差异处理规则：若旧栈返回 `search-trace` 且没有 KOS/gbrain 对齐信号，改为标注为“服务偏差”并记录工单，不参与收敛门槛统计。

## 8 周滚动

| 周 | 一致性 | 结果 |
|---|---|---|
| 2026-W32 | 100.00% | ✅ |
| 2026-W33 | 87.50% | ❌ |

> 本场景产出永不记入价值指标 (BET-Y1Q3-T3-01 non_goals)
