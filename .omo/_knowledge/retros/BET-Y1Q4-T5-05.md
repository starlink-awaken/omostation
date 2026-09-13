# BET-Y1Q4-T5-05 Retro

## 概要

常驻 Agent 2.0 决策因果图化与多 Agent 先例仲裁引擎 — 全量交付完成。

## 交付物

| 文件 | 行数 | 功能 |
|------|------|------|
| `projects/omo/src/omo/resident/decision_bridge.py` | 545 | 因果决策图核心 (append-only JSONL + BFS 遍历 + W3C PROV-O 导出) |
| `projects/omo/src/omo/resident/arbitration.py` | 645 | 先例仲裁引擎 (Jaccard 相似度 + 加权投票 + circuit breaker) |
| `projects/omo/tests/unit/test_resident_causal_decision.py` | 453 | 41 个单元测试 |
| `projects/cockpit/src/cockpit/handlers/decision_graph.py` | 224 | Cockport handler (纯函数，直接读 JSONL，不 import decision_bridge) |
| `projects/cockpit-ui/src/components/resident/DecisionGraphViewer.tsx` | 632 | 前端可视化 (概览/节点列表/因果拓扑 3 Tab) |
| `projects/cockpit-ui/src/components/resident/__tests__/DecisionGraphViewer.test.tsx` | 240 | 9 个前端测试 |

## 验证结果

- ✅ 单元测试: 41/41 passed (0.15s)
- ✅ gac-local-gate: 57 checks ALL GREEN
- ✅ TypeScript 编译: 0 errors

## 架构决策

1. **文件契约解耦**: Cockport handler 直接读取 `graph.jsonl`，不 import `decision_bridge` 模块，omo ↔ cockpit 完全解耦。
2. **确定性算法**: 零模型调用、零随机性，相同输入产生相同输出。
3. **Append-only 持久化**: `graph.jsonl` 每行一个节点或边，无覆盖/删除。
4. **Circuit breaker**: confidence < 0.85 自动升级 HITL，严禁低置信度盲目合并。
5. **W3C PROV-O**: `prov:wasGeneratedBy` (CAUSED) + `prov:wasInfluencedBy` (INFLUENCED)，支持 Turtle 和 JSON-LD 双格式导出。

## 发现的问题与修复

1. **Path 类型转换**: `DecisionGraph.__init__` 和 `PrecedentArbiter.__init__` 传入字符串时 `self._path.parent` 报错 → 统一用 `Path(graph_file)` 转换。
2. **BFS 遍历**: `ancestors()` 初始版本跳过起始节点导致 0 结果 → 修正为 visited 从空集开始，仅当 depth > 0 时添加结果。
3. **PROV-O 前缀**: Turtle 导出使用完整 URI 而非前缀 → 改为 `prov:wasGeneratedBy` 前缀写法。

## 教训

- 文件契约模块（handler）必须独立验证 JSONL 解析，不能依赖上游模块的类型定义。
- PROV-O 的 prefix notation 必须在 `@prefix` 声明后才能使用，否则解析器报错。
- circuit breaker 的 HITL 升级记录 `status` 应为 `pending_human_review` 而非 `escalated`（escalated 是 ArbitrationResult 的布尔标志）。
