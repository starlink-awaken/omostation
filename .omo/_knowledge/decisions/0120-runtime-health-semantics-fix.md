---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-07-02
---

# ADR-0120: Runtime 健康监控语义修正与 SSOT 一致性加固

- **Status**: PROPOSED
- **Date**: 2026-07-02
- **Authors**: governance-team (基于 2026-07-02 服务健康根因分析)
- **Supersedes**: 无
- **Superseded by**: 无
- **Related**:
  - [ADR-0119: 系统性优化 Roadmap](0119-systemic-optimization-roadmap-2026h2.md) (S2-5/S2-6 状态监控闭环)
  - [ARCHITECTURE.md §1](../../../ARCHITECTURE.md) (SSOT 边界)
  - `~/runtime/matrix.yaml` (服务注册 SSOT)
  - `protocols/port-registry.yaml` (端口注册 SSOT)

## Context and Problem Statement

2026-07-02 服务健康排查发现: `system_health.yaml` 报告 "2 在线 / 3 离线 / 2 陈旧",
但实时进程检查显示 4/5 daemon 实际正常运行,仅 ollama 真实离线。

根因不是服务故障,而是**监控系统自身的两个系统性设计缺陷**:

### 缺陷 A: `freshness_seconds` 语义混淆 (uptime vs staleness)

`scheduler.py` 的 `running_since` 记录首次检测到 running 的时间戳,一旦写入永不更新。
`freshness_seconds = now - running_since`,实际语义是 **uptime**(运行时长)。

但 `omo_state_schema.py` 的 `summarize_system_health_snapshot` 把 `freshness_seconds > 86400`
判为 stale。**uptime > 1 天 ≠ stale**,反而代表稳定。所有长期运行的服务最终都会被误判。

实测证据 (`scheduler_state.json`):
- `hermes-gateway` / `cron-service`: `running_since` = 2026-06-05, freshness = 26.8 天 → 误报 stale
- `agora-sse` / `agora-gateway`: `running_since` = 2026-07-01, freshness = 19.5h → 暂未超阈值,再过几小时也会变 stale

### 缺陷 B: 服务注册 SSOT 不一致 (matrix.yaml vs port-registry vs 实际架构)

| 服务 | matrix.yaml 配置 | 实际架构 | port-registry.yaml | 矛盾 |
|------|------------------|----------|---------------------|------|
| agora-gateway | `port: 7422` | stdio MCP gateway, 不监听端口 | `7422: agora-mcp-http (env-only)` | 配了 port 但 notes 写 "无 HTTP 端口" |
| ollama | 无 `launchd_label` | Ollama.app 自管 (`com.ollama.ollama`) | — | 有系统 launchd job 但 matrix 未引用, scheduler 标记 unmanaged 不自愈 |
| hermes-gateway | 无 `port`, 无 `health_url` | launchd 保活, 无 HTTP 端口 | — | 无法被判 online (port_listening 永远 false/null) |

缺少一致性校验: matrix.yaml 配了 port 但服务是 stdio、daemon 无 launchd_label 但有系统 launchd job — 这些矛盾无 lint 拦截。

### 健康分数影响链

```
matrix.yaml 配置矛盾                scheduler.py 语义混淆
        │                                  │
        ▼                                  ▼
agora-gateway: port_listening=false   hermes/cron: freshness=26.8天
ollama: unmanaged (无 launchd_label)        │
        │                                  ▼
        ▼                          summarize_system_health_snapshot
omo_state_schema.py                         │
  _RESIDENT_TYPES={daemon}                  ▼
  + port_listening!=True            stale_services=[hermes, cron]
  → offline_services=3              (freshness > 86400)
        │                                  │
        ▼                                  ▼
  online_services=2 (仅 port_listening=True)
  service_online_ratio=0.33 (应 0.80)
        │
        ▼
  system.yaml: health_score 被拉低
```

## Decision Drivers

