---
title: README
type: doc
---

# CodeAnalyze (代码分析核心引擎)

> Unified code & document analysis toolkit for AI Agents

`codeanalyze` 是 Kairon 内部集成的核心分析包，专门为 AI Agent 提供**多维度代码库感知、重构影响面分析、和超大规模知识图谱构建**能力。

## 🎯 核心能力与集成的分析工具

我们通过统一的 Registry 和命令系统，将业界最强的静态/动态代码分析与文档处理工具整合在一个包中：

### 1. 代码理解与检索层
| 工具名称 | 核心用途 | 集成方式 |
| :--- | :--- | :--- |
| **`ast-grep (sg)`** | 基于 AST 的结构化搜索。可以准确找到 `$FUNC($___)` 这种逻辑结构，突破传统正则盲区。 | `analyzers/ast_grep.py` |
| **`ripgrep (rg)`** | 全代码库文本极速检索，10x 性能提升。 | `analyzers/ripgrep.py` |
| **`repomix`** | AI 友好的**上下文打包**。把包含数千文件的代码库，智能合并为一个 LLM 友好的 XML / MD 文件。 | `analyzers/repomix.py` |

### 2. 架构与依赖图谱层
| 工具名称 | 核心用途 | 集成方式 |
| :--- | :--- | :--- |
| **`CodeGraphContext (CGC)`**| 基于 Tree-sitter 和 SCIP 构建包含调用链、继承等关系的现代化语义属性图谱。支持通过 Cypher/KuzuDB 对图查询。 | `analyzers/cgc.py` |
| **`gitnexus`** | 代码库的 Git 提交维度、修改依赖频率等依赖关系图与调用链监控（LadybugDB）。 | `analyzers/gitnexus.py` |
| **`code-review-graph`** | 轻量化 Token 级别的持续知识图谱压缩组件。 | `analyzers/crg_graph.py` |

### 3. 多模态/文档分析层
| 工具名称 | 核心用途 | 集成方式 |
| :--- | :--- | :--- |
| **`docling` & `mineru`**| 将 PDF、Word、HTML 等复杂文档结构化转为 Agent 可读数据。 | `documents/` & `extractors/` |
| **`graphify`** | 文档到语义知识图谱构建。 | `analyzers/graphify.py` |

---

## ⚡️ 高阶自动工作流 (Workflows)

通过组合多个底层分析器，我们封装了开箱即用的高频 Agent 场景工作流：

### A. 全局上下文获取 (Onboarding Context)
将零散的代码库一次性“灌”进 LLM 的上下文窗口。
- **机制**: 使用 `ast-grep` 提取核心入口点，用 `repomix` 完成全局压缩合并。
- **CLI**: `uv run codeanalyze workflow onboarding . --output ./out/`
- **MCP API**: `workflow_onboarding`

### B. 重构影响面排查 (Impact Analysis)
当你想修改一个核心公共类/函数时，排查所有受到波及的地方。
- **机制**: 使用 `ast-grep` 精准抽取使用现场代码段，结合 `CodeGraphContext` (如已初始化) 进行深度依赖追溯。
- **CLI**: `uv run codeanalyze workflow impact process_data . -l py`
- **MCP API**: `workflow_impact_analysis`

---

## 💻 命令行速查表 (CLI)

```bash
# 检查所有的工具依赖状态 (看看哪些工具可用，哪些缺失)
uv run codeanalyze status

# 安装缺失的底层工具依赖
uv run codeanalyze install

# 执行结构化搜索
uv run codeanalyze ast '$FUNC($___)' --lang py

# 将 repo 打包为一个 xml 并预估 tokens
uv run codeanalyze pack . --format xml

# 初始化图数据库并查询
uv run codeanalyze cgc init .
uv run codeanalyze cgc query "MATCH (n) RETURN n LIMIT 10"

# 启动给其他 Agent 调用的 MCP 服务器
uv run codeanalyze serve
```

## 🔌 MCP 接口暴露 (供 Agent 调用)

通过 `uv run codeanalyze serve`，将对外暴露以下标准 MCP Tools 接口（可被 Serena、Claude 或本工程的各个 Agent 调度）：
- `ast_search`: 基于语法树的精准查找。
- `pack_repo`: 打包当前工作区所有上下文给主控 Agent。
- `cgc_query`: 执行对知识图谱的高级 Cypher 挖掘。
- `workflow_onboarding`: 调用 Onboarding 引导组合工作流。
- `workflow_impact_analysis`: 调用依赖影响排查组合工作流。

---
> 维护提示：若要新增工具，在 `src/codeanalyze/core/registry.py` 中注册 `ToolSpec`，并添加对应适配器即可。
