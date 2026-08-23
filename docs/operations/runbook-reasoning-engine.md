# Runbook: 推理引擎异常排查

## 症状
- `mof-reason impact` 返回 0 依赖 (应为 >0)
- `mof-derive` 覆盖率 <100%
- `mof-gate` 报告违规 >0

## 排查步骤

### 1. 检查 M1 关系图谱
```bash
cd projects/ecos
uv run python3 src/ecos/ssot/tools/mof-relation-builder.py
```
- 如果 `有边节点 = 0`: 关系图谱未构建, 运行:
  ```bash
  uv run python3 src/ecos/ssot/tools/mof-relation-builder.py --apply
  ```

### 2. 检查 M1 status 合规
```bash
uv run python3 src/ecos/ssot/tools/mof-scan.py --check-status
```
- 如果有不合规: 检查具体节点, 添加缺失的 status 字段

### 3. 检查约束编译器
```bash
uv run python3 src/ecos/ssot/tools/ecos-constraint-compiler.py --enforce
```
- 如果失败: 读取输出定位违反的 required 约束

### 4. 验证修复
```bash
uv run python3 src/ecos/observability/dashboard.py
```

## 预防
- CI 每次 commit 自动运行 reasoning checks
- 关系图谱在 M1 节点变更后需重建
