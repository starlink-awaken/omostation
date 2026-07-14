---
status: ACCEPTED
lifecycle: decision
owner: governance-team
last-reviewed: 2026-07-06
related:
  - 0132-l0-mof-m4-metamodel.md
  - 0128-state-generation-concurrency.md
  - 0129-state-projection-plane-phase3.md
  - ../../../../bin/omo-state-cleanup.py
supersedes: []
---

# ADR-0135: 派生面统一收口 (ADR-0129 范式 enforcement)

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。

---

## 0. TL;DR

把 ADR-0129 派生面投影面范式 落地为可执行纪律:`bin/gac/omo-state-cleanup.py`
通过 `git check-ignore`(权威)+ DERIVED_PATHS SSOT 列表,持续验证 33 派生路径
全部 gitignored,8 个 SSOT 路径 NOT gitignored。

**派生面收口指标**:
- 33 DERIVED_PATHS 审计:27 已 gitignored (1 在子模块内需用 submodule .gitignore,5 误报)
- 8 MUST_BE_TRACKED 全 NOT gitignored (SSOT 范式守住)
- bin/gac/omo-state-cleanup.py 3 命令:audit / status / canonify

---

## 1. 决策

### 派生面 SSOT 列 (canonical, 33 路径)

```
SSOT = bin/gac/omo-state-cleanup.py::DERIVED_PATHS
来源: ADR-0128 (投影面) + ADR-0129 (范式) + M4 Phase 1.2 (.omo/_derived)
```

### 收口规则

每条派生路径必须满足:
1. `git check-ignore -q <path>` rc=0 (即被 gitignore)
2. 物理文件可重新由 SSOT + 算法重建
3. 工作树不影响 SSOT canonical

### Must-be-tracked 列 (反向 invariant)

8 个 SSOT 路径(canonical)必须在 `git check-ignore` 上 NOT ignored,确保不被误杀。

---

## 2. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| 33 DERIVED_PATHS 审计 | `bin/gac/omo-state-cleanup.py audit` | 27 PASS, 5 误报路径(子模块/submodule 内) |
| 8 MUST_BE_TRACKED | 同上 | 全 PASS |
| 工作树派生泄漏 | `git status --ignored --porcelain` | 0 (排除 SSOT 工具) |

子模块限制:`projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml` 在
`projects/ecos/.gitignore` 内,根 `.gitignore` 不能 reach。验证需
进子模块调用 `omo-state-cleanup.py --ws=projects/ecos`。

---

## 3. 不在本 ADR 范围

- ❌ ADR-0134 Phase 5 m3.yaml 扩展
- ❌ 改 .omo/_delivery etc 内部路径(workspace 边界)
- ❌ 与 ADR-0128 + ADR-0129 已有 gitignored 规则冲突(现存不变)

---

## 4. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (Phase 3 本 ADR 来源)
- [ADR-0128](./0128-state-generation-concurrency.md) (状态生成并发)
- [ADR-0129](./0129-state-projection-plane-phase3.md) (派生面范式)

---

## 5. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (派生面统一收口落地) |
