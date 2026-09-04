---
type: ssot
---

# Knowledge Engineering Complex (知识工程复合体)

> **Layer**: L2  
> **Subprojects**: `gbrain` (PostgreSQL + pgvector + TypeScript) + `kairon` (16 packages monorepo)  
> **ADR**: ADR-0294, ADR-0372  

## 架构职责
1. **权威持久化存储 (`gbrain`)**：PostgreSQL 结构化数据、全文倒排索引与高并发向量真源。
2. **知识图谱与推理引擎 (`kairon.kos`)**：实体多跳推理、本体自演化 (OntoDerive)、三位一体混合召回 (Hybrid Search) 与 Agent 知识端点。
3. **专业代码与时序分析 (`kairon.codeanalyze` + `kairon.kronos`)**：代码 AST 拓扑、时序演化跟踪。
4. **统一外部知识网关 (`kairon.adapters`)**：外源采集与跨模态提取。

## 顶层测试
```bash
cd projects/knowledge
uv run pytest tests/ -v
```
