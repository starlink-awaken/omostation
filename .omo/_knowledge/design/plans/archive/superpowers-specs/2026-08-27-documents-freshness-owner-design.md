---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: human-principal
created: 2026-08-27
last-reviewed: 2026-08-27
bet_id: BET-Y1Q3-T10-24
risk_level: L1
type: ssot
last_updated: 2026-09-03
---

# Workspace-owned Documents freshness audit

## Objective

将 Documents 的控制面保鲜检查下沉到 Workspace owner。新能力只读取
`L4-DOMAIN-REGISTRY.yaml` 指向的域入口和 `STATE.md`，输出不含正文的聚合
evidence；状态、日志和 evidence 只能写 Workspace root。它通过既有
`bin/gac/documents-domain-owner-job.py freshness-audit` 入口暴露。

## Contract

- 默认读取 `DOCUMENTS_CONTENT_ROOT` 或显式 `--documents-root`。
- 域列表必须来自 Documents L4 manifest registry，不重复维护域本体。
- 每个域分别报告 `ok`、`missing`、`invalid` 或 `stale`；聚合结果在任一
  非 `ok` 时返回 exit 1，输入/registry 不可用返回 exit 2。
- 输出 schema 为 `documents.freshness-audit.v1`，只含 domain id、日期、天数、
  status 和 counts，不泄漏正文。
- `--evidence` 必须位于显式 Workspace root 且位于 Documents root 之外；命令
  不得修改 Documents 文件。
- 旧 Documents 脚本和宿主 schedule 本轮不删除、不切换，保持可回滚。

## Acceptance

1. fixture 覆盖全新、逾期、缺失、非法日期、registry path traversal 和
   Documents symlink/非目录。
2. 同一输入输出稳定排序；固定 `--today` 时结果确定。
3. healthy 返回 0，任何真实 freshness finding 返回 1，输入错误返回 2。
4. evidence 只能写 Workspace；测试证明 Documents bytes/mtime 不变。
