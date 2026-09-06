---
schema_version: specification/v1
spec_version: 1.0.0
title: "E-DOC 双平面边界门禁落地"
bet_id: BET-Y1Q4-T6-20
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-06
last-reviewed: 2026-09-06
type: ssot
last_updated: 2026-09-06
---

# E-DOC 双平面边界门禁落地 (T6-20)

## Intent

将 ADR-0191 长期处于 DESIGN-ONLY 的 E-DOC-001~005 边界规则正式接线入 MOF 规则引擎与 CI 门禁。
实现 Documents 内容平面：零脚本、零构建缓存、零跨域裸写与客户端配置防漂移硬拦截。

## Architecture

```
bin/gac/check-documents-boundary.py（统一入口）
├─ E-DOC-001: Documents 目录下可执行脚本扫描 (.py/.sh/.js/.ts/.rb/.go)
├─ E-DOC-002: 环境依赖目录检测 (node_modules/.venv/__pycache__/.pytest_cache)
├─ E-DOC-003: 跨域写入拦截 (Workspace→Documents 非 BOS 裸写)
├─ E-DOC-004: 关键事实文件 Schema 校验 (_entities/facts/*.yaml, 14天保鲜)
├─ E-DOC-005: 多客户端配置一致性 (documents-domain-projects.yaml → IDE configs)
└─ Diagnostic Envelope: 违规时输出自愈修复建议

.omo/_truth/registry/governance-checks.yaml（注册 E-DOC-001~005）
└─ 接入 make gac-local-gate 与 pre-commit

tests/test_documents_boundary_check.py（违规样本注入测试）
└─ 验证拦截率 100% + 准确自愈建议
```

## Done Criteria

1. `bin/gac/check-documents-boundary.py` 覆盖 E-DOC-001~005 全部 5 条规则
2. `governance-checks.yaml` 注册 E-DOC-001~005，接入 `gac-local-gate`
3. 测试覆盖违规样本，拦截率 100%，自愈建议准确
4. 支持 `--dry-run` 模式与 Diagnostic Envelope 输出

## Non-Goals

- 不物理删除历史已归档的旧代码文件
- 不修改 Documents 物理目录中已受保护的真实业务事实
