---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# P0-SMART_NOTIFY 设计方案

> 2026-06-06 | 状态: design-locked

## 目标
从"服务挂了只有日志"进化到事件驱动推送 + 每日服务摘要简报。

## 现状分析
- `projects/runtime/scheduler.py` — 健康扫描，检测到状态变化但只写日志
- `projects/runtime/scripts/notify-alerts.sh` — 通知脚本骨架
- `agent-runtime/tools.py` — 有 `send_message` 工具（iLink → WeChat）
- 没有统一的告警通道配置

## 设计方案

### 通知通道
```
通知通道 (按优先级):
  P0: WeChat (通过 Hermes/agent-runtime send_message)
  P1: 本地通知 (macOS Notification Center)
  P2: 日志 (始终)
```

### 事件类型
| 事件 | 级别 | 动作 |
|------|------|------|
| 服务不可达 | P0 | WeChat 推送 |
| 服务恢复 | P1 | 本地通知 |
| 债务到期 | P1 | 本地通知 |
| 每日摘要 | P2 | WeChat 推送 |

### 实施

在 `projects/runtime/scheduler.py` 中:
```
_LAST_NOTIFY: dict[str, float]  # 防重复推送 dedup

def _notify(level, title, body):
    if level == P0 and time_since_last > 300:  # 5min dedup
        subprocess.run([script/notify-alerts.sh, title, body])
```

### 依赖
- `scripts/notify-alerts.sh` — 需要配置 WeChat webhook URL

参考: `scheduler.py`, `notify-alerts.sh`, `agent-runtime/tools.py:send_message`
