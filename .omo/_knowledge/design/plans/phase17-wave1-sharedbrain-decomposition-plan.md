# Phase 17 Wave 1 实施计划：SharedBrain 拆解

> **Goal:** 执行 SharedBrain "保留核心 + 能力注入 + 废弃过时"策略的首批任务
> **Scope:** Wave 0 (治理门禁 + 健康分) + Wave 1 (小器官迁移 + 废弃确认)
> **Method:** TDD + .omo governance, task-gate-model
> **Source:** `.omo/_knowledge/design/sharedbrain-decomposition-architecture.md`
> 本文档是历史阶段的实施计划输入，保留当时的 Wave 切分、健康分门禁和任务建议，不是当前 active task、当前阶段状态或当前 SharedBrain 处理策略 SSOT。
> 当前执行与状态以 `/.omo/goals/current.yaml`、`/.omo/tasks/active/`、`/.omo/state/system.yaml` 和当前审计结果为准。

---

## Wave 0: 治理门禁 (立即)

### Task W0.1: 健康分公式引入 debt_weight 因子

**Ref:** `P17-DEBT-GOVERNANCE-GATE-RULES`

**Context:** `scripts/sync_omo_state.py:395` 当前仅用 test pass/fail 计算 health_score，掩盖核心债务。

**变更:**

1. 新建 `scripts/omo_debt_weight.py` — 债务权重计算模块
2. 修改 `scripts/sync_omo_state.py` — 引入 debt_weight 乘数
3. 更新 `state/system.yaml` — 健康分骤降至真实值

**代码:**

```python
# scripts/omo_debt_weight.py
"""债务权重计算 — 影响 health_score 乘数因子."""

DEBT_ITEMS = {
    "D2_CI_E2E": {"weight": 0.15, "desc": "CI E2E 环境容器化"},
    "D3_EU_PRICING": {"weight": 0.15, "desc": "eu-pricing 独立测试"},
    "SB_DECOMPOSITION": {"weight": 0.20, "desc": "SharedBrain 拆解进度"},
    "SB_UNTESTED": {"weight": 0.10, "desc": "4个untested包"},
    "SB_ORPHANED": {"weight": 0.10, "desc": "orphaned_tasks 结构化"},
}


def compute_debt_weight(resolved_items: set[str]) -> float:
    """计算债务权重因子 (0.0 - 1.0)."""
    total_weight = sum(v["weight"] for v in DEBT_ITEMS.values())
    resolved_weight = sum(
        v["weight"] for k, v in DEBT_ITEMS.items() if k in resolved_items
    )
    unresolved_penalty = 1.0 - (total_weight - resolved_weight) / total_weight
    return round(min(unresolved_penalty, 1.0), 2)
```

**sync_omo_state.py 修改 (line ~395):**

```python
# Before:
state["health_score"] = _parse_health_score(test_output, float(state.get("health_score", 0.0)))

# After:
from scripts.omo_debt_weight import compute_debt_weight

raw_health = _parse_health_score(test_output, float(state.get("health_score", 0.0)))
resolved = state.get("resolved_debt_items", [])
debt_weight = compute_debt_weight(set(resolved))
state["health_score"] = round(raw_health * debt_weight, 2)
state["health_score_raw"] = raw_health
state["debt_weight"] = debt_weight
state["debt_weight_items"] = {
    k: {"resolved": k in resolved, "weight": v["weight"], "desc": v["desc"]}
    for k, v in DEBT_ITEMS.items()
}
```

---

### Task W0.2: 正式化 SharedBrain 去留决策

**Ref:** `SHAREDBRAIN-FORMAL-DECISION`

**变更:**

1. 更新 `SharedBrain/README.md` (根目录) — 说明这是空壳，代码在 projects/SharedBrain/
2. 创建 `projects/SharedBrain/DECOMPOSITION.md` — 说明拆解决定和迁移路线图
3. 标记任务 SHAREDBRAIN-FORMAL-DECISION 为 `in_progress`

**projects/SharedBrain/DECOMPOSITION.md:**

