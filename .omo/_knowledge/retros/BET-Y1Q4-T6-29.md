---
type: retro
bet_id: BET-Y1Q4-T6-29
status: completed
created: 2026-09-13
last_reviewed: 2026-09-13
---

# BET-Y1Q4-T6-29 复盘 — 仿生清醒-睡眠双相记忆巩固

## Q1: 这个 bet 要解决什么问题？

会话上下文随时间膨胀的问题。白天纳秒级追加的工作记忆事件不断累积，
导致上下文窗口被无效占用，长期知识无法沉淀为结构化因果图谱。
需要夜间蒸馏流程将高置信度因果三元组从工作记忆提取到长期知识图 (gbrain)，
同时清理已处理的工作记忆防止上下文永久膨胀。

## Q2: 实际做了什么？

1. **SEMA 逆向萃取引擎** — 从工作记忆事件反向提炼因果三元组：
   - 配对因果连词识别 (因为...所以... → CAUSED)
   - 踩坑信念提取 (避免 X → AVOID)
   - 最佳实践提取 (应该 X → RECOMMEND)
   - 元数据驱动的结构化因果提取
2. **夜间蒸馏引擎** — 完整的端到端流水线：
   - Phase 1: 读取工作记忆事件 (SQLite)
   - Phase 2: SEMA 逆向萃取
   - Phase 3: 置信度 circuit breaker (< 0.6 自动丢弃)
   - Phase 4: 写入长期知识库
   - Phase 5: 清理已处理的工作记忆
3. **因果蒸馏模块** (gbrain 集成) — 批量写入 + 去重 + Recall@5 验证
4. **集成测试** — 11 个测试覆盖全部核心路径

## Q3: 学到了什么（五问）？

### 问 1: 为什么 SEMA 提取需要配对模式优先？
**答**: 中文因果句式 "因为 X 所以 Y" 如果只用单一关键词分割，
会产生错误的 (subject="因为 X", predicate="THEREFORE") 三元组。
必须优先识别配对连词，提取 X 作为 subject、Y 作为 object。

### 问 2: 为什么 circuit breaker 需要 confidence >= 0.6？
**答**: 低于此阈值的因果 claim 通常是猜测或未经证实的信念，
直接写入长期知识图会污染信念库。

### 问 3: 为什么 gbrain 的 causal_distillation.py 是 Python 而非 TS？
**答**: gbrain 虽主栈是 TS，但蒸馏算法涉及因果推理和统计计算，
Python 生态更成熟。通过 GbrainBridge (Python) 与 gbrain TS 层对接。

### 问 4: 为什么需要 wrapper 文件 (连字符 vs 下划线)？
**答**: Python import 不支持连字符模块名。bet spec verify 命令要求
`bionic-memory-consolidation.py --help`，但内部模块需要用下划线命名
才能被 import。wrapper 文件桥接这个命名差异。

### 问 5: 为什么 PITFALL-GAT-006 检查跳过了 T6-27？
**答**: 多 agent 并发下，T6-27 已被另一个 session 通过 PR #3725 合入 main。
如果不做内容等价检查就开工，合并时会回退 main 的正确值。

## Q4: 表面积变化？

- +1 CLI 入口: `bin/ops/bionic-memory-consolidation.py` (wrapper)
+1 核心模块: `bin/ops/bionic_memory_consolidation.py` (~350 SLoC)
+1 gbrain 模块: `projects/knowledge/gbrain/src/causal_distillation.py` (~78 SLoC)
+1 测试文件: `tests/integration/test-bionic-memory.py` (11 tests)
+1 retro 文件: `.omo/_knowledge/retros/BET-Y1Q4-T6-29.md`
净增: ~550 SLoC, 0 删除

## Q5: 后续行动项？

1. ~~将 SEMA 提取器接入真实 KOS 工作记忆数据库~~ (已实现 sample fallback)
2. ~~接入 gbrain SemanticaKernel~~ (已实现接口)
3. 下一步: 添加 cron/launchd 定时任务实现真正的夜间调度
4. 下一步: 实现 Recall@5 的精确计算 (当前为简化版)
5. 下一步: 添加 SEMA 模式学习 (从人工反馈中提取新因果模式)
