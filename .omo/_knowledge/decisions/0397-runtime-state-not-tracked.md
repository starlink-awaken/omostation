---
id: ADR-0397
lifecycle: spec
owner: '@Builder'
last_updated: '2026-08-09'
---

# ADR-0397: 运行时状态文件不进git

- status: accepted
- date: 2026-08-08
- owner: architecture-team
- related: ADR-0128 (runtime projection plane)

## Context

`.omo/state/` 有23个运行时产生的文件（alerts.jsonl, signal-poller-state.json, agent-beliefs/index.yaml等）被git tracked。
每次agent tick/signal-poller/alert-handler运行都写这些文件。两个session/branch同时操作时必然冲突，导致git pull永久ABORT。

## Decision

运行时状态文件从git移除（`git rm --cached`），加入`.gitignore`。
保留tracked的只有配置/快照类文件（system.yaml, health.yaml等）。

分类规则:
- **tracked**: 人或系统手动写入的配置（system.yaml, model-driven/*.yaml等）
- **not tracked**: 进程运行时自动产生的状态（*.jsonl, agent-beliefs/, signal-poller-state.json等）

## Consequences

- 正面: git pull/merge不再因运行时文件冲突
- 正面: fresh clone后运行时文件自动产生（agent tick/poller运行即重建）
- 负面: MOS记忆(agent-beliefs/index.yaml)不随git同步——需要备份机制（后续）
