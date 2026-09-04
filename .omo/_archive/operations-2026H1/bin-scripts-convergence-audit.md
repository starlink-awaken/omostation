---
status: superseded
lifecycle: contract
owner: runtime-team
last_updated: 2026-08-22
review-state: metadata-only
title: bin/scripts 收敛审计
type: doc
---

# bin/scripts 收敛审计

> **已退役** (2026-08-21): `scripts/bin/` 工具已迁移到 `bin/`，scripts 仓库已 archive。
> 本文档保留作为历史记录。

本审计把三类事实分开：

- `docs/operations/bin-scripts-convergence-manifest.json`：收敛决策 SSOT，记录当前主入口、兼容 shim 或已退休副本。
- `docs/operations/bin-scripts-close-duplicate-exec.md`：执行证据，只有明确标记为 `removed` 的条目才可驱动安全 reconcile。
- 工作树实际文件：最终事实，脚本是否存在必须由文件系统核实。

## 执行

```bash
python3 bin/ssot/bin-scripts-convergence-audit.py --json --check
python3 bin/ssot/bin-scripts-convergence-audit.py --reconcile
```

`--check` 会阻断以下情况：

- manifest key 重复；
- `bin` 主实现缺失；
- 执行报告声称已移除但 `scripts/bin` 副本仍存在；
- 兼容 shim 声明存在但实际缺失；
- 仍标记为待收敛但副本已经被移除，导致 SSOT 过期。

`--reconcile` 只允许两类可证明变更：

- 删除完全重复的 manifest 条目；
- 对“执行报告明确标记 `removed` 且工作树确认脚本不存在”的条目，将动作固化为 `bin-master, scripts-retired`，并保留退休路径和证据来源。

该工具已接入 `bin/gac/gac-local-gate.py` 和 `.omo/_truth/registry/ci-surfaces.yaml`，后续每次 bin/scripts 变更都会重新验证声明、执行和实际文件三层事实。
