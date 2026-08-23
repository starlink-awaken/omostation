# Runbook: CI 红了怎么办

## 定位失败步骤
```bash
gh pr checks <PR_NUMBER>
```
找到第一步 RED 的步骤名。

## 本地复现
```bash
cd projects/ecos
# 约束编译器
uv run python3 src/ecos/ssot/tools/ecos-constraint-compiler.py --enforce
# M1 合规
uv run python3 src/ecos/ssot/tools/mof-scan.py --check-status
# 推理引擎
uv run python3 src/ecos/ssot/tools/mof-reason.py impact ACTION-ACP-IMPLEMENT
# 完整测试
uv run pytest tests/ -q
```

## 常见修复
- **约束违规**: 读 JSON 输出 → 定位规则 → 修代码/文档
- **M1 status 不合规**: 修节点 status 字段 → 重跑 relation-builder
- **测试失败**: 读 pytest output → 修源码或测试

## 验证
```bash
uv run python3 src/ecos/observability/dashboard.py
# 应显示 Overall: HEALTHY
```
