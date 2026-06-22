---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# omo 子包重组计划

> Created: 2026-06-19
> Status: PLANNED — 待 Batch 1 执行

## 当前状态

125 个 .py 文件平铺在 `src/omo/` 下，缺乏子包组织。

## 重组方案

### 目标结构

```
src/omo/
├── debt/           # 17 files — 债务评分/诚实度/遗留
├── audit/          # 4 files — 审计追踪
├── bos/            # 6 files — BOS URI 路由/指标
├── worker/         # 7 files — Worker 调度/promotion
├── governance/     # 10 files — 治理面核心
├── cli/            # CLI 入口
├── mcp/            # MCP Server
├── bus/            # Bus 适配器
└── _shared/        # AppendOnlyLog, IO, 工具函数
```

### 文件映射

#### debt/ (17 files)
- omo_debt.py → debt/scoring.py
- omo_debt_actions.py → debt/actions.py
- omo_debt_classify.py → debt/classify.py
- omo_debt_dashboard.py → debt/dashboard.py
- omo_debt_dispatch.py → debt/dispatch.py
- omo_debt_gate.py → debt/gate.py
- omo_debt_honesty.py → debt/honesty.py
- omo_debt_ingress.py → debt/ingress.py
- omo_debt_legacy.py → debt/legacy.py
- omo_debt_owner_routing.py → debt/owner_routing.py
- omo_debt_review_queue.py → debt/review_queue.py
- omo_debt_reviewer.py → debt/reviewer.py
- omo_debt_stage.py → debt/stage.py
- omo_debt_watcher.py → debt/watcher.py
- omo_debt_xml_lint.py → debt/xml_lint.py
- omo_debt_xml_report.py → debt/xml_report.py
- omo_debt_xml_seed.py → debt/xml_seed.py

#### audit/ (4 files)
- omo_audit.py → audit/trail.py
- omo_audit_bos_metrics.py → audit/bos_metrics.py
- omo_audit_rollout.py → audit/rollout.py
- omo_audit_xplane.py → audit/xplane.py

#### bos/ (6 files)
- omo_bos.py → bos/router.py
- omo_bos_metrics.py → bos/metrics.py
- omo_bos_middleware.py → bos/middleware.py
- omo_bos_resolver.py → bos/resolver.py
- omo_bos_resources.py → bos/resources.py
- omo_bos_invoke.py → bos/invoke.py

#### worker/ (7 files)
- omo_worker.py → worker/dispatch.py
- omo_worker_dispatch.py → worker/scheduler.py
- omo_worker_promotion.py → worker/promotion.py
- omo_worker_budget.py → worker/budget.py
- omo_worker_evidence.py → worker/evidence.py
- omo_worker_gate.py → worker/gate.py
- omo_worker_state.py → worker/state.py

#### governance/ (10 files)
- omo_governance.py → governance/core.py
- omo_governance_overlay.py → governance/overlay.py
- omo_governance_surfaces.py → governance/surfaces.py
- omo_governance_history.py → governance/history.py
- omo_governance_inspect.py → governance/inspect.py
- omo_goal.py → governance/goals.py
- omo_ingress.py → governance/ingress.py
- omo_task_schema.py → governance/task_schema.py
- omo_promote.py → governance/promote.py
- omo_phase.py → governance/phase.py

### 执行步骤

1. 创建子包目录 + __init__.py
2. git mv 文件到子包
3. 更新 omo 内部 import
4. 更新外部 import (cockpit 4处, runtime 1处, ecos 1处)
5. 更新 __init__.py re-export (向后兼容)
6. 运行全量测试
7. 更新 ARCHITECTURE.md / AGENTS.md

### 向后兼容

在 `src/omo/__init__.py` 中 re-export 所有公共 API，确保旧 import 路径仍然工作：
```python
from omo.debt.scoring import *  # backwards compat
from omo.audit.trail import *   # backwards compat
```

### 风险

- 中等: 需要更新 6 处外部 import
- 低: omo 内部 import 多但可控
- 测试: 530 tests (225 skip)，有效 ~305