* 健康分数必须反映真实服务状态, 误报会掩盖真实故障
* `freshness_seconds` 语义必须与其消费方 (`summarize_system_health_snapshot`) 一致
* matrix.yaml 作为服务注册 SSOT 必须与 port-registry.yaml 和实际架构保持一致
* 修复不能引入回归 — 现有自愈机制 (launchd repair, crash-loop detection) 必须保留
* 与 ADR-0119 S2-5/S2-6 (状态监控闭环) 对齐

## Considered Options

### 方案 A: 最小修复 (仅改数据, 不改代码)

1. matrix.yaml: agora-gateway `port: 7422` → `null`
2. matrix.yaml: ollama 补 `launchd_label: com.ollama.ollama`
3. 删除 `scheduler_state.json` 的 `running_since` 字段

**优点**: 零代码风险, 立即见效
**缺点**: 治标不治本 — freshness 语义混淆未修, 下次 running_since 积累到 86400s 后 stale 误报复发; 无防御性 lint 防止配置漂移

### 方案 B: 语义分离 + 配置修正 + 防御 lint (推荐)

1. **Layer 1 (即时)**: 方案 A 的三项数据修正
2. **Layer 2 (架构)**: scheduler.py 分离 uptime/staleness 语义; omo_state_schema.py 修正 stale 判定
3. **Layer 3 (防御)**: 新增 matrix-consistency-lint 校验 SSOT 一致性

**优点**: 根治语义混淆 + 防止复发
**缺点**: 涉及 2 个子模块代码修改 (runtime + omo), 需测试验证

### 方案 C: 重构健康监控体系

用 Prometheus-style 健康模型替换当前 launchd+port 检查, 统一 staleness/uptime/readiness 概念。

**优点**: 彻底解决
**缺点**: 工时巨大 (2-3 周), 远超当前问题所需; 与 ADR-0119 S2 路线冲突

## Decision Outcome

**Chosen option: "方案 B — 语义分离 + 配置修正 + 防御 lint", because 根治语义混淆且工时可控, 同时与 ADR-0119 S2-5/S2-6 对齐。**

### Consequences

* Good: 健康分数反映真实状态; stale 判定基于真实心跳而非 uptime; SSOT 漂移有 lint 拦截
* Bad: scheduler.py / omo_state_schema.py 接口变更需同步更新消费方; matrix-consistency-lint 需纳入 GaC gate

### Confirmation

1. 修复后 `summarize_system_health_snapshot` 输出: online_services=4, offline_services=1 (仅 ollama), stale_services=[]
2. `make gac-local-gate` 含 matrix-consistency-lint 且通过
3. 服务运行 >24h 后 freshness_seconds 不再触发 stale 误报

---

## 实施方案 (diff 级别)

### Layer 1: 即时数据修正 (P0, ~15min, 零风险)

#### 1.1 matrix.yaml: agora-gateway port 修正

**文件**: `~/runtime/matrix.yaml`

```diff
     - name: "agora-gateway"
       type: "daemon"
       launchd_label: "com.agora.gateway"
-      port: 7422
+      port: null
       status: "running"
       health_url: null
       notes: >
         Agora MCP Gateway (I0). 后台服务注册, 无 HTTP 端口.
```

**理由**: agora-gateway 是 stdio MCP gateway (`agora.auth.mcp_gateway`), 设计上不监听端口。
port-registry.yaml 中 `7422: agora-mcp-http (env-only)` 是另一个服务 (HTTP transport 预留),
与 agora-gateway 不是同一个东西。matrix.yaml 配 port: 7422 是过时配置。

#### 1.2 matrix.yaml: ollama 补 launchd_label

**文件**: `~/runtime/matrix.yaml`

```diff
     - name: "ollama"
       type: "daemon"
+      launchd_label: "com.ollama.ollama"
       port: 11434
       health_url: "http://localhost:11434/api/tags"
       status: "idle"
       notes: >
         Local LLM runtime. Required by gbrain for embeddings.
-        Not managed by launchd or brew.
+        Managed by Ollama.app launchd (com.ollama.ollama).
```

