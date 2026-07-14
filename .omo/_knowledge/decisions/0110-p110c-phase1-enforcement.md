---
status: active
lifecycle: contract
owner: governance-team
last-reviewed: 2026-06-25
---

# ADR-0110: P110-C Phase 1 BOS Contract Linter 强制接入 (3 交付物)

- **Status**: ACCEPTED
- **Date**: 2026-06-25
- **Authors**: omostation P110-C
- **Extends**: ADR-0105 (Phase 0) + ADR-0106 (Phase 2) + ADR-0107 (Phase 3) + ADR-0108 (P110-A) + ADR-0109 (P110-B)
- **Superseded by**: (无)

## Context and Problem Statement

Phase 0+2+3 完成 (commit 197d670b + 4c1fc70f + 1a098355):
- v0.1 (基础 4 模式 CLI) + v0.2 (--explain + --impact) + v0.3 (agent + skill)
- pre-commit 本地门禁已工作 (Phase 0 实施)
- 但 CI / system health / 监督 仍未接入 (Phase 1 提案 5 天工作量)

**P110-C 调研前置条件**:
- ✅ `projects/agora/.github/workflows/ci.yml` 存在 (40L, 有 lint + test jobs)
- ✅ `projects/agora/src/agora/mcp/resolver/api.py` 存在 (URI 解析器)
- ❌ `projects/l4-kernel/src/l4_kernel/monitor/` 目录不存在 (需创建)

**P110-C 决策**: 实施 3 交付物 (agora CI gate + agora contract_health + l4-kernel monitor), Phase 1 完整闭环。

## Decision

### D1: 3 交付物实施 (P110-C R3)

| 交付物 | 路径 | 行数 | 状态 |
|:-------|:-----|:----:|:----:|
| **D4: CI gate** | `projects/agora/.github/workflows/ci.yml` | 40→63L (+23L) | ✅ |
| **D5: contract_health** | `projects/agora/src/agora/mcp/resolver/api.py` | 153→~240L (+87L) | ✅ |
| **D6: l4-kernel monitor** | `projects/l4-kernel/src/l4_kernel/monitor/contract_monitor.py` | (新) 152L | ✅ |
| **D6: monitor pkg** | `projects/l4-kernel/src/l4_kernel/monitor/__init__.py` | (新) 1L | ✅ |

### D2: D4 - agora CI gate 详细

```yaml
# 触发条件: PR 修改 projects/agora/etc/bos-services.yaml
if: ${{ github.event_name == 'pull_request' && contains(github.event.pull_request.changed_files, 'projects/agora/etc/bos-services.yaml') }}

# 步骤:
- Install ecos (uv sync in projects/ecos)
- Run: uv run mof-contract-lint --json --bos-yaml "../agora/etc/bos-services.yaml"
- exit 1 on error, 0 on pass
```

**关键设计**:
- `if:` 条件避免 PR 未改 bos-services.yaml 时无效运行
- `if: github.event_name == 'pull_request'` 仅 PR 触发 (push to main 不触发)
- `changed_files` 检查精确到具体文件

### D3: D5 - agora contract_health 详细

**新增 API**: `get_bos_contract_health(yaml_path: str = "") -> dict`

**实现**:
```python
def get_bos_contract_health(yaml_path: str = "") -> dict:
    # subprocess 跑 mof-contract-lint --json
    # 解析 status 字段: success/warning/error → GREEN/YELLOW/RED
    # 返回 {status, summary, raw, error (optional)}
```

**验证结果** (实测):
```
status: ERROR
summary: {'total_checks': 100, 'errors': 19, 'warnings': 42, 'successes': 39}
```
(对应当前 19 INTERNAL_MODULE_NOT_FOUND + 42 warnings)

**与现有 health 集成路径**:
- 未来可在 `list_backend_health()` 中调用 `get_bos_contract_health()`, 添加 `contract_health` 字段
- 当前保留独立函数, 避免影响现有 health 逻辑

### D4: D6 - l4-kernel monitor 详细

**功能**: 扫描 git log 找修改 bos-services.yaml 的 commit, 检查 commit message 含 "mof contract-lint" 关键字

**流程**:
1. `find_modified_commits(days_back=7)` → 7 天内 SHAs
2. `check_commit_for_lint(sha)` → 检查 commit message 含 LINT_KEYWORDS
3. 失败: 写 audit log + 创建 DEBT 条目 + exit 1

**LINT_KEYWORDS** (4 个关键字):
- `mof contract-lint` (Phase 0 pre-commit 标记)
- `mof-contract-lint` (CLI 名)
- `bos contract linter` (完整名)
- `contract lint` (短形)

**实测**:
```
[P110-C] Running BOS Contract Linter Bypass Monitor...
[OK] No suspicious commits found. All bos-services.yaml changes went through linter.
```
(当前 7 天内所有 bos-services.yaml commit 都含 lint 关键字)

### D5: 收口统计

| 指标 | P110-B 末 | P110-C 末 | 变化 |
|:-----|:----------|:----------|:-----:|
| `agora/.github/workflows/ci.yml` | 40L | 63L | +23L (CI gate) |
| `agora/src/agora/mcp/resolver/api.py` | 153L | ~240L | +87L (contract_health) |
| `l4-kernel/monitor/contract_monitor.py` | (新) | 152L | +152L |
| `l4-kernel/monitor/__init__.py` | (新) | 1L | +1L |
| 工具数 | 47 | 47 | 不变 |
| ADR 数 | 69 | **70** | +1 (本 ADR) |
| mof-version | v0.0.104 | v0.0.105 | +1 |

