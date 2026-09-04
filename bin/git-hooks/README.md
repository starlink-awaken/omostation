---
owner: governance-team
last_updated: 2026-09-04
type: ssot
last_updated: 2026-09-04
---

# bin/git-hooks — 活跃 git hooks 的版本化源码

`.git/hooks/` 不受版本控制（已有 .legacy/.bak 多次手工改痕迹）。
本目录是活跃 hook 的入库副本，改动走 PR；部署方式：

```bash
cp bin/git-hooks/pre-commit  /Users/xiamingxing/Workspace/.git/hooks/
cp bin/git-hooks/post-checkout /Users/xiamingxing/Workspace/.git/hooks/
chmod +x /Users/xiamingxing/Workspace/.git/hooks/{pre-commit,post-checkout}
```

- `pre-commit`: submodule-guard 含 P97 gitlink 可达性前置（悬空当场拦，
  动态枚举全量子模块——原硬编码 3 个是 12 子仓裸奔漏洞）
- `post-checkout`: M3 orphan 保护 + P96 checkout 追溯（.omo/locks/checkout-log.tsv）