**理由**: Ollama.app 自带 launchd job (`com.ollama.ollama`), 当前 PID=- (未运行)。
补充 launchd_label 后 scheduler 可检测其状态并在 down 时标记 unhealthy (而非 unmanaged),
为后续 autoheal 集成铺路。

#### 1.3 scheduler_state.json: 清除污染的 running_since

**文件**: `~/runtime/scheduler_state.json`

```diff
   "running_since": {
-    "hermes-gateway": 1780642947.343405,
-    "agent-runtime": 1780642947.343405,
-    "cron-service": 1780642947.343405,
-    "agora-gateway": 1782889214.27097,
-    "agora-sse": 1782889320.697134
+    "hermes-gateway": null,
+    "cron-service": null,
+    "agora-gateway": null,
+    "agora-sse": null
   },
```

**操作**: 实际执行时删除 `running_since` 整个键, 下次扫描时 `state.setdefault("running_since", {})`
会重建为空 dict, 所有服务重新初始化 uptime 基线。

**理由**: 当前 running_since 中 hermes/cron 的值是 2026-06-05 (26.8 天前), 是首次扫描时写入的。
虽然 Layer 2 会修复语义, 但清除旧值确保 Layer 2 修复后 freshness 从 0 重新计算。

---

### Layer 2: 架构语义修正 (P1, ~2h, 中风险)

#### 2.1 scheduler.py: 分离 uptime_seconds 与 staleness

**文件**: `projects/runtime/src/runtime/scheduler.py`

**修改点 1** (L333-340): `freshness_seconds` → `uptime_seconds` + 新增 `last_healthy_at`

```diff
             # Freshness seconds for state reporting
             running_since = state.setdefault("running_since", {})
+            last_healthy = state.setdefault("last_healthy", {})
             if rt == "running":
                 if svc.name not in running_since:
                     running_since[svc.name] = current_time
-                result["runtime"]["freshness_seconds"] = int(
+                result["runtime"]["uptime_seconds"] = int(
                     current_time - running_since[svc.name]
                 )
+                # Track last time service was confirmed healthy (for staleness detection)
+                last_healthy[svc.name] = current_time
+                result["runtime"]["last_healthy_seconds"] = 0  # just checked, fresh
             else:
                 running_since.pop(svc.name, None)
+                last_healthy.pop(svc.name, None)
+                # If previously healthy but now not running, report staleness
+                result["runtime"]["last_healthy_seconds"] = int(
+                    current_time - last_healthy.get(svc.name, current_time)
+                )
```

**修改点 2** (L357): 保存 last_healthy 到 scheduler_state.json

```diff
         # Save state back
         state["restart_history"] = restart_history
         state["running_since"] = state.get("running_since", {})
+        state["last_healthy"] = state.get("last_healthy", {})
         try:
             with open(state_file, "w") as f:
                 json.dump(state, f)
```

**语义说明**:
- `uptime_seconds`: 服务连续运行时长 (从首次检测到 running 开始)。值越大越稳定。
- `last_healthy_seconds`: 距上次确认健康的时间。0 = 刚检查过 (fresh); 值大 = 可能 stale。
- `_freshness` (monotonic, 内存) 保留不变, 用于 `_check_stale_services` 的实时 staleness 判定。

#### 2.2 omo_state_schema.py: 修正 stale 判定逻辑

**文件**: `projects/omo/src/omo/omo_state_schema.py`

