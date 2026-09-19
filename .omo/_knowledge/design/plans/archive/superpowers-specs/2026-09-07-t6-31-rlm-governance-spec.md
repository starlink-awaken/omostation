---
status: accepted
lifecycle: spec
owner: governance-team
created: 2026-09-07
last-reviewed: 2026-09-07
title: BET-Y1Q4-T6-31 RLM 变量命名空间 GC 与 GaC 安全门禁设计
type: doc
---

# BET-Y1Q4-T6-31: RLM 变量命名空间生命周期 GC、资源核算与 GaC 安全门禁

## Context

T10-136 RLM 变量内核已落地持久化命名空间，T10-137 子代理编排已落地异步派生。但当前变量空间存在长周期命名泄漏风险，且沙箱执行缺乏安全门禁。本 BET 弥补权限裸奔与泄漏短板。

## Goals

- 交付 `projects/omo/src/omo/resident/rlm_governance.py` 治理门禁与 GC 引擎
- 变量空间基于任务生命周期的周期性自动 GC 与脏状态重置
- 步数/Token/内存耗用硬核算体系
- AST 静态安全审查拦截破坏性系统调用，拦截率 100%
- 长周期长驻任务内存泄漏检测为 0

## Non-Goals

- 不在只读查询场景施加过重的 AST 分析开销
- 不允许绕过安全审查执行动态代码注入

## Technical Design

### 核心模块：rlm_governance.py

1. **NamespaceGC** — 命名空间垃圾回收
   - 基于 TTL 的自动过期（默认 1 小时）
   - 基于 LRU 的淘汰策略
   - 脏状态检测与重置
   - 周期性后台清理（asyncio task）

2. **ResourceAccountant** — 资源核算
   - 步数计数器（每次操作 +1）
   - Token 消耗累计
   - 内存占用追踪（sys.getsizeof）
   - 硬上限：单变量 10MB，总命名空间 100MB

3. **ASTSecurityGate** — AST 静态安全审查
   - 解析代码 AST，检测危险调用
   - 黑名单：`eval/exec/__import__/os.system/subprocess/open/compile`
   - 拦截率 100%，误报率 0%
   - 可配置的白名单机制

4. **GaCGovernor** — 统一治理入口
   - 集成 GC + 核算 + 安全门禁
   - 装饰器模式：`@governed`
   - 上下文管理器：`with sandbox_governance():`
   - 监控指标暴露：`metrics()`

### 与 T10-136/T10-137 的集成

- RLMKernel 创建时自动启用治理
- SubagentSpawner 派生子代理时继承治理策略
- 治理事件写入 kernel store

### 测试策略

- `test_rlm_governance.py`：35+ 测试用例
- GC 测试：TTL 过期/脏状态重置/LRU 淘汰
- 资源核算测试：内存超限/Token 上限
- 安全门禁测试：AST 解析/危险调用拦截
- 压力测试：1000 变量并发 GC

## Write Surfaces

- projects/omo/src/omo/resident/rlm_governance.py
- projects/omo/tests/test_rlm_governance.py
- docs/plans/3y-bet-ledger.yaml
- .omo/_knowledge/retros/BET-Y1Q4-T6-31.md

## Dependencies

- BET-Y1Q4-T10-136 (done) — RLM 变量内核
- BET-Y1Q4-T10-137 (done) — 子代理编排

## Verification

```bash
python3 -m pytest projects/omo/tests/test_rlm_governance.py
python3 bin/plan/bet-ledger.py lint
```

## Circuit Breaker

- 单变量内存占用 > 10MB 时自动拒绝存入
- 总命名空间 > 100MB 时触发全量 GC
- AST 检测到危险调用时阻断执行并告警
