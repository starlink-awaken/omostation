---
lifecycle: entry
owner: auto-fix-loop
last_updated: 2026-08-24
title: BCOS 业务域系统 v1 — 功能规格 SSOT
type: doc
---

# BCOS 业务域系统 v1 — 功能规格 SSOT

> 最后更新: 2026-08-23
> 定位: BCOS (Business Operating System) 业务域系统的功能规格单一事实源 (SSOT)。
> 边界: 本文件描述 **能力契约**（是什么/怎么调/验证），不复制运行时计数（见 doc-ssot-contract）。

## 1. 定位

BCOS 是 omostation 的**业务闭环系统**，把个人工作流（信号 → 路由 → 进化 → 价值度量）做成可观测、可治理、可进化的运行面。核心组件:

| 组件 | 职责 | 场景卡引用 | 状态 |
|------|------|-----------|------|
| `bin/bc-os/signal_router.py` | W1-D2 统一信号路由（公文/会议/调研/代码） | unified-inbox `integrated_via: signal_router` | ✅ active (恢复 2026-08-23) |
| `bin/bc-os/evolution_engine.py` | W1 进化引擎四阶段（observe/propose/evaluate/approve/rollback） | 4 场景卡 `status: applied_by_evolution_engine` | ✅ active (恢复 2026-08-23) |
| `bin/bc-os/north_star_meter_v2.py` | 北极星价值度量 v2（排除 self-data） | 台账 W3 | ✅ active |

> 背景: evolution_engine / signal_router 曾被 scripts 迁移误归档，后依 `3y-bet-ledger.yaml:6033` + T6-13 retro 恢复（PR #2050）。

## 2. 里程碑

- **W1 信号 → 场景** (done): inbox_folder → signal_router → 5 场景 active
- **W2 场景 → 进化** (done): EvolutionEngine 四阶段，真实改变状态 (PR #1736)
- **W3 价值度量** (done): 北极星 v2 排除 self-data，真实价值闭环
- **W4 业务闭环** (持续): 信号消费 → 价值投影 → 周报

## 3. CLI 接口

```bash
# EvolutionEngine — 进化四阶段 (dry-run 默认)
python3 bin/bc-os/evolution_engine.py              # 观察/提案/评估/批准 汇总 (dry-run)
python3 bin/bc-os/evolution_engine.py --apply      # 真正批准提案
python3 bin/bc-os/evolution_engine.py --json       # JSON 输出

# signal_router — W1-D2 信号路由
python3 bin/bc-os/signal_router.py --inbox <dir>   # 扫描并路由信号
python3 bin/bc-os/signal_router.py --json          # JSON 输出

# north_star_meter_v2 — 北极星价值度量
python3 bin/bc-os/north_star_meter_v2.py --json    # 价值真值快照
python3 bin/bc-os/north_star_meter_v2.py --record --scene <s> --action <a>   # 记录消费
python3 bin/bc-os/north_star_meter_v2.py --json    # 周报
```

## 4. 状态面

| 状态文件 | 拥有者 | 说明 |
|----------|--------|------|
| `.omo/state/knowledge-shadow.json` | evolution_engine | 知识影子 (W1 验证) |
| `.omo/state/routed-signals.json` | signal_router | 路由日志 (幂等) |
| `.omo/state/evolution-proposals.json` | evolution_engine | 提案存储 |
| `.omo/state/evolution-rollouts.json` | evolution_engine | 灰度状态 |
| `.omo/state/value-ledger.json` (默认) | north_star_meter_v2 | 价值账本 (记录消费) |

## 5. 治理接线 (6 支撑面)

| 支撑面 | 接入 |
|--------|------|
| 文档 | 本文件 (SSOT) + SYSTEM-INDEX / INDEX-TOOLS |
| MOF 治理规范 | `m2/bcos_system.yaml` (BCOSystem extends System) + m1 实例 |
| 约束 | L0-constraints.yaml `CR-BCOS-*` |
| Cockpit CLI | `cockpit bcos` (委派 bin/bc-os 脚本) |
| Agora MCP | `bcos_*` 工具 |
| BOS URI | `bos://bcos/*` 服务 |

## 6. 运维

- 进化引擎触发: 手动 (无 cron)，`--apply` 需显式
- 信号路由: 手动扫描 inbox 或由 inbox watcher 触发
- 北极星度量: 周报生成 (weekly_report)

## 7. 验证

```bash
cd bin/bc-os && python3 -m pytest test_evolution_engine.py test_integration_e2e.py -q   # 12 PASS
python3 bin/bc-os/evolution_engine.py --json      # 四阶段输出
python3 bin/bc-os/north_star_meter_v2.py --json   # 价值快照
make gac-local-gate                               # 治理门禁
```