```diff
     for name, service in services.items():
         if not isinstance(service, dict):
             continue
         if service.get("port_listening") is True:
             online += 1
         if service.get("health_check") == "healthy":
             healthy += 1
         elif service.get("health_check") in _UNHEALTHY_STATES:
             unhealthy_services.append(str(name))
-        freshness_seconds = service.get("runtime", {}).get("freshness_seconds")
-        if isinstance(freshness_seconds, int) and freshness_seconds > 86400:
-            stale_services.append(str(name))
+        # Staleness: based on time since last confirmed healthy, not uptime
+        last_healthy_seconds = service.get("runtime", {}).get("last_healthy_seconds")
+        if isinstance(last_healthy_seconds, int) and last_healthy_seconds > 3600:
+            stale_services.append(str(name))
         # offline: 只算常驻服务没监听端口 (非常驻类型按需, 不计离线)
+        # NOTE: daemon 类型若无 port 配置 (如 hermes-gateway, stdio gateway),
+        #       port_listening 为 None, 不应算 offline — 用 runtime.status 判断
         if (
             service.get("type") in _RESIDENT_TYPES
-            and service.get("port_listening") is not True
+            and service.get("port_listening") is not True
+            and service.get("runtime", {}).get("status") not in ("running", "idle")
         ):
             resident_offline += 1
```

**变更说明**:
1. **stale 判定**: 从 `freshness_seconds > 86400` (uptime > 1天) 改为 `last_healthy_seconds > 3600` (距上次健康 > 1h)。真正的 staleness 是"服务在跑但长时间没确认健康", 而非"服务跑了很久"。
2. **offline 判定**: 增加条件 `runtime.status not in ("running", "idle")`。daemon 服务如果进程在跑 (launchd running) 但没有 HTTP 端口 (如 hermes-gateway), 不应算 offline。只有进程也没跑才算 offline。

#### 2.3 向后兼容: 保留 freshness_seconds 别名 (过渡期)

**文件**: `projects/runtime/src/runtime/scheduler.py` (L333 区域)

```diff
             if rt == "running":
                 if svc.name not in running_since:
                     running_since[svc.name] = current_time
                 result["runtime"]["uptime_seconds"] = int(
                     current_time - running_since[svc.name]
                 )
+                # Backward compat: freshness_seconds alias (deprecated, remove in P43+)
+                result["runtime"]["freshness_seconds"] = result["runtime"]["uptime_seconds"]
                 last_healthy[svc.name] = current_time
                 result["runtime"]["last_healthy_seconds"] = 0
```

**理由**: 避免破坏依赖 `freshness_seconds` 字段的下游消费者。过渡期同时输出两个字段,
P43+ 清理时移除别名。

#### 2.4 matrix.yaml: hermes-gateway 补 health_url (可选增强)

**文件**: `~/runtime/matrix.yaml`

```diff
     - name: "hermes-gateway"
       type: "daemon"
       launchd_label: "ai.hermes.gateway"
       port: null
-      health_url: null
+      health_url: "http://127.0.0.1:4001/health"
       status: "running"
```

**理由**: hermes-gateway 当前无 port 无 health_url, 无法被判 online。实测 `lsof` 显示
PID 1248 监听 `localhost:4001` (可能是 hermes 的 HTTP 端口)。补充 health_url 后 scheduler
可做 HTTP 健康检查, 确认服务不仅进程在跑而且能响应请求。

**注意**: 需先确认 `:4001` 确实是 hermes-gateway 的健康检查端点, 而非其他服务。

---

### Layer 3: 防御性 SSOT 一致性校验 (P2, ~3h, 低风险)

#### 3.1 新建 bin/matrix-consistency-lint.py

**文件**: `bin/matrix-consistency-lint.py` (新建)

**校验规则**:

| # | 规则 | 严重级别 | 说明 |
|---|------|----------|------|
| R1 | daemon 类型服务必须有 `launchd_label` 或 `docker_container` | ERROR | 否则 scheduler 标记 unmanaged, 无法监控自愈 |
| R2 | 配了 `port` 的服务, port 必须在 port-registry.yaml 注册 | WARN | 防止幽灵端口 |
| R3 | stdio/scheduled/integrated 类型不应配 `port` | WARN | 除非有 `health_url` 验证 HTTP |
| R4 | `port` 值与 port-registry.yaml 的服务名应语义一致 | WARN | 防止端口归属张冠李戴 |
| R5 | `launchd_label` 引用的 launchd job 应实际存在 | ERROR | 防止引用不存在的 launchd label |

