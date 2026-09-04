---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: Workflow waiver 证据 — 差距治理实施 (S1-S4)
type: doc
---

# Workflow waiver 证据 — 差距治理实施 (S1-S4)

> ADR-0203 窄豁免记录。用户书面明确授权实施。

```text
waiver: user-explicit
when: 2026-08-24T00:00:00Z
who: user (starlink-awaken)
quote: "全面推进落地吧"
scope: S1-S4 差距治理 (CAP-OWN / PROJ-FORCE / AUTO-FIX / GEN-FORCE / CONV-3 / GOV-REBAL / UX-NOISE / TP-RELATIVE / PATH-ANCHOR)
reason: 3Y 台账无可认领治理 bet (124 bet: 122 done, 2 blocked 且不相关); 用户明确要求全面推进治理落地
risk: 无 active bet 绑定, run 无 bet_id 关联; 用 AGCP_REQUIREMENT_ITERATION_GATE=0 旁路 + 本证据记录
residual: 实施完成后如产生新可认领 bet 需补台账关联; 治理演进建议登记新 bet (架构成熟度 90%)
```

## 范围

本次实施覆盖复盘识别的 9 大差距治理（对应健康分 70→90 目标）：
1. CAP-OWN 能力所有权 + 删除闸门
2. PROJ-FORCE 投影强制化
3. AUTO-FIX 自动修复环
4. GEN-FORCE 生成物契约
5. CONV-3 项目收敛决策
6. GOV-REBAL 约束重平衡
7. UX-NOISE 命令发现层
8. TP-RELATIVE 测试时序模板
9. PATH-ANCHOR 脚本路径模板

## 用户授权原文

> 用户指令链：
> 1. "做全面的项目粒度的架构分析和战略分析...做全面的分析和迭代，架构成熟度确保达到90%"
> 2. (收到方案后) "全面推进落地吧"
> 3. (CONV-3 决策, 2026-08-24T05:48Z) "继续剩余工作，你来帮我决策，给你授权"
>    → 用户明确授权由 agent 代为做出 CONV-3 收敛决策 (family-hub / metaos / mesh-router 三态定案)

## CONV-3 决策 (2026-08-24, 用户授权定案)

基于实证数据 (GitHub tree 权威规模 + commit 活跃度 + bet 台账 + gate/CI 引用)：

| 项目 | 决策 | 理由 (实证) |
|------|------|------------|
| family-hub | C 归档观察 (paused, 不删除) | 6 py 极小, v0.1.0, 无专属 bet, 愿景占位性质 |
| metaos | A 明确边界 + 接口契约 | 102 py 中等规模, 2026-08-20 活跃, 与 omo 划清"治理执行 vs 编排决策" |
| mesh-router | A 正式归档 (bin/_archive/) | deprecated, 零代码/CI/测试引用, 完成"半吊子归档" |
