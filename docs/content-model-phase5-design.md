---
schema: md/v1
status: active
lifecycle: planning
owner: governance-team
type: plan
last-reviewed: 2026-09-28
---

# Phase 5 实时约束执行设计

## 目标

从 CI 批量 → pre-commit → 写入时即时验证。

## 设计

### 1. pre-commit 扩展

在 `.pre-commit-config.yaml` 增加 content-model-check hook：
- FM schema 检查
- 引用完整性检查
- 提交时拦截违规

### 2. 增量执行

规则引擎支持 `--changed-only`：
- 只检查 git diff 涉及的文件
- 大型 PR 门禁 <30s

### 3. MCP 写入验证（后期）

评估 MCP 工具写入时验证的可行性。

## 实施步骤

1. 实现 pre-commit hook（1-2 天）
2. 实现增量执行（1 天）
3. 评估 MCP 写入验证（0.5 天）

## 风险

- pre-commit hook 性能：需要增量执行
- MCP 写入验证：风险高，放后期

## 成功标准

- pre-commit 拦截内容模型违规
- 大型 PR 门禁 <30s
