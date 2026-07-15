---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-07-15
related:
  - p76-launcher-zombie-false-positive.md
  - decl-exec-gap-meta-pattern.md
  - ../../projects/agora/src/agora/mcp_proxy/health.py
  - ../../projects/runtime/src/runtime/health/agora_gateway_probe.py
---

# P77 — Agora Heartbeat Transport Mismatch (stdio 按需服务被当 daemon heartbeat 验活 → 永久假 dead)

> **适用范围**: agora hub (MCP ProxyManager) 注册的 backend, stdio 按需 spawn 服务被一视同仁用常驻 heartbeat 验活, 导致永久假 dead 噪音淹死真病.
>
> **治本**: PR#375 (agora `a20926a` `_is_transient` + `_tick` 跳过) + PR#363 (runtime probe 三态)
> **家族**: 假信号系统性家族 — 兄弟 P76 (launcher-zombie 假 running), 本 pattern 是 **假 dead** 形态

## 症状 (识别特征)

1. agora-gateway stdout 每 30-90s 刷 `heartbeat_report alive=X dead=Y total=Z`, `dead>0` 持续
2. `heartbeat_auto_remove failures=3 service=<stdio服务>` 循环 (auto_remove 后下次 tick 又注册又 dead)
3. 假 dead 多是 stdio MCP (kos/eidos/minerva/forge/c2g/gbrain/runtime/l4-kernel 等 `uv run` 按需 spawn)
4. cockpit 显示 backend alive/dead 与 runtime `system_health.yaml` 打架 (cockpit `import agora._health_checker`, 共享假 dead)
5. `agora_gateway_probe` PID-only 不数 dead → 健康分假绿灯 (health=100 但 14/20 后端 "dead")

## 根因

agora hub heartbeat 对**所有注册 backend 一视同仁** probe (`get_tools`/client `list_tools`), 但 transport 不同验活语义不同:

```
stdio MCP (bos-services.yaml transport: stdio):
  config = {command: ["uv","run",...], 无 mcp_endpoint}
  调用时 spawn 进程, 调完即退 → 平时无进程
  ↓ heartbeat 每 30s probe
  进程不存在 → get_tools 空 + client None → mark_dead
  ↓ failures 累积
  auto_remove → 下次又注册又 dead → 永久假 dead 噪音

daemon/http/sse (config 有 mcp_endpoint):
  常驻进程 + 端口 → heartbeat probe 真活
```

stdio 按需服务**根本不是常驻 heartbeat 的目标** (调用时才存在), 但 hub 没按 transport 分类, 全当常驻验活.

## 治法 (分层, 对应 PR#375 + PR#363)

### 1. 根因层: hub heartbeat 按 transport 分类 (PR#375, 必做)
`BackendHealthChecker._is_transient(name)`: config 有 `command` 无 `mcp_endpoint` = stdio 按需 = transient.
`_tick` 跳过 transient (不 probe) + 清出之前误判入 `_status` 的 transient + log `heartbeat_skip_transient`.
alive/dead/total 只反映常驻 (daemon/http/sse) backend.

### 2. 探测层: probe 数真业务 dead/total (PR#363)
runtime `agora_gateway_probe` 三态: 0 healthy / 1 unhealthy (PID死|fatal|全死) / 2 degraded (部分后端无响应). parse `heartbeat_report` alive/dead/total, 不再 PID-only 盲.

### 3. 显示层: cockpit schema 对齐 (agent `fdd8c68`)
cockpit L1 matrix schema 对齐 (healthy 键不存在→恒0/N 修复) + fallback 服务表指向真实 HTTP 面.

## 实例

**agora-gateway (2026-07-15, 本 pattern 发现案例)**:
- stdout 每 90s `heartbeat_report alive=6 dead=14 total=20` + 14 服务 auto_remove 循环
- 14 dead 全 stdio MCP (eidos/kronos/minerva/forge/c2g/gbrain/runtime/l4-kernel/aetherforge/model-driven/cron-service/ecos-bos-mounter/sot-bridge-persona)
- 根因: bos-services.yaml 73/159 `transport: stdio`, hub 当 daemon heartbeat
- 治本 PR#375: `_is_transient` 跳过 stdio → heartbeat_report 只报真 daemon → 假 dead 噪音消失
- DRY 兑现: cockpit `from agora.auth.mcp_gateway import _health_checker` → PR#375 改 agora 一处, agora hub + cockpit 显示双受益

**cron-service (两套探测打架)**:
- runtime `system_health` 报 healthy (自身 launchd daemon port 7450)
- agora hub 报 dead (注册为 `command:"cron-service"` stdio, heartbeat 判死)
- 治本 PR#375: cron-service = transient → agora 跳过 → 不再判 dead → 两套探测不再打架

## 防重蹈检查清单

- [ ] 新增 agora backend 时, 按 transport 标注 (stdio `command` vs daemon `mcp_endpoint`)
- [ ] heartbeat/probe 禁止对 stdio 按需服务用常驻验活 (用 `_is_transient` 跳过)
- [ ] 健康分计算前, 区分常驻/按需服务 (按需服务健康 = 调用时能 spawn 响应, 非 heartbeat)
- [ ] 探测层 (runtime/agora/cockpit) 共享 checker 时, 根因改共享处 (DRY), 别各打补丁
- [ ] 假绿灯必查业务指标 (dead/total), `health=100` 可能探测失真

## 关联

- `p76-launcher-zombie-false-positive` (假信号家族兄弟: P76 假 running, P77 假 dead)
- `decl-exec-gap-meta-pattern` (声明面 backend 注册漂亮 vs 执行面 heartbeat transport 错配)
- ADR-0179 (runtime probe 假阳性治本, 本 pattern 是其 agora 延伸)
- PR#375 (agora transport 分类) + PR#363 (runtime probe 三态)
