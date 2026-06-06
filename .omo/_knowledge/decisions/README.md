# Architecture Decision Records (ADR)

> 制度化 omostation 的架构决策记录 · 防止隐性知识单点集中
> 启用日期: 2026-06-05 (Phase 28 W3) · MADR 风格

---

## 目的

记录 omostation 的重大架构决策的**背景、选项、决策、后果**，让任何后续协作者
（人类或 Agent）能回答：

- 当时为什么这样选？
- 还有哪些备选？备选的代价是什么？
- 这个决策现在还有效吗？是否已被替代？

---

## 命名规则

- 文件名: `NNNN-<kebab-case-title>.md`
- 编号: 4 位 zero-padded 全局递增（0001, 0002, 0003, ...）
- 标题: 动词 + 宾语（例如 "agora 路由表精简策略"）
- 路径: 全部存放在本目录 `.omo/_knowledge/decisions/`

---

## Status 状态机

```
   PROPOSED ──> ACCEPTED ──> DEPRECATED
                    │
                    └──> SUPERSEDED by ADR-NNNN
```

| Status | 含义 |
|--------|------|
| `PROPOSED` | 提案中，待评审；尚未落地实施 |
| `ACCEPTED` | 已接受并实施；当前生效 |
| `DEPRECATED` | 仍然有效但不再推荐用于新场景；旧系统维持 |
| `SUPERSEDED` | 已被新的 ADR 替代；必须填 `Superseded by: ADR-NNNN` |

**Status 流转规则**:
- 新建 ADR 默认为 `PROPOSED`，评审通过后改为 `ACCEPTED`
- 决策被新 ADR 替代时，**旧 ADR 改 `SUPERSEDED`** + 填新 ADR 号；**新 ADR 写 `Supersedes: ADR-NNNN`**
- 不允许直接删除任何 ADR 文件（仅可标记 `DEPRECATED` 或 `SUPERSEDED`）

---

## MADR 模板

每份 ADR 至少包含以下章节（顺序锁定）：

```markdown
# ADR-NNNN: <动词+宾语 标题>

- **Status**: ACCEPTED | PROPOSED | DEPRECATED | SUPERSEDED
- **Date**: YYYY-MM-DD
- **Authors**: <who>
- **Supersedes**: (无 或 ADR-NNNN)
- **Superseded by**: (无 或 ADR-NNNN)

## Context and Problem Statement

<2-4 段：什么场景、什么痛点、什么约束>

## Decision Drivers

* <驱动 1>
* <驱动 2>
* ...

## Considered Options

1. <方案 A>
2. <方案 B>
3. <方案 C>

## Decision Outcome

**Chosen option: "<X>", because <主要理由>.**

### Consequences

* Good: <好处>
* Bad: <代价>

### Confirmation

<如何验证这个决策生效>

## Pros and Cons of the Options

### <方案 A>

<优点/缺点>

### <方案 B>

<优点/缺点>

## References

* <链接/文件>
```

---

## 维护规则

1. **每个 Phase 关闭前**: 治理 Agent 必须检查本 Phase 是否有新的架构决策未记录
2. **新 ADR 编号**: 取 `INDEX.md` 中最大编号 + 1；冲突时由人类审批
3. **不接受空决策**: 任何"暂不决策"或"延后"必须以 ADR 形式记录（含 `Status: PROPOSED` + 延后原因）
4. **不复制事实**: 引用其他文档时用相对路径指针，不复制内容

---

## 相关文件

- 索引表: `INDEX.md`
- 候选收集（历史）: 由 `P28-W1-ADR-COLLECT` 任务完成

---

*创建于 2026-06-05 · Owner: P28-W3-ADR-SETUP*
