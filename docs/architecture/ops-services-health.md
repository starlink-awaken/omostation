# ops services 健康状态说明 (BET-Y1Q4-T14)

> **关联**: BET-Y1Q4-T14 (ops services 清理立项)
> **生成**: 2026-09-09

## 概述

omostation ops 服务注册表 (`.omo/_truth/registry/services.yaml`) 当前包含 **338 个服务**,分为 4 类:

| 状态 | 数量 | 含义 |
|---|---|---|
| `healthy` | 4 | 实时运行, 探测通过 |
| `stale` | 306 | 注册但很久未探测 (大多是 cron/agent 进程, 默认非持续运行) |
| `missing` | 20 | 注册但本机 entrypoint 不存在 (本地未装) |
| `disabled` | 8 | 显式禁用 (status=disabled) |
| **合计** | **338** | - |

> ⚠️ "20 missing" 是设计如此 — 声明面 (服务注册) 与实际部署面 (本机 entrypoint) 分离。
> 大部分 missing 是 omlxc/lmstudio/searxng/aetherforge.gateway 等外部可选依赖, 主仓不预装。

## 20 missing 服务清单

| 服务 ID | 类型 | 缺失原因 |
|---|---|---|
| `lmstudio.server` | external | 本机未装 LM Studio (~/.lmstudio/bin/lms 不存在) |
| `omlxc.daemon` | external | 本机未装 omlxc daemon |
| `omlx.dma_daemon` | external | 同 omlxc, 需要额外依赖 |
| `omlx.gateway` | external | omlx 网关未装 |
| `omlx.gateway-ui` | external | omlx 网关 UI 未装 |
| `omlx.autopilot` | external | omlx autopilot 未装 |
| `omlx.autostart` | external | omlx autostart 引导未装 |
| `docker.searxng` | docker | searxng 容器未启动 |
| `aetherforge.gateway` | external | aetherforge 网关守护进程未装 |
| `omo.sse_daemon` | port-conflict | 端口 7432 与 omlxc.daemon 冲突 |
| `mcp.omo_web` | runtime | 未启动 (mcp_gateway 需 server 模式) |
| `cron.*` (多) | cron | 多个 cron 服务在本机无对应 launchd plist |

(以上为批次 10 整理的子集, 完整列表 `cockpit ops validate` 输出)

## 修复优先级

### P2 (本季度清理)
- **cron.* missing (多)**: 8 个 cron 服务 launchd 标签缺失导致 scheduler 永久 false-positive
  - 跟踪: PITFALL-ENV-002 (matrix.yaml 退役服务遗留)
  - 修复: 启动对应 cron 或从注册表移除
- **port-conflict (omo.sse_daemon vs omlxc.daemon)**: 选择一个停掉

### P3 (不修)
- **外部服务 missing** (lmstudio/omlxc/searxng/aetherforge 等): 可选依赖, 不安装不算问题

## 命令改进建议

### 批次 10 后续 (BET-Y1Q4-T14)

1. **ops status 默认隐藏 missing**: 减少噪声 (`cockpit ops status` 默认显示 healthy + stale + disabled, missing 仅在 `--show-missing` 时显示)
2. **required vs optional 分类**: 在 services.yaml 加 `required: true/false` 字段, 默认过滤 optional
3. **ops validate 改为 cron 检查**: cron 服务缺失改为警告而非错误

### 修复方式

- **真修复**: bin/ops/cli.py 加 `--show-missing` flag + services.yaml 加 `required` 字段
- **跨仓协作**: cockpit 仓改 cmd_ops dispatcher + 主仓 bin/ops/cli.py 加 flag

## 关联 PR

- BET-Y1Q4-T14 跟踪 ops services 清理
- 完整状态: `cockpit ops validate` (报告 11 项 configuration issues, 跨 6+ 类型)
