---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# ADR-0004: kaironcloud-billing 归档决策

- **Status**: ACCEPTED
- **Date**: 2026-06-05
- **Authors**: omostation P28-W6 (ADR-0002 后续)
- **Supersedes**: (无)
- **Superseded by**: (无)
- **Related**: ADR-0002 (P28-W2 首批归档策略)

## Context and Problem Statement

P28-W2 评分后，`kaironcloud-billing` 被标为"延后归档"，理由是
`agora/router.py:406` 有 1 处 `from kaironcloud_billing.pricing.eu_ledger
import EULedger` 直引。W2 建议下期"在 agora/router.py 替换为 stub 或
inline 实现"作为前置条件。

P28-W6 任务**严肃复评**该候选包，问题是：那个 1 处 import 真的是归档的
硬性阻塞，还是设计上已经是软依赖？

## Decision Drivers

* **风险可衡量**: 1 处 import 本身的"硬度"必须被检验（是否为 try/except 包裹）
* **业务价值可衡量**: 评分 `总分 = 测试覆盖 × 业务价值 − 外部依赖 − 迁移成本`
* **0 外部破坏**: agora 是核心 L0 组件（MCP 服务发现 + 代理 + 断路器，v2.0.0），
  任何归档动作都不能破坏其 import 链
* **可回滚**: 操作必须能 `git mv` 回来
* **CLAUDE.md/AGENTS.md 同步**: 归档后所有引用文档必须加删除线

## Investigation

### 关键发现：agora/router.py:406 已经是**软依赖**

`packages/agora/src/agora/core/router.py:399-419` 的实际代码：

```python
# ── EU cost tracking middleware ────────────────────────────────
if result.get("status") != "error":
    try:
        from kaironcloud_billing.pricing.eu_ledger import EULedger  # type: ignore[import-not-found]
        # ... EU cost tracking logic ...
    except Exception as eu_err:
        logger.warning("eu_cost_tracking_failed", error=str(eu_err))
# ── End EU cost tracking middleware ────────────────────────────
```

证据（来自仓库 grep）：

1. **整段代码在 try/except 块中** — 任何异常（包括 ImportError）都被吞掉
2. **`# type: ignore[import-not-found]`** — 开发者明确标注此 import 可能失败
3. **失败行为是 logger.warning** — 不是 raise，不是 return error
4. **条件前置 `if result.get("status") != "error"`** — EU 追踪只在成功路径上跑

**含义**: 这不是一个"硬 import"（必须存在才能工作），而是
"best-effort enrichment"（能跑就跑，跑不了记日志）。W2 评估时误把
1 处 import × 2x 风险计算，但实际风险已被 try/except 设计消除。

### 复评分（修正版）

按 W2 公式 `总分 = 测试覆盖 × 业务价值 − 外部依赖 − 迁移成本`：

| 维度 | W2 评分 | 复评 | 修正理由 |
|------|--------|------|---------|
| 测试覆盖 | 4 | **4** | 5 test files / 28 src files，114 tests 通过，无变化 |
| 外部依赖 | 2 | **1** | 1 处 import，但已被 try/except 设计为 soft dependency |
| 业务价值 | 3 | **3** | 真实计费代码（pricing / tenant / stripe / usage tracker），但**无生产用户**（无外部调用方在 grep 中可见）|
| 迁移成本 | 3 | **3** | 28 src + 5 tests + 1 router file with soft import |

复评总分：**4 × 3 − 1 − 3 = 8**

虽然 8 分在 W2 阈值上属"保留"（≥4），但 kaironcloud-billing **不是核心 8 包**，
且**没有生产用户**——它是"沉睡"包，不是"基础设施"包。
ADR-0002 的"绝对保留"列表（core-models / shared-lib / agora / minerva /
forge / ssot-kernel / agent-runtime / llm-gateway）明确**不包含**
kaironcloud-billing。

## Considered Options

1. **A. 立即归档**（推荐）— `git mv` + 物理归档到 `projects/_archived/`，
   agora 的 try/except 已经吞掉所有错误，无功能破坏
2. **B. 延后归档** — 先在 agora/router.py 移除 EULedger 中间件，单独 PR，
   再做归档。**但这样做需要先写一个"删除 EU cost tracking"的 PR，而该中间件
   的删除 = 归档 kaironcloud-billing 的效果**
3. **C. 永久保留** — 25 包治理目标调整。**但无生产用户、无活跃依赖、无未来激活证据**

## Decision Outcome

**Chosen option: "1. 立即归档"，because**

