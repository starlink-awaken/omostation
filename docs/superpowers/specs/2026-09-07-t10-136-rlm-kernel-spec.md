---
schema_version: specification/v1
spec_version: 1.0.0
title: BET-Y1Q4-T10-136 specification
bet_id: BET-Y1Q4-T10-136
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-07
---

# BET-Y1Q4-T10-136: RLM 交互式变量执行空间与 Context-as-Variables 引擎

## Status

accepted

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

1. **Sandbox Namespace Manager**
   - 持久化 Python `sandbox_locals` 字典
   - 任务开始时初始化，任务结束时自动 GC
   - 支持 `set_var(name, value)` / `get_var(name)` / `del_var(name)` API

2. **Variable Slicer**
   - 对大型数据结构（list/dict/DataFrame）原地切片
   - 支持 `slice_var(name, start, end, step)` 操作
   - 返回紧凑统计摘要而非原始数据

3. **Context-as-Variables Compiler**
   - 将工具调用结果自动编译为内存变量
   - 上下文仅保留变量名引用 + 摘要统计
   - 目标：Token 压缩率 >= 70%

4. **Observations Renderer**
   - 将变量状态渲染为精炼结构化观测
   - 支持 JSON/YAML/Markdown 三种输出格式
   - 包含 schema 摘要 + 样本数据 + 统计指标

### 测试策略

- `test_rlm_kernel.py`：单元测试（命名空间/切片/编译/渲染）
- 压力测试：1000 个变量的创建/查询/GC 性能
- Token 压缩率基准测试

## Write Surfaces

- projects/omo/src/omo/resident/rlm_kernel.py
- projects/omo/tests/test_rlm_kernel.py
- docs/plans/3y-bet-ledger.yaml
- .omo/_knowledge/retros/BET-Y1Q4-T10-136.md

## Dependencies

- BET-Y1Q4-T10-133 (done) — sandbox-timemachine 沙箱基础设施
- PCM-v3 沙箱运行时（已有）

## Verification

```bash
python3 -m pytest projects/omo/tests/test_rlm_kernel.py
python3 bin/plan/bet-ledger.py lint
```

## Circuit Breaker

- 单变量内存占用 > 10MB 时自动拒绝存入，要求 Agent 预先切片
- 任务命名空间变量数 > 500 时自动触发 GC
