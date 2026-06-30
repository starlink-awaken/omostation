---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-30
---

# ADR-0116: Tier 1 渐进式修复 vs Tier 2 真治本 (Meta-Reflection)

- **Status**: ACCEPTED
- **Date**: 2026-06-30
- **Authors**: governance-team (治本路线反思)
- **Related**:
  - ADR-0114 (L4 GaC 豁免)
  - ADR-0115 (model-driven 8 阶段 — **将撤销**, 见 ADR-0117)
  - 4 个 Tier 1 commit:
    - l4-kernel `b865ab4` (env 注入) — **Tier 1, 伪治本**
    - aetherforge `28d33c1` (PEP 735 dev-deps) — **Tier 1, 半治本**
    - model-driven `ad90c48` (7→8 断言) — **Tier 1, 伪治本**
    - ADR-0115 (7→8 接受) — **Tier 1, 伪治本**

## Context and Problem Statement

2026-06-30 治本路线 (P52-final) 启动, 目标: **解决 ci-python-coverage.yml 在
aetherforge/l4-kernel/model-driven 的 4 + 7 + 4 = 15 个测试 fail**。

初始方案 (Tier 1 渐进式, 已落地):
- l4-kernel: 加 `L4_<ID>_PATH` env + `path_overrides` 参数, 保留 `Path.home()` 默认
- aetherforge: 加 `[dependency-groups] dev`, 升 pytest 8.4.2
- model-driven: 测试 7→8, ADR-0115 接受 P60 第 8 阶段

反思: **Tier 1 是"伪治本"**:
- 真治本 = 撤销错误前提 (Path.home() 默认 / 散落 dev-deps / 错塞 X 阶段)
- 伪治本 = 为错误前提加配置 (env 注入 / PEP 735 / 7→8 改测试)

具体问题:

| 修复 | 错误前提 | 伪治本 | 真治本 (Tier 2) |
|------|---------|--------|----------------|
| l4-kernel path | `_BUILTIN_DOMAINS` 用 `Path.home()` 默认 | env 注入 | **删除默认**, 强制 path_overrides |
| aetherforge deps | 各项目独立声明 dev-deps | `[dependency-groups]` | **根仓统一**, 子项目只 business |
| model-driven stages | P60 误把 governance 塞 L2 | 7→8 改测试 | **撤销 P60 第 8 阶段** |

## Decision

### Tier 1 定位: 渐进式 (Quick Win)

承认 Tier 1 commit (`b865ab4`/`28d33c1`/`ad90c48`/`ADR-0115`) 是**临时**:
- 价值: CI 立即转绿, 给 Tier 2 争取时间
- 局限: 错误前提仍存活, 真治本需 Tier 2 撤销
- 接受: 短期不重构, 避免大规模破坏, 但**必须**进入 Tier 2

### Tier 2 真治本路线 (Roadmap)

1. **l4-kernel 强制 path_overrides** (Phase 1.1)
   - 删除 `_load_env_overrides` 整个方法
   - `DomainRegistry.__init__` 必须传 `path_overrides`, 缺失抛 `ValueError`
   - 测试 fixture 改为显式传 (不是 env)
   - `l4_kernel/cli.py` 从 TOML 配置文件读 path

2. **model-driven 撤销 8 阶段** (Phase 1.2, 详见 ADR-0117)
   - 撤销 `LifecycleStage.GOVERNANCE_MAINTENANCE`
   - 撤销 `STAGES` 中 `STAGE-GOVERNANCE-MAINTENANCE`
   - 测试 8→7 (恢复原状)
   - ADR-0115 改写为 ADR-0117 (撤销记录)

3. **根仓 dev-deps 统一** (Phase 2)
   - 根仓新建 `pyproject.toml`, 集中 `[tool.uv].dev-dependencies`
   - 17 子项目删除 `[dependency-groups] dev` 和 `[project.optional-dependencies] dev`
   - CI 改 `uv sync --group dev` (在根仓) + `cd projects/X && uv run pytest`
   - pytest 版本统一 (避免 8.4.2 vs 9.0.3 漂移)

4. **集成验证** (Phase 3)
   - 17 项目 pytest 全跑, 记录 baseline
   - 真实 CI runner 模拟 (`HOME=/home/runner`)
   - 文档更新 (CLAUDE.md, AGENTS.md, docs/PANORAMA.md)

### 不做 Tier 2 的代价

- l4-kernel: 错误前提 `Path.home()` 仍存活, 任何 Windows/Linux/容器部署都需要
  monkeypatch 或环境变量绕道, 增加维护成本
- aetherforge/model-driven/runtime/cockpit: dev-deps 散落, pytest 版本漂移
  风险, 新项目加入需手动对齐
- model-driven: 8 阶段错塞 L2, 5+4+1+1 分层被破坏, 后续 governance
  误塞风险高

## Consequences

**正向** (接受 Tier 1 的代价):
- CI 立即转绿, 治理分回升
- 治本路线时间窗口拉长, 不阻塞

**负向** (Tier 1 的局限):
- 错误前提仍存活, 真治本需 Tier 2
- ADR-0115 之后会**被 ADR-0117 撤销** (Tier 1 ADR 反转是公开记录, 不删)

**Tier 2 后的统一**:
- l4-kernel: 任何部署必须显式提供 path, 错误即 fail-fast
- aetherforge 等 17 项目: dev-deps 集中在根仓, pytest 版本统一
- model-driven: 7 阶段恢复, governance 归 X 轴

## Alternatives Considered

### A. 不回滚 Tier 1, 接受现状

- **拒绝**: 长期保留 3 个错误前提, 维护成本高, ADR 公开承认"伪治本"是
  反向压力

### B. 一次性全部 Tier 2 (不回滚, 直接重写)

- **拒绝**: 跨 17 项目 + 3 个 commit 反转, 风险高, 不符合渐进式
- **采用**: 分阶段 (1.1, 1.2, 2, 3), 每步独立 commit + 验证

### C. 撤销 Tier 1 commit

- **拒绝**: Tier 1 commit 给 CI 转绿, 撤销会再次 fail
- **采用**: 保留 Tier 1 commit 作为"过渡", 但文档化说明 Tier 2 真治本方向

## References

- Tier 1 commit: `b865ab4` (l4-kernel env), `28d33c1` (aetherforge PEP 735),
  `ad90c48` (model-driven 7→8)
- ADR-0115 (7→8 接受, **将撤销**)
- 后续: ADR-0117 (撤销 P60 第 8 阶段, 待写)
- 后续: Tier 2 真治本 commit 序列 (待实施)
