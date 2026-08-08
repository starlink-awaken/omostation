# BET-Y1Q2-T6-05 Closeout: 减法配额制门禁上线

**BET ID**: BET-Y1Q2-T6-05
**Track**: T6-SUBTRACT
**Window**: Y1Q2
**Status**: done
**Completed at**: 2026-08-08

## Objective
实现"增1删1"门禁：PR 新增 GaC 规则必须同时删除一条，新增 ADR 必须同时归档一份。

## Implementation
- `bin/gac/check-subtraction-quota.py`: 读 staged diff，统计 GAC-RULE-*.yaml 和 ADR 的增删数
- 注册至 `gac-local-gate.py` GATES_LIST (pre-commit + CI 双触发)
- 例外机制: `SWARM_ESCAPE_ID=subtraction-quota` 可绕过

## Design Decisions
- 仅检查 `--diff-filter=AD` (Added/Deleted)，忽略 Modified (重命名不算新增)
- GaC 规则匹配: `projects/ecos/.*/GAC-RULE-.*\.yaml$` (M1 派生文件路径)
- ADR 匹配: `\.omo/_knowledge/decisions/\d{4}-.*\.md$` (标准 ADR 路径)
- 门禁默认 non-strict (pre-commit 可跳过), CI strict 兜底

## Verification
- 脚本 exit 0 = PASS, exit 1 = FAIL
- 无 staged changes 时直接 PASS
- SWARM_ESCAPE_ID 绕过已实现
- 已注册至 gac-local-gate.py GATES_LIST
