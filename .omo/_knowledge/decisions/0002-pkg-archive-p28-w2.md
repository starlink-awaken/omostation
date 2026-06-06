# ADR-0002: kairon-assistant / kairon-voice 首批归档策略

- **Status**: ACCEPTED
- **Date**: 2026-06-05
- **Authors**: omostation P28-W3
- **Supersedes**: (无)
- **Superseded by**: (无)

## Context and Problem Statement

kairon workspace 当前在 `packages/` 下有 25 个包，其中仅 17 个是 `[tool.uv.sources]`
列出的活跃成员。**其余 8 个包是"孤儿"**：未在 workspace sources 列出、未被任何
活跃包按名依赖，但物理存在于 `packages/` 目录。

P28-W0-TOOL-HEATMAP 审计后，P28-W2-PKG-SLIM 任务对 6 个候选孤儿包做评分，
目标是选择首批归档清单。问题：

- **场景**: P28 进入"工具瘦身"阶段，需要决定哪些孤儿包先归档
- **痛点**: 25 → 17 的"活跃包"集合是事实，但 8 个孤儿在 CLAUDE.md/AGENTS.md 中
  仍有引用，对下游 Agent 产生误导（"这个包应该还在用"）
- **约束**:
  - 归档操作必须 0 外部破坏（无活跃包引用 = 0 引用 = 0 破坏）
  - 归档必须可回滚（`git mv` 到 `projects/_archived/`）
  - 任务规约明确将 `kairon-assistant` / `kairon-voice` 列为初始候选

## Decision Drivers

* **0 外部引用优先**: 候选包必须被外部 `import` 数为 0，否则归档 = 破坏活跃包
* **业务价值可衡量**: 评分 `总分 = 测试覆盖 × 业务价值 − 外部依赖 − 迁移成本`
  中，"业务价值"必须有证据（生产用户、活跃调用），不能凭印象
* **低迁移成本**: 归档操作应可在 1 个 PR 内完成，便于 review
* **CLAUDE.md/AGENTS.md 同步**: 归档后所有引用文档必须加删除线，避免误导
* **核心 8 包绝对保留**: `core-models / shared-lib / agora / minerva / forge /
  ssot-kernel / agent-runtime / llm-gateway` 禁止归档

## Considered Options

1. **`git mv` + workspace 移除成员 + 0 外部引用验证**（推荐）
2. 一次性归档所有 8 个孤儿包（含 kaironcloud-billing / engine-core 等）
3. 保留所有 25 个包不动，仅在文档中标"孤儿"

## Decision Outcome

**Chosen option: "1. git mv + workspace 移除成员 + 0 外部引用验证", because
评分 3 分（低风险高收益）的 `kairon-assistant` / `kairon-voice` 已通过
0 外部引用 + 0 生产用户 + whisper 依赖缺失三重验证；其他 6 个孤儿中
`shared-lib` 实际有 347 处引用、`kaironcloud-billing` 评分 7 分（风险高）、
`engine-core` 57 处内部引用，均不适合本批归档。**

具体执行：

- `kairon-assistant` → `git mv packages/kairon-assistant
  projects/_archived/kairon-archived-pkg-kairon-assistant-2026-06-05/`
- `kairon-voice` → 同上
- `[tool.uv.sources]` 不需改（glob 自动跳过；本来就没列这 2 个）
- `projects/kairon/CLAUDE.md` 在 L4 表格中加删除线
- `projects/kairon/AGENTS.md` 从"业务支撑"分组移除

### Consequences

* Good: 25 包 → 23 包（活跃 17 + 孤儿 6），CLAUDE.md/AGENTS.md 与 live 事实一致
* Good: 0 外部破坏（已验证 0 外部 import）
* Good: whisper 依赖缺失的 kairon-voice 不再产生"运行时报错但没人修"的死代码
* Bad: 未来若有人想启用 kairon-assistant / kairon-voice 需从 `_archived/` 恢复
  （有 `git mv` 可回滚，代价低）
* Bad: 下批归档需重新评分（kaironcloud-billing / engine-core 等），工作量前置

### Confirmation

* 即时验证: `cd projects/kairon && uv run python -c "import kairon_assistant"`
  应报 `ModuleNotFoundError`（即"找不到"是预期结果）
* 核心包验证: `uv run python -c "import minerva, kos, eidos, agora"` 仍可导入
* 测试验证: `uv run pytest packages/ -q --ignore=packages/_archived` 全量通过
* 文档验证: `CLAUDE.md` / `AGENTS.md` 中 `kairon-assistant` / `kairon-voice`
  标记为"已归档"

## Pros and Cons of the Options

### 1. git mv + workspace 移除成员 + 0 外部引用验证

* Good: 低风险（0 外部 import 已验证）
* Good: 可回滚（`git mv` 双向操作）
* Good: 1 PR 内完成
* Bad: 后续 6 个孤儿仍待处理（下批工作量）

### 2. 一次性归档所有 8 个孤儿包

* Good: 一步到位
* Bad: `shared-lib`（347 处引用）= 绝对禁止；归档 = 全面崩溃
* Bad: `kaironcloud-billing` 有 1 处 agora 引用，agora 是核心 L0 组件
* Bad: `engine-core` 57 处内部引用，136 文件 / 25.6k LOC，影响面不可控
* Bad: 风险分布不均，不符合"低风险批次先走"原则

### 3. 保留所有 25 个包不动

* Good: 0 操作、0 风险
* Bad: CLAUDE.md 仍声称 25 包、文档与 live 持续不一致
* Bad: 孤儿包继续被误 import（whisper 缺失仍会运行时报错）
* Bad: 治理债务只增不减
* Bad: 与 P28-W0-TOOL-HEATMAP 识别的瘦身机会完全脱节

## References

* `.omo/_delivery/phase28-pkg-slim-plan.md` — P28-W2 瘦身计划（评分细节）
* `.omo/_knowledge/management/tool-heatmap-phase28.md` — P28-W0 热力图审计
* `projects/kairon/CLAUDE.md` — 25 包结构描述（待更新加删除线）
* `projects/kairon/AGENTS.md` — 业务支撑分组（待更新移除）
* `projects/kairon/pyproject.toml` — `[tool.uv.sources]` 17 个活跃成员
