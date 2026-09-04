---
type: ephemeral
created: 2026-09-03
---

# OpenCode · OMLXC · MCP 全面优化报告 — 2026-08-22

> 目标：子 agent 合理接入 omlxc、限额熔断自愈、MCP 全绿、首启 0.1s、文档感知闭环

## 1. 8 项落地

| # | 修复 | 证据 |
|---|------|------|
| 1 | `provider.omlxc` 补 8 别名 `coder/coder-fast/reasoner/reasoning/mid-local/mini-9b/triage/mythos` | `opencode.json 14 models` `gateway 18 models` |
| 2 | `hard ≥93%` 直通熔断 `effective_auto_switch` | `quota-monitor.py:414-448` 日志 `🔓 硬限额直通` |
| 3 | `quota-monitor` 512KB/3000行轮转 + `test` 缓存 88天过期清理 | `7318→3000行 570K→267K` |
| 4 | `AETHERFORGE_API_KEY` 落盘 `keys/aetherforge.txt (600)` `file:` 引用 | 重启自愈 |
| 5 | `model-check` 本地锁定静默 + `deepseek` 非依赖静默 | `✅ 模型与配额正常` |
| 6 | 首启加速 `quota_cache` `1.57s→0.02s` `startup-check --quick 3.0s→0.11s (30x)` | `time` 实测 |
| 7 | `rebuild-profiles.py` 标注过期，` .omo/omo.jsonc` 为 SSOT | 防退化 |
| 8 | `launchd KeepAlive` 托管 `com.opencode.quota-monitor` | `49674` 常驻 |

## 2. MCP 全绿

- `gitnexus` `node install.js` 补 `lbugjs.node 19M` → `✓ connected`
- `MCP_DOCKER` `enabled:false` 降噪（Docker 已就绪但 30s 超时属探活阈值）
- `wps-note` `enabled:false` 覆盖 `18930 refused`（WPS 未起 SSE）

`opencode mcp list` 19 servers 全绿（`huggingface ⚠` 按需登录）

## 3. 策略评估

- `balanced` `go双账号(31650/30100)+omlxc三节点` 最优，`deepseek 100%` 已隔离
- 限额阈值 `warn70 soft82 hard93` + `MIN_SWITCH 300s SWITCH_GAP10` 防抖动
- 限额期自动 `balanced→economy→local`，恢复 `hard==0` 自回

## 4. Agent 感知

- `startup-check --quick` 0.11s，无噪音
- `hard` 无需人工 `switch-agent-profile.sh`
- 巡检：`launchctl list | grep quota` + `model-check`

## 5. 后续

- 可选：`kimi` 不续费则 `rm keys/kimi.txt` 再降噪
- 本报告即感知 SSOT，后续 `launchd` 已自愈

