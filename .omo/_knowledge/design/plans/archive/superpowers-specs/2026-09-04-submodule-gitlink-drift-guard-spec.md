---
schema_version: specification/v1
spec_version: 1.0.0
title: 子模块 gitlink 漂移自动防护 + sync-check 机制强化
bet_id: BET-Y1Q4-T6-03
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-04
last-reviewed: 2026-09-04
type: ssot
last_updated: 2026-09-04
---

# 子模块 gitlink 漂移自动防护 + sync-check 机制强化（BET-Y1Q4-T6-03）

## 背景（Context）

子模块指针（gitlink）在以下场景可能出现漂移：
1. squash merge 后 SHA 悬空（P97 模式）
2. 本地未提交改动导致 gitlink SHA 与实际 HEAD 不一致
3. sync-check hook 缺少自动 fast-forward 能力

## 目标（Goal）

建立子模块 gitlink 漂移的自动检测与修复机制，防止 P97 squash-SHA 悬空和本地未提交改动导致的 gitlink 不一致。强化 sync-check hook 在 submodule pointer 变更时的自动同步能力。

## 非目标（Non-Goals）

- 不改变现有 submodule-guard 的 fast-forward 校验逻辑
- 不自动 push 子模块变更（仍需人工确认）

## 完成标准（Done When）

1. `bin/ssot/submodule-reachability-gate.py` 增加 gitlink drift 快速检测（本地 vs gitlink SHA 不一致时告警）
2. sync-check hook 增加自动 fast-forward 子模块到 gitlink SHA 的能力
3. `docs/architecture/submodule-sync-sop.md` 记录 submodule 同步 SOP

## 验证标准（Verify）

- `python3 bin/ssot/submodule-reachability-gate.py --source index` exit 0
- `python3 bin/ssot/submodule-reachability-gate.py --help` 正常输出

## 实现范围

| 路径 | 说明 |
|------|------|
| `bin/ssot/submodule-reachability-gate.py` | 核心增强：gitlink drift 检测 + auto fast-forward |
| `docs/architecture/submodule-sync-sop.md` | 文档：submodule 同步 SOP |
