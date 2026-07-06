---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0141-m2-base-schema.md
  - 0132-l0-mof-m4-metamodel.md
  - ../../../../bin/m2-date-migrate.py
  - ../../../projects/ecos/src/ecos/ssot/mof/m2/
supersedes: []
---

# ADR-0143: 45 m2 schema date → datetime 迁移 (Round 4c)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

ADR-0141 (Round 3a) 揭示** 45 个 m2 schema **用 `YYYY-MM-DD` (date) 而非
`YYYY-MM-DDThh:mm:ss` (datetime) 格式。M2BS-03 设计上接受 2 种格式(兼容性),
但 ADR-0143 治本一致性: 45 个 schema 全部迁移到 datetime。

**实施**: `bin/m2-date-migrate.py` 自动迁移(`--apply` 模式), 默认 08:00:00
标准化时刻 (m2 schema 普遍以工作日早 8 点创建)。

---

## 1. 触发

R3a check_5 实证发现:
- 49 个 m2 schema (除 M2BaseSchema 抽象类)
- 8 schema (Round 3a 当时感知) → 实测 **45 个 schema** 用 date 格式
- 4 schema 用 datetime (含 `'`23:27:00'` ` `T10:00:00'` 等格式混用)

M2BaseSchema M2BS-03 兼容 date 格式(原始):
- [ADR-0141 §2.4 created 兼容性](./0141-m2-base-schema.md) 接受 `YYYY-MM-DD`

但这只是**向前兼容**, 不是 SSOT 唯一目标。45 schema 不一致是真问题:

1. **审计盲点**: 当 created 用于"m2 schema 创建时间排序"时, 没法区分
   "上午还是下午", 损害 governance timeline 重构能力
2. **跨仓 SSR**: 跨仓工具若按 ISO-8601 datetime 处理 created, 8 schema
   会成"零时刻"(无小时部分)
3. **测不准**: OMO health_score / mof-validate 等工具的"最近改动"
   指标需要 datetime 精度

---

## 2. 决策

### 决策 1: 治本迁移, 不继续兼容

`bin/mof-bootstrap.py check_5` M2BS-03 验证**只接受 datetime** (移除 date 兼容)。
**例外**: 1 天内 (2026-07-06) 过渡期, 由 `bin/m2-date-migrate.py --apply` 完成迁移。

### 决策 2: 时刻标准化 08:00:00

所有 date 格式 schema 用 `T08:00:00` 标准化时刻:
- 时间选 8:00 (上班早 8 点) 是 empirical 习惯
- 不暴露真实作者本人的创建时刻 (SSOT 是 "schema 第一次入仓")
- 后续 `omo` 工具读 created 不会有歧义

### 决策 3: 不动 schema 内容

仅改 `created:` 字段一行, 不动 m3_parent / description / requiredProperties 等。
治本影响局部最小, P72 守门。

---

## 3. 实施

### 3.1 bin/m2-date-migrate.py

CLI 工具, 默认 dry-run, --apply 才改:
- 扫描 m2/*.yaml (除 m2_base_schema.yaml 抽象类)
- 匹配 `created: 'YYYY-MM-DD'` (无 T, 无时分秒)
- 输出每个 schema 的"current → new"
- 一次全部 apply, 不可单文件 (P72 一致性批量原则)

### 3.2 check_5 加强

`bin/mof-bootstrap.py check_5`:
```python
- if not re.match(r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?(\.\d+)?", ...):
+ # Round 4c: 严格要求 datetime, 不再兼容纯 date
+ if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ...):
+ # 治本回归
```

(本 ADR 配套 commit 实施)

### 3.3 45 个 schema 一次性迁移

```
ComputeEngine.yaml: created '2026-06-07' → '2026-06-07T08:00:00'
ComputeNode.yaml: ...
[+43 个]
```

---

## 4. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| 45 schema 全部迁 | `bin/m2-date-migrate.py --apply` | 45/45 ✓ |
| 5-check strict | `bin/mof-bootstrap.py all` | check_1..5 全 0 err (无回退) |
| 46 回归测试 | `tests/integration/m4_metamodel/run_all.py` | 46/46 PASS |
| Health Score | `bin/m4-health-score.py --emit` | 99.17/100 (无回退) |

### 治本后 L0-constraint 数据完整性

(m2 维度)
- created 字段 51 个 schema (49 旧 + 1 M2BaseSchema + 49 旧) 全 datetime
- 跨仓 SSOT 工具读 created 不会丢精度
- 后续 schema 治理按 M2BS-03 datetime 严格执行

---

## 5. 不在本 ADR 范围

- ❌ 改 m3.yaml / model-driven 引擎
- ❌ 改 meta_model.py
- ❌ 跨仓 caller 同步
- ❌ Round 4d (OMO cron hook)

---

## 6. 关联

- [ADR-0141](./0141-m2-base-schema.md) (本 ADR 是 M2BS-03 的治本, 替代 ADR-0141 §2.4 兼容策略)
- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (M4 主决策)
- [ADR-0137](./0137-derived-plane-relocation.md) (Round 2a 同源派生模式)

---

## 7. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (Round 4c, 45 m2 schema 迁 datetime, M2BS-03 治本) |
