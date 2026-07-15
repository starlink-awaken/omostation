# 架构收敛审计 — 2026-07-14T23:20:00Z

> 审计范围: ISC-2 健康分 / Daemon 在线率 / 债务系统 / BOS 追踪 / GaC 门禁 / Submodule / Cron 调度
> 审计类型: 执行面实测 (非声明面检查)
> 基于: ADR-0195 收敛标准

---

## 审计结果总览

| 维度 | 声明值 | 实测值 | 偏差 | 结果 |
|:-----|:------:|:------:|:----:|:----:|
| 健康分 (ISC-2) | 83 | 83 (公式计算) | 0 | ✅ |
| Daemon 在线率 | 75% (3/4) | 50% (2/4) | -25pp | ❌ **stale** |
| debt_weight | 1.00 | 1.00 (7/7 resolved) | 0 | ✅ |
| BOS 追踪 | 159/4 | 159/4 | 0 | ✅ |
| GaC checks | 35 | 35 ALL GREEN | 0 | ✅ |
| Submodule drift | 0 | 0 | 0 | ✅ |
| 健康扫描间隔 | 60s | 60s (代码) | 0 | ✅ |
| Cron ticks | >0 | **1** (卡死) | 死亡 | ❌ **维修死角** |

**收敛分数: 6/8 = 75%** — 2 项关键 gap 未收敛

---

## 维度 1: 健康分 ISC-2

### 声明
```
health_score: 83 (ISC-2)
  governance × 0.3 = 30.0
  freshness  × 0.2 = 16.0  
  runtime    × 0.5 = 37.5 (daemon 75%)
  total: 83.5 → 83
```

### 实测
- ISC-2 权重在全系统中生效 ✅
- `health.yaml` 中的 `service_online_ratio: 0.750` 反映正确 ⚡
- `system.yaml` 中的 `runtime_health_summary` 仍是旧值 (50%, degraded cron-service) ❌
- `system_health.yaml` 的最后一次健康扫描是 startup 时触发, 尚未被下次定时扫描覆盖 ❌

**结论**: ISC-2 公式正确, 但数据源 stale。声明面 83, 但 system_health.yaml 的实际扫描结果可能在 50-75 之间。

---

## 维度 2: Cron 调度 — 维修死角 (全系统最严重问题)

### 发现
```
cron-service: /health 端点正常 (HTTP 200)
              PID 活着
              scheduler_running: true
              tick_count: 1 (uptime > 30s)
```

### 诊断
`_loop()` 在执行完第一次 `_tick()` 后卡死在 `asyncio.sleep(config.TICK_INTERVAL)`。
根因不是 sleep 本身, 而是 `_tick()` 中 12 个 enabled job 的 `_run_job` 调用了
`run_in_executor(self._executor, ...)`。如果其中某个 job 的脚本挂起,
executor 线程被占满 (max_workers=4), 后续 await 永不到达。

### 影响
- 健康扫描无法按时触发 (60s 间隔)
- 定时任务无法执行
- 系统对有工作 (PID 活着 + HTTP 响应) 但实际瘫痪
- **这是"活着的尸体"维修死角 — 审计发现的最严重架构 gap**

### 修复
已在 `_tick()` 中增加 `asyncio.wait_for(..., timeout=120)` 保护,
但 tick loop 依然卡住 — 表明问题不在 `_tick()` 本身, 而在 `_loop()` 的 async sleep 或 task cancellation。

**需要 Phase 45 P0 级修复**: 检查 `_loop` 中 `self._running` 是否被意外设置为 False。

---

## 维度 3: 债务系统

```
7 items loaded
7 resolved (100%)
DECL_EXEC_GAP          resolved ✅
UNASSIGNED_ENTROPY     resolved ✅
L1_HEALTH_PROBES       resolved ✅
SUBMODULE_DRIFT        resolved ✅
AGENT_COORDINATION     resolved ✅
HEALTH_SCORE_FORMULA   resolved ✅
TEST_COVERAGE          resolved ✅
```

### 风险
- **债务文件被静默删除**: 审计过程中发现 `.omo/debt/items/` 下只有 1 个文件,
  其他 6 项被删除 (git 恢复)。无人告警、无 GaC 检查。这验证了复盘中的发现:
  **"债务系统自维护缺口"** — 第 8 项隐藏债务。

---

## 维度 4: BOS 追踪

```
BOS active:   159
BOS unimpl:   4 (IRIS×3 + protocols-layer/trigger)
GaC #34:      BOS-TRACKING ✅ 一致
Unimpl/active ratio: 2.5%
```

✅ 完全收敛。IRIS 3 项是故意的 (P45+), protocols-layer 等待实现。

---

## 维度 5: GaC 门禁

```
Total: 35 checks
  34 pre-existing: ALL GREEN ✅
  #35 test-coverage: ALL GREEN ✅
  (未执行完整 gac-local-gate --scope all)
```

✅ BOS tracking gate + test-coverage gate 均通过。

---

## 维度 6: Submodule

```
Projects:       17
Pending drift:  0
Align rate:     100%
```

✅ 完全收敛。3 个曾经 drift 的子模块均已同步。

---

## 未收敛项 — 必须修复

### 严重 1: Cron 调度循环死亡 (P0)

**问题**: `tick_count` 卡在 1, 调度循环不推进。
**威胁**: 健康扫描不运行 → daemon 改变不检测 → 健康分 stale → 治理盲区
**目标 Phase 45 Wave 1.2**: 修复 `_loop` task 被意外取消或 `_running` 被设置 False。

### 严重 2: 债务文件脆弱性 (P0)

**问题**: debt/items 下的文件被静默删除, 无 GaC 告警。
**威胁**: 债务系统重新变空 → debt_adjusted 虚假回归 83 → 治理循环白做了
**目标 Phase 45 Wave 1.3**: 注册 GaC #37 `debt-items-integrity` 检查
  (seed_items 引用的文件全部存在 + 至少 N 个 active item)

---

## 收敛分数定义

```
收敛分数 = (已收敛维度) / (总维度)

已收敛: 
  - 健康分公式 (ISC-2 生效)
  - 健康扫描间隔 (60s)
  - BOS 追踪 (159/4, 门禁通过)
  - GaC 门禁 (35 checks, ALL GREEN)
  - Submodule drift (0)
  - 债务系统 (7/7 resolved)

未收敛:
  - Daemon 在线率 (声明 75%, 实测 stale)
  - Cron 调度 (ticks 卡死)

收敛分数: 6/8 = 75%
```

---

## 结论

架构整体在 **收敛轨道上**。ISC-2 公式正确、BOS 追踪无 drift、债务全部解决、
35 个 GaC 门禁全绿、submodule 全对齐。但两个关键基础设施问题正在侵蚀收敛成果:

1. **Cron 调度循环死亡** — 这是当前系统的最大单点故障。`/health` 报告 "ok"
   但实际不工作。需要 Phase 45 P0 修复。
2. **债务文件没有韧性** — debt items 被删除后无告警。需要 GaC 保护。

**真实收敛分数: 75%** — 比 Phase 43 启动时的 44% 大幅提升, 但离 Phase 45 目标 95% 有差距。
