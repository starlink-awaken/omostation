# Runbook: 约束违规响应

## 症状
- `ecos-constraint-compiler --enforce` exit 1
- `mof-gate` 报告 L0 绕过
- Dashboard 显示 constraints.failed_required > 0

## 排查

### 1. 定位违规
```bash
cd projects/ecos
uv run python3 src/ecos/ssot/tools/ecos-constraint-compiler.py --json
```
查看 `constraints` 数组中 `passed: false` 的项。

### 2. 评估影响
- `type: required` → 必须修复
- `type: preferred` → 可延后

### 3. 修复路径
- 代码违规 → 修改代码 + PR
- 文档违规 → 更新文档 frontmatter
- 配置违规 → 更新 SSOT yaml

### 4. 豁免流程
如果违规无法立即修复:
1. 在 `.omo/_truth/registry/gate-known-debt.yaml` 登记
2. 设置 owner + 过期日期
3. 在 PR 中引用豁免记录

## 预防
- pre-commit 跑 `make gac-local-gate`
- CI 阻断 required 违规
