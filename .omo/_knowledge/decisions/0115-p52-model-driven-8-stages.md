---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-30
---

# ADR-0115: model-driven LifecycleStage 7→8 阶段 (P60 GOVERNANCE_MAINTENANCE)

- **Status**: ACCEPTED (P60 实施, P52 闭环测试)
- **Date**: 2026-06-30
- **Authors**: governance-team (CI pytest 修复 + 治本路线)
- **Superseded by**: (无)
- **Related**: model-driven commit `87b7914` (P60 实施), `.omo/_knowledge/audits/2026-06-29-l0-ssot-m0-mof-alignment.md`

## Context and Problem Statement

model-driven M3 扩展 `LifecycleStage` 枚举在 P60 (2026-06-24) 从 7 阶段
扩为 8 阶段, 新增 `GOVERNANCE_MAINTENANCE` 阶段:

```python
class LifecycleStage(Enum):
    PLANNING = "planning"
    DESIGN = "design"
    DEVELOPMENT = "development"
    DEPLOYMENT = "deployment"
    RUNTIME = "runtime"
    OPERATIONS = "operations"
    BUSINESS_OPS = "business_ops"            # P60+ 运营态
    GOVERNANCE_MAINTENANCE = "governance_maintenance"  # P60+ 治理维护态
```

但 `tests/test_lifecycle.py` 和 `tests/test_m3_extended.py` 中 4 处
断言仍为 `assert len(...) == 7`, 与 P60 实施冲突:

```
tests/test_lifecycle.py:43:        assert len(tracker.stages) == 7  # expected 8
tests/test_lifecycle.py:75:        assert progress["total_stages"] == 7  # expected 8
tests/test_m3_extended.py:22:    assert len(list(LifecycleStage)) == 7  # expected 8
tests/test_m3_extended.py:45:    assert len(STANDARD_STAGES) == 7  # expected 8
```

**后果**: ci-python-coverage.yml 在 model-driven 的 4 个测试 fail,
阻断整个 matrix。P60 设计 (含完整 entry/exit_criteria) 落地但测试未同步。

## Decision

1. **测试断言 7→8 同步** (3 个文件, 4 处断言) — 反映 P60+ 实际 enum 数量
2. **不加注释"历史 7"**: 8 是当前规范, 7 是 P60 前的临时态, 测试对齐
   当前规范而非历史, 避免 ADR 链上形成"为什么从 7 改 8"的反向考古
3. **P60 GOVERNANCE_MAINTENANCE 阶段保留**:
   - entry_criteria: 系统进入稳态治理 + governance_score=100 A+
   - exit_criteria: drift_low<=2, frontmatter>=95%, commit_closure=健康
4. **未来扩展规则**: 阶段数变更必须先在 ADR 登记, 再改代码 + 测试同步

## Consequences

**正向**:
- ci-python-coverage.yml 在 model-driven 重回 green
- 8 阶段语义与 P60 设计一致, 后续 LifecycleTracker.get_progress() 等
  返回正确 total_stages
- 治本: 测试与生产代码语义同步, 防止类似 STAGE 数量错位再现

**负向**:
- 测试从此锁死 "8 阶段" 假设, 第 9 阶段添加时需 3 处同步改
- 缓解: ADR-0115 末尾约定"阶段数变更需先 ADR 登记"

## Alternatives Considered

- **A. 撤销 P60 新增 GOVERNANCE_MAINTENANCE**:
  - 拒绝: P60 有完整设计理由 (稳态治理闭环), 撤销是倒退
- **B. 测试跳过 stage count 断言**:
  - 拒绝: 失去回归保护, 未来 enum 不一致会再次 fail 在生产
- **C. 测试改为 >= 7**:
  - 拒绝: 弱化断言, 不能捕获"多加一个意外 stage" 的回归

## References

- model-driven commit `87b7914 chore(model-driven): P60 M3 第 8 阶段 GOVERNANCE_MAINTENANCE`
- model-driven commit `ad90c48 test: 7→8 断言同步 (P60+)`
- omo root commit `036b833a chore: bump model-driven 7→8 修复`
- 测试 4 处修改:
  - `tests/test_lifecycle.py:43` len(tracker.stages) == 7→8
  - `tests/test_lifecycle.py:75` progress["total_stages"] == 7→8
  - `tests/test_m3_extended.py:22` len(list(LifecycleStage)) == 7→8
  - `tests/test_m3_extended.py:45` len(STANDARD_STAGES) == 7→8
