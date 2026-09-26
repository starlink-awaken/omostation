---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: 产能轨与知识复用指标口径校准 — dualtrack planned 池陈旧计数与 KOS 死路径归零
bet_id: BET-Y2Q4-T1-04
---

# BET-Y2Q4-T1-04 — 产能轨与知识复用指标口径校准

## 背景与实证（2026-09-26 实测）

1. **产能轨陈旧计数**：`.omo/state/collab-dualtrack.yaml::throughput_track` 声明
   `data_source: 真实 backlog (.omo/tasks/done+planned/)` 并记 `63 planned / 0 done`，
   但 `.omo/tasks/registry/planned/` 物理上仅存 2 个 OBSOLETE 标记文件；
   `.omo/tasks/planned/` 目录不存在。63 是陈旧快照，误导 BRIEF 决策收件箱与双轨纯度检查。
2. **KOS 死路径**：`bin/mof/generate-brief.py` 把"知识复用 KOS 索引篇"计在 `kos/` 目录
   （`ls kos/` → No such file or directory，恒为 0），而真实索引
   `data/kos/kos-index.sqlite` 有 **12,553** 篇 documents 且 2026-09-26 17:41 仍在更新。
3. 产线写入者：`bin/collab/export-dualtrack.py` 产出 collab-dualtrack.yaml；
   消费者：`generate-brief.py` / `check-dual-track-purity.py` / `check-silent-loss.py`。

## 目标

两个指标校准为度量物理现实（D1 禁代理量）：
- planned 池计数改为**可复算的物理枚举**（枚举命令记录在状态文件内）；
- KOS 指标改读 sqlite 真实 documents 计数；
- 若决策收件箱待决卡 `w3w3-planned-status-normalize` 同根源，一并落地其归一规则。

## 写面（write_surfaces）

`.omo/state/collab-dualtrack.yaml`、`bin/collab/export-dualtrack.py`、
`bin/mof/generate-brief.py`、`bin/gac/check-dual-track-purity.py`、
`docs/plans/3y-bet-ledger.yaml`、本 spec、retro。

## 验收（done_when 摘要）

1. dualtrack 计数可复算且同日重算与 BRIEF 产能轨一致；
2. KOS 指标 >0 且与 `sqlite3 ... COUNT(*)` 一致，`kos/` 死路径移除或显式标注；
3. `check-dual-track-purity.py` 通过；
4. retro 记录 before/after 数字与枚举命令。

## 红线（circuit_breaker / non_goals）

- 不得改变指标语义（如重定义 completion_rate 公式）；不得为让指标变好看改口径（D1/D6）。
- 不触碰 `.omo/tasks/**` 任务文件本体、`config/**`、kos-index.sqlite 数据。
- 不铸造业务首单（由 BET-Y2Q4-T4-01 承接）；不重写 KOS 索引器。
- 已知 pre-existing：`BET-Y2Q3-T9-01` 的 SPEC_DIGEST_MISMATCH lint 报错不在本 bet 范围。

## verify

- `sqlite3 data/kos/kos-index.sqlite "SELECT COUNT(*) FROM documents;"` → ≥12000，且 BRIEF 指标一致
- `python3 bin/gac/check-dual-track-purity.py` → exit 0
- `python3 bin/mof/generate-brief.py` → 产能轨/知识复用反映物理现实
- `python3 bin/plan/bet-ledger.py lint` → 不引入新错误
- `make gac-local-gate` → exit 0
