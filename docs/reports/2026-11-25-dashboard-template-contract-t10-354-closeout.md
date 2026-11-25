---
schema: md/v1
status: completed
lifecycle: evidence
owner: laowang
last-reviewed: 2026-11-25
type: report
bet_id: BET-Y2Q4-T10-354
title: BET-Y2Q4-T10-354 closeout 回执 — done_when 三条实测
---

# BET-Y2Q4-T10-354 closeout 回执

生成时间：2026-11-25T14:00Z（UTC），在 worktree
`/Users/xiamingxing/ws-bet-t354-dashboard-template-contract`（base = origin/main@facb9c4df4）
实测；live payload 取自 `curl http://127.0.0.1:43191/data.json`（HTTP 200, 114 键）。

## 结论

本 BET 的写面为模板 SSOT 与债条目，全部在仓内；交付待 merge 后由
zhixing-dashboard-refresh 刷新周期发布新 release 生效。

## done_when 逐条实测

| 条款 | 命令 | 实测读数 | 判定 |
|---|---|---|---|
| 模板 D.<7 字段> 引用清零 | `rg -c "D\.(anomaly_events\|current_findings\|library\|live_sources\|pending_publications\|reconciliation_candidates\|value_loop)\b" template.html` | 零命中 (退出码 1)；退役注释 2 处在位 | 达成 |
| 守卫 dry-run missing 7 → 0 | 守卫同款逻辑 (`re.findall D\.<field>` × live payload) | 引用 62→55，missing `[]` (0) | 达成 |
| zhixing-host-sync check 维持 in_sync | `python3 bin/gac/zhixing-host-sync.py check` (主仓) | template.html `state: in_sync` (source_sha == runtime_sha) | 达成 |

## 裁定执行明细 (12 处 Edit, 全部行为等价或死面清除)

- live_sources → source_states 兜底 (2 处): swarm 面板「Live Sources」从恒
  NO_DATA 变真实 21 源数据
- 退役 6 字段 (10 处): pending_publications / reconciliation_candidates 连
  死面板整卡移除; current_findings 渲染行+空 ul 移除 (卡片 summary-source 仍活);
  value_loop / anomaly_events 死引用改字面量 `{};` (fallback/空态逻辑原样);
  library 规范化行 + 死拼接移除

## 诚实边界

- worktree 的 gac-local-gate 另有 3 项红 (write-guard / evidence-freshness /
  ratio): 主仓对照实测前两项为子模块 clone 半途环境病 (主仓 100 分全绿), ratio
  为 30d 滚动统计预存债 (主仓同红, 走 waiver 先例) —— 均非本 BET diff 引入。
- 页面生效延迟: merge 后需等 zhixing-dashboard-refresh 下一个刷新周期发布
  新 release, current symlink 切换即生效 (分钟级, 非即时)。

## 回滚

revert 单提交即可 (模板单文件 + 债条目); host-sync check 保证交付一致性。
