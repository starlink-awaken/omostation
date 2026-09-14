---
schema: bet-retro/v1
bet_id: BET-Y1Q4-T8-24D
status: closed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-12
type: ephemeral
---

# BET-Y1Q4-T8-24D retro — Operations/Mission 工作台

## What changed

- **`views/OperationsView.tsx`**（新）：Work Cases 案件大厅（状态筛选/
  卡片列表）+ PersistentQueue 监控面板（水位/最老消息），数据消费
  `/api/bc-os/cases` 既有端点。
- **`views/MissionView.tsx`**（新）：3Y-BET 全景矩阵（窗口分组 +
  BetMatrixCell 状态色块）+ 窗口时间轴甘特图（GanttBar）+ Golden Slice
  价值公证面板（GoldenSliceCard），数据消费 `/api/ledger/bets`。
- 测试：vitest 2 个（渲染结构 + testid 断言，mock api），全过；tsc 无
  两文件错误；ruff 清零（cockpit-ui 不属 ruff 面）。
- 写面三次修正后完整（+retro +ledger +tests）。

## Q3 (打假)

- **cwd 漂移导致文件错写主仓三次**（/Users/xiamingxing/Workspace/src/）：
  heredoc 尾部 `cd` 失败后继续写文件。教训：写文件脚本一律用绝对路径，
  或写前 `test -d <target-dir>` 断言。
- done_when[0] "Work Cases 流畅运行" 目前为**渲染层交付**（mock API），
  真实案件数据流（signal_router→cases 端点）属后端接线，未做。
- "Golden Slice 真实价值公证"目前只消费 `/api/ledger/bets` 的
  golden_slice 字段——该字段后端尚未产出，面板为空态。

## Q4 (遗留)

- Operations 数据源接线（bc-os cases 端点真实化）。
- 甘特图目前是窗口示意跨度（每窗口 4 格），非真实起止日期。