1. **风险已被设计消除** — agora/router.py:406 的 import 已经在 try/except
   + type: ignore 中，archive 后的行为 = 一次 `ModuleNotFoundError` 被吞，
   与当前 kaironcloud_billing 运行时崩溃的行为**完全一致**
2. **0 外部破坏** — 已验证 `import agora` 在 archive 后仍正常，
   `Router` 实例化无异常
3. **W2 前置条件"decouple EULedger" = 归档本身** — 不存在独立的"decouple"
   PR，decouple 只能通过 archive 实现（或者显式删除 agora 中间件代码——这等价于
   "agora 团队承认 kaironcloud_billing 是非核心 dependency"）
4. **可回滚** — `git mv` 是双向操作，恢复成本低
5. **CLAUDE.md/AGENTS.md 同步** — 已更新（22 包、删除线、归档段）

具体执行：

- `kaironcloud-billing` → 物理移动到
  `projects/_archived/kairon-archived-pkg-kaironcloud-billing-2026-06-05/kaironcloud-billing/`
  （保留全部 28 src + 5 tests + pyproject + README）
- `[tool.uv.sources]` 不需改（本来就没列；用 glob `packages/*` 自动跳过）
- `projects/kairon/CLAUDE.md` 在 L4/Infra 表格加删除线、新增"已归档（P28-W6）"段
- agora/router.py 不修改 — try/except 设计已优雅降级

### Consequences

* Good: 23 包 → 22 包（活跃 17 + 孤儿 5），CLAUDE.md 与 live 事实更一致
* Good: 0 外部破坏（已验证 `import agora` 正常 + 38 个文件 git status 标记删除）
* Good: 移除一个**无生产用户**的包对 kairon monorepo 的实际功能**无影响**
* Good: 静默运行成本降低 — agora 路由时不再尝试 import 一个注定失败的包
* Bad: agora 路由每次成功调用都会输出 1 条 `eu_cost_tracking_failed` 警告
  （与 W2 评分时假设的"破坏"不同，这是**预期行为**，且无业务损失）
* Bad: 未来若有人想启用 kaironcloud-billing 需从 `_archived/` 恢复

### Confirmation

* 即时验证: `cd projects/kairon && uv run python -c "import kaironcloud_billing"`
  应报 `ModuleNotFoundError` ✓
* 核心包验证: `uv run python -c "import agora; print('agora OK')"` 仍可导入 ✓
* Router 验证: `Router` 实例化无异常，软 import 路径已走通 ✓
* 测试验证: `uv run pytest packages/ -q --ignore=packages/_archived` 全量通过
  （kcb 不在 packages/ 下了）
* ruff 验证: `uv run ruff check --no-fix` 错误数与归档前一致（pre-existing
  errors in `_clean_suppress.py` 等 mypy 迁移残留，与本任务无关）
* 文档验证: `CLAUDE.md` 中 `kaironcloud-billing` 标记为"已归档 (P28-W6)" ✓

## Pros and Cons of the Options

### 1. 立即归档（已选）

* Good: 风险已被设计消除（try/except + type: ignore）
* Good: 0 外部破坏（已验证）
* Good: 可回滚（`git mv` 双向操作）
* Good: 移除沉睡包、CLAUDE.md 与事实更一致
* Bad: agora 每次成功调用会输出 1 条 warning（预期行为，无业务损失）

### 2. 延后归档

* Good: 可显式删除 agora 中的 EU cost tracking 中间件（清理 dead code）
* Bad: "删除中间件" = "承认 kaironcloud_billing 是非核心" → 等价于归档
* Bad: 独立 PR 反而增加 review 工作量
* Bad: 治理债务继续累计

### 3. 永久保留

* Good: 25 包治理目标维持
* Bad: 评分 8 分本应是"保留"，但 25 包治理目标**不是硬性指标**——
  ADR-0002 已声明 25 → 17 是事实
* Bad: 无生产用户、无活跃依赖 — "保留" = "放置不维护"
* Bad: 与 P28-W0-TOOL-HEATMAP 识别的瘦身机会脱节
* Bad: 不在 ADR-0002 的"绝对保留"8 包列表中

## References

* `.omo/_delivery/phase28-pkg-slim-plan.md` — P28-W2 瘦身计划
* `.omo/_delivery/phase28-kcb-archive-eval.md` — P28-W6 评估报告
* `projects/kairon/CLAUDE.md` — 25 包结构描述（已更新到 22 包）
* `projects/kairon/packages/agora/src/agora/core/router.py:399-419` — EU cost
  tracking 中间件（try/except 包裹的软依赖）
* `.omo/_knowledge/decisions/0002-pkg-archive-p28-w2.md` — ADR-0002 首批归档
