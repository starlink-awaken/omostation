---
status: accepted
lifecycle: history
owner: governance-team
created: 2026-09-07
last-reviewed: 2026-09-07
title: BET-Y1Q4-T10-137 异步递归子代理编排与低阻保护膜设计
type: doc
---

# BET-Y1Q4-T10-137: 异步递归子代理编排契约与 Low-Friction 低阻保护膜机制

## Context

T10-136 RLM 变量内核已落地持久化命名空间。但当前 Agent 调用子代理仍是同步阻塞模式，且网络抖动/BOS 超时/语法错误直接穿透到主上下文，造成 Token 浪费与认知中断。本 BET 实现异步子代理派生契约和低阻保护膜。

## Goals

- 交付 `projects/omo/src/omo/resident/rlm_subagent.py` 异步派生与低阻保护膜驱动
- 子代理派生延迟 <= 500ms
- 偶发网络抖动与超时自动重试自愈率 100%
- 单元测试 100% 通过

## Non-Goals

- 不允许子代理无限递归派生，最大递归深度硬限 <= 3
- 不绕过 Agora A2A 审计日志

## Technical Design

### 核心模块：rlm_subagent.py

1. **AsyncSubagentSpawner** — 异步子代理派生
   - `async spawn(task, depth=0)` — 在独立沙箱中异步派生子代理
   - 强类型 Python 对象返回值（非文本）
   - 派生延迟 <= 500ms
   - 最大递归深度硬限 <= 3

2. **LowFrictionMembrane** — 低阻保护膜
   - 拦截网络抖动、BOS 超时、轻微语法错误
   - 自动重试（指数退避，max 3 次）
   - 隔离机架基础设施异常与模型认知失败
   - 认知失败（非基础设施错误）不重试，直接上报

3. **SubagentPool** — 并发子代理管理
   - 并发子代理数硬限 <= 5
   - 超出限制时排队或降级为串行
   - 任务完成后自动回收资源

4. **RetryPolicy** — 重试策略
   - 可重试错误：网络超时、连接断开、503
   - 不可重试错误：权限拒绝、模型幻觉、语法错误

### 与 T10-136 的集成

- 子代理执行上下文自动注入 `sandbox_locals`
- 子代理返回值自动注册为父代理命名空间变量
- 观测使用 `RLMKernel.observe()` 控制 Token 预算

### 测试策略

- `test_rlm_subagent.py`：30+ 测试用例
- 异步测试：spawn/并发/超时/重试
- 保护膜测试：网络抖动模拟/退避策略
- 压力测试：深度递归/并发限制

## Write Surfaces

- projects/omo/src/omo/resident/rlm_subagent.py
- projects/omo/tests/test_rlm_subagent.py
- docs/plans/3y-bet-ledger.yaml
- .omo/_knowledge/retros/BET-Y1Q4-T10-137.md

## Dependencies

- BET-Y1Q4-T10-136 (done) — RLM 变量内核
- BET-Y1Q4-T6-29 (candidate) — 仿生双相记忆（非阻塞依赖，可并行）

## Verification

```bash
python3 -m pytest projects/omo/tests/test_rlm_subagent.py
python3 bin/plan/bet-ledger.py lint
```

## Circuit Breaker

- 递归深度超过 3 层或并发子代理数超过 5 个时自动拒绝派生并降级为单代理串行
- 重试次数超过上限直接报错，不无限退避
