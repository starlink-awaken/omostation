---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-27
risk_level: L2
type: ssot
last_updated: 2026-09-03
---

# Versioned accepted Workspace release for Documents cutover

## Objective

为宿主 schedule 提供一个不依赖共享 dirty checkout 的稳定 Workspace release
根。release 必须对应已合并 root main，保留可验证的 root/child commit 与子模块
指针；candidate schedule 使用该 release 根运行两个已通过 owner smoke 的任务。

## Contract

- release root: `$HOME/.local/share/omostation/accepted-20260827`。
- release checkout is detached/read-only for runtime use; no runtime task edits
  its source tree.
- candidate commands use the release root for code, Documents remains the explicit
  read root, and evidence/logs stay under the release's runtime/evidence roots.
- record root commit, child pointers, release path, owner smoke output and SHA-256
  in the evidence report.
- this BET does not delete or mutate the old release (none exists), shared
  Workspace, Documents, LaunchAgents, or crontab.

## Acceptance

1. release contains the merged owner entrypoint and both implementation modules.
2. both owner smokes run against live Documents and return structured findings,
   not entrypoint/import errors.
3. candidate schedule contains no shared Workspace code path and remains marked
   NOT INSTALLED until the separate cutover operation.
