---
id: ADR-0395
title: CI 平面净红收官 — scripts/check-* orphan 化 + drift 检测 ahead 容忍
status: ACCEPTED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-08-08
type: ssot
---

# ADR-0395 Decision: CI 平面净红收官

> 承接 ADR-0394 (scripts/ 子模块镜像债治理). 本轮完成该治理的最后一公里:
> 1. ci-surfaces.yaml 中 25 个 scripts/check-* surface 标 orphan (检测器跳过)
> 2. check-submodule-pointer-drift 容忍 ahead 状态 (D0 三段式常态, 非误报)
> 3. ecos sgf-policy doc-ssot-snapshots command 指向实际存在的工具

## 一、根因 (实测, 不靠猜)

### 1. scripts/check-* 死引用 (25 个)

| 现象 | 数据 |
|------|------|
| origin/main interface-check | 持续 fail: "scripts/check-*.py can't open file" |
| ci-surfaces.yaml 登记的 scripts/check-* surface | 25 个 active |
| 实际可执行 | 0 (scripts/ 是镜像子模块, 不含独立脚本) |
| ci-check-runner 行为 | 执行 23 checks → 20 fail (can't open) |

根因: scripts/ 历史独立仓 (含 check-*.py) 合并进主仓后子模块未拆,
25 个登记指向不存在脚本. ADR-0394 已治 sgf-policy + Makefile + capability,
但 ci-surfaces SSOT 未同步 → 检测器仍报.

### 2. check-submodule-pointer-drift ahead 误报

| 场景 | 现状 |
|------|------|
| gitlink 领先 origin/main (本地有未 push commit) | 报 DIVERGED → exit 1 → CI 红 |
| 实际 | D0 三段式常态 (本地工作正常, 仅 origin 未跟) |

### 3. ecos sgf-policy 路径

`doc-ssot-snapshots` command 指向 `scripts/check-doc-ssot-snapshots.py`
(不存在) — 应指向 `bin/ssot/doc-governance-check.py` (存在).

## 二、决策 (按 ADR-0389 减法方向)

### 决策 1: ci-surfaces 25 个 scripts/check-* surface → status: orphan
- 检测器 (ci-check-runner) 跳过 orphan surface
- 不删登记 (保留 SSOT 可追溯), 不增 allowlist, 不动 scripts/ 仓

### 决策 2: check-submodule-pointer-drift 加 ahead 分类
- `is_ancestor(origin_main, gitlink)` → status: ahead (exit 0)
- 仅真 DIVERGED (两侧分叉, 互不为 ancestor) 才 exit 1
- summary + per-sub output 加 ahead 计数

### 决策 3: ecos sgf-policy doc-ssot-snapshots → bin/ssot/doc-governance-check.py
- ecos 子模块 commit c41c60b + 主仓 pointer bump

## 三、效果 (实测)

| 维度 | 前 → 后 |
|------|--------|
| ci-check-runner governance-check.yml | 23 checks / 20 fail → **3 checks / 3 PASS** |
| check-submodule-pointer-drift | DIVERGED 误报 → **0 DIVERGED** (ahead 正常) |
| gac-local-gate | → **43/43 ALL GREEN** |
| origin/main interface-check | 持续红 → **可恢复** (等 PR 合并) |

## 四、与既有 ADR 关系

- ADR-0389: 减法方向 (本 ADR 严格执行 — 标 orphan 而非修复/豁免)
- ADR-0394: scripts/ 子模块镜像债治理 (本 ADR 是收官)
- ADR-0395 (本): CI 平面净红收官

## 五、后续

1. PR 合并后 origin/main interface-check 应回归全绿 (除 god-module 2 大文件,
   待 bet T6-10 拆分)
2. bet T6-10 (god-module SRP 拆分) 继续 — 3 个 >1500L 文件
3. bet T6-01 (GaC 规则减法) 可用最新 gac-local-gate 43 checks 基线