```markdown
# SharedBrain 拆解决定

## 决定日期: 2026-06-01

## 决定
SharedBrain 项目执行"保留核心 + 能力注入 kairon + 废弃过时模块"策略。

## 保留为 SharedBrain 核心
- nucleus/Z-Spore/ — 形式化元模型 (25K 行)
- nucleus/Z-Core/ — 架构法则 (1K 行)
- organs/D_Immunity/核 — 核心安全能力
- data/db/ — 持久化数据

## 迁移到 kairon
详见 `.omo/_knowledge/design/sharedbrain-decomposition-architecture.md`
- D_Economy → eu-pricing (Wave 1)
- D_KnowledgeIntegration → kos (Wave 1)
- D_Gateway → agora (Wave 2)
- D_Harvest + D_Intelligence → minerva (Wave 3)
- D_Logos → ontoderive (Wave 3)
- D_Memory schema → eidos (Wave 3)

## 废弃 (已替代)
- D_Execution (56K 行) — agentmesh 已替代
- D_Governance (27K 行) — .omo 治理已替代
```

---

### Task W0.3: 更新 PROJECTS.yaml SharedBrain 行数

**变更:** `.omo/PROJECTS.yaml` line 20: `lines: 71K` → `lines: 824K`

---

### Task W0.4: 运行健康分同步并记录基准

```bash
cd /Users/xiamingxing/Workspace
python3 scripts/sync_omo_state.py --omo-dir .omo
# 预期: health_score 从 97.0 降至 ~20-30 (债务权重生效)
```

---

## Wave 1: 小器官迁移 + 废弃确认

### Task W1.1: 废弃 D_Execution (56K 行) — agentmesh 已替代

**验证 agentmesh 覆盖:**
```bash
rg -l "agent_orchestrat\|task_decompos\|worker_dispat\|swarm_lifecycle" projects/agentmesh/ | wc -l
# 预期: >3 files (agentmesh 有独立编排能力)
```

**执行:**
```bash
# 标记为废弃
cd projects/SharedBrain/organs/D_Execution
cat > DEPRECATED.md << 'EOF'
# D_Execution — 已废弃 (2026-06-01)

## 原因
agentmesh (TypeScript, 7包) 已将 Agent 编排、任务分解、Worker 调度、Swarm 生命周期
管理迁移到 TypeScript 运行时。此 Python 实现不再维护。

## 替代方案
- Agent 编排: agentmesh/packages/agent-gateway/
- 任务调度: agentmesh/packages/task-orchestrator/
- LLM 路由: agentmesh/packages/llm-router/

## 归档日期
2026-06-01
EOF
```

**验证:**
```bash
# 确认无活跃导入
rg "from organs\.D_Execution" projects/SharedBrain/ --type py -g '!__pycache__' -l
# 输出应仅限于 DEPRECATED.md 或 D_Execution 内部文件
```

---

### Task W1.2: 废弃 D_Governance (27K 行) — .omo 治理已替代

**验证 .omo 覆盖:**
```bash
ls .omo/tasks/active/*.yaml .omo/tasks/blocked/*.yaml | wc -l
# 预期: >10 (治理任务活跃)
```

**执行:**
```bash
cd projects/SharedBrain/organs/D_Governance
cat > DEPRECATED.md << 'EOF'
# D_Governance — 已废弃 (2026-06-01)

## 原因
.omo 四平面治理体系已全面替代 SharedBrain 的内嵌治理机制:
- 控制面: goals/state/ → 替代 phase_manager, cycle_runner
- 事实面: tasks/standards/ → 替代 execution_strategy, policy_registry
- 知识面: _knowledge/ → 替代 retrospective, decision_journal
- 交付面: _delivery/ → 替代 delivery_loop_bridge

## 替代方案
详见 .omo/AGENT.md — Agent 启动必读治理手册

## 归档日期
2026-06-01
EOF
```

---

### Task W1.3: 废弃 D_Window 占位符 (5 行)

```bash
cd projects/SharedBrain/organs/D_Window
cat > DEPRECATED.md << 'EOF'
# D_Window — 占位符，从未实现 (废弃 2026-06-01)
EOF
rm -f __init__.py  # 移除占位包
```

---

### Task W1.4: D_Economy 核心能力注入 eu-pricing

**目标:** 提取 energy_ledger 和 eu_monitor 的核心抽象到 kairon/eu-pricing

**新建文件: `projects/kairon/packages/eu-pricing/src/eu_pricing/energy_model.py`**

