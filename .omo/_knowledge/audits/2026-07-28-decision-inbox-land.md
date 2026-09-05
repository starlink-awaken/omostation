---
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-07-28
type: ephemeral
status: archived
---
# 决策 Inbox 落地收口（2026-07-28）

> worktree: `ws-decision-inbox-land-20260728` · branch `work/decision-inbox-land-20260728`
> run: `20260728T091034Z-governance-state-mutation-c8fbd835`
> 人类授权: (1) MOF 追认 A/A/A/A (2) metaos 批准 A/A/B/A (3) 僵尸卡清理

## 落地
| 项 | 结果 |
|----|------|
| MOF D1-D4 | ADR-0240 ACCEPTED · 卡 closed |
| metaos D1-D4 | ADR-0252 ACCEPTED · 卡 closed |
| C1 角色 | closed (ADR-0235+#510) |
| Batch4 | closed (superseded) |
| 物理 hosts/recovery | needs-human:false deferred (ADR-0247) |
| bos-stdio | needs-human:false engineering_debt |

## 未在本 PR 实施
- MOF Phase 1 代码（删 CLI / 迁 schema）— 仅授权，分批另 PR
- metaos Phase 1/2 代码 — 仅授权，分批另 PR
- 关闭远程 PR #513/#516 等 — 合入本 PR 后处理
