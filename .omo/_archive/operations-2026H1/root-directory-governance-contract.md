---
lifecycle: contract
owner: runtime-team
last_updated: 2026-08-17
review-state: maintained
title: 根目录治理契约
type: doc
---

# 根目录治理契约

根目录扫描不是目录美化工具，而是防止代码、运行态、缓存、客户端元数据和临时工作树互相伪装的边界门。

## 分类规则

- `tracked`: 已入库的稳定入口，必须由目录自己的 `README.md` 或 `AGENTS.md` 说明职责。
- `allowed-ignored`: 已登记的运行态、缓存、数据或本机工作面，可以不入库，但必须在策略 SSOT 的 `allowed_ignored_dirs` 中有明确分类。
- `active-worktree`: 目录包含有效的 Git linked-worktree marker。它是并行交付面，不属于根仓源码；生命周期由 Git worktree 管理，不得把它复制进根仓或长期遗留。
- `ignored-unregistered`: 被 Git 忽略但未在策略中登记，必须先判定归属，不能靠扩大通配符消音。
- `untracked`: 未入库且未被忽略，默认阻断。它通常意味着临时副本、误放文件或未完成交付。

## 白名单纪律

`allowed_ignored_dirs` 只登记稳定的运行态类别。IDE、本地客户端和兼容 checkout 必须登记在 `local_surfaces`，同时写明 `owner`、`class`、`lifecycle` 和 `reason`。禁止新增一个覆盖全部隐藏目录的 wildcard。

## 生命周期

- `disposable`: 可由清理任务安全回收，不得作为事实源。
- `local`: 仅服务本机工具，迁移机器时重新生成。
- `transient`: 只允许在明确的迁移、兼容或调试窗口内存在；关闭窗口后应清理。
- `contract`/`runtime`: 由对应 SSOT 或运行时 broker 管理，不能手工改成源码目录。

## 操作与门禁

```bash
python3 bin/ssot/root-directory-governance-scan.py --check --json
make root-directory-governance
```

扫描器会自动识别有效 linked worktree，并继续阻断未知的 ignored/untracked 根目录。发现临时面时，优先回收工作树或把内容迁移到正确子项目；不要为了让门禁变绿而把残留目录加入白名单。

报告 `docs/operations/root-directory-governance-scan.md` 是生成视图，策略文件和实际文件系统才是事实来源。
