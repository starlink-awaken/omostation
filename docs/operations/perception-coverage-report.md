---
type: ephemeral
status: active
created: 2026-09-03
owner: governance-team
---

# 感知覆盖率报告

> 目标: 将感知维度从 4/10 提升到 7/10
> 策略: 先量化覆盖率 → 识别差距 → 逐步补齐

## 当前感知能力

### Harness 7 探针 (已接线 ✅)

| 探针 | Topic | 数据源 | 状态 |
|------|-------|--------|------|
| arch_upgrade | mesh:observability:arch | mof-drift, sfop-slots, architecture-drift | ✅ 已接线 |
| feature_add | mesh:workflow:step | c2g pitch, bet-ledger candidate | ✅ 已接线 |
| bug_fix | mesh:workflow:failed | CI fail, gac fail, gac-local-gate fail | ✅ 已接线 |
| experience | mesh:personal:signal | lighthouse, NFR | ✅ 已接线 |
| doc_governance | mesh:workflow:doc | doc-freshness, hygiene-patrol, doc-ssot-lint | ✅ 已接线 |
| toolchain | mesh:system:health | bin-scripts-convergence-audit, capability-ownership | ✅ 已接线 |
| business_process | mesh:pipeline:episode | cockpit journey, panorama value_gap | ✅ 已接线 |

### Resident Agent 角色 (5 类 ✅)

| 角色 | 模式 | 事件过滤 | Handler |
|------|------|----------|---------|
| sediment (记忆) | write | WorkflowClosed/Succeeded, Signal | knowledge_sediment |
| decision (决策) | decision | WorkflowFailed, StepFailed, StepTimeout | decision_agent |
| execute (执行) | write | ExecutionRequested, WorkPacketDispatched | execution_agent |
| monitor (监控) | read | system.health, gate_failed, alert | alert |
| heartbeat (心跳) | read | heartbeat, system.alive | heartbeat |

### 路由覆盖 (25 条规则 ✅)

| 类别 | 路由数 |
|------|--------|
| workflow 生命周期 | 12 |
| step 执行 | 6 |
| decision/execute | 4 |
| monitor/heartbeat | 3 |

## 感知差距

### 缺失的感知能力

| 能力 | 优先级 | 说明 |
|------|--------|------|
| 实时 Dashboard | 🔴 | 无可视化面板展示感知数据 |
| 趋势分析 | 🟡 | 无历史数据聚合 |
| 异常检测 | 🟡 | 无自动异常识别 |
| 预测推演 | 🟢 | 无预测能力 |
| 自然语言查询 | 🟢 | 无 NL 接口 |

### 数据源健康度

| 数据源 | 状态 | 问题 |
|--------|------|------|
| mof-drift | ✅ | 正常 |
| sfop-slots | ✅ | 正常 |
| architecture-drift | ⚠️ | 部分 checker 缺失 |
| c2g pitch | ⚠️ | 数据不完整 |
| bet-ledger | ✅ | 正常 |
| CI fail | ✅ | 正常 |
| lighthouse | ❌ | 未配置 |
| NFR | ❌ | 未配置 |
| doc-freshness | ✅ | 正常 |
| hygiene-patrol | ✅ | 正常 |
| doc-ssot-lint | ✅ | 正常 |
| bin-scripts-convergence | ✅ | 正常 |
| capability-ownership | ✅ | 正常 |
| cockpit journey | ⚠️ | 数据不完整 |
| panorama value_gap | ⚠️ | 数据不完整 |

## 感知覆盖率计算

```
已接入数据源: 10/14 (71%)
已接线探针: 7/7 (100%)
活跃路由: 25/25 (100%)
Dashboard: 0/1 (0%)

综合感知覆盖率: 40% → 评分 4/10
```

## 提升路径

### Phase 1 — 数据源补齐 (4→5)

1. 配置 lighthouse CI (experience 探针)
2. 定义 NFR 指标采集 (experience 探针)
3. 补全 c2g pitch 数据 (feature_add 探针)
4. 激活 cockpit journey 追踪 (business_process 探针)

### Phase 2 — Dashboard 建设 (5→6)

1. cockpit-ui HarnessDashboard 增加覆盖率面板
2. 实时显示 7 探针健康状态
3. 数据源健康度矩阵
4. 路由命中率统计

### Phase 3 — 趋势与异常 (6→7)

1. 历史数据聚合 (SQLite/TimescaleDB)
2. 趋势图表 (drift 变化率)
3. 异常检测 (3-sigma 规则)
4. 自动告警 (threshold breach)

### Phase 4 — 预测与 NL (7→8)

1. 简单预测 (线性外推)
2. 自然语言查询 (cockpit ask)
3. 场景推演 (what-if analysis)

## 验证命令

```bash
# 1. 检查探针数据源健康度
python3 bin/gac/self-evolution-loop.py --data-sources

# 2. 检查路由覆盖
grep -c "event_type:" projects/omo/src/omo/resident/resident-routes.yaml

# 3. 检查 resident 角色
grep -c "role:" projects/omo/src/omo/resident/roles.py

# 4. 运行 journey runner 验证
python3 bin/ssot/journey-runner.py --dry-run
```

## 下一步

1. 补齐 lighthouse + NFR 数据源
2. 在 cockpit-ui 增加 Harness 覆盖率面板
3. 建立历史数据存储