**伪代码**:

```python
#!/usr/bin/env python3
"""Matrix SSOT consistency linter.

Validates ~/runtime/matrix.yaml against:
  - protocols/port-registry.yaml (port registration)
  - launchctl list (launchd job existence)
  - Internal type constraints (daemon must have launchd_label or docker_container)
"""
import json, subprocess, sys, yaml
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
MATRIX = Path.home() / "runtime" / "matrix.yaml"
PORT_REGISTRY = WORKSPACE / "protocols" / "port-registry.yaml"

def load_matrix_services():
    # 复用 runtime.matrix.load_matrix() 或直接解析
    ...

def check_r1_daemon_has_launcher(services):
    """R1: daemon must have launchd_label or docker_container."""
    errors = []
    for svc in services:
        if svc.type == "daemon" and not svc.launchd_label and not svc.docker_container:
            errors.append(f"R1 ERROR: '{svc.name}' is daemon but has no launchd_label/docker_container")
    return errors

def check_r2_port_registered(services, port_registry):
    """R2: port must be in port-registry.yaml."""
    warnings = []
    registered_ports = set(port_registry.get("ports", {}).keys())
    for svc in services:
        if svc.port and str(svc.port) not in registered_ports:
            warnings.append(f"R2 WARN: '{svc.name}' port {svc.port} not in port-registry.yaml")
    return warnings

def check_r3_non_daemon_no_port(services):
    """R3: stdio/scheduled/integrated/mcp should not have port."""
    warnings = []
    for svc in services:
        if svc.type in ("scheduled", "integrated", "mcp", "cli") and svc.port:
            if not svc.health_url:  # health_url implies HTTP is expected
                warnings.append(f"R3 WARN: '{svc.name}' type={svc.type} has port but no health_url")
    return warnings

def check_r5_launchd_exists(services):
    """R5: launchd_label should exist in launchctl list."""
    errors = []
    r = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
    existing_labels = set(line.split("\t")[2] for line in r.stdout.strip().split("\n")[1:])
    for svc in services:
        if svc.launchd_label and svc.launchd_label not in existing_labels:
            errors.append(f"R5 ERROR: '{svc.name}' launchd_label '{svc.launchd_label}' not found in launchctl")
    return errors

def main():
    services = load_matrix_services()
    port_registry = yaml.safe_load(PORT_REGISTRY.read_text())
    errors, warnings = [], []
    errors += check_r1_daemon_has_launcher(services)
    warnings += check_r2_port_registered(services, port_registry)
    warnings += check_r3_non_daemon_no_port(services)
    errors += check_r5_launchd_exists(services)
    # Output
    for e in errors: print(e, file=sys.stderr)
    for w in warnings: print(w)
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
```

#### 3.2 纳入 GaC gate

**文件**: `bin/gac-local-gate.py`

在 `CHECKS` 列表中新增:

```diff
 CHECKS = [
     ...
+    Check(
+        name="matrix-consistency",
+        command="uv run --with pyyaml python bin/matrix-consistency-lint.py",
+        scope="always",
+        description="Matrix SSOT consistency (port-registry + launchd)",
+    ),
     ...
 ]
```

---

## 执行顺序与验证

### 执行顺序

