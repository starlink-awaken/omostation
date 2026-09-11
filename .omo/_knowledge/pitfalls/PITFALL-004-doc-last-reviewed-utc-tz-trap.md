---
status: active
lifecycle: pattern
owner: governance-team
last-reviewed: 2026-09-11
type: ssot
---
# PITFALL-004: doc-governance `last-reviewed` UTC 时区陷阱

- **条目编号**: `PITFALL-004`
- **严重等级**: `MEDIUM`
- **关联架构**: document-governance SSOT (`.omo/_truth/registry/document-governance.yaml`) / omo-knowledge surface
- **首次踩坑**: 2026-09-12 (fix/bet-entries-145-147 residue + PR #3606 首跑)

---

## 1. 踩坑现象与根因

### 现象
给 `.omo/_knowledge/**/*.md` 补 frontmatter 时写 `last-reviewed: 2026-09-12`（本地日期，CST 已过零
点），CI `doc-governance-check --no-new-warnings` 报
`invalid_metadata: last-reviewed cannot be in the future`，并使
`legacy-omo-knowledge-enums` 预算 59→60 超限，gac-gate 硬失败。

### 根因
校验器以 **UTC 日期** 判 "future"。本地时区 (Asia/Shanghai UTC+8) 08:00–24:00 之间，本地日期比
UTC 日期大一天；此时写本地日期必被判 "未来"。

### 规避配方
- 写 `last-reviewed` 一律用 **UTC 当天或之前** 的日期（保守: 写昨天）。
- CI 失败信息含 `cannot be in the future` 时，先查本地时区与 UTC 的日期差，不要盲目上调预算。
- 该陷阱会把新文件从 `legacy-omo-knowledge-frontmatter` 桶移入 `legacy-omo-knowledge-enums` 桶
  （补 frontmatter 后才开始枚举校验），两个预算别混淆。
