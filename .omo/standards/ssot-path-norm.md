---
type: standard
version: "1.0"
status: active
owner: governance-team
last_updated: 2026-09-04
---

# SSOT 路径规范 (ssot-path-norm)

> SSOT 声明路径必须与 broker 实际写入路径一致

## 规则

1. **路径一致性**: SSOT 文档中声明的路径必须与实际文件路径完全匹配
2. **禁止路径错位**: 不得将 SSOT 文件声明在 `.omo/` 但实际写入 `runtime/omi/` (gitignored)
3. **source_ref 有效**: governance-checks.yaml 中的 source_ref 必须指向存在的文件

## 案例

- **反面案例**: `dependency-baseline` 从 `.omo/` 迁到 `runtime/omo/` 导致 CI 无法获取
- **正面案例**: 所有 `.omo/_truth/registry/*.yaml` 路径与实际文件一致

## 检查命令

```bash
python3 bin/ssot/doc-ssot-lint.py --json
python3 bin/gac/governance-convergence-lint.py --rule ssot-path-norm
```

## 相关

- ADR-0121: SSOT 路径与 broker 写入路径一致
- CR-L0-SSOT-PATH-NORM: 对应 GaC 规则
- `.omo/standards/doc-ssot-contract.md`: SSOT 契约总纲
