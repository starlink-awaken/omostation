# 复盘 — M2.5 Knowledge Closed-Loop (2026-05-30)

## 完成内容

- **KOSSaveStage** — 管道阶段，将 ResearchContext 报告保存为 KOS CONCEPT 实体（zone=minerva_research）
- **KnowledgeClosedLoop** — 编排器：KOS 缓存命中 → 研究管线运行 → KOS 保存 → 审计日志
- **MCP 工具** `knowledge_closed_loop` — 带 `level/confirmed/fresh` 参数
- **Operation Level** — 单次保存 L1（自动）、批量 L2（需 confirmed=True）
- **RCH- 前缀** — 添加到 KOS Entity ID 前缀体系
- **18 个新测试** — KOSSaveStage 6 + KnowledgeClosedLoop 6 + MCP 4 + 集成 2

## 关键数据

| 项目 | 变更 |
|------|------|
| 新文件 | `kos_save.py`, `knowledge_closed_loop.py`, `test_knowledge_closed_loop.py` |
| 修改文件 | `_types.py`, `stages/__init__.py`, `engine.py`, `init.py`, `server.py`, `test_mcp_server.py` |
| 测试 | 18 新增 + 1 回归修复 = **237 全量通过** |
| 总增量 | ~420 LOC |

## 设计决策

1. **RCH- 前缀**: 用 `hash("query")[:12]` 确定性 ID，避免重复实体
2. **KOS 可选**: `try/except ImportError` 优雅降级，无硬依赖
3. **Pipeline 阶段 vs 独立模块**: 复用现有管线架构，无需修改 executor

## 待办调整

| 文件 | 状态 |
|------|------|
| `tasks/active/M2.5-*.yaml` | ✅ 标记 completed |
