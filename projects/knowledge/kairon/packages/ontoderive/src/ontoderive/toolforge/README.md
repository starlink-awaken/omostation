---
title: README
type: doc
---

# ToolForge — 思维工具匹配模块

> 从 MindForge 项目并入 OntoDerive，作为推导的前置步骤。

## 定位

在 OntoDerive 的推导链中，Step 0 是"选择分析框架"——但此前没有工具支持这一步。ToolForge 填补了这一空缺。

## 快速使用

```bash
# 独立使用
python3 engine/toolforge/matcher.py "分析新能源汽车市场" --context "竞争,政策"

# 输出推导指导
python3 engine/toolforge/matcher.py "设计数字化平台" --context "政府,教育" --inference-guide

# JSON 输出（供程序调用）
python3 engine/toolforge/matcher.py "产业园区规划" --context "区域,创新" --json

# 与 OntoDerive 联动
python3 engine/derive.py --project my-project --with-tools --goal "目标描述" --tool-context "关键词" --derive
```

## MCP 工具

```bash
# 启动 MCP Server（可注册到 Agora）
python3 engine/toolforge/mcp_server.py
```

提供 3 个 MCP 工具：`toolforge_match`、`toolforge_select`、`toolforge_guide`。

## 工具目录

52 个思维工具，覆盖 6 个维度（方法论/策略/模式/原则/理论/技能），适配 3 个垂直领域：

| 领域 | 代表工具 |
|------|---------|
| 通用分析 | 波特五力、SWOT、PEST、金字塔原理 |
| 政府治理 | 利益相关者分析、多源流模型、渐进决策、公共价值 |
| 教育科技 | ADDIE模型、产教融合、建构主义、布鲁姆分类 |
| 产业园区 | 产业集群理论、三螺旋创新、TRL、技术转移 |

## 架构

```
MindForge (原独立项目) → ToolForge (OntoDerive 子模块)
    111行匹配引擎           →  +MCP Server, +推导指导生成
    30工具目录              →  52工具目录
    独立CLI                 →  OntoDerive --with-tools 联动
```

## 相关文档

- OntoDerive 使用指南
- OntoDerive Agent 指南
- 产品愿景
