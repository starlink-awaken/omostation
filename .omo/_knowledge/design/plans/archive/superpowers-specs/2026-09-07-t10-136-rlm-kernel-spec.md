---
schema_version: specification/v1
spec_version: 1.0.0
status: accepted
lifecycle: contract
owner: governance-team
created: 2026-09-07
last-reviewed: 2026-09-07
title: BET-Y1Q4-T10-136 RLM 变量内核设计
bet_id: BET-Y1Q4-T10-136
---

# BET-Y1Q4-T10-136: RLM 交互式变量执行空间与 Context-as-Variables 引擎

## Context

PCM-v3 沙箱运行时需要 RLM (Recursive Language Model) 核心机制。当前 Agent 工具调用结果直接追加文本至对话上下文，导致长程 Context Rot 与 Token 暴增。本 BET 提供沙箱持久化 Python 命名空间，允许 Agent 将大型 AST、检索数据与中间结果作为内存变量就地过滤、切片与统计。

## Goals

- 交付 `projects/omo/src/omo/resident/rlm_kernel.py` 实现 RLM 持久化变量内核
- 支持内存变量原地切片与紧凑观测提炼，长上下文 Token 压缩率 >= 70%

## Architecture

### VariableStore
持久化 Python 命名空间，支持:
- `set(name, value, token_budget)` — 存储变量
- `get(name)` — 取出变量
- `slice(name, start, end)` — 原地切片
- `filter(name, predicate)` — 过滤
- `observe(name, max_tokens)` — 紧凑观测提炼

### RLMKernel
封装 VariableStore，提供:
- `compact_observation(name, max_tokens)` — Token 受限观测
- `token_count(value)` — 估算 token 数
- `get_kernel()` — 单例访问

## Non-Goals

- 不在沙箱外部全局暴露未授权的 Python 执行环境
- 不放弃文本摘要能力，核心观测依然以精炼结构呈现
