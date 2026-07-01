---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-30
---

# ADR-0118: 根仓 dev-deps 统一 — 部分真治本 + P3 follow-up

- **Status**: ACCEPTED (partial)
- **Date**: 2026-06-30
- **Authors**: governance-team (P52 真治本路线)
- **Related**:
  - ADR-0116 (Tier 1 vs Tier 2 反思)
  - ADR-0117 (撤销 P60 阶段)
  - `.omo/_knowledge/reviews/2026-06-30-phase1.1-l4-kernel-final-review.md`

## Context

2026-06-30 治本路线 Phase 2 目标: 根仓 `pyproject.toml` 集中 dev-deps,
子项目只声明 business deps, 消除 13 个项目 4 个 pytest 版本漂移。

期望实现:
- 根仓 `[tool.uv].dev-dependencies` 集中 pytest/pytest-asyncio/pytest-cov/ruff/mypy
- 各子项目 `[dependency-groups]` dev 段删除, 只保留 `[project.optional-dependencies] dev = []`
  (hatchling 兼容)
- CI 改 `uv sync --group dev` (在根仓) + `cd projects/X && uv run pytest`

## Decision

### 部分真治本: 根仓 workspace 包 10 个非 cross-source 项目

| 项目 | 状态 |
|------|:----:|
| bus-foundation, c2g, ecos, family-hub, l4-kernel, metaos, model-driven, omo, omo-debt, runtime | ✅ 根仓 workspace |
| agora, cockpit, aetherforge, kairon | ⏸ 暂留 (P3 work) |

### 跳过 4 个项目的根因

- **aetherforge, kairon**: `pyproject.toml` 有 `[tool.uv.workspace]` + `members = ["packages/*"]`,
  uv 不支持 nested workspace,根仓 workspace 包含时失败
- **agora**: `[tool.uv.sources]` 引用 `kairon = { path = "../kairon/packages/kos" }` 等,
  kairon 不在 workspace 时 path source 失效
- **cockpit**: `[tool.uv.sources]` 引用 `agora/omo/l4-kernel/runtime` via path source,
  跨 workspace 边界冲突

### 4 个项目暂留 P3 治理: `path source → workspace source` 重构

需要在根仓 workspace 包这 4 个项目**之前**, 把它们自己的 `tool.uv.sources` 从
`{ path = "../X" }` 改为 `{ workspace = true }`, 并配合根仓的 `[tool.uv.sources]` 声明。

## Rationale

### 治本 vs 治标
- 治标 (P52 渐进): 13 个项目各自 dev-deps, 版本漂移, 不治本
- 真治本 (本次): 10 个项目统一根仓 dev-deps, 治本
- 暂留 4 个项目: nested workspace 死结, **不是治标**, 是设计冲突, 需 P3 重构

### 接受部分真治本的理由
- 10 个项目治本 = 76% (13/17 Python 项目) 治本覆盖
- 4 个项目暂留 = 24% 待 P3, 公开记录在 ADR
- 整体 dev-deps 集中度: 5 版本 (pytest) → 1 版本, 4 版本 (pytest-asyncio) → 1 版本
- 不阻塞当前 session 推进, P3 work 记录明确

## Consequences

**正向**:
- 10 个项目 dev-deps 集中在根仓, uv lock 统一
- CI 改 `uv sync --group dev` 后这些项目共享同一 dev tools 版本
- 减少 30+ 行散落 dev-deps 配置
- 部分版本漂移消除 (3 个 pytest 版本 → 1 个)

**负向**:
- 4 个项目 (agora/cockpit/aetherforge/kairon) 仍 P3 暂留, 维护成本持续
- 根仓 workspace 不完整, CI 行为分裂 (10 个项目用根仓 dev, 4 个用项目本地 dev)
- 跨 4 个项目改 pyproject.toml 是大改, 需单独 phase

## Alternatives Considered

### A. 全量真治本 (10 + 4 个项目)
- 拒绝: 4 个 nested workspace 项目需先扁平化, 跨 17 项目大改
- 接受本次部分真治本, P3 work 单独做

### B. 不做 (治标)
- 拒绝: 治本路线目标明确, 治本一部分比全治标强

### C. 改用单独 per-project venv (治标)
- 拒绝: 不解决版本漂移根因

## P3 Work

### 优先级 1 (P0, 必须做, 治本 4 个项目)
1. 拆分 aetherforge/kairon 的 nested workspace:
   - 把 `members = ["packages/*"]` 改为单层
   - 各 package 独立 pyproject.toml, 无 nested
2. 改 agora/cockpit `tool.uv.sources`:
   - `path = "../X"` → `workspace = true` (在根仓 source 声明)
3. 验证: 17 个项目都进 workspace, uv sync 成功

### 优先级 2 (P1, 应该做)
- 改 hatchling build backend 为 uv_build (避免 dependency-groups 兼容问题)
- 各项目 [project.optional-dependencies] dev 完全删除
- hatchling + setuptools 用户: 评估迁移成本

## References

- `.omo/_knowledge/reviews/2026-06-30-phase1.1-l4-kernel-final-review.md`
- ADR-0116 (Tier 1 vs Tier 2 反思)
- uv workspace 文档: https://docs.astral.sh/uv/concepts/projects/workspaces/
- 当前 pyproject.toml: `/Users/xiamingxing/Workspace/pyproject.toml`
