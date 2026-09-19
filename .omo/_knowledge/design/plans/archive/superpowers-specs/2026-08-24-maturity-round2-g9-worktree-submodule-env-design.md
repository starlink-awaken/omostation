---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-08-24
last-reviewed: 2026-08-24
schema_version: specification/v1
spec_version: 1.0.0
bet_id: BET-Y1Q3-T10-09
type: ssot
last_updated: 2026-09-03
---

# Maturity Round 2 — G9: worktree submodule init 策略 + gate 环境感知

> 日期：2026-08-24
> 状态：accepted
> BET：BET-Y1Q3-T10-09
> 上游设计：docs/operations/90pct-maturity-design.md (Round 2, G9)

## 背景与问题

12 个 submodule 未 checkout 时，本地 gate 产生环境性失败（CR-RESIDENT-BOS-01 缺
bos-services.yaml、omo-state-projection-guard 缺投影文件等），被误判为真实缺陷。
gac-worktree.sh claim 已默认 init 全部子模块，但失败路径无"环境感知"提示，
worktree-hygiene 文档也未说明"未 init 子模块 → gate 环境性失败"的识别与修复。

## 架构选择

- `gac-worktree.sh` claim 的 init 失败路径增加**环境感知提示**：列出未 checkout 的
  子模块清单，并说明其导致的 gate 检查（CR-RESIDENT-BOS-01 等）是环境性失败，
  应 init 后重跑，而非当作真实缺陷上报。
- `worktree-hygiene.md` 新增"未 init 子模块的环境性 gate 失败"识别节：症状 → 根因 →
  修复（`git submodule update --init <sub>`）。

## 验收标准

1. **[gac-worktree.sh init 失败有环境感知提示]**
   - 验证方式：grep "环境" bin/gac/gac-worktree.sh
   - 证据类型：失败路径含未 checkout 子模块 + 环境性提示

2. **[worktree-hygiene 含环境性 gate 失败识别节]**
   - 验证方式：grep "环境性" docs/operations/worktree-hygiene.md
   - 证据类型：症状→根因→修复

## 反指标

- 不自动跳过 gate（环境感知是提示, 不降低门禁）
- 不改 gac-local-gate 的检查逻辑

## Decision Log

| # | 分叉 | 裁定 | 理由 |
|---|------|------|------|
| 1 | 自动 init vs 环境感知提示 | 环境感知提示 | init 已有, 缺的是"失败时识别为环境性" |

## 变更历史

| 日期 | 变更内容 | 变更人 |
|------|----------|--------|
| 2026-08-24 | 初始版本 (grill-me 设计树 G9) | agent |
