# omo Subsystem Map

> **Generated**: 2026-06-20 (mof-analyze quality)
> **Purpose**: 为 omo 模块分包重构提供 SSOT 索引
> **Status**: 文档已建立, 重构未执行 (368 internal imports, 改动面过大需 dedicated session)

## 当前文件分布 (135 个 .py 文件)

按子系统聚合 (基于 `ls projects/omo/src/omo/omo_*.py` + 前缀分析):

| Subsystem | Count | Files | 角色 |
|-----------|------:|-------|------|
| **debt** | 17 | omo_debt*.py | 债务全生命周期 (lifecycle/registry/weight/metrics/dispatch/review/approval/campaign/owner_routing/execution/reporting/io/cli/action_packet) |
| **governance** | 11 | omo_governance.py, omo_audit*.py, omo_approval_board.py, omo_promotion*.py, omo_phase_state.py, omo_signal.py, omo_xplane_audit.py | 治理面 (审计/审批/晋升/Phase/Signal/X-Plane) |
| **worker** | 7 | omo_worker_*.py | Worker 调度 (core/dispatch/state/promotion/internal/execution/rebalance) |
| **promotion** | 7 | omo_promotion*.py (部分), omo_worker_promotion.py (重复计算) | 任务晋升逻辑 |
| **bos** | 6 | omo_bos*.py | BOS URI 服务 (core/schema/seeds/dispatcher/metrics/discovery) |
| **audit** | 4 | omo_audit*.py (dedup/rollout/sync) | 审计去重/汇总/同步 |
| **task** | 3 | omo_task*.py | 任务 schema / policy / packet |
| **self** | 3 | omo_self_*.py (healing/evolution/experience) | 自愈/自演/经验 |
| **trail** | 2 | omo_trail*.py | 操作轨迹 |
| **sync** | 2 | omo_sync*.py | 状态同步 |
| **state** | 2 | omo_phase_state.py, omo_state*.py | 阶段状态 |
| **observability** | 2 | omo_observability*.py, omo_metrics*.py | 可观测性 |
| **metrics** | 1 | omo_metrics.py | 指标 |
| **io** | 2 | omo_io*.py (含 omo_io_schemas) | JSONL 物理写盘 |
| **xplane** | 1 | omo_xplane_audit.py | X-Plane 审计 |
| **其他** | ~25 | cli / mcp_server / model_driven_bridge / adapter / cards / contract_request / delivery / event / evidence / bridge / admission / agora_pool / bus / capability / cockpit_bridge / cost / daemon / dashboard / discovery / doc_lint / drift_detector / provider_plane / etc. | 横切面工具 |

## 重构建议 (P44 dedicated session)

### 目标结构 (建议)
```
projects/omo/src/omo/
├── __init__.py
├── cli.py                          # CLI 入口 (不动)
├── mcp_server.py                   # MCP server 入口 (不动)
├── model_driven_bridge.py          # Model-driven 桥接 (不动)
├── categories/                     # 已存在, 不动
├── _shared/                        # 已存在, 不动
├── debt/                           # 🆕 17 files
│   ├── __init__.py (re-export)
│   ├── core.py (omo_debt.py + omo_debt_lifecycle.py)
│   ├── registry.py (omo_debt_registry.py)
│   ├── weight.py (omo_debt_weight.py)
│   ├── metrics.py (omo_debt_metrics.py)
│   ├── review_queue.py (omo_debt_review_queue.py)
│   ├── approval.py (omo_debt_approval.py)
│   ├── dispatch.py (omo_debt_dispatch.py)
│   ├── owner_routing.py (omo_debt_owner_routing.py)
│   ├── campaign.py (omo_debt_campaign.py)
│   ├── execution.py (omo_debt_execution.py)
│   ├── reporting/                  # 4 files (diff/history/trend/root)
│   ├── action_packet.py
│   └── cli.py (omo_debt_cli.py)
├── governance/                     # 🆕 11 files
│   ├── __init__.py
│   ├── core.py (omo_governance.py)
│   ├── audit/ (4 files: omo_audit*.py)
│   ├── approval.py
│   ├── promotion/ (4-5 files)
│   ├── phase_state.py
│   ├── signal.py
│   └── xplane.py
├── worker/                         # 🆕 7 files
│   ├── __init__.py
│   ├── core.py
│   ├── dispatch.py
│   ├── state.py
│   ├── promotion.py
│   ├── internal.py
│   ├── execution.py
│   └── rebalance.py
├── bos/                            # 🆕 6 files
│   ├── __init__.py
│   ├── core.py
│   ├── schema.py
│   ├── seeds.py
│   ├── dispatcher.py
│   ├── metrics.py
│   └── discovery.py
└── io/                             # 🆕 2 files
    ├── __init__.py
    ├── core.py (omo_io.py)
    └── schemas.py
```

### 兼容层 (back-compat shim)
在 `projects/omo/src/omo/` 顶层保留所有旧 `omo_xxx.py` 文件作为转发层 (from new_pkg import *) — 0 import sites 改动。

### 风险评估
- **368 internal imports** in current codebase
- **back-compat shim** 可消除 95% 改动
- 真正需要改的是 **外部 import** (c2g/agora/cockpit) → 检查后约 7-10 处
- **mypy 校验** 必须 0 error
- **215 omo tests** 必须全过

### 增量步骤
1. Phase A: 建新包 + shim (不改 import), 验证测试通过
2. Phase B: 改 1 个外部 import (c2g) 作 dogfood
3. Phase C: 逐步迁 1-2 个子系统到新结构
4. Phase D: 完成所有 17+11+7+6+2 个文件迁移

## 当前评估
- governance A+ 但模块膨胀是 **"隐藏债务"** — 不影响运行但增加认知负担
- 重构 **不在 P43 范围** (P43 焦点: 治理债务闭环 + lint 修复)
- 建议 **P44** 起 dedicated session