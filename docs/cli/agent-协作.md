---
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-24
type: derived
source: bin/ssot/gen-help-docs.py
---

# Cockpit CLI · 🤖 Agent 协作

> 自动生成于 1970-01-01T00:00:00Z | 分册源自 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)
> 生成器: `bin/ssot/gen-help-docs.py` | 请勿手动编辑

本册收录 **4** 个命令。索引与交叉表见 [docs/CLI-REFERENCE.md](../CLI-REFERENCE.md)。

## `cockpit agent-onboard`

新 Agent 入职 checklist + 环境初始化

**用法**:

```bash
cockpit agent-onboard [flags]
cockpit agent-onboard --json          # 机器可读输出
cockpit agent-onboard --dry-run       # 预检 (无副作用)
cockpit agent-onboard --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit cell`

🤖 AGE-v2 动态 Agent Cell (规划/执行/验证/治理)

**用法**:

```bash
cockpit cell [flags]
cockpit cell --json          # 机器可读输出
cockpit cell --dry-run       # 预检 (无副作用)
cockpit cell --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


## `cockpit resident`

Resident 常驻 Agent 体系 (status/roles/daemon/decision/execute/...)

**用法**:

```bash
cockpit resident [flags]
cockpit resident --json          # 机器可读输出
cockpit resident --dry-run       # 预检 (无副作用)
cockpit resident --help          # 完整参数面
```

  · 所属域: `workflow`  |  成熟度: stable  |  风险: low  |  委派目标: `omo resident`


## `cockpit swarm`

多 agent 实时活动监控 (runs/locks/worktree/冲突)

**用法**:

```bash
cockpit swarm [flags]
cockpit swarm --json          # 机器可读输出
cockpit swarm --dry-run       # 预检 (无副作用)
cockpit swarm --help          # 完整参数面
```

  · 成熟度: stable  |  风险: low


---

*由 `bin/ssot/gen-help-docs.py` 于 1970-01-01T00:00:00Z 生成*