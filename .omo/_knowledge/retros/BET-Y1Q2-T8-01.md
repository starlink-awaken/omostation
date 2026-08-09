# BET-Y1Q2-T8-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
约 1 小时（vs appetite 2 周）。核心组件已由并发 agent 在共享 checkout 开发（untracked），本 session 完成入库 + 验证 build。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 三视图: 待裁决队列 / 已裁决历史 / 校准曲线 | ✅ OutcomesView.tsx 三 tab (pending/history/calibration) |
| 未接入的指标显示"未接入"而非 0 (守 D1) | ✅ 知识引用率/场景校准/能力校准均显示"未接入"当无数据 |
| /journeys 时间线同期上线 | ✅ JourneysTimelineView.tsx + useJourneysTimeline hook, routes 已接 /journeys |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **main build 已损坏**: cockpit-ui main 的 routes.tsx 已引用 OutcomesView/JourneysTimelineView (L87-89/161-162), 但组件文件 untracked 未提交 → `npm run build` 引用缺失组件失败。T8-01 实际是"补全缺失组件恢复 build"。
2. **并发 agent 在共享 checkout 开发未提交**: OutcomesView.tsx (453L) + JourneysTimelineView.tsx (241L) 是共享 checkout 的 untracked 文件。worktree 从 main checkout 无这些组件。交付 = 将并发工作入库。
3. **worktree 子模块指针落后**: worktree 的 cockpit-ui 指针是 0c0a245e (旧分支), 落后 main 01eb421a。需 `git -C projects/cockpit-ui checkout 01eb421a` 更新到 main 才含 hooks/routes。
4. **dist 被 gitignore**: build 产物 dist/ 被 gitignore, 只提交 src 组件。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（cockpit-ui 子模块 commit 9ad22125）:
- `src/components/OutcomesView.tsx` (453L): 三视图 + D1
- `src/components/JourneysTimelineView.tsx` (241L): 旅程时间线

hooks/endpoints/routes 已在 main (tracked)。无新增 GaC 规则 / ADR / bin 脚本。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **cockpit-ui 组件位置**: `src/components/OutcomesView.tsx` + `JourneysTimelineView.tsx`, hooks 在 `src/api/hooks.ts` (useOutcomesSummary/Pending/History/Calibration + useJourneysTimeline), endpoints 在 `src/api/endpoints.ts` (/api/outcomes*).
2. **构建**: `cd projects/cockpit-ui && npm install && npm run build`。dist 被 gitignore。
3. **PASW 提交**: cockpit-ui 子模块改动走 projects/cockpit-ui → .subtrees/cockpit-ui → push → bump-pointer。
4. **main build 依赖**: routes.tsx 引用组件须存在, 否则 build 失败 (本 bet 修复)。
5. **待办**: 无 (T8-01 完整交付)。
