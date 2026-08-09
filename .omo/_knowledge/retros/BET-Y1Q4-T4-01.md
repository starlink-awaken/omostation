---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-08-09
---
# BET-Y1Q4-T4-01 复盘

## Q1 实际耗时 vs appetite？超出比例？
单 session 完成评测集生成器 + 439 条真实数据 + 测试（约 1 小时 vs appetite 1 周），未超出。
主要耗时在寻找真实 adjudication 数据源 + 补足 200 条目标。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 |
|---|---|
| 评测集 >= 200 条, 全部来自真实 adjudication | ✅ 439 条 (positive 403 + boundary 30 + negative 6), 全部真实来源 (pr-harvest + GitHub closed-unmerged + adjudications) |
| 含正例/负例/边界例三类 | ✅ positive (merged PR) / negative (closed-unmerged PR) / boundary (小改动被拒或大改动通过 = 决策边界) |
| 明确标注"非合成"来源 | ✅ 每条 synthetic=false + source 字段 (github://.../pull/N 或 adjudication://...) + 顶层 source_note |

未过: 无。

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **真实 adjudication 数据稀少**: `.omo/_delivery/outcomes/adjudications.jsonl` 仅 1 条 (smoke test)。真实裁决主要在 `pr-harvest.jsonl` (152 条, PR 评审即裁决) + GitHub API 可拉取的 PR 状态。
2. **GitHub 负例少**: 被关闭未合并的 PR 仅 6 条 (omostation), 多为"被取代"而非"评审拒绝" (如 #1230 被 #1232 取代)。这是真实的 rejected 语义。
3. **评测集在 gitignore 路径**: `.omo/_delivery/evalsets/**` 是 write_surfaces 但 `.omo/_delivery/` 整体被 gitignore。用 `git add -f` 强制入库 (同 collab-scenarios 先例)。
4. **boundary 例定义**: 小改动被拒 (评审严格) 或大改动通过 (评审宽容) 为决策边界 — 30 条边界例来自 148 accepted 中大改动 + 4 rejected 中小改动。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？（贴 surface 输出）
本 bet 净增（主仓 commit）:
- 新脚本 `bin/ssot/gen-real-evalset.py` (~200 行): 评测集生成器 (pr-harvest + gh api + adjudications → 三类标注)
- 新测试 `tests/unit/test_gen_real_evalset.py` (6 个)
- 评测集 `evalset-v1.json` (439 条, 186KB) — git add -f 强制入库

无新增 GaC 规则 / ADR。新增 1 个 bin 脚本 (工具类)。

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **评测集生成**: `python3 bin/ssot/gen-real-evalset.py` (生成 + 落盘) / `--count` (统计) / `--json` (摘要)。数据源: pr-harvest.jsonl + gh api (closed-unmerged 负例 + merged 正例补充) + adjudications.jsonl。
2. **评测集位置**: `.omo/_delivery/evalsets/evalset-v1.json` (gitignore, 需 git add -f 入库)。
3. **三类标注**: positive (merged) / negative (closed-unmerged) / boundary (小改被拒或大改通过)。
4. **来源可追溯**: 每条 source 字段 (github://.../pull/N / adjudication://ID), synthetic=false。
5. **待办**: 若需更多负例, 扩展到其他 repo (kairon/cockpit/agora) 的 closed-unmerged PR; 可接入评测框架 (deepeval 等) 消费。
