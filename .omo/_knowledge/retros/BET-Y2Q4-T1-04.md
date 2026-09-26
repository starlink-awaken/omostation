---
schema: md/v1
status: completed
lifecycle: history
owner: governance-agent
last-reviewed: 2026-09-26
type: retro
schema_version: retrospective/v1
title: "BET-Y2Q4-T1-04 Closeout Retro — 两个 BRIEF 指标与物理现实脱节的校准"
bet_id: BET-Y2Q4-T1-04
created: "2026-09-26"
run_id: 20260926T110649Z-governance-state-mutation-de800e71
---

# BET-Y2Q4-T1-04 Closeout Retro

> **TL;DR**: BRIEF 两个指标与物理现实脱节。产能轨 `63 planned / 0 done` 是陈旧快照
> （写出口径枚举 `.omo/tasks/{done,planned}/`，但状态文件从未随任务归档刷新，物理池
> 实际 11 done / 0 planned）；知识复用 `KOS 索引篇: 0` 是死路径
> （generate-brief.py 读不存在的 `kos/`，真实索引在 `data/kos/kos-index.sqlite`，
> 实测 12,553 篇 + 63 实体）。本次把两者校准为度量物理现实，验证命中 12,616。

## 计划 vs 实际

| 项 | 计划 | 实际 |
|---|---|---|
| dualtrack 校准 | 重导 + 枚举命令留档 | ✅ `refresh_command` 随状态文件落盘；done 11 / planned 0 / silent_loss 0 / selfprod_excluded 1 |
| KOS 指标 | 改读 sqlite | ✅ `data/kos/kos-index.sqlite`；sqlite 缺失时如实报 0（D1 禁代理量） |
| w3w3 卡同根源 | 判定后一并落地 | ✅ 判定为同根源：planned 池物理已空，63 是归档前快照；卡已在 archived/done，前提随本次校准消解，无需再动任务文件 |
| verify | purity PASS / lint 无新错 / gate PASS | ✅ 全过 |

## 改动面（3 文件，全部在 claim 写面内）

1. `bin/mof/generate-brief.py` — KOS 路径 `kos/` → `data/kos/`；sqlite 缺失报 0（原降级扫描 nonexistent 目录恒 0，即 bug 本体）；展示源标签同步。
2. `bin/collab/export-dualtrack.py` — 输出增加 `refresh_command` 透明字段（计数可复算，防陈旧快照复发）。
3. `.omo/state/collab-dualtrack.yaml` — 重导产物（governance_state lane）。

## 验证记录（可复算）

- 产能轨：`python3 bin/collab/export-dualtrack.py --throughput-only` → done=11, planned=0（raw_done 12，Z4 去污剔 1 自产）。
- KOS：worktree 无 gitignored 运行时数据 → 临时 symlink `data/kos → 主 checkout data/kos`，`python3 bin/mof/generate-brief.py` 输出 **12,616**，与 `sqlite3 "SELECT (SELECT COUNT(*) FROM documents)+(SELECT COUNT(*) FROM kos_entities);"` 逐位一致；验证后 symlink 已拆除。
- `python3 bin/gac/check-dual-track-purity.py` → PASS。
- `python3 bin/plan/bet-ledger.py lint` → 7 ERROR 全部 pre-existing（T9-01 digest / T10-16 refs 等历史项），本 bet 0 新增。
- `make gac-local-gate` → PASS（68 checks，ALL GREEN）。

## 事故与自救（诚实记录）

- 验证期间用 `rm -rf data/` 清理临时 symlink 时**误删 worktree 内 12 个受跟踪文件**
  （`data/` 是跟踪目录，仅 `kos/` 子目录被其 `.gitignore` 忽略——先查 `data/kos` 不存在
  误判整个 `data/` 未跟踪）。同刻 `git checkout -- data/` 全量恢复，未入 commit、未推送，
  零外溢。教训：**删目录前先 `git ls-files <dir>` 确认跟踪状态**，`ls` 缺子路径 ≠ 目录未跟踪。

## 失败与指标口径反思

- 指标恒 0 的根因是"指标读死路径 + 降级扫描 nonexistent 目录当合法值"——降级路径没有
  失败语义，读 0 读得心安理得。修复后降级路径显式报 0（=未接入），与 D1 一致。
- 陈旧快照的根因是"状态文件无再生成契约"。`refresh_command` 留档让任何消费者可以一条
  命令复核；未改计数语义（redline 遵守）。

## 后续

- 产能轨现在如实反映"真实 backlog 池为空"——这正是 BET-Y2Q4-T4-01（业务首单候选盘点）
  的立项依据；T4-01 的决策卡落 `.omo/tasks/planned/` 后，本指标将首次度量真实业务任务。
- `kos/` 顶层目录如需恢复语义（篇目表层），归 BET-Y2Q4-T3-02 消费端闭环处理。
