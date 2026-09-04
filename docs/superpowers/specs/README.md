---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# Superpowers Spec Registry

本目录存放 `eCOS` 超能力项目的规格说明书（specs），用于约束高风险 bet 的设计和验收。

## Spec 生命周期

每个 spec 经历以下状态流转：

```
draft → accepted → superseded
```

- **draft**：草稿状态，正在讨论和完善
- **accepted**：已通过 grill-me 收束，成为约束性规格
- **superseded**：已被新 spec 替代，保留历史记录

## Spec 模板

新建 spec 时，请复制 `_TEMPLATE.md` 并填写各章节。必含章节：

- **背景与问题**：基于事实的问题描述
- **验收标准**：每条可被命令验证（assertion + evidence_type）
- **反指标**：明确不作为成功度量的指标（对齐蓝图 §20）
- **Decision Log**：grill-me 拷问裁定表（|#|分叉|裁定|理由）

## Grill-me 收束约定

所有 L2/L3 高风险 bet 必须经过 grill-me 收束：

1. 在 spec 中通过 **Decision Log** 章节记录关键分叉的裁定
2. 每条裁定包含明确的理由（基于事实或约束）
3. 避免模糊表述，确保裁定可追溯

## Digest 绑定机制

L2/L3 bet 必须绑定 accepted spec：

1. 在 bet 的 `accepted_specifications` 字段中声明
2. 每条绑定包含：
   - `spec_ref`：spec 文件路径（相对本目录）
   - `content_digest`：spec 文件的 SHA256 哈希
3. `bet-ledger.py lint` 会自动验证文件存在性和 digest 匹配

向后兼容窗口：2026-09-01 起强制。

## 现有 Specs

| 文件 | 状态 | BET | 最后审查 |
|------|------|-----|----------|
| `_TEMPLATE.md` | draft | — | — |
| `2026-08-12-documents-owner-job-design.md` | active | — | 2026-08-13 |
| `2026-08-13-codex-exec-worker-design.md` | active | — | 2026-08-13 |
| `2026-08-13-orchestration-contract-mvp-design.md` | active | — | 2026-08-13 |
| `2026-08-13-personal-capability-mainline-restore.md` | active | — | 2026-08-13 |
| `2026-08-14-codex-acp-stdio-cutover-design.md` | active | — | 2026-08-14 |
| `2026-08-14-supervised-blueprint-control-loop-design.md` | active | BET-Y1Q2-T1-18 | 2026-08-14 |
| `2026-08-14-weijian-sanyi-status-consistency-design.md` | active | — | 2026-08-14 |
