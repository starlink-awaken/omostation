---
lifecycle: history
owner: governance-team
last_updated: 2026-08-18
title: BET-Y1Q2-T8-01 复盘
type: retro
---
# BET-Y1Q2-T8-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite: 2 weeks；实际: 约 1.5 小时（本轮从 claim-check 到 verify）。超出比例: 未超出。未触发 circuit_breaker（阈值 3 周）。

## Q2 done_when 是否全部通过？哪条没过，为什么？

本轮 `python3 bin/plan/bet-ledger.py verify BET-Y1Q2-T8-01 --execute` 真实输出（摘要）：

```
[BET-Y1Q2-T8-01] /outcomes 结果与校准面板

done_when:
  [ ] 三视图: 待裁决队列 / 已裁决历史 / 校准曲线
  [ ] 未接入的指标显示"未接入"而非 0 (守 D1)
  [ ] /journeys 时间线同期上线

verify:
  $ cd projects/cockpit-ui && npm run build
    → vite v8.0.16 building client environment for production...
    ✓ built in 180ms
    期望: exit 0
```

完整捕获: 本会话 scratch `bet-verify-t8.txt`。**CLI 不会给 done_when 打勾**（只跑 build）。下面的勾是对照 **本轮 verify 的 build 产物 + 驱动已上线视图的 vitest**，不是旧复盘照抄。

| done_when | 本轮判定 | 证据 |
|---|---|---|
| 三视图: 待裁决队列 / 已裁决历史 / 校准曲线 | ✅ | `OutcomesView.test.tsx` 三个 tab；`Dashboard.outcomes-routes.test.tsx` 证明 `/outcomes` 不再被打回首页 |
| 未接入的指标显示"未接入"而非 0 (守 D1) | ✅ | 同上测试：断连 feed 出现字面量「未接入」且无代理 `0`；live `pending_count=0` 显示 `0`；知识漏斗 `status!==live` 显示「未接入」，`citation_rate=0` 显示 `0.0%` |
| /journeys 时间线同期上线 | ✅ | `JourneysTimelineView.test.tsx` + Dashboard `/journeys` 路由接线测试；build 含 `JourneysTimelineView` |

无时间窗口条款。**未**把台账 `status` 改为 done（`write_surfaces` 不含 `docs/plans/3y-bet-ledger.yaml`）。

## Q3 过程中发现的与 plan 不符的事实（打假）？
1. **旧复盘已宣称 3/3 通过，台账仍是 candidate。** 旧 Q2 不能当 closeout。复验发现 D1 未闭环：summary 缺数用 `—`；`pending = []` 默认值把断连 feed 画成「暂无待裁决项」。
2. **`verify` 只跑 `npm run build`。** 命令 exit 0 看不见三 tab / 未接入。done_when 框在 CLI 输出里全是 `[ ]`。
3. **第一棵隔离工作树在写文件后被清掉。** `ws-bet-y1q2-t8-01` 消失，主树仍在 `main`；已 reclaim。未入库的第一稿丢失，证明 D0「写完立刻 add」是对的。
4. **PASW 两套 inode。** 改 `.subtrees/cockpit-ui` 后，`projects/cockpit-ui` 仍停在 `9ad22125`，必须 commit + push 子模块分支 + `bump-pointer`，ledger verify 才会打到新代码。
5. **cockpit-ui 已有三视图骨架（commit 9ad22125）。** 本轮不是从零铺页面，是补 D1 与可驱动测试。
6. **routes.tsx 登记了 /outcomes /journeys，Dashboard 没接。** 直开 URL 被 `path="*"` 打回首页。浏览器实证先截到首页，才发现这不是「组件未写」而是「路由未接线」。已补 Dashboard Route。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
`python3 bin/plan/bet-ledger.py surface` 本轮输出：

```
=== 表面积实测（git tracked 口径，含子模块）===
指标                        当前     基线(2026-08)              变化   Y1 判据
----------------------------------------------------------------------------------------
src_loc              891,943         726,412  +165,531(+23%)   —
test_loc             439,883         350,854   +89,029(+25%)   不得下降
src_files              3,813           3,204      +609(+19%)   —
test_files             2,141           1,827      +314(+17%)   —
adr_total                375             344       +31(+9%)   只分层不裁剪
gac_rules                136             136        +0(+0%)   —
gac_required              27              26        +1(+4%)   0
bin_scripts              476             310      +166(+54%)   零调用归档
standards                 55              53        +2(+4%)   —
collab_scenarios           5             221      -216(-98%)   —

✅ test_loc 未下降（+89,029）
```

本 bet 自身（cockpit-ui `3e081819`，相对上一指针 `9ad22125`）：+1 显示规则文件 +3 测试文件；改 2 个已有视图。无新 GaC / ADR / bin 脚本。净增测试是为了让 done_when 可被驱动，不是新页面。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. 改 cockpit-ui 必须走 `.subtrees/cockpit-ui`（PASW），commit 后 `git push origin HEAD`，再 `gac-worktree.sh bump-pointer <session> projects/cockpit-ui`。
2. D1 规则在 `src/components/outcomesDisplay.ts`：断连 →「未接入」；live 0 → `0`。不要再给 hook 写 `data: pending = []`。
3. 台账 `verify` 仍只有 `npm run build`。要验 tab / 未接入，跑 `npm run test:unit -- src/components/__tests__/OutcomesView.test.tsx src/components/__tests__/JourneysTimelineView.test.tsx src/components/__tests__/outcomesDisplay.test.ts`。
4. 台账 `write_surfaces` 不含 yaml；**2026-08-15 人类口头授权**后由 `bet-ledger.py complete --force` 置 done（done_at 2026-08-15）。
5. 隔离工作树可能被并发清掉。写完立刻 `git add`，子模块尽快 commit。
