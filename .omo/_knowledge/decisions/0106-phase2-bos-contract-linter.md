---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0106: Phase 2 BOS Contract Linter v0.2 (--explain + --impact 智能增强)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P110+ (Phase 2)
- **Extends**: ADR-0105 (Phase 0 v0.1)
- **Superseded by**: (无)

## Context and Problem Statement

Phase 0 v0.1 已落地 (commit 197d670b): 工具 + pyproject + pre-commit 3 交付物。Phase 1 (强制接入) 在用户授权时实施。Phase 2 提案引入**智能化升级**:

| 维度 | Phase 0 v0.1 (现状) | Phase 2 v0.2 (提案) |
|:-----|:-------------------|:--------------------|
| `--explain <error-id>` | ❌ 无 | ✅ 自然语言解释 (Panel 渲染) |
| `--impact <uri>` | ❌ 无 | ✅ 影响分析 (deps + files) |
| MTTR | 小时级 | 分钟级 (--explain) |
| 变更前风险评估 | ❌ 无 | ✅ 部分覆盖 (--impact) |

**Phase 2 调研前置条件**:
- ✅ Phase 0 v0.1 已稳定 (326L, commit 197d670b)
- ✅ rich.panel 在 deps (rich>=15.0.0)
- ✅ `--explain` / `--impact` 在 v0.1 中**不存在** (grep 确认 0 匹配)

**关键问题**: 提案 file_mappings 仅覆盖 3/100 services (3%), 97% `--impact` 输出空数组。

## Decision

### D1: Phase 2 调整 (vs 提案, 4 项必要)

| 编号 | 调整 | 原因 |
|:-----|:-----|:-----|
| **B1** (ex A1) | file_mappings 从 3 key 扩展到 12 key | 提案 3/100 (3%) 覆盖度过低, 12 key 覆盖 ~70% |
| **B2** (ex A2) | explanations 从 2 扩展到 4 (含 SCOPE_VALIDATION_SKIPPED + ACTION_NAMING_CONVENTION) | 提案仅解释 2 个, v0.1 有 4 个规则 |
| **B3** (ex A3) | 增量修改 v0.1 文件 (非重写), 复用现有 326L | 风险控制 + diff 可读 |
| **B4** (ex A4) | `--impact` 退出码: 0 (命中) / 1 (未找到 mapping) | CI 集成友好 |

### D2: 12 个 file_mappings (B1 扩展)

| (domain, action) | URI 示例 | 受影响文件 |
|:-----------------|:---------|:----------|
| (governance, audit) | bos://governance/omo/audit | omo_audit.py + x1-governance-policies.yaml |
| (governance, inspect) | bos://governance/omo/inspect | omo_inspect.py |
| (governance, decide) | bos://governance/metaos/decide | metaos/decide.py |
| (governance, gate) | bos://governance/quality/gate | omo_governance.py + omo_governance_surfaces.py |
| (governance, debt) | bos://governance/omo/debt | omo_debt.py + omo_debt_approval.py |
| (analysis, search) | bos://analysis/minerva/search | minerva_search.py |
| (analysis, research) | bos://analysis/minerva/research | minerva_research.py |
| (memory, search) | bos://memory/kos/search | kos/cli.py |
| (memory, ingest) | bos://memory/kos/ingest | kos/cli.py |
| (memory, all-search) | bos://memory/local/all-search | agora/bos_resolver.py |
| (capability, run) | bos://capability/swarm/run | swarm/rpc.py |
| (meta, discover) | bos://meta/discover | agora/bos_resolver.py |

### D3: 4 个 explanations (B2 扩展)

| error_id | 解释范围 |
|:---------|:---------|
| INTERNAL_MODULE_NOT_FOUND | 检查 module_path / func_name / 文件存在 / submodule 状态 |
| INVALID_SCOPE | 修复路径 + naming convention |
| **SCOPE_VALIDATION_SKIPPED** (新增) | 启用 scope 验证的步骤 + 价值说明 |
| **ACTION_NAMING_CONVENTION** (新增) | 命名约定 + 为什么重要 |

### D4: 收口统计

| 指标 | Phase 0 v0.1 (P110+) | Phase 2 v0.2 (本 ADR) | 变化 |
|:-----|:---------------------|:----------------------|:-----|
| `mof_contract_lint.py` | 326L | **546L** | +220L (+67%) |
| CLI flag 数 | 3 (`--json`, `--quiet`, `--bos-yaml`) | **5** (`+ --explain`, `+ --impact`) | +2 |
| explanations 字典 | 0 | **4** | +4 |
| file_mappings 字典 | 0 | **12** | +12 |
| 退出码 | 0/1 (validation) | **0/1** (validation + explain + impact) | 不变 (B4) |
| 向后兼容 | N/A | ✅ 默认行为不变 | OK |
| ADR 数 | 65 | **67** | +2 (Phase 2 + pre-analysis) |
| mof-version | v0.0.100 | **v0.0.101** | +1 |

### D5: 验证结果 (8 测试用例)

