---
title: "runbook-agent-silent"
type: runbook
owner: governance-team
lifecycle: history
last_updated: 2026-08-23
---
# Runbook: Agent 静默排查

## 症状
- Dashboard agents status = silent
- 任务长时间无进展

## 排查
```bash
pgrep -fl signal-poller agent-tick governance-scanner
launchctl list | grep omostation
tail -50 ~/.omo/logs/agent-tick.log 2>/dev/null
```

## 重启
```bash
launchctl unload ~/Library/LaunchAgents/com.omostation.agent-tick-daemon.plist
launchctl load ~/Library/LaunchAgents/com.omostation.agent-tick-daemon.plist
```

## 预防
- Dashboard `--watch` 模式监控
