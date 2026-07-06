---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-06
related:
  - 0132-l0-mof-m4-metamodel.md
  - 0133-l0-constraints-v2-cutover.md
  - 0134-m3-meta-cutover.md
  - 0135-derived-plane-unification.md
  - 0136-m3-yaml-extension-p5.md
  - 0137-derived-plane-relocation.md
  - 0138-meta-element-promotion.md
  - 0139-model-driven-8stage-revival-rejected.md
  - 0140-m4-health-score.md
  - 0141-m2-base-schema.md
  - ../../../../docs/M4-DECISIONS-INDEX.md
supersedes: []
---

# ADR-0142: M4 决策速查表 (Round 4b)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

新增 `docs/M4-DECISIONS-INDEX.md`, 把 11 个 M4 ADR + ADR-0142 自身
(本 ADR) 速查组织成单一文档, 让开发者能在 60 秒内定位任一 M4 决策。

**与既有文档的关系**:
- `.omo/_knowledge/decisions/INDEX.md` 是**权威索引**(单源 SSOT)
- `docs/M4-ROADMAP.md` 是**时间线**(14 周 5 phase 38 里程碑)
- **本文档** 是**面向开发者的人可读速查**(以人为本, 不是 SSOT)

---

## 1. 决策

### 1.1 文档三件套范式

```
SSOT (权威): .omo/_knowledge/decisions/INDEX.md
时间线: docs/M4-ROADMAP.md
速查: docs/M4-DECISIONS-INDEX.md     ← 本 ADR 新增
```

**为什么需要速查**: INDEX 是 markdown table 格式, 适合机读。
ROADMAP 是 narrative 格式, 适合规划阶段。
开发者调试时需要"看一眼就知道哪条 ADR 解决哪类问题", 速查表最有效。

### 1.2 速查表结构

每行一个 ADR:
- ADR ID
- 标题 (≤ 1 行)
- Round (R0/R2a/R2b/R2c/R3a/R3b/R4b)
- 实施产物 (代码/schema 文件指针)
- 关闭测试 (T1..T44 ID 范围)

### 1.3 沉淀原则清单

11 个 M4 决策沉淀出 4 条主导原则:
1. **P52**: 不动元模型/引擎/历史撤销决定
2. **P72**: 派生面跟随 SSOT 源, 不集中到主仓根
3. **P74**: 每阶段独立 PR + ADR + 回归测试
4. **ADR-0129**: 派生面 gitignored 双轨

---

## 2. 不在本 ADR 范围

- ❌ 改 `.omo/_knowledge/decisions/INDEX.md` (那是 SSOT)
- ❌ 改 `docs/M4-ROADMAP.md` (那是 timeline)
- ❌ 把速查表升级为 SSOT (本 ADR 明确 SSOT 在 INDEX.md)

---

## 3. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (M4 主决策)
- [.omo/_knowledge/decisions/INDEX.md](./../../../../.omo/_knowledge/decisions/INDEX.md) (SSOT)
- [docs/M4-ROADMAP.md](./../../../../docs/M4-ROADMAP.md) (timeline)
- [docs/M4-DECISIONS-INDEX.md](./../../../../docs/M4-DECISIONS-INDEX.md) (本文档产出)

---

## 4. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 4b, 11 + 1 ADR 速查) |