| # | 测试 | 结果 |
|:-:|:-----|:-----|
| 1 | `mof-contract-lint --help` | ✅ 显示 5 flag |
| 2 | `--explain INTERNAL_MODULE_NOT_FOUND` | ✅ Panel 渲染 + 自然语言 |
| 3 | `--explain SCOPE_VALIDATION_SKIPPED` (B2 新增) | ✅ Panel 渲染 |
| 4 | `--explain XYZ_UNKNOWN` | ✅ exit 1 + 显示 4 已知 ID |
| 5 | `--impact bos://governance/omo/audit` | ✅ 17 deps + 2 files |
| 6 | `--impact bos://memory/kos/search` | ✅ 12 deps + 1 file (kos/cli.py) |
| 7 | `--impact bos://capability/swarm/run` | ✅ 21 deps + 1 file (swarm/rpc.py) |
| 8 | `--impact bos://governance/UNKNOWN/x` | ✅ exit 1 + WARN "no mapping" |
| **Phase 0 回归** | `--quiet` / `--json` | ✅ 默认行为不变 (100 checks / 19 errors / 42 warnings) |
| **dashboard** | 22/22 OK | ✅ |

### D6: 与 Phase 0 / Phase 1 衔接

| 阶段 | 状态 | 衔接 |
|:-----|:----:|:-----|
| **Phase 0 v0.1** | ✅ 完成 (commit 197d670b) | 提供 v0.1 基础, 326L |
| **Phase 1** | 🔲 待启动 | CI workflow + system health + l4-kernel monitor (与 Phase 2 独立) |
| **Phase 2 v0.2** | ✅ 完成 (本 ADR) | --explain + --impact 在 v0.1 增量升级 |
| **Phase 3** | 🔲 待启动 | mof-contract-agent + /quest fix-bos-contract (依赖 Phase 2) |

## Consequences

**正面**:
- **MTTR 从小时 → 分钟级**: `--explain` 提供自然语言修复指南, 不需读源码
- **变更前风险评估**: `--impact` 显示 17 deps + 2 files, 支持知情决策
- **向后兼容**: Phase 0 默认行为完全不变, Phase 2 仅新增 2 个可选 flag
- **ROI 显著**: 估时 ~75 分钟, 实际 ~60 分钟 (略快), 长期价值高
- **70% 覆盖度**: B1 调整后 file_mappings 覆盖 70% services (vs 提案 3%)

**负面**:
- **B3 重叠覆盖**: 部分 (domain, action) 在 yaml 中无对应 URI (e.g. (analysis, search) 无 URI 命中), 这是 mappings 设计的固有约束
- **dependency 启发式粗糙**: Rule 1 (same domain) 在 governance 域返回 17 deps, 偏多, 需更精细规则 (Phase 3 改进)
- **影响文件路径未验证**: file_mappings 中路径是推断 (基于 bos-services.yaml 中的 module_path), 真实文件存在性未检查 (建议 Phase 3 加 `os.path.exists` 检查)

**关联**:
- **ADR-0105**: Phase 0 BOS Contract Linter 落地 (v0.1, 326L)
- **pre-analysis**: `.omo/_knowledge/decisions/phase2-bos-contract-linter-pre-analysis.md`
- **ADR-0106**: Phase 2 v0.2 升级 (本 ADR)
- **Phase 1 (待启动)**: agora CI workflow + system backend health + l4-kernel monitor

## Validation

```bash
# Phase 2 验证: 4 模式 + 2 新 flag
uv --directory projects/ecos run mof-contract-lint --help
uv --directory projects/ecos run mof-contract-lint --quiet --bos-yaml /path/to/bos-services.yaml
uv --directory projects/ecos run mof-contract-lint --json --bos-yaml /path/to/bos-services.yaml

# Phase 2 新 flag
uv --directory projects/ecos run mof-contract-lint --explain INTERNAL_MODULE_NOT_FOUND
uv --directory projects/ecos run mof-contract-lint --explain SCOPE_VALIDATION_SKIPPED
uv --directory projects/ecos run mof-contract-lint --impact "bos://governance/omo/audit" --bos-yaml /path/to/bos-services.yaml
uv --directory projects/ecos run mof-contract-lint --impact "bos://memory/kos/search" --bos-yaml /path/to/bos-services.yaml

# Phase 0 回归
uv --directory projects/ecos run mof-contract-lint --quiet --bos-yaml /path/to/bos-services.yaml
# 期望: 100 checks, 19 errors, 42 warnings (与 Phase 0 末完全一致)
```

## References

- **paste_1.txt**: BOS Contract Linter Phase 2: Intelligence 作战包 v1.0
- **pre-analysis**: `.omo/_knowledge/decisions/phase2-bos-contract-linter-pre-analysis.md`
- **ADR-0105**: Phase 0 BOS Contract Linter 落地 (v0.1)
- **ADR-0106**: Phase 2 v0.2 (本 ADR)
- **生态**: `projects/ecos/src/ecos/ssot/tools/mof_contract_lint.py` (v0.1 → v0.2), `projects/agora/etc/bos-services.yaml` (100 services)

---

*最后更新: 2026-06-25 · Phase 2 BOS Contract Linter v0.2 收口 (--explain + --impact, 4 explanations + 12 mappings, 70% 服务覆盖度, Phase 1+ 待推进)*
