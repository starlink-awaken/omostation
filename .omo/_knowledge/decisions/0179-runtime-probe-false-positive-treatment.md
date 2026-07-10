---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-10
related:
  - 0178-p79-phase5-closeout.md
  - ../patterns/p76-launcher-zombie-false-positive.md
  - ../../projects/runtime/src/runtime/scheduler.py
  - ../../projects/agora/src/agora/mcp_proxy/manager.py
  - ../../projects/agora/src/agora/core/service_base.py
supersedes: []
---

# ADR-0179: runtime 探测假阳性根治本 (launcher-zombie + import 断裂 + self-heal 死循环)

> **2026-07-10 agora 事件**: 健康分 84 是假的 — agora 全家端口死但报 healthy, bos:// 路由中枢瘫痪无人知晓.
> 根因是 **4 层独立缺陷叠加**, 每层单独看像小问题, 叠加后造成"假绿灯"系统性失效.

## 0. TL;DR

| 层 | 治本 | commit |
|----|------|--------|
| **A·业务** | agora import 断裂修复 (误删 `parse_protocol_config/parse_tags` + entry 跟随迁移) | agora `5068d70` |
| **D·路由** | backend `--package` sanitize (path 依赖非 workspace member) | agora `0f6694b` |
| **探测①** | launchd running 交叉校验 port/health, 不符→降级 `degraded` | runtime `a11906c` |
| **探测②** | stdio-only daemon 日志新鲜度探测 (无 port/health 时) | runtime `d4af19d` |
| **自愈** | `unrecoverable` 判定终结确定性故障死循环 | runtime `2cc6697` |

## 1. 背景: 假绿灯事件

调查起因: 深度理解项目时发现 `system_health.yaml` 声明态与实测态全面矛盾:

- `agora-gateway`: 声明 `running` (launchctl PID=1897), 实测 7430 端口无监听, curl HTTP 000
- `agora-sse`: 声明 `healthy/running/pid=85857`, 实测 launchctl `failed(256)`, pid 不存在
- **uptime 造假实锤**: 声明 uptime 683280s (7.9天), 但 pid etime 仅 4.67天, 且**机器开机才 4.67天** — 服务 uptime 比机器开机还长, 物理不可能
- 健康分 84 建立在这些假数据上, runtime 维度 (权重 0.3) 全是幻觉

## 2. 根因链 (8 层, 自底向上)

```
① 并发 agent 重构 agora (89c5aa7 "consolidate") 误删 parse_protocol_config/parse_tags
② 模块迁移 mcp_gateway→auth.mcp_gateway, 但 pyproject entry + console_script 没跟
③ import 断裂 → com.agora.sse 启动即 ImportError (exit 256)
④ _check_launchd 只验 launchctl PID 字段, 不验端口/HTTP/进程真活
⑤ scan_once 跑了 1238 次, 每次都写假健康数据 (running_since 跨 scan 累积造假 uptime)
⑥ service_online_ratio 基于 PID 判定 → 健康分 84 假绿灯
⑦ KNOWN_BACKENDS 用 --package (workspace member 语法), 但 backend 是 path 依赖 → 20 backend 全 disconnect (自 2026-07-01 共 15522 次)
⑧ self-heal 对 ImportError 确定性故障 launchctl stop/start 无限重试 (hermes 实测死循环 6 天 = 521109s)
```

核心洞察: **健康分不是"算错", 是输入数据本身是假的** — 探测器信任了一个"永远撒谎的证人" (launchd PID). 这比服务挂掉严重得多: 绿灯机制失效, 任何真实故障都会被同样掩盖.

## 3. 决策: 逐层治本

### 3.1 A·业务恢复 (agora import)
- `service_base.py` 补回 `parse_tags` + `parse_protocol_config` (89c5aa7 误删, 但 tools_registry/commands_registry 仍依赖)
- `pyproject.toml` entry `agora.mcp_gateway` → `agora.auth.mcp_gateway` (跟随模块迁移)
- **验证**: com.agora.sse exit256→running, 7431 监听 + curl HTTP 404, 408 pytest passed

