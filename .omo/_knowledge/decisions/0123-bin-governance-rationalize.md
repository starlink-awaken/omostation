---
status: proposed
lifecycle: rfc
owner: governance-team
last-reviewed: 2026-07-02
---

# ADR-0123: bin/ 治理工具集重整 (命名归一 + 孤立工具接入 gate)

- **Status**: PROPOSED
- **Date**: 2026-07-02
- **Authors**: P3-1 audit (work/p0-baseline-fix)
- **Supersedes**: —
- **Related**: ADR-0106 (GaC 北极星), `bin/README.md`

## Context and Problem Statement

`bin/` 当前 97 个工具,审计发现 3 类治理面问题:

### 问题 1: 命名混乱 (gov- vs governance-)

| 短前缀 | 长前缀 | 数量 |
|--------|--------|------|
| `gov-` | `governance-` | 2 vs 6 |
| `dashboard-` | (混合) | 2 (4 个 dashboard 工具混在 gac- / governance-) |

`bin/gov-history-stats.py` 和 `bin/gac/governance-history-insight.py` 是同类工具两个名字,
新人 grep `gov-` 找不到 `governance-` 系列。`bin/dashboard-readiness-summary.py` 和
`bin/dashboard-ui-render.py` 与 `bin/gac/governance-dashboard.py` 职责重叠但命名分裂。

### 问题 2: 8 个 check-* 工具游离于 gate 之外

| 工具 | 调方数 | 在 gac-local-gate CHECKS? |
|------|--------|--------------------------|
| `check-god-module` | 3 | ❌ |
| `check-boundary` | 1 | ❌ |
| `check-cross-refs` | 0 | ❌ |
| `check-dashboard-registry-consistency` | 0 | ❌ |
| `check-dead-path-refs` | 0 | ❌ |
| `check-domain-m1-alignment` | 0 | ❌ |
| `check-toolbox-ssot` | 0 | ❌ |
| `check-alert-coverage` | 0 | ❌ |
| `check_health_ssot` | 0 | ❌ |

9 个 check- 工具**仅在 `bin/README.md` 和自指里被提到**,**没有任何 caller 实际调**——典型
"工具存在但未接" 治理盲区,与 P2-1 CR-X1-EVIDENCE-RUNNABLE 警示的"声明绿/执行红" 同源。

### 问题 3: 4 个 dashboard 工具职责重叠

- `bin/dashboard-readiness-summary.py`
- `bin/dashboard-ui-render.py`
- `bin/gac/governance-dashboard.py`
- `bin/gac-dashboard.py`

4 个 dashboard 工具输入/输出/数据源 高度重叠 (governance readiness 视角), 但分散在 4 个
文件, 维护成本高, 调用方混乱。

## Decision Drivers

- 工具命名一致性 (新人不必记两套前缀)
- 治理面 (gate) 覆盖完整 (check- 工具真接)
- 维护成本降低 (dashboard 合并)
- 不破坏现有 caller (Makefile / .github/workflows / pre-commit)
- 与 ADR-0106 (GaC) 方向一致 (机制 4: drift 自检)

## Considered Options

### A. 渐进 rename + 接入 (推荐)

**Phase 1 (本 PR)**: 写 standards + GaC 规则, 不动文件.
**Phase 2 (后续 PR)**: 短前缀 → 长前缀 rename (gov- → governance-, dashboard-readiness-
→ governance-readiness-), Makefile / workflows / pre-commit / docs 同步改.
**Phase 3 (后续 PR)**: 8 个 check-* 工具接入 gac-local-gate CHECKS (评估每个的
false-positive 风险, 4 类: 立即接 / scoped 接 / CI-only / 归档).
**Phase 4 (后续 PR)**: 4 个 dashboard 工具合并为 1 个 `governance-dashboard.py`
+ 可选 subcommand (`render` / `summary` / `ui`).

### B. 一次性全改

- 优点: 一步到位
- 缺点: 大 PR 难 review, 跨多 caller 改路径风险高, 违反"小步快跑" 治理原则

### C. 维持现状 + 写文档

- 优点: 0 风险
- 缺点: 治理盲区持续, 工具碎片化加剧, 与 GaC 7 机制冲突 (机制 4: drift 自检)

## Decision

**采用 A: 渐进 rename + 接入**。Phase 1 仅写 standards + 规则, 不动文件。

## Consequences

### 正面

- 标准 + 规则先落地, 后续 PR 有了 SSOT 指针
- 4 个 phase 各自独立可回滚
- 与 GaC 7 机制 + 6 层 drift 矩阵方向一致

### 负面

- 需要 4 个 phase 跨多 commit 完成, 时间长
- 工具重整期间, 旧 prefix 文件可能暂时还存在, doc-ssot 短暂不一致

## Implementation Phases (后续 PR 启动)

#### Phase 1: 标准 + 规则 (本 ADR 提交, 配套 commit)

- [x] 写本 ADR
- [ ] 在 `.omo/standards/bin-tool-naming.md` 写命名规范 (gov-→governance-, dashboard-→governance-dashboard-)
- [ ] 在 `.omo/_truth/registry/governance-checks.yaml` 加 `CR-META-BIN-NAMING` 规则守命名
- [ ] 在 `.omo/_truth/registry/governance-checks.yaml` 加 `CR-META-BIN-ORPHAN` 规则守"工具未接" (类似 P2-1 evidence-runnable, 但覆盖 bin/*)

#### Phase 2: 短前缀 rename (后续 PR)

- `gov-history-stats.py` → `governance-history-stats.py`
- `gov-trend-report.py` → `governance-trend-report.py`
- 同步改 Makefile / workflows / pre-commit / docs (估计 5-10 个 caller)

#### Phase 3: check-* 工具接入 (后续 PR)

每个 check-* 工具评估:
- 0 false-positive 风险 → 立即进 CHECKS
- 有 false-positive 但低 → CI_ONLY (strict 模式跑)
- 频繁 false-positive → 归档到 `bin/_archive/` + GaC 规则标记 deprecated
- 评估结果写进 ADR-0116 (后续)

#### Phase 4: dashboard 合并 (后续 PR)

`bin/gac/governance-dashboard.py <subcommand>` 统一入口, 4 个原工具标 deprecated, 后续删.

## Alternatives Not Chosen

- **不重命名, 写 alias shim**: 增加维护成本, 不解决根因
- **只 Phase 1 不后续**: 标准 + 规则无执行, 落入"声明/执行鸿沟" (P2-1 已警示)

## Open Questions

- check-* 工具的真实 false-positive 率需要跑数据, 暂无样本
- dashboard 合并后是否需要保留 sub-frontend (HTML / JSON / 终端) 三种输出格式
- `gov-` vs `governance-` 短前缀是否在某些老 caller 里"已被记住" (影响 Phase 2 优先级)
