#!/bin/bash
export PATH=/opt/homebrew/bin:/usr/local/bin:$PATH
export LC_ALL=C
R=starlink-awaken/omostation

echo "########## 关闭 #1206 ##########"
gh pr close 1206 --repo $R --comment "关闭 —— 这个 PR 的全部内容是 9 个 gitlink bump,**实际内容改动 0 行**,而其中 8 个指向被误清空的空 commit(详见上一条评论,约 5,200 个文件)。

T6-01 的真实工作已经在 main 上了:

- \`2f71eb08a feat(T6-01): dynamic GaC rule subtraction — vitality tracking + downgrade engine\` (#1200)
- \`c8e8f398f chore(ledger): mark BET-Y1Q2-T6-01 done\`

所以关掉它不丢任何东西 —— 它只是那次 partial-worktree 事故留下的残渣。

如果之后确实需要 bump 这些子模块,请在**子模块已正确 init** 的环境里重做。#1210 的批量删除闸门今天已合入 main,同类推送会在 pre-push 阶段被自动拦下。" 2>&1 | tail -3

echo
echo "########## 触发 #1207 的 CI(close/reopen) ##########"
gh pr close 1207 --repo $R --comment "重开以触发 CI(此前该分支上没有任何 check 被调度)。" 2>&1 | tail -2
sleep 4
gh pr reopen 1207 --repo $R 2>&1 | tail -2
sleep 12
echo "  --- 重开后状态 ---"
gh pr view 1207 --repo $R --json state,mergeStateStatus --jq '"  state=\(.state) mergeState=\(.mergeStateStatus)"' 2>&1
gh pr checks 1207 --repo $R 2>&1 | head -8
echo CCDONE
