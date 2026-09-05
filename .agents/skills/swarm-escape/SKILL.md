---
title: Swarm Escape
type: skill
owner: governance-team
version: "1.0"
status: active
triggers:
  - git hook blocked
  - CI failure bypass needed
  - emergency state sync
---

# swarm-escape — 蜂群逃生口

> 将 AGENTS.md §1.3 Swarm 逃生口规则转为可执行 skill

## 唯一逃生口

```bash
SWARM_ESCAPE_ID=<your-id> <command>
```

## 使用场景

| 场景 | 命令 |
|------|------|
| chore(state) 需直连 main | `SWARM_ESCAPE_ID=xxx git push origin main` |
| CI 预检需跳过 | `SWARM_ESCAPE_ID=xxx CI_LOCAL_SKIP=1 git push` |
| 子模块 ancestry 回退 | `SWARM_ESCAPE_ID=xxx git push --force` |

## 规则

1. **必须记录 fingerprint** — 逃生操作记入 `gate-known-debt.yaml`
2. **目标率 <5%** — 超过说明流程有问题
3. **shrink_only 策略** — 已知债只减不增

## 指纹记录

逃生后自动记录:
```yaml
- id: <your-id>
  timestamp: <ISO8601>
  reason: <justification>
  command: <executed-command>
```

## 相关

- AGENTS.md §3 — Git & Submodule Discipline
- `.omo/_truth/registry/gate-known-debt.yaml` — 已知债登记
- `.githooks/pre-commit` — 自动化检查
