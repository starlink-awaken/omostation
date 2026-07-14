---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-06
related:
  - 0152-m4-gac-rules.md
  - 0153-m4-agent-workflows-tools.md
  - 0140-m4-health-score.md
  - 0151-submodule-hygiene-gate.md
  - 0144-m4-cron-hook.md
  - ../../../../.omo/cron/operating-rhythm-crontab
  - ../../../../bin/m4-health-score.py
  - ../../../../bin/check-submodule-hygiene.py
supersedes: []
---

# ADR-0154: M4 OMO cron 集成 (Phase 4)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。
> **Phase 4 of M4→GaC 全面接入**: OMO operating-rhythm cron 扩展。

---

## 0. TL;DR

向 `.omo/cron/operating-rhythm-crontab` 追加 2 条 cron 任务:

| cron 时间 | 命令 | 结果 |
|-----------|------|------|
| daily 09:15 (每日) | `bin/mof/m4-health-score.py --emit` | 派生面 m4-health.json 每日写入 |
| weekly 周一 10:15 | `bin/ssot/check-submodule-hygiene.py --strict` | 子模块卫生周报 |

接在 ADR-0144 `m4-cron-hook.py` 已落地的 OMO 桥接之后。

---

## 1. OMO cron 节奏

### 1.1 Daily 节奏 (09:15)

```cron
15 9 * * * cd "$HOME/Workspace" && uv run --with pyyaml python bin/mof/m4-health-score.py --emit >> runtime/cron/operating-rhythm-daily.log 2>&1
```

- 接人现有 daily status 节奏(09:00 agent-workflow status, 09:05 governance-evolution, 09:10 governance-evolution packages)
- m4-health-score --emit 写派生面 → 被 `M4-HEALTH-SCORE` (ADR-0152 X2/freshness) 监控

### 1.2 Weekly 节奏 (周一 10:15)

```cron
15 10 * * 1 cd "$HOME/Workspace" && uv run --with pyyaml python bin/ssot/check-submodule-hygiene.py --strict >> runtime/cron/operating-rhythm-weekly.log 2>&1
```

- 接入现有 Monday 10:00 MOF 节奏(mof-state-bridge + mof-drift)
- --strict 模式: 找到任何 findings(包括 4 个 submodule-dirty) → exit 1 → cron 告警

---

## 2. 依赖

- 需要 `bin/mof/m4-health-score.py` 在 PATH 中(已在 workspace)
- 需要 `bin/ssot/check-submodule-hygiene.py` 在 PATH 中(已在 workspace)
- 不需要安装 cron(已在主仓 `.omo/cron/` 目录)

---

## 3. 关联

- [ADR-0152](./0152-m4-gac-rules.md) (GaC rules, Phase 1)
- [ADR-0153](./0153-m4-agent-workflows-tools.md) (agent-workflows, Phase 2b)
- [ADR-0140](./0140-m4-health-score.md) (Health Score 量化)
- [ADR-0151](./0151-submodule-hygiene-gate.md) (子模块卫生守门)
- [ADR-0144](./0144-m4-cron-hook.md) (M4 OMO 桥接, 事前)
- [docs/M4-GAC-INTEGRATION-PLAN.md](./../../../../docs/M4-GAC-INTEGRATION-PLAN.md)

---

## 4. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Phase 4, OMO cron +2 条) |
