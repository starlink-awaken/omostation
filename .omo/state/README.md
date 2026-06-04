# .omo/state/ — Agent 共享状态

> 所有 Agent 共享的运行时状态。每个 Agent 维护自己的状态文件，`system.yaml`
> 为聚合快照；当前推荐通过自动化脚本同步，而不是手工编辑计数。

---

## 目录结构

```
state/
├── README.md            ← 本文件
├── agents/              ← 每个 Agent 一个 YAML（Agent 自己维护）
│   └── {agent-name}.yaml
├── system.yaml          ← 系统全局状态（聚合快照）
└── locks/               ← 分布式锁（Agent 互斥操作时使用）
```

## Agent 状态格式

```yaml
# agents/minerva_agent.yaml
agent: minerva_agent
status: running              # starting | running | idle | blocked | dead
current_task: T2.3.1         # 当前执行的任务 ID
last_heartbeat: "2026-05-29T14:30:00Z"
eu_balance: 850
capabilities: [deep_research, web_search, paper_writing]
dependencies: [agora, gbrain, eu-pricing]
tools_available: [minerva/search, minerva/research, kos/search]
recent_actions:
  - action: "research topic 'AI regulation'"
    result: PASS
    time: "2026-05-29T14:00:00Z"
errors:
  - time: "2026-05-29T13:00:00Z"
    type: EU_EXHAUSTED
    resolved: true
```

## 系统状态格式

```yaml
# system.yaml (通过 sync-omo-state 自动刷新)
current_phase: 2
current_sprint: 2
health_score: 75.0
active_agents: 3
idle_agents: 1
dead_agents: 0
blocked_tasks: 1
completed_tasks: 12
total_tasks: 24
last_go_nogo: "PASS (2026-05-29T10:00Z)"
```

## Agent 使用约定

1. 心跳：每 30s 更新 `last_heartbeat`（通过更新自己的 agent YAML）
2. 状态变更：开始/结束任务时更新 `status`, `current_task`, `eu_balance`
3. 错误记录：追加到 `errors` 列表
4. 读取全局状态：读 `system.yaml`（不直接读其他 Agent 的文件）
5. 锁：需要互斥操作时，在 `locks/` 中创建锁文件（文件存在=锁定）

## 当前推荐同步方式

Use the automation script instead of manual count edits:

```bash
scripts/sync-omo-state.sh
```

Optional health-score input:

```bash
python3 scripts/sync_omo_state.py --test-output-file /path/to/pytest-output.txt
```
