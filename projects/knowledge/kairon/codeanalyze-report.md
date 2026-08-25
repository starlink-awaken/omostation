# 代码分析报告 — kairon
> 生成时间: ... | 路径: /Users/xiamingxing/Workspace/projects/knowledge/kairon

## 📦 项目概览
- Python 文件: 1,092
- 源码行数: ~179,424
- 目录总文件: 1,355

## 🌐 Graphify 语义图谱
  ❌ graphify: /Users/xiamingxing/Workspace/projects/knowledge/kairon/.venv/bin/python3: No module named graphify


## 🧬 CRG (Code Review Graph)
  ⏭️ None

## 🔗 GitNexus 依赖图
  ❌ unknown error

## 🔍 Serena 符号级分析
  ✅ 已索引 **1** 个符号
  🔧 12 个 MCP 工具: find_symbol, find_referencing_symbols, find_implementations, find_declaration, get_symbols_overview, get_diagnostics_for_file
    ... 还有 6 个
  💡 在对话中直接调用 MCP 工具进行符号级查询

## 💡 建议
  - 安装 code-review-graph: npm install -g code-review-graph

## 🔬 洞察分析
  💡 **[代码异常]** 空文件 (18 个)
    tests/__init__.py
    packages/eidos/src/eidos/adapters/__init__.py
    packages/codeanalyze/src/codeanalyze/analyzers/__init__.py
  💡 **[文档覆盖]** 文档覆盖率: 75% (723/966)
    文档覆盖良好
  💡 **[架构]** 层级依赖检查已跳过
    pyproject.toml 未配置 [tool.codeanalyze.layers]，跳过架构层级检查
  ⚠️ **[代码安全]** 不安全模式 (10 处)
    sys.path 修改: tests/conftest.py
    sys.path 修改: tests/scripts/test_e2e_health_eval.py
    sys.path 修改: tests/scripts/test_e2e_health_demo.py

---
> 由 codeanalyze v0.3.0 生成