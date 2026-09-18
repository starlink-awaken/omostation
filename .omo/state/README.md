---
type: ssot
owner: governance-team
last-reviewed: 2026-09-18
---

# .omo/state/ — Agent 共享状态

> 所有 Agent 共享的运行时状态。每个 Agent 维护自己的状态文件，`system.yaml`
> 为聚合快照；当前推荐通过自动化脚本同步，而不是手工编辑计数。

---

## 目录结构

```
state/
├── README.md            ← 本文件
├── system.yaml          ← 系统全局状态（聚合快照）
├── health.yaml          ← 治理健康分（c2g.strategy 合成）
├── system_health.yaml   ← 运行态快照
├── runtime/             ← 运行时投影面（ADR-0129，gitignored，需投影生成）
└── <domain>/            ← 各域状态目录（scene-cards/、handoffs/、proposals/ …）
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
# system.yaml (经 `make ssot-sync` → `bin/ssot-watcher.py sync` 追踪变更)
current_phase: 2
current_sprint: 2
health_score: 75.0  # 示例值, 实际见 .omo/state/system.yaml (SSOT, 勿在文档硬编码)
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

Use the automation instead of manual count edits:

```bash
make ssot-sync   # → bin/ssot-watcher.py sync（交互输入 author/reason，变更记入审计日志）
```
