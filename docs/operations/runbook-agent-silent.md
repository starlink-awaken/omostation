# Runbook: Agent 静默排查

## 症状
- Dashboard 显示 agent status = silent
- 任务长时间无进展

## 排查

### 1. 检查进程
```bash
pgrep -fl signal-poller agent-tick governance-scanner
```

### 2. 检查 launchd
```bash
launchctl list | grep omostation
```

### 3. 查看日志
```bash
tail -50 ~/.omo/logs/agent-tick.log 2>/dev/null
```

### 4. 重启
```bash
# 重新加载 launch agent
launchctl unload ~/Library/LaunchAgents/com.omostation.agent-tick-daemon.plist
launchctl load ~/Library/LaunchAgents/com.omostation.agent-tick-daemon.plist
```

## 预防
- Dashboard `--watch` 模式持续监控
- CI 检测 agent 健康度
