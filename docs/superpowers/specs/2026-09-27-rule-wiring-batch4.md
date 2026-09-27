---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 规则接线批次四 — 归零收口（真 bug 修复 + B006 启用 + retired 机制）
bet_id: BET-Y2Q4-T10-07
---

# BET-Y2Q4-T10-07 — 规则接线批次四（归零收口）

## 授权链

principal 对批次三遗留 9 条幻影批复「同意，go」：安全组接线（ruff），AGE×5 退役。

## 目标

1. **真 bug 修复**：bin/gac/check-episode-pipeline.py:101 缩进损坏（#4442 迁移工具
   产物，main 上文件不可编译，ast/自测均炸）——dedent 2 行恢复。
2. **B006 启用**：pyproject ruff select 增 "B006"（基线实测 bin/ 零违规，启用免费）
   → CR-PY-MUTABLE-DEFAULT 接线；CR-SEC-EVAL-EXEC 经 ruff S307（已在 select）接线。
3. **retired 统计口径分离**：check-rule-wiring-coverage.py 支持 alias map `retired:`
   清单——弃用/收窄/并入决策的条目从"未引用候选"分离，单独计数（可见性保留）。
4. **归零**：AGE×5 + BIN-RETIREMENT + L2-TASK + L0-SSOT-PATH-NORM + X1/X2 + 
   EVIDENCE-DECLARED 共 11 条入 retired；coverage 未引用 = **0**。
5. --strict shadow 起跑（retro 记录）；DEBT-20260920 关单待 shadow 周期。

## 红线

- retired 条目仅从接线候选统计分离，声明条目保留在注册表（可见性不灭）；
- 缩进修复最小化（2 行 dedent），不改 SH-9 迁移的逻辑语义（自测 + SH-5.2 guard 验证）；
- B006 启用前基线为零违规（已实测），不引入新红。

## 验收

1. check-episode-pipeline.py ast 可编译 + --self-test rc=0；
2. pyproject 含 B006，ruff 全扫 rc=0；
3. coverage unreferenced = 0，retired 计数 = 11 可见；
4. lint 0 新增 / gac-local-gate PASS；
5. retro 固化（含 --strict shadow 起跑与 DEBT 关单条件）。
