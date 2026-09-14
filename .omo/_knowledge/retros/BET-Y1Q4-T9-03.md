---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-11
---
# BET-Y1Q4-T9-03 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 0.5–1 day，落在 appetite（1 day）内。主要为方案调研、IA 定稿、台账/战役绑定与 PR。
另含一次 ID 重编号 follow-up：归档区已有 T9-01/T9-02，避免撞号改为 T9-03。

## Q2 done_when 是否全部通过？哪条没过，为什么？
- 规格文档：通过（plans + superpowers/specs 双落盘，后者为 binding 契约）
- ledger 含 BET/CMP/MS 且 lint：通过（重编号后为 BET-Y1Q4-T9-03）
- campaign/milestone 关联 OBJ-HOLDABILITY：通过
- show 可解析：通过

## Q3 过程中发现的与 plan 不符的事实（打假）？
1. `find('milestones:')` 会误匹配 `required_milestones:`——台账外科插入必须用行首锚定。
2. `start --bet` 强制 `accepted_specifications` 且 spec 必须在 `docs/superpowers/specs/` 下；仅 `docs/plans/` 不够。
3. 活跃台账里多数 BET 未挂 `campaign_ref`；关联需同时写 campaign + milestone.required_bets + bet.campaign_ref。
4. **ID 撞号**：归档已有 `BET-Y1Q4-T9-01/02`（resident ledger）；只扫 active ledger 会漏判。新 bet 编号前必须扫 archive。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
- 文件 +3（plans spec、superpowers design、retro）+ ledger/CLAUDE 增量
- 规则/ADR/脚本：0
- 实现代码：0（MVP 留给 T9-04）

## Q5 下一个认领本 track 的 agent 需要知道什么？
- 读 `docs/superpowers/specs/2026-09-06-agent-session-dashboard-design.md`
- 下一 bet 预告：`BET-Y1Q4-T9-04`（MVP aggregator + compact CLI），勿做 Web UI
- bootstrap 钩子与 MCP 属 `BET-Y1Q4-T9-05`，不要提前扩面
- 编号前先扫 `3y-bet-ledger-archive.yaml`