### 3.2 探测①·HTTP/SSE 交叉校验 (scheduler.py)
`_check_launchd` 只验 PID 的缺陷, 用交叉校验修正: launchd/docker 报 `running`/`idle` 时, 必须叠加 port/health 校验:
- 有 port 且 `port_listening is False` → 降级 `degraded`
- 有 health_url 且 health_check 非 healthy → 降级 `degraded`
- 降级连锁修正 freshness / uptime (running_since pop, 不再累积造假) / staleness

### 3.3 探测②·stdio 日志新鲜度 (scheduler.py)
agora-gateway (mcp_gateway) 是**纯 stdio proxy** (ProxyManager 通过 stdin/stdout 与 backend 通信), 无 HTTP 端口 — port/health 交叉校验抓不到它.
- 新增 `_check_log_freshness(log_path, max_age=90)`: 日志 mtime 新鲜 (heartbeat 持续更新) = 真活
- 对无 port 无 health_url 的 launchd daemon, 用日志新鲜度交叉校验
- agora-gateway 配 `log_path: ~/.agora/logs/gateway-stdout.log` (heartbeat 每 30s)

### 3.4 D·backend --package sanitize (manager.py)
ProxyManager `_connect_one()` 原地 sanitize `svc["args"]`: 去掉 `--package` 及包名, backend 直接 `python -m MOD` (已 editable 装进 agora venv, import 验证通过). **验证**: ok 0→1, workspace-member 秒崩消除.

### 3.5 B·unrecoverable 死循环防护 (scheduler.py)
确定性故障 (ImportError/配置错) 重启不可能修复. 新增判定: launchd failed 且服务持续未 healthy 超 1800s (30min) → 标 `unrecoverable`, 停止 self-heal. 区别于 `FROZEN_CRASH_LOOP` (5 分钟窗口), 用绝对时长兜底长周期死循环. **验证**: hermes 6 天死循环终结.

## 4. GaC 规则建议 (待 governance-team 审批)

> ⚠️ GaC 处于 freeze 状态 (ADR-0178, max_rules:173, exemption 需 ADR + governance-team approval). 本 ADR 不擅自加规则, 仅登记建议供审批.

- **规则建议① (建议注册名: `RUNTIME-PROBE-TRUTH`, 未注册)**: runtime 健康探测禁止仅凭 launcher (launchd/docker) PID 判定 running; 必须交叉校验端口监听 / HTTP health / 日志新鲜度 (对 stdio 服务), 命中不符降级 degraded.
- **规则建议② (建议注册名: `DECL-EXEC-CONSISTENCY`, 未注册)**: `system_health.yaml` 声明的 `port_listening`/`status` 必须与实时 lsof/launchctl 交叉一致, 不一致 = drift.

## 5. 残留 / 下一层 debt

- **D 剩余 19 backend** "Subprocess disconnected": `--package` 已修 (ok 0→1), 剩余是 mcp_server 启动/MCP 握手层, 独立 dig
- **bos-services.yaml drift**: 3 个 kos 服务定义错 (rest-api 缺 http_url, graphrag/mcp-v2 无效 transport) — `test_default_registry_is_valid` fail, 预存
- **6 个预存 gitlink 悬空** (aetherforge/cockpit/ecos/l4-kernel/metaos/omo): 并发 agent 残留
- **docker 分支 unrecoverable 一致性**: 本 ADR 只包裹 launchd 分支, docker 分支结构类似可后续补 (当前无 docker daemon 触发)

## 6. 教训 (防重蹈)

1. **"重构 consolidate" 类 commit 必须验证 import 链完整**: 89c5aa7 删函数时没跑 `python -c "from agora.server.tools_registry import register_registry_tools"`, 单测绕过了 mcp 启动路径
2. **launchd KeepAlive + launcher 进程 = 健康探测陷阱**: launcher 不死, launchctl 永远报 PID, 探测必须穿透到端口/HTTP/日志层
3. **健康分基于探测, 探测失真则全链失真**: 假绿灯比红灯危险 (红灯至少触发响应)
4. **声明/执行鸿沟要用实证交叉验证**: memory `verify-claim-three-layers` + `decl-exec-gap-meta-pattern` 的又一次应验