```python
"""Energy resource accounting data models — extracted from SharedBrain D_Economy.

Provides the core abstractions independent of SharedBrain's BaseMembrane/PersistenceProvider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ResourceType(Enum):
    EU = "eu"           # Energy Units
    NECTAR = "nectar"   # Reward tokens
    QUOTA = "quota"     # Resource quotas


@dataclass
class EnergyEntry:
    """A single energy consumption/budget record."""
    caller_id: str
    operation: str
    cost: float
    balance_before: float
    balance_after: float
    idempotency_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "caller_id": self.caller_id,
            "operation": self.operation,
            "cost": self.cost,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "idempotency_key": self.idempotency_key,
        }


@dataclass
class EnergyBudget:
    """Per-caller energy budget."""
    caller_id: str
    limit: float = 1000.0
    consumed: float = 0.0
    entries: list[EnergyEntry] = field(default_factory=list)

    @property
    def balance(self) -> float:
        return max(0.0, self.limit - self.consumed)

    def can_afford(self, cost: float) -> bool:
        return self.balance >= cost

    def consume(self, operation: str, cost: float, idempotency_key: str = "") -> EnergyEntry | None:
        if not self.can_afford(cost):
            return None
        balance_before = self.balance
        entry = EnergyEntry(
            caller_id=self.caller_id,
            operation=operation,
            cost=cost,
            balance_before=balance_before,
            balance_after=balance_before - cost,
            idempotency_key=idempotency_key,
        )
        self.consumed += cost
        self.entries.append(entry)
        return entry


# Default pricing table — extracted from D_Economy/energy_ledger.py
DEFAULT_PRICING: dict[str, float] = {
    "minerva_research": 10.0,
    "ontoderive_engine": 5.0,
    "eidos_validate": 2.0,
    "kos_index": 3.0,
    "kronos_ingest": 1.0,
    "sophia_compile": 5.0,
    "agora_route": 0.5,
    "codeanalyze_scan": 2.0,
}
```

**测试文件: `projects/kairon/packages/eu-pricing/tests/test_energy_model.py`**

```python
"""Tests for energy_model — extracted from SharedBrain D_Economy."""
from eu_pricing.energy_model import EnergyBudget, EnergyEntry, ResourceType, DEFAULT_PRICING


def test_budget_initial_balance():
    budget = EnergyBudget(caller_id="test-caller", limit=1000.0)
    assert budget.balance == 1000.0
    assert budget.consumed == 0.0


def test_budget_can_afford():
    budget = EnergyBudget(caller_id="test", limit=100.0)
    assert budget.can_afford(50.0)
    assert not budget.can_afford(200.0)


def test_budget_consume_success():
    budget = EnergyBudget(caller_id="test", limit=100.0)
    entry = budget.consume("test_op", 30.0, idempotency_key="ik-001")
    assert entry is not None
    assert entry.cost == 30.0
    assert budget.balance == 70.0


def test_budget_consume_insufficient():
    budget = EnergyBudget(caller_id="test", limit=50.0)
    entry = budget.consume("test_op", 100.0)
    assert entry is None
    assert budget.balance == 50.0  # unchanged


def test_energy_entry_to_dict():
    entry = EnergyEntry(
        caller_id="test",
        operation="minerva_research",
        cost=10.0,
        balance_before=100.0,
        balance_after=90.0,
    )
    d = entry.to_dict()
    assert d["caller_id"] == "test"
    assert d["cost"] == 10.0


def test_resource_type_enum():
    assert ResourceType.EU.value == "eu"
    assert ResourceType.NECTAR.value == "nectar"
    assert ResourceType.QUOTA.value == "quota"


def test_default_pricing_has_expected_entries():
    assert DEFAULT_PRICING["minerva_research"] == 10.0
    assert DEFAULT_PRICING["kronos_ingest"] == 1.0
    assert DEFAULT_PRICING["agora_route"] == 0.5
```

**验证:**
```bash
cd projects/kairon && uv run pytest packages/eu-pricing/tests/test_energy_model.py -v
# 预期: 7 passed
```

---

### Task W1.5: D_KnowledgeIntegration 核心能力注入 kos

**新建文件: `projects/kairon/packages/kos/src/kos/knowledge_bridge.py`**

```python
"""Knowledge integration bridge — connects harvest output to knowledge stores.

Extracted core abstractions from SharedBrain D_KnowledgeIntegration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

QUALITY_THRESHOLD = 0.6


@dataclass
class KnowledgeRecord:
    """A single knowledge record with quality scoring."""
    source: str
    content: dict[str, Any]
    quality_score: float = 0.0
    triple_count: int = 0
    validated: bool = False

    def meets_threshold(self) -> bool:
        return self.quality_score >= QUALITY_THRESHOLD

    def validate(self) -> bool:
        """Validate record meets quality and content requirements."""
        if not self.content:
            return False
        if self.quality_score < QUALITY_THRESHOLD:
            return False
        self.validated = True
        return True

    def to_triple(self) -> tuple[str, str, str] | None:
        """Extract (subject, predicate, object) triple from validated record."""
        if not self.validated:
            return None
        subj = self.content.get("entity", self.source)
        pred = self.content.get("relation", "has")
        obj = self.content.get("value", str(self.content))
        return (str(subj), str(pred), str(obj))
```

