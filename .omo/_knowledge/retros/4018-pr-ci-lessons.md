---
schema: bet-retro/v1
bet_id: 4018-pr-ci-lessons
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-16
type: ephemeral
---

# 4018 PR CI 教训固化 retrospective

## Q1. What was intended?

4014 窗口 (TASK-B3229A65 A4 收尾) 跟 4016 窗口 (pre-existing test 修复) 都顺利合入,
但 PR #3811 (A4 dedup) 在 CI 上反复 fail, 经历了 3 次重开 PR (#3811 → #3827
→ #3829) 才正确合入 (#3827 merge 成功). 整个过程积累了 3 个值得固化的 PR/CI 教训.

## Q2. What happened?

### 3 个 PR 的时间线

| 时间 | 动作 | 结果 |
|---|---|---|
| 4014 11:30 | push branch agent/governance-agent/a4-cleanup-v2 | PR #3811 |
| 4014 11:30 | CI 跑 13 个 lint, 1 fail: interface-check | 看到 fail 是 cockpit/console/ 子模块 pre-existing 违规, 跟本 PR 无关 |
| 4014 11:30 | 关闭 #3811, push agent/governance-agent/a4-rebase-retry (cherry-pick) | PR #3827 |
| 4014 11:35 | #3827 re-run CI pass → 等合并 | |
| 4014 16:36 | #3827 merge 成功 (commit 21dc2ad10a) | mergedAt 2026-09-16T08:36:51Z |
| 4018 09:30 | 本地 fetch 看 main 仍是 47 jobs + 4 dups (没 reset) | 误以为 PR 没合 |
| 4018 09:35 | reset --hard origin/main, 看到 43 jobs + 0 dups | 明白 PR 已合, 关闭 #3829 (redundant) |

### 3 个具体教训

#### 1. CI lint fail 不一定是本 PR 引入 (PITFALL-COO-004)

PR #3811 的 interface-check 抓 `projects/cockpit/src/cockpit/console/harness_runner.py`
和 `bos_invoker.py` 有 `forbidden direct mutation via .mkdir()` / `.write_text()` 违规.
本 PR 只动 4 个文件 (.omo/cron/registry.yaml, bin/scheduler-compile.py, tests/, retro),
跟 cockpit 子模块完全无关.

查近 5 个 PR 同 lint 状态: #3815 / #3816 / #3817 全部同样 fail. 是 pre-existing.
后续 #3817 修了 cockpit bump 后 re-run 就能 pass.

**为什么会被 PR 抓**: 主仓 CI workflow (governance-check.yml) 跑全仓 lint,
任何 gitlink 子模块的 violation 都会让主仓 PR 失败. 子模块 violation 跟本 PR 无关,
但 CI 不区分.

**正确做法**: PR body 标注 "Known pre-existing failures (unrelated)", 让人审一眼看到;
rebase 到含子模块 bump 的 main, 让 bump 修复覆盖.

#### 2. cherry-pick 跨 base 重放带 parent reverse (PITFALL-COO-005)