```
Layer 1 (P0, 立即)
  ├─ 1.1 matrix.yaml: agora-gateway port → null
  ├─ 1.2 matrix.yaml: ollama + launchd_label
  ├─ 1.3 scheduler_state.json: 清除 running_since
  └─ 1.4 启动 Ollama.app (恢复 gbrain-index 依赖)
       │
       ▼ 触发一次健康扫描 (health_scan_once)
       │
Layer 2 (P1, 架构修正)
  ├─ 2.1 scheduler.py: uptime_seconds + last_healthy_seconds
  ├─ 2.2 omo_state_schema.py: stale/offline 判定修正
  ├─ 2.3 scheduler.py: freshness_seconds 向后兼容别名
  └─ 2.4 matrix.yaml: hermes health_url (需先确认 :4001)
       │
       ▼ 单元测试 (projects/runtime + projects/omo)
       │
Layer 3 (P2, 防御)
  ├─ 3.1 bin/matrix-consistency-lint.py 新建
  └─ 3.2 gac-local-gate.py 纳入
       │
       ▼ make gac-local-gate 全量验证
```

### 验证清单

| # | 验证项 | 命令 | 预期 |
|---|--------|------|------|
| V1 | ollama 恢复 | `launchctl list com.ollama.ollama` | PID 非 - |
| V2 | agora-gateway 不再报 offline | 触发 health_scan_once 后查看 system_health.yaml | port_listening 字段消失 (port=null) |
| V3 | stale_services 清空 | `summarize_system_health_snapshot` 输出 | stale_services: [] |
| V4 | online_services 修正 | 同上 | online_services: 4 (agora-sse, cron-service, agora-gateway, ollama 或 hermes) |
| V5 | uptime 不触发 stale | 服务运行 >24h 后检查 | stale_services 仍为 [] |
| V6 | runtime 单测 | `cd projects/runtime && uv run pytest tests/ -q` | 全绿 |
| V7 | omo 单测 | `cd projects/omo && uv run pytest tests/ -q` | 全绿 |
| V8 | matrix-consistency-lint | `python3 bin/matrix-consistency-lint.py` | exit 0 (无 ERROR) |
| V9 | GaC gate | `make gac-local-gate` | 含 matrix-consistency 且通过 |

### 风险与回滚

| 风险 | 缓解 | 回滚 |
|------|------|------|
| scheduler.py 接口变更破坏下游 | 保留 freshness_seconds 别名 (2.3) | revert scheduler.py + omo_state_schema.py |
| ollama launchd_label 不匹配 | R5 lint 校验 launchd 存在 | 移除 launchd_label 恢复 unmanaged |
| hermes health_url 端点错误 | 先 curl 确认 :4001/health | 移除 health_url 恢复 null |
| matrix-consistency-lint 误报 | WARN 级不阻断, 仅 ERROR 阻断 | 从 gac-local-gate 移除该 check |

## Pros and Cons of the Options

### 方案 A: 最小修复 (仅改数据)

**优点**: 零代码风险, 15 分钟完成
**缺点**: freshness 语义混淆未根治, 24h 后 stale 误报复发; 无 lint 防止配置再次漂移

### 方案 B: 语义分离 + 配置修正 + 防御 lint (推荐)

**优点**: 根治语义混淆; stale 判定基于真实心跳; SSOT 漂移有 lint 拦截; 与 ADR-0119 S2 对齐
**缺点**: 涉及 2 个子模块代码修改; 需单元测试验证; 工时 ~5h (Layer 1+2+3)

### 方案 C: 重构健康监控体系

**优点**: 彻底解决, 统一健康模型
**缺点**: 工时 2-3 周; 远超当前问题所需; 与 ADR-0119 S2 路线冲突; 回归风险高

## References

- [ADR-0119: 系统性优化 Roadmap](0119-systemic-optimization-roadmap-2026h2.md) (S2-5/S2-6 状态监控闭环)
- [scheduler.py](../../projects/runtime/src/runtime/scheduler.py) (L333-370 freshness 逻辑)
- [omo_state_schema.py](../../projects/omo/src/omo/omo_state_schema.py) (L70-108 summarize 逻辑)
- [matrix.yaml](../../../runtime/matrix.yaml) (服务注册 SSOT)
- [port-registry.yaml](../../../protocols/port-registry.yaml) (端口注册 SSOT)
- [scheduler_state.json](../../../runtime/scheduler_state.json) (持久化状态)