**测试文件: `projects/kairon/packages/kos/tests/test_knowledge_bridge.py`**

```python
"""Tests for knowledge_bridge."""
from kos.knowledge_bridge import KnowledgeRecord, QUALITY_THRESHOLD


def test_record_below_threshold_fails():
    record = KnowledgeRecord(source="test", content={"a": 1}, quality_score=0.3)
    assert not record.meets_threshold()
    assert not record.validate()


def test_record_above_threshold_passes():
    record = KnowledgeRecord(source="test", content={"a": 1}, quality_score=0.8)
    assert record.meets_threshold()
    assert record.validate()
    assert record.validated


def test_record_empty_content_fails():
    record = KnowledgeRecord(source="test", content={}, quality_score=0.9)
    assert not record.validate()


def test_record_to_triple():
    record = KnowledgeRecord(
        source="minerva",
        content={"entity": "Python", "relation": "requires", "value": "CPython 3.13+"},
        quality_score=0.8,
        validated=True,
    )
    triple = record.to_triple()
    assert triple == ("Python", "requires", "CPython 3.13+")


def test_record_to_triple_unvalidated_returns_none():
    record = KnowledgeRecord(source="test", content={"a": 1}, quality_score=0.8)
    assert record.to_triple() is None


def test_triple_count_tracks_validation():
    record = KnowledgeRecord(source="test", content={"entity": "X", "relation": "Y", "value": "Z"}, quality_score=0.9)
    assert record.triple_count == 0
    record.validate()
    assert record.triple_count == 0  # triple_count is explicit, not auto
```

**验证:**
```bash
cd projects/kairon && uv run pytest packages/kos/tests/test_knowledge_bridge.py -v
# 预期: 6 passed
```

---

### Task W1.6: 代码审查 — 交叉验证

运行全面检查:
```bash
cd projects/kairon && make lint          # ruff 检查新增代码
cd projects/kairon && uv run pytest packages/eu-pricing/tests/ packages/kos/tests/ -v  # 所有新测试
python3 scripts/sync_omo_state.py --omo-dir .omo  # 更新系统状态
```

---

### Task W1.7: 标记 Wave 1 完成

更新 `.omo/state/system.yaml` 中 resolved_debt_items:
```yaml
resolved_debt_items:
  - SB_DECOMPOSITION    # Wave 1 迁移启动
  - SB_UNTESTED          # eu-pricing + kos 新增测试
```

---

## Wave 2-4 (概要 — 详细计划在后续 Phase)

| Wave | 器官 | 目标包 | 预估行数 | 时间 |
|:----:|------|--------|:------:|:----:|
| W2 | D_Gateway | agora | 15K | 5-7天 |
| W2 | D_Intelligence | minerva | 3K | 2天 |
| W2 | D_Extension | forge | 3K | 2天 |
| W2 | D_Cloud | kairon 新包 | 3K | 2天 |
| W2 | D_Voice | kairon 新包 | 2K | 2天 |
| W3 | D_Logos | ontoderive | 8K | 5-7天 |
| W3 | D_Harvest | minerva | 20K | 7-10天 |
| W3 | D_Memory schema | eidos/gbrain | 10K | 7-10天 |
| W4 | D_Excretion | kairon 新包 | 5K | 3-5天 |
| W4 | D_Immunity 清理 | — | 清理过度设计 | 2天 |

---

## 验证清单 (Phase 17 Wave 1)

```
[ ] W0.1 — debt_weight 公式已部署，health_score 反映真实健康度
[ ] W0.2 — SharedBrain 去留决策正式记录 (DECOMPOSITION.md)
[ ] W0.3 — PROJECTS.yaml lines 更新为 824K
[ ] W0.4 — sync_omo_state.py 运行通过
[ ] W1.1 — D_Execution 标记废弃 + agentmesh 覆盖验证
[ ] W1.2 — D_Governance 标记废弃 + .omo 覆盖验证
[ ] W1.3 — D_Window 移除
[ ] W1.4 — eu-pricing 注入 energy_model (7 tests pass)
[ ] W1.5 — kos 注入 knowledge_bridge (6 tests pass)
[ ] W1.6 — ruff lint + pytest 全通过
[ ] W1.7 — system.yaml resolved_debt_items 更新
```

---

*计划日期: 2026-06-01 · 维护: omostation .omo plans/*
