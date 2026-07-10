---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-10
related:
  - ../decisions/0179-runtime-probe-false-positive-treatment.md
  - ../../projects/runtime/src/runtime/scheduler.py
  - p73-truth-driven-engineering-pattern.md
  - decl-exec-gap-meta-pattern.md
---

# P76 — Launcher Zombie False Positive Pattern (launchd 保活掩盖子服务死亡)

> **适用范围**: launchd/docker KeepAlive 管理的 daemon, launcher 进程被保活但实际服务子进程已崩溃, 导致健康探测假阳性.
>
> **ADR**: [0179-runtime-probe-false-positive-treatment](../decisions/0179-runtime-probe-false-positive-treatment.md)
> **SSOT**: `projects/runtime/src/runtime/scheduler.py` (`_check_launchd`, `_check_log_freshness`)
> **GaC 规则建议**: `CR-RUNTIME-PROBE-TRUTH` (待 governance-team 审批)

## 症状 (识别特征)

1. 健康分/状态报 `running`/`healthy`, 但实际服务无响应 (curl HTTP 000, 端口无监听)
2. `launchctl list <label>` 报 PID 存在, 但该 PID 对应进程不监听任何服务端口
3. **uptime 造假实锤**: uptime 跨 scan 累积, 可能超过机器开机时间 (物理不可能)
4. 日志 heartbeat 停止更新 (进程卡死) 但 launchd 仍报 PID
5. self-heal 反复 stop/start (restart_history 满) 但服务始终起不来 — 确定性故障死循环

## 根因

launchd KeepAlive 机制保活的是 **launcher 进程** (uv/python/node), 而非实际服务:

```
launchd plist → uv run python -m service   (uv = launcher, service = 真服务)
                ↓ service 子进程崩溃退出
                uv 不退出 (或被 KeepAlive 拉起)
                ↓ launchctl list 永远报 PID (uv 的 PID)
探测器只验 launchctl PID → 永远报 running (假阳性)
```

## 治法 (3 层, 对应 ADR-0179)

### 1. 探测交叉校验 (必做)
launchd/docker 报 `running`/`idle` 时, 必须叠加真活校验, 不能只信 PID:
- **HTTP/SSE 服务**: `port_listening` (lsof) + `health_check` (HTTP), 任一不符 → 降级 `degraded`
- **stdio 服务** (无端口, 如 MCP ProxyManager): 日志新鲜度 `_check_log_freshness(log_path, max_age)`, heartbeat mtime 陈旧 → 降级

### 2. uptime 防造假
`running_since` 跨 scan 持久化累积, 降级时 `pop` → uptime 不再对死服务累积. 防止 "死服务 uptime 比机器开机还长" 的荒谬数据.

### 3. unrecoverable 死循环防护
确定性故障 (ImportError/配置错) 重启不可能修复. 服务持续未 healthy 超绝对时长 (如 30min) → 标 `unrecoverable`, 停止 self-heal. 区别于 `FROZEN_CRASH_LOOP` (5 分钟窗口), 用绝对时长兜底长周期死循环.

## 实例

**agora-gateway (2026-07-10, 本 pattern 的发现案例)**:
- launchctl 报 `com.agora.gateway` PID=1897 running (uv launcher 被 KeepAlive 保活 4.67天)
- 但 mcp_gateway 子服务崩了 (import 断裂 exit 256), 7430 端口无监听
- 原 `_check_launchd` 只看 PID → 报 running, uptime 7.9天 (超机器开机 4.67天, 造假实锤)
- 治本: 配 `log_path` + `_check_log_freshness` 交叉验 heartbeat + 修 import 根因

**hermes-gateway (死循环案例)**:
- exit 113 确定性故障, self-heal launchctl stop/start 无限重试
- 实测持续 failed 521109s (6天) 仍在死循环 (restart_history 满)
- 治本: `unrecoverable` 判定 (last_healthy 超 30min) 终结死循环

## 防重蹈检查清单

- [ ] 新增 launchd daemon 时, 注册 `port` 或 `health_url` 或 `log_path` (至少一项真活信号)
- [ ] 探测器禁止仅凭 launchctl PID 判 running (见 GaC 规则建议 CR-RUNTIME-PROBE-TRUTH)
- [ ] 健康分计算前, 交叉验证声明态 (system_health.yaml) 与实测态 (lsof/launchctl)
- [ ] 重构 "consolidate/remove dead code" 类 commit 后, 必跑入口 import 链 (不只单测)

## 关联

- `verify-claim-three-layers` (三层验证, 避免 grep 假阴性 — 本次 debt.yaml 误判空集的教训)
- `decl-exec-gap-meta-pattern` (声明/执行鸿沟 meta pattern, 本 pattern 是 runtime 探测层的鸿沟实例)
- `p73-truth-driven-engineering-pattern` (实证驱动, 不凭路径直觉判存在性)
