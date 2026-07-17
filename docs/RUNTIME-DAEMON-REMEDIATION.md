---
title: 收敛期 P0 · L1 runtime daemon 整改盘点
status: active
type: remediation-spec
owner: 夏明星
created: 2026-07-15
related:
  - .omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md
  - .omo/_knowledge/decisions/0179-runtime-probe-false-positive-treatment.md
  - docs/STRATEGY-M1-EVIDENCE.md
  - projects/runtime/src/runtime/health/agora_gateway_probe.py
note: >
  daemon 在线率 0.6 的根因盘点。运行时数字为 2026-07-15 沙箱实测快照，
  权威源 .omo/state/system_health.yaml。整改代码/PR 在授权 dev 环境执行。
---

# 收敛期 P0 · L1 runtime daemon 整改盘点（2026-07-15）

> **核心结论**：daemon 60% **主要是测量假阳性 + 口径分化，不是 40% 服务真死**。
> 4 个 daemon 的 PID/端口全部存活。修复方向是**治探测，不是重启服务**——
> 这与 P1「重构 health_score」天然合流，也再次印证 ADR-0210 的声明-执行鸿沟。

## 一、daemon 实测清单（4 个 type=daemon）

| daemon | PID/端口 | probe 判定 | 真相 | 计入在线? |
|--------|---------|-----------|------|-----------|
| **agora-gateway** | PID 73731, uptime ~48h | ⚠️ degraded | **假阳性**：14/20 stdio 后端"unresponsive"，但 stdio 是按需管道非常驻 | ❌ 被扣 |
| agora-sse | PID 29109, port listening | ✅ healthy | 真健康 | ✅ |
| cron-service | PID 76784, port listening | ✅ healthy | 真健康 | ✅ |
| **ollama** | port listening, healthy | status=`idle` | idle ≠ down（端口在听 + healthy）| ⚠️ 疑被误扣 |

> 另有 gbrain(cli)/kos(integrated)/runtime-mcp(mcp)/gbrain-index(scheduled) = unmanaged/scheduled，
> 非常驻 daemon，不计入 daemon 在线率。

## 二、根因（两条假阳性 + 一条口径分化）

### 根因 A · agora-gateway：**修复已在源码，问题在运行态**（2026-07-15 深挖修正）

初判是 probe `dead>0 → degraded` 假阳性。**深挖后修正**：transient/stdio 跳过逻辑
**源码里早已实现**（`projects/agora/src/agora/mcp_proxy/health.py`）：
- `_is_transient(name)` L116：`has_command and not has_endpoint` → stdio 按需服务识别（ADR-0179）。
- `_tick()` L211：`persistent = [n for n in all_backends if not self._is_transient(n)]`，
  只探测 persistent，transient 删出 `_status`，**不计入 alive/dead**。

所以**跑当前源码的 gateway 根本不该报 14/20**。真相是**运行进程与源码脱节**：

| 时刻 | gateway PID | uptime | probe 报告 | 诊断 |
|------|------------|--------|-----------|------|
| 本会话早期 | 73731 | ~175002s（**48h**）| degraded 14/20 | 跑 48h 前旧代码（修复前）|
| 本会话后期 | 73731 | ~5274s（**88min**）| **ALL 20 dead**（unhealthy）| 被并发重启，但重启后 `_is_transient` 运行时未生效/20 persistent 真不可达 |

> **这是 decl-exec-gap 最纯粹的形态**：修复代码已 commit（图纸对），但①运行进程曾 48h 未重启
> 跑旧码；②重启后又报 all-dead——说明 `_is_transient` 依赖的 `registry.get_saved_config`
> 在运行时可能返回**无 transport 区分的配置**，导致 20 个后端全被当 persistent 探测、全 fail。

**因此 ② 不是"写探测修复码"任务（那已存在），是运行态诊断任务**：
1. 确认 gateway 加载的是最新 health.py（重启拾取源码修复）。
2. 活体查 `_is_transient` 分类：`registry.get_saved_config(name)` 是否真带 `command`/`mcp_endpoint`
   字段——若配置里缺 `mcp_endpoint`，persistent 判定失准，stdio 被误当 persistent 全探全 fail。
3. 若重启后仍 all-20-dead，则是**真故障（20 persistent 后端不可达）**而非假阳性——需查后端本身。
> 这一步需在你机器上活体调进程（sandbox 无法 attach 运行时 registry），并避开并发重启窗口。

### 根因 B · ollama `idle` 被当离线
ollama `health_check: healthy` + `port_listening: true`，但 `status: idle`。若聚合把 idle 计为非在线，则又一个 idle≠down 的假阳性。

### 根因 C · service_online_ratio 口径分化
`.omo/state/system.yaml` = **0.6**（online 3/total 4）vs `.omo/state/health.yaml` = **0.75**（注释"3/4 daemon online"）。
两文件对同一指标给不同值 = SSOT drift（战略点名的 P2 痛点）。

## 三、整改步骤（授权 dev 环境执行，每步走 ADR-0203 workflow + 独立 worktree + PR）

1. **修 probe A**（最大杠杆）：`agora_gateway_probe.py` 的 degraded 判定**排除 stdio-transport 后端**——
   仅当持久/HTTP 后端 dead 才 degraded；stdio 后端 unresponsive 视为预期（对齐 docstring 与 ADR-0179）。
   预期：agora-gateway degraded → healthy。
2. **修 idle 语义 B**：聚合器把"port_listening + healthy + idle"计为在线（idle 是空闲非离线）。
   预期：ollama 计入在线。
3. **收口径 C**：`service_online_ratio` 单源化——确定 system.yaml 与 health.yaml 谁是权威，
   另一个改为 AUTOGEN 回指（消除 0.6 vs 0.75 分歧）。
4. **重算验收**：`omo state sync` 后 `service_online_ratio` 应 → ≥ 0.9（4/4 或 3/4→修正后接近满）。
5. **衔接 P1**：本整改把 daemon 权重"去假阳性"后，再做 health_score 公式重构才有意义
   （否则新权重放大的是假信号）。

## 四、验收标准（M1 daemon 门禁）

- `.omo/state/system_health.yaml`：agora-gateway `health_check: healthy`（stdio 不再触发 degraded）。
- `service_online_ratio` 单源 ≥ 0.9，system.yaml 与 health.yaml 一致。
- probe 单测覆盖"stdio 后端全 unresponsive 仍 healthy"这一回归。

## 五、一句话

> daemon 60% 是**假绿灯的反面——假红灯**：服务没死，是探测把 stdio 按需管道误判成故障。
> 治本是修探测 + 收口径，不是重启。这一步做完，M1 的 daemon 门禁即可达标，且为 health_score
> 重构（P1）扫清"放大假信号"的隐患。

---

*整改盘点 · 2026-07-15 · 夏明星 · 运行时数字以 .omo/state/system_health.yaml 为准*
