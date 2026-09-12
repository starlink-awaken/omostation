---
bet_id: BET-Y1Q4-T6-26
title: "Semantica 嵌入式图引擎内核集成与统一 BOS 决策网格"
retro_type: bet-retro
status: done
done_at: "2026-09-12"
---

# BET-Y1Q4-T6-26 Retro

## 交付摘要

T6-26 交付了 Semantica 嵌入式图引擎内核与统一 BOS 决策网格，
在 kairon 中实现本地化 RDF 图存储与 Datalog 确定性推理能力。

## 交付内容

| 交付物 | 路径 | 说明 |
|--------|------|------|
| SemanticaKernel | `projects/knowledge/kairon/src/kairon/graph/semantica_kernel.py` | 双后端 (Oxigraph/SQLite) 嵌入式图引擎 |
| CausalTracer | `projects/knowledge/kairon/src/kairon/decision/causal_tracer.py` | 决策因果链追溯引擎 |
| 单元测试 | `projects/knowledge/kairon/tests/test_semantica_kernel.py` | 29 个测试用例 |
| BOS 路由 | `projects/agora/etc/bos-services.yaml` | 5 条新路由 (decision×3 + graph×2) |
| Spec | `docs/superpowers/specs/2026-09-12-t6-26-semantica-graph-kernel-design.md` | 设计文档 |

## 关键设计决策

1. **双后端策略**: Oxigraph 优先（纯 Rust 嵌入式），SQLite fallback（零依赖）
2. **BOS 域映射**: `decision` → `governance`，`graph` → `memory`（遵循 BOS_URI_DOMAINS 约束）
3. **因果关系类型**: CAUSED（强因果）+ INFLUENCED（弱影响）
4. **数据本地化**: 全部本地存储，严禁外部 API 调用
5. **确定性推理**: Datalog 引擎基于传播式求值，相同输入保证相同输出

## 经验教训

1. **Element 真值判断陷阱**: `if not element` 对 ElementTree Element 返回错误结果，
   须用 `is not None`（T6-25 踩坑，T6-26 规避）
2. **BOS URI domain 约束**: domain 必须在 BOS_URI_DOMAINS 列表中，
   `decision` 和 `graph` 不在列表，需映射到 `governance` 和 `memory`
3. **Oxigraph 不可用场景**: 必须确保 SQLite fallback 路径完整，
   测试覆盖 auto/sqlite/oxigraph 三种模式
