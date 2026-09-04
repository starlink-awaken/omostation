---
title: USER_GUIDE
type: doc
---

# Minerva — 用户使用指南

> 面向人类用户：快速上手、常见场景、最佳实践、问题排错

---

## 目录

1. [5 分钟快速上手](#5-分钟快速上手)
2. [场景一：快速了解一个概念](#场景一快速了解一个概念)
3. [场景二：深度技术调研](#场景二深度技术调研)
4. [场景三：竞品分析](#场景三竞品分析)
5. [场景四：文献综述](#场景四文献综述)
6. [场景五：持续监控与维护](#场景五持续监控与维护)
7. [Web 控制台使用](#web-控制台使用)
8. [配置详解](#配置详解)
9. [常见问题](#常见问题)

---

## 5 分钟快速上手

### 安装

```bash
cd /path/to/minerva
pip install -e .
minerva init    # 首次运行向导：检查 Ollama、配置、API 密钥
```

### 第一条研究

```bash
# 30 秒出结果，完全免费（本地运行）
minerva research "什么是 transformer 架构" --level L0
```

你会看到：
```
⚡ Minerva — Deep Research
  Pipeline: L0 Quick [Search → QualityGate → Output]
  ⏱ Searching 5 sources...
  ✅ Report: ~/knowledge/reports/20260514-*.md
  📊 Quality: 7.8/10
```

### 读懂报告

报告位于 `~/knowledge/reports/`，包含：
- **TL;DR** — 一句话摘要
- **Research Process** — 研究过程说明（分析深度、方法说明）
- **Findings** — 核心发现
- **Sub-questions Analysis** — 子问题逐一分析
- **Source Confidence** — 每个来源的可信度评分
- **Verification Notes** — 验证说明

### 在浏览器中查看

```bash
minerva web                      # 启动 Web 服务
open http://localhost:8765       # 仪表盘
open http://localhost:8765/docs  # API 文档
```

---

## 场景一：快速了解一个概念

**适合：** 初次接触某个技术概念，需要快速概览。

```bash
minerva research "什么是 RAG（检索增强生成）" --level L0
```

**选择 L0 的原因：**
- 30 秒出结果
- 搜索 5 个来源（DDG + Scholar + arXiv）
- 本地 LLM 处理，零费用
- 适合"是什么"类问题

**预期输出：** 一份约 500 字的中英双语报告，包含定义、核心原理和关键引用。

---

## 场景二：深度技术调研

**适合：** 需要深入了解某个技术方向的实践细节和行业现状。

```bash
minerva research "MoE 混合专家模型在 2025 年的生产实践" --level L2
```

**选择 L2 的原因：**
- 约 2 分钟，成本 ~$0.30
- 自动将问题分解为子问题（架构、训练、推理、成本）
- 搜索 8 个来源 + 深度内容提取
- 实体提取 + 矛盾分析

**过程：**
```
Pipeline: L2 Deep [Decompose → Search → Extract → DeepRead → CrossAnalyze → QualityGate → Output]
  🔍 Decompose: 4 sub-questions
  📚 Search: 8 sources (DDG, Scholar, arXiv, Exa, Metaso, Brave, Zhipu, SearXNG)
  🏷  Extract: 23 entities, 18 relations
  📖 DeepRead: top-5 sources全文提取
  🔬 CrossAnalyze: 矛盾检测
  ✅ QualityGate: 8.2/10
```

---

## 场景三：竞品分析

**适合：** 对比多个产品/技术的优劣。

```bash
minerva research --template competitor-analysis --target "OpenAI vs Anthropic 模型安全策略"
```

或在 CLI 中直接：
```bash
minerva research "对比 OpenAI、Anthropic、Google 在 AI Safety 方面的技术路线和治理策略" --level L2
```

**模板提供：**
- 预设的分析维度（技术架构、安全策略、商业模式、社区生态）
- 偏好使用比较型搜索源
- 输出中包含对比表格

---

## 场景四：文献综述

**适合：** 学术文献调研、论文写作前的背景研究。

```bash
minerva research --template literature-review --target "大语言模型幻觉问题的检测与缓解"
```

**模板特点：**
- 优先 Semantic Scholar 和 arXiv
- 按时间线组织（经典 → 最新）
- 自动生成分类体系（检测方法、缓解策略、评估基准）

---

## 场景五：持续监控与维护

### 定期维护

```bash
# 检查知识库健康状态
minerva maintenance

# 检测过时条目（超过 30 天未更新）
minerva maintenance --action staleness

# 发现知识缺口
minerva maintenance --action gaps

# 检测矛盾信息
minerva maintenance --action contradictions
```

### 后台守护进程

```bash
minerva daemon &  # 定期自动执行维护任务
```

---

## Web 控制台使用

```bash
minerva web  # http://localhost:8765
```

### 仪表盘

浏览器打开 `http://localhost:8765`：
- 左侧：系统状态（SQLite、LLM、Executor）
- 中间：研究入口（输入问题 → 选择级别 → 提交）
- 底部：管道阶段时间线可视化

### API 端点

| 端点 | 说明 | 用法 |
|------|------|------|
| `/` | 仪表盘 | 浏览器打开 |
| `/health` | 健康检查 | `curl localhost:8765/health` |
| `/api/research` | 提交研究 | POST Form: `query` + `level` |
| `/api/report?path=...` | 渲染报告 | 浏览器查看格式化的报告 |
| `/api/report/pdf?path=...` | A4 PDF | 打印友好的 PDF 版本 |
| `/api/paradigm?query=...` | 范式分析 | 查看 Sophia 建议的操作序列 |
| `/api/stream` | SSE 进度 | 实时系统状态推送 |
| `/docs` | Swagger UI | 交互式 API 文档 |

---

## 配置详解

### 必需环境变量

```bash
# 至少配置一个推理后端
export DEEPSEEK_API_KEY="sk-..."     # V4 Pro，1M 上下文
export LONGCAT_API_KEY="ak-..."      # 免费 500 万 token/天

# 至少配置一个搜索后端
export EXA_API_KEY="..."             # 语义搜索（免费额度）
```

### 可选配置

```bash
# 中文搜索增强
export METASO_API_KEY="mk-..."       # 秘塔搜索
export ZHIPU_API_KEY="..."           # 智谱搜索

# Web API 安全
export MINERVA_API_KEY="your-secret" # 启用 API 认证

# Neo4j（Tier 2，知识图谱功能）
export NEO4J_PASSWORD="your-pass"    # 配合 docker compose 使用
```

### 配置文件

`config/minerva.yaml`：
```yaml
llm:
  provider: ollama           # 或 deepseek / openai
  base_url: http://localhost:11434/v1
  models:
    agent: qwen3.6:27b       # 本地模型
    reasoning: deepseek-v4-pro  # 云端推理（L3+）

execution:
  monthly_budget_usd: 5.0    # 月度成本上限
```

---

## 常见问题

**Q: 为什么 L0 结果太简单？**
A: L0 设计为 30 秒快速概览。如需深度分析，使用 `--level L2` 或更高。

**Q: 云端 LLM 调用失败？**
A: 检查 API 密钥是否设置（`echo $DEEPSEEK_API_KEY`）。Minerva 有断路器保护，连续失败 3 次后自动熔断 60 秒。

**Q: MCP 工具不响应？**
A: 确保 MCP 服务器在运行：`minerva mcp`。如果 SQLite 不可用会自动降级到 4/9 工具。

**Q: 搜索返回空结果？**
A: 部分搜索后端需要 API 密钥。至少配置 Exa 或确保 DDG/arXiv 可用。中国大陆用户可能需要代理访问某些后端。

**Q: 如何只使用本地模型（零成本）？**
A: 使用 `--level L0` 或 `--level L1`，这两个级别完全在本地 Ollama 上运行。
