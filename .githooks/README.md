# Git Hooks (主仓)

## pre-push — 子模块自动同步

主仓 push 前自动把"本地领先远程"的子模块 push 上去,让 gitlink 可达,防 CI 悬空。

**病根**:自动化 agent (OMC/autopilot) commit 子模块 + bump 主仓指针却不 push → 主仓 gitlink 指向子模块远程没有的 commit → CI `submodules: recursive` 拉不到 (`not our ref`) → 整条 CI 红。(2026-06-17 实测 14/18 子模块悬空)

## 安装 (新 clone 必跑)

```bash
make install-hooks
```

从 `.githooks/pre-push` 复制到 `.git/hooks/pre-push`。

同步逻辑见 [`bin/sync-submodules-push.sh`](../bin/sync-submodules-push.sh)。