cherry-pick 是 "重放 commit 的 diff", 不考虑 target base 跟 commit parent 之间
的关系. PR #3827 第一次提的 commit `ad7c7af5a7` 是 a4-cleanup-v2 branch 上的,
parent `15644ffe6d` 含 T10-151 / T7-01 retro / T7-01 spec 等文件. main 在此期间
已合入这些文件 (PR #3815 / #3818 / #3820 等).

cherry-pick 到 main 最新 (含 T10-151 等) 时, git 试图 "delete from parent, then
add the same" → 实际上 reverse 删除了 main 已有的 T10-151.md / T7-01 spec / ledger 改.

**正确做法**: 跨 base 重放改动, 应该:
1. `git show <old>:<path>` 拿文件内容
2. 在新 base 上 claim worktree + 重做改动 + 重新 commit
3. 验证: `git diff origin/main...HEAD --name-status` 应该只看到新增文件, 不见 "D" 行

#### 3. 本地工作树 ≠ origin/main 状态 (PITFALL-COO-006)

PR #3827 merge 后, 本地 (没有 reset) 看到:
- registry.yaml 47 jobs + 4 dups (没 dedup)
- compile_crontab 旧版本 (含嵌套 cd bug)
- test_scheduler_compile.py 不存在

差点据此在 #3827 之上又开 #3829 做重复改动. `git fetch origin main` 后
发现工作树停留在 fetch 前快照. `git reset --hard origin/main` 才看到真值:
43 jobs + 0 dups + bug 修过 + 测试齐全. PR #3827 的 merge commit 21dc2ad10a 完整覆盖.

**正确做法**: 任何 "main 是不是这样" 判断, 必须先:
- `git fetch origin main` + `git reset --hard origin/main` (想完全同步)
- 或 `git show origin/main:<path>` / `curl https://raw.githubusercontent.com/<owner>/<repo>/main/<path>` (只读单文件)

## Q3. What went well?

1. **3 个 PR 教训可清晰分类成 "pre-existing CI 误判 / 跨 base 重放 / main 真值",
   都是 4014-4018 实证可重现, 有具体 PR 引用作证据 (PITFALL-COO-004 引用 #3811/15/16/17,
   PITFALL-COO-005 引用 #3827 第一次提交, PITFALL-COO-006 引用 #3829 redundant close).
2. **retro Q1-Q5 格式跟 T10-146 / T7-06 / T5-01 一致**, 易搜易 review.
3. **3 个 pitfall YAML 文件直接写, 不走 error-knowledge.py record CLI** (record CLI
   本身有 bug — lookup 报 'int' object has no attribute 'lower', 推测 record 也有
   类似 fuzzy 假阳性问题). 直接写 YAML 跳过了 CLI 的 bug, 但同步绕过了
   `.index.json` 缓存 — 这是 4019 候选改进项 (修 error-knowledge.py lookup bug).

## Q4. What went poorly?

1. **3 个 PR (#3811 → #3827 → #3829) 反复重开浪费了 1 个窗口** (4014 全天).
   第一次 (cherry-pick) 没用是因为 PITFALL-COO-005; 第二次 (#3829 重做) 没用是因为
   #3827 已合, 跟 PITFALL-COO-006 一起. 教训: 行动前先想清楚 "为什么" —
   "PR fail 了, 重开能解决吗?" — 多数情况重开不解决根因, 找到根因 (这次是
   子模块 pre-existing + 跨 base 重放) 才能真正修好.
2. **本地工作树 ≠ main 真值** 现象在 4018 差点导致做错 (开 #3829 重复做 PR #3827 已做的事).
   如果先 reset, 一开始就看到 PR #3827 已合, 直接结束. 浪费 ~30 分钟.
3. **cherry-pick 时没看 diff 就 push**, 是个无脑操作. 应该:
   1. cherry-pick 完
   2. 立即 `git diff origin/<target_base>..HEAD --name-status`
   3. 看 "D" 行 (反向删除) → abort + 重做
4. **error-knowledge.py 工具本身有 bug** (lookup 抛 'int' object has no attribute 'lower'),
   不能直接 record. 4019 候选: 修 bug + 补 3 条 record.

## Q5. What will we do differently?

1. **PR body 模板加 "Known pre-existing failures (unrelated)" 章节**: 让审者一眼看到
   哪些 lint fail 是 pre-existing, 哪些是新引入. PR #3811 当时如果有这章节,
   不用先 close 再 rebase 再开新 PR.
2. **新加 `bin/gac/sync-main.sh` 工具**: 跑 `git fetch origin main && git reset --hard origin/main
   && git status --short` 一行, 4019 候选. 在 .agents/AGENTS.md §5 "Essential Commands"
   列为开工第一步.
3. **写 PR retry SOP** (写进 .omo/standards/): "PR CI fail 时, 先看 fail 是不是本 PR 引入
   (PITFALL-COO-004 检查表) → 是, 修代码; 否, 标 known pre-existing → rebase 到含
   fix 的 main. 不要 close + 重开 (PITFALL-COO-005 风险)."
4. **修 error-knowledge.py lookup bug** (4019 候选): `cmd_lookup` 第 189 行
   `e_tags = set(t.lower() for t in e.get("tags", []))` 在某些 entry tags 是 int
   时抛 AttributeError. 应改成 `tags = e.get("tags") or []; e_tags = set(str(t).lower() for t in tags)`.
5. **改 cherry-pick 操作习惯**: cherry-pick 必跑 `git diff origin/<base>..HEAD --name-status`,
   出现 "D" 立即 abort.

## Evidence

- 改动文件:
  - `.omo/_knowledge/pitfalls/coordination/PITFALL-COO-004.yaml`: +60 (新)
  - `.omo/_knowledge/pitfalls/coordination/PITFALL-COO-005.yaml`: +60 (新)
  - `.omo/_knowledge/pitfalls/coordination/PITFALL-COO-006.yaml`: +60 (新)
  - `.omo/_knowledge/pitfalls/INDEX.md`: +3 行表格 (3 个 PITFALL-COO-*)
  - `AGENTS.md`: §11 Key Patterns 加 3 条新 pitfall 引用
  - `.omo/_knowledge/retros/4018-pr-ci-lessons.md`: +200 (retro Q1-Q5 + evidence)