### D6: Phase 1 完整闭环 (3 阶段 4 ADR)

| 阶段 | 状态 | 累计交付物 |
|:-----|:----:|:----------|
| Phase 0 | ✅ | mof-contract-lint v0.1, pyproject, pre-commit |
| Phase 2 | ✅ | v0.2 (--explain + --impact + 12 mappings) |
| Phase 3 | ✅ | v0.3 (agent + skill + 30 天作战包收官) |
| **Phase 1** | ✅ (本 ADR) | **CI gate + contract_health + monitor** |

**Phase 1 价值**:
- **CI gate**: 阻止 PR 绕过 mof contract-lint (Phase 0 已有 pre-commit 兜底, CI 是双保险)
- **contract_health**: system 域健康度集成, dashboard 可见
- **monitor**: 7 天回溯检测 bypass 行为, 失败时记 DEBT

### D7: Phase 2 (智能) + Phase 3 (自治) 衔接

- Phase 2 已完成 (commit 4c1fc70f)
- Phase 3 已完成 (commit 1a098355)
- Phase 1 完成后, **30 天作战包 4 阶段全部闭环** (Phase 0+1+2+3)

**作战包最终状态**:
- Phase 0: 奠基 (mof-contract-lint v0.1, pre-commit)
- **Phase 1: 强制 (本 ADR, CI gate + health + monitor)**
- Phase 2: 智能 (--explain + --impact v0.2)
- Phase 3: 自治 (agent + skill v0.3)

## Consequences

**正面**:
- **30 天作战包 4 阶段 100% 闭环**: 4 ADR (0105/0106/0107/0110) + 5 commits
- **3 层门禁**: pre-commit (本地) + CI gate (PR) + l4-kernel monitor (定期)
- **system health 可见性**: `get_bos_contract_health()` API 可被 dashboard 调用
- **bypass 检测**: 7 天回溯, 自动 DEBT 创建, 触发 omo_alert

**负面**:
- **3 跨 submodule 改动**: agora CI / agora api / l4-kernel monitor (各自需人类审批 commit)
- **19 errors 当前**: CI gate 仍会失败 (INTERNAL_MODULE_NOT_FOUND), Phase 1 不修复此问题 (Phase 1 解决"如何检测", 不解决"如何修复")
- **monitor 检测精度有限**: 7 天回溯 + 关键字匹配是启发式, 实际 bypass 可能漏检
- **contract_health 函数未集成到 list_backend_health**: 留独立函数, 后续 P111+ 集成

**关联**:
- **ADR-0105**: Phase 0 v0.1
- **ADR-0106**: Phase 2 v0.2
- **ADR-0107**: Phase 3 v0.3 (mof-contract-agent + skill)
- **ADR-0108**: P110-A ecos domain_manager 跨 submodule 治理
- **ADR-0109**: P110-B omo_governance_surfaces build_report
- **ADR-0110**: P110-C Phase 1 强制接入 (本 ADR, 30 天作战包收官)

## Validation

```bash
# D4 验证: CI YAML
python3 -c "import yaml; yaml.safe_load(open('projects/agora/.github/workflows/ci.yml')); print('✅ ci.yml valid')"

# D5 验证: contract_health API
cd projects/agora && PYTHONPATH=src python3 -c "
from agora.mcp.resolver.api import get_bos_contract_health
result = get_bos_contract_health()
print(f'status: {result[\"status\"]}')
print(f'summary: {result.get(\"summary\", {})}')
"
# 期望: status=ERROR, summary={errors:19, warnings:42, ...}

# D6 验证: l4-kernel monitor
python3 projects/l4-kernel/src/l4_kernel/monitor/contract_monitor.py
# 期望: "[OK] No suspicious commits found"

# 综合验证: dashboard
PYTHONPATH=projects/omo/src python3 bin/gac/governance-dashboard.py
```

## References

- **paste_1.txt**: BOS Contract Linter 30 天作战包 (Phase 0+1+2+3 完整路线图)
- **ADR-0105**: Phase 0 v0.1 (commit 197d670b)
- **ADR-0106**: Phase 2 v0.2 (commit 4c1fc70f)
- **ADR-0107**: Phase 3 v0.3 (commit 1a098355)
- **ADR-0108**: P110-A ecos domain_manager (commit 5472b8aa)
- **ADR-0109**: P110-B omo_governance_surfaces build_report (commit cba9fa3e)
- **ADR-0110**: P110-C Phase 1 强制接入 (本 ADR, 30 天作战包 4 阶段收官)
- **生态**: `projects/agora/.github/workflows/ci.yml` (D4), `projects/agora/src/agora/mcp/resolver/api.py:get_bos_contract_health` (D5), `projects/l4-kernel/src/l4_kernel/monitor/contract_monitor.py` (D6)

---

*最后更新: 2026-06-25 · P110-C Phase 1 BOS Contract Linter 强制接入收官 (3 交付物, 30 天作战包 4 阶段 100% 闭环, 4 ADR + 5 commits)*
