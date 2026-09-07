---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-09-07
last-reviewed: 2026-09-07
title: BET-Y1Q4-T10-136 RLM 变量内核设计
type: doc
---

# BET-Y1Q4-T10-136: RLM 交互式变量执行空间与 Context-as-Variables 引擎

## Context

PCM-v3 沙箱运行时需要 RLM (Recursive Language Model) 核心机制。当前 Agent 工具调用结果直接追加文本至对话上下文，导致长程 Context Rot 与 Token 暴增。本 BET 提供沙箱持久化 Python 命名空间，允许 Agent 将大型 AST、检索数据与中间结果作为内存变量就地过滤、切片与统计。

## Goals

- 交付 `projects/omo/src/omo/resident/rlm_kernel.py` 实现 RLM 持久化变量内核
- 支持内存变量原地切片与紧凑观测提炼，长上下文 Token 压缩率 >= 70%
- 单元测试与压力测试 100% 通过

## Non-Goals

- 不在沙箱外部全局暴露未授权的 Python 执行环境
- 不放弃文本摘要能力，核心观测依然以精炼结构呈现

## Technical Design

### 核心模块：rlm_kernel.py

1. **VariableStore** — 持久化 Python `sandbox_locals` 命名空间
   - `set(name, value)` — 存储任意 Python 对象
   - `get(name)` — 检索
   - `slice(name, start, stop, step)` — 原地切片
   - `filter(name, fn)` — 原地过滤
   - `stats(name)` — 统计摘要
   - `compact(name, budget)` — 紧凑观测提炼

2. **Token Estimation** — 基于 `len(json.dumps(value)) // 4` 估算

3. **Compact Observation** — 超出预算时自动压缩：
   - list: 头 + 尾采样 + 数值统计
   - dict: 按 value 大小排序，展示 top keys
   - str: 头 + 尾行采样

4. **RLMKernel** — 顶层封装
   - `sandbox_locals` 字典同步
   - `execute_with_context(code)` — 在沙箱命名空间中执行代码
   - `token_savings()` — 估算 Token 节省量

### 测试策略

- `test_rlm_kernel.py`：40 个测试用例（CRUD/切片/过滤/统计/紧凑观测/集成/压力）
- 压力测试：1000 个变量、100KB 对象、快速存取循环
- Token 压缩率基准测试：>= 70%

## Write Surfaces

- projects/omo/src/omo/resident/rlm_kernel.py
- projects/omo/tests/test_rlm_kernel.py
- docs/plans/3y-bet-ledger.yaml
- .omo/_knowledge/retros/BET-Y1Q4-T10-136.md

## Dependencies

- BET-Y1Q4-T10-133 (done) — sandbox-timemachine 沙箱基础设施

## Verification

```bash
python3 -m pytest projects/omo/tests/test_rlm_kernel.py
python3 bin/plan/bet-ledger.py lint
```

## Circuit Breaker

- 单变量内存占用 > 10MB 时自动拒绝存入
- 任务命名空间变量数 > 500 时自动触发 GC
