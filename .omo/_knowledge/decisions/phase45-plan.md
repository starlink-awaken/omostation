# Phase 45 — 治理可观测性: 从"执行"到"自维护"

> Status: **PLANNED** · 基于: 2026-07-14 深度复盘
> 前序: Phase 44 (架构收敛固化) — 7 项债务全部解决

---

## 战略目标

Phase 44 完成了"让系统对自己诚实"。Phase 45 必须回答一个更深的问题：

**"谁来确保治理系统本身被治理？"**

所有 7 项债务由同一个 agent 在同一个 session 内解决。没有第二个 observer、
没有外部审计、没有自动化回滚检测。如果一个修复引入了新错误，只能等下一轮治理循环发现。

## Phase 45 三个 Wave

### Wave 1 — 治理自检 (P0)

#### 1.1 健康扫描自检 (P0)

**问题**: cron-service 可能 PID 活着但 tick loop 卡死 (维修死角)。
健康扫描报告 "running" 但实际不调度任务。

**方案**: 
- 在 system_health.yaml 中记录 `last_tick_at` / `ticks_per_minute`
- GaC 检查 `ticks > 0` 且 `ticks_per_minute >= 3`
- 健康扫描增加自检: 检查自己的 `scheduler_running` + `tick_count`

**文件**: `projects/runtime/src/runtime/cron_service/health_scan.py`
**门禁**: 新增 GaC #36 `health-self-check`

#### 1.2 cron tick 超时保护 (P0)

**问题**: `_tick()` 中 `run_scan_if_due` 可能被 `run_in_executor` 阻塞,
导致 tick loop 卡死在第一次 tick 后不再醒来。

**方案**:
- `run_scan_if_due` 调用加 30s 超时 (`loop.run_in_executor(...)` → `asyncio.wait_for(..., timeout=30)`)
- 失败时日志告警 + 继续 tick loop (不阻断)

**文件**: `projects/runtime/src/runtime/cron_service/scheduler.py`

#### 1.3 债务系统自动种子 (P0)

**问题**: `debt.yaml` 的 `seed_items` 无人维护, 旧文件被静默跳过。
没有机制在高熵时自动创建债务项。

**方案**:
- 新增 `bin/ssot/debt-auto-seed.py` — 分析 `health.yaml` 中 `priority_dist.unassigned > 20`
  或 `phase_dist.unphased > 30` 等熵指标, 自动生成债务建议文件
- GaC 注册 check: `debt-auto-seed` — 如果 `debt_weight > 0.50` (超过一半债务未解决) 且
  最近 7 天无新 debt item 创建 → 警告

**文件**: `bin/ssot/debt-auto-seed.py` (新建)

---

### Wave 2 — 可观测性加固 (P1)

#### 2.1 agora-gateway 真实 HTTP /health (P1)

**问题**: 当前 probe 是 PID + log grep, 无法被标准化健康扫描协议检测。
agora-gateway 是唯一一个没有 HTTP health endpoint 的 daemon。

**方案**:
- 在 `agora.auth.mcp_gateway` 中嵌入 uvicorn + 最小的 `/health` 端点
- 端点返回 `{"status": "ok", "backends": {...}, "uptime": ...}`
- 更新 `runtime.scheduler.MatrixScheduler` 识别 agora-gateway 的 health endpoint

**文件**: `projects/agora/src/agora/auth/mcp_gateway.py` (新增 HTTP 层)
**风险**: 中等 — 需要引入 uvicorn/FastAPI 依赖; 可回退: 保持现有 probe

#### 2.2 debt_adjusted 实时计算 (P1)

**问题**: `debt_adjusted_health_score` 是 system.yaml 中的静态值, 不随
债务状态实时变化。

**方案**:
- 在 cron-service `/health` 端点增加实时 `debt_adjusted` 字段
- `GET /health` → `"debt_adjusted": health × compute_debt_weight(...)`
- system.yaml 中 保留快照值, 但标记 `debt_adjusted_dynamic: true`

**文件**: `projects/runtime/src/runtime/cron_service/server.py`

---

### Wave 3 — 熵清理 + 收敛 (P2)

#### 3.1 472 task 文件熵清理 (P2)

**问题**: `.omo/tasks/` 有 472 个 task-*.yaml 文件, 但 `health.yaml`
只追踪 104 个 (tracked tasks)。368 个是孤儿任务文件。

**方案**:
- `bin/ssot/task-archive.py` — 归档未被任何 registry 引用的 task 文件
- 归档目标: `.omo/tasks/archived/` (保留历史但退出活跃 view)

**文件**: `bin/ssot/task-archive.py` (新建)

#### 3.2 BOS transport 迁移试点 (P2)

**问题**: 67.5% BOS 服务走 stdio, 无法被 HTTP 健康探针检测。
已在 Phase 43 发布规划 (`plans/bos-transport-migration.md`) 但未执行试点。

**方案**:
- 选 3 个低风险 stdio 服务 (capability/forge, analysis/coder, system/least-used)
- 包装为 mcp_proxy 模式
- 验证健康探针可达 + 功能不变

**文件**: 引用 `.omo/plans/bos-transport-migration.md`

---

## 时间估算

| Wave | 项 | 复杂度 | 预估人天 |
|:-----|:---|:------:|:--------:|
| W1 | health self-check + tick timeout | L | 1 |
| W1 | debt auto-seed | M | 1 |
| W2 | agora-gateway /health | XL | 3 |
| W2 | debt_adjusted live | S | 0.5 |
| W3 | task archive cleanup | M | 1 |
| W3 | BOS migration pilot | L | 2 |
| **总计** | | | **8.5** |

## 验收标准

```
Phase 45 endpoint:
  health_scan.ticks_ok: true          # ticks 自检通过
  cron.tick_timeout_seconds: 30       # tick 超时保护生效
  debt.auto_seeded_last_7d: true      # 自动种子机制运行
  agora_gateway.health_check: live    # HTTP /health 在线
  debt_adjusted.computed: live        # 健康端点实时计算
  task_files: < 200                   # 熵清理到 200 以下
  bos_stdio_ratio: < 65%              # 试点迁移后从 67.5% 降 2 个百分点
```

## 回退

- Wave 1 不可回退 (基础设施加固)
- Wave 2.1 可回退至 PID probe + log grep (当前做法)
- Wave 3 可延迟 (熵不影响功能)
