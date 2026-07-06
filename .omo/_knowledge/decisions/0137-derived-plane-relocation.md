---
status: ACCEPTED
lifecycle: decision
owner: governance-team + eCOS team
last-reviewed: 2026-07-06
related:
  - 0129-state-projection-plane-phase3.md
  - 0132-l0-mof-m4-metamodel.md
  - 0133-l0-constraints-v2-cutover.md
  - 0136-m3-yaml-extension-p5.md
  - ../../../../bin/l0-constraints-migrate.py
  - ../../../../bin/omo-state-cleanup.py
  - ../../../projects/ecos/src/ecos/ssot/mof/m0/mof_driven.py
  - ../../../projects/ecos/.gitignore
  - ../../../../.gitignore
supersedes:
  - 0133 (partial: the v2 derived-path default)
---

# ADR-0137: 派生面落点纠偏 — 跟随 SSOT 源所在子模块

> **For agentic workers**: 本 ADR 是 ACCEPTED 状态(2026-07-06)。
> **重要**: 退役 commit 38c6377c 的"主仓根 .omo/_derived/ 入 ignore"规则。

---

## 0. TL;DR

P1-S2 (ADR-0133) 留下的技术债:派生面写到主仓根 `.omo/_derived/`,
违反 ADR-0129 投影面范式。修正:
- `bin/l0-constraints-migrate.py` 默认写到 `projects/ecos/.omo/_derived/`
- `projects/ecos/src/ecos/ssot/mof/m0/mof_driven.py` 默认写到 `projects/ecos/.omo/_derived/`
- 主仓根 `.gitignore` 移除 `.omo/_derived/` 规则 (commit 38c6377c 退役)
- 子模块 `projects/ecos/.gitignore` 新增 `.omo/_derived/` 规则
- 旧主仓派生面文件删除

---

## 1. 触发回顾

P1-S2 (ADR-0133) 实施时,l0-constraints.migrate 默认写到主仓根 `.omo/_derived/l0-constraints.v2.yaml`。
这是设计缺陷 — L0-constraints.yaml SSOT 在 `projects/ecos/src/ecos/ssot/registry/`,
派生面应跟随源。

ADR-0129 投影面范式核心原则:
  - SSOT = 手写, git tracked, 物理位置跟源
  - 派生面 = SSOT 算法重建产物, gitignored
  - 派生面应**靠近 SSOT**, 不集中到主仓根

---

## 2. 决策

**决策**:派生面默认写到 SSOT 所在子模块内的 `.omo/_derived/`。

```
SSOT: projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml
派生面: projects/ecos/.omo/_derived/l0-constraints.v2.yaml  ✓
       .omo/_derived/l0-constraints.v2.yaml               ✗ (退役)
```

**例外**:
- 跨仓派生(同时由多个子模块 SSOT 聚合)— 写主仓 `.omo/state/runtime/` 等集中投影面, 仍 gitignored
- LADS/M0 等运行时快照 — 在已 gitignored 的 `projects/ecos/src/ecos/ssot/mof/m0/snapshot.yaml` 位置不动

---

## 3. 实施

### 3.1 子模块 gitignore

`projects/ecos/.gitignore` 新增 `.omo/_derived/`(文件已写, 在子模块 commit 1dffde1 后)。

### 3.2 主仓 gitignore

`.gitignore` 移除 `.omo/_derived/` 规则(原 commit 38c6377c 那条),
改注释指明 ADR-0137 治本。

### 3.3 工具默认路径

- `bin/l0-constraints-migrate.py::V2_PATH_DEFAULT`:
  - 原: `.omo/_derived/l0-constraints.v2.yaml`
  - 新: `projects/ecos/.omo/_derived/l0-constraints.v2.yaml`
- `projects/ecos/src/ecos/ssot/mof/m0/mof_driven.py` `--write` 默认:
  - 原: `.omo/_derived/m0-driven.yaml`
  - 新: `projects/ecos/.omo/_derived/m0-driven.yaml`(工具运行 cwd 在 projects/ecos 内, 用 `../.omo/_derived/`)

### 3.4 旧文件清理

`rm .omo/_derived/l0-constraints.v2.yaml` (主仓根单文件, 自动重派生时回到正确位置)。

---

## 4. 验证

| 检查 | 工具 | 结果 |
|------|------|------|
| 38 测试不回归 | `tests/integration/m4_metamodel/run_all.py` | 38/38 PASS |
| 派生面 gitignored (子模块内) | `cd projects/ecos && git check-ignore .omo/_derived/l0-constraints.v2.yaml` | rc=0 ✓ |
| 派生面 gitignored (主仓根) | `git check-ignore .omo/_derived/l0-constraints.v2.yaml` | rc=1 ✓ (因为该路径不存在) |
| 新默认路径正确 | `bin/l0-constraints-migrate.py` 输出 | `v2 派生面: projects/ecos/.omo/_derived/l0-constraints.v2.yaml` |
| 38c6377c commit 退役 | `grep .omo/_derived/ .gitignore` | 仅注释, 无 active rule |

---

## 5. 不在本 ADR 范围

- ❌ 改 ADR-0133 主决策(只覆盖其派生面路径, 不覆盖 L0-constraints v2 形状)
- ❌ 改 L0-constraints.migrate 派生面逻辑
- ❌ 改 L0-constraints.v1 yaml 文件

---

## 6. 关联

- [ADR-0132](./0132-l0-mof-m4-metamodel.md) (主决策)
- [ADR-0133](./0133-l0-constraints-v2-cutover.md) (本 ADR 覆盖其 v2 默认路径)
- [ADR-0129](./0129-state-projection-plane-phase3.md) (本 ADR 是该范式 enforcement)
- [ADR-0136](./0136-m3-yaml-extension-p5.md) (preceding)

---

## 7. 变更日志

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初稿 ACCEPTED (派生面落点纠偏) |
