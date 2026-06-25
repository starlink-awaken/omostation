---
category: workflows
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# ontoderive engine/ 合并方案

> Created: 2026-06-19 | Status: DEFERRED — 需 dedicated session

## 当前状态

| 位置 | 文件数 | 说明 |
|------|--------|------|
| `packages/ontoderive/engine/` | 116 | 根目录幽灵目录，包含完整实现 |
| `packages/ontoderive/src/ontoderive/` | 21 | 安装包，仅部分实现 |
| `packages/ontoderive/src/ontoderive/engine/` | 6 | src 内的 engine 子目录 |
| `packages/ontoderive/tests/` | 50 | 全部通过 sys.path 导入 engine/ |

## 根 engine/ 子目录结构

```
engine/
├── core/           # 核心引擎 (derive/check/export/pipeline)
├── theories/       # 理论层 (analytics/bayesian/controller)
├── reasoners/      # 推理器 (rules/)
├── intelligence/   # 智能层 (llm/enhancer)
├── foundation/     # 基础层 (config/rules/)
├── ecosystem/      # 生态层
├── ontolang/       # DSL 解析器
├── pipeline_steps/ # 管道步骤
└── toolforge/      # 工具锻造
```

## 合并步骤

1. 将 engine/ 子目录内容复制到 src/ontoderive/
2. 保留 src/ontoderive/ 现有文件不动
3. 更新 pyproject.toml packages 配置
4. 更新 50 个测试文件的 import 路径
5. 移除 sys.path hack
6. 删除根 engine/ 目录
7. 全量测试验证

## 风险

- 高：50 个测试文件的 import 更新可能遗漏
- 中：两个目录可能有同名文件冲突
- 低：pyproject.toml 构建配置变更

## 前置条件

- 需要完整理解 engine/ 和 src/ontoderive/ 的文件对应关系
- 建议先做文件 diff 分析，确认无冲突再执行
