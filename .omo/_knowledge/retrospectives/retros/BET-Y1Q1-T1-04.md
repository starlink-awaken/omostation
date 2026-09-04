---
lifecycle: history
owner: governance-team
last_updated: 2026-08-09
title: BET-Y1Q1-T1-04 复盘
type: retro
---
# BET-Y1Q1-T1-04 复盘

## Q1 实际耗时 vs appetite？超出比例？
appetite 2 days。普查 + D0 门禁 + lane 修正合计约 2 天，未超出。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 全仓 untracked 非 gitignore 文件清单产出并逐条裁定 | ✅ 2026-08-06 未入库产物普查 |
| closeout 增加 D0 检查: 声明的 deliverable 必须 git ls-files 通过 | ✅ D0 铁律 + verify 校验 |
| AGENTS.md 收录 D0 铁律 | ✅ AGENTS.md §1.6.2 |
| change-lane-check 对 docs/ 下数据文件判为 docs 或 docs_data lane | ✅ |
| 若新增 docs_data lane, {docs, docs_data} 允许混合 | ✅ |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **E3 docs yaml 被误判为 code lane**: docs/plans/3y-bet-ledger.yaml 仅因 .yaml 后缀被判 code，导致「文档 + 配套数据」改动被拆两个 commit。lane 应按变更意图判，不应只按扩展名。
2. **gitignore 是重灾区**: `.omo/_delivery/`、`.subtrees/` 等被忽略，但产物需要入库时必须 `git add -f`（evalset 先例）。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增:
- change-lane-check.py docs_data lane 判定
- .gitignore 逐条裁定注释
- AGENTS.md D0 铁律
- 无新增 GaC 规则

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **D0 铁律**: 交付物必须 git add → commit → tag（或独立分支）。`git ls-files --error-unmatch <file>` 验收入库。
2. docs/ 下的 .yaml 数据文件走 docs_data lane，可与 docs 同 commit。
3. gitignore 路径产物入库用 `git add -f`，并在 closeout 注明。
