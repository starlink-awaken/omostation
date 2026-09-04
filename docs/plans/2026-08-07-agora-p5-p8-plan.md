---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# agora P5-P8 战略深化方案 (2026-08-07)

> 前置: 超长链路验证报告 (docs/reports/2026-08-07-agora-long-chain-scenarios.md)
> 暴露 4 个架构短板 → 本方案落地 P5-P8 四阶段补齐。
> 战略路线: P1-P4 已打通"网关→能力编排大脑"骨架, P5-P8 夯实治理面。

## 四维对齐

| 维度 | P5 能力管理网关化 | P6 契约统一 | P7 冷启动优化 | P8 面板增强 |
|------|------------------|------------|--------------|------------|
| **架构** | capability 工具挂主 mcp, 消除独立实例孤岛 | internal 签名统一 (args:dict), registry lint 签名断言 | 预热机制/结果缓存, 消除首调延迟 | dashboard 读 /health+metrics 聚合 |
| **战略** | 能力编排大脑"管理面"可编程 | 能力声明=实现 (契约即事实) | 生产级响应 (p50 达标) | 治理可观测闭环 |
| **场景** | HTTP 远程 admit/retire 能力 | 全部 internal 服务可执行 | 首次调用毫秒级 | 面板显示契约健康+配额 |
| **功能** | 能力生命周期 API 化 | 无 10/50 执行失败 | 冷路径预热 | 一屏看全链路 |

## P5: 能力管理网关化

### 问题
`bos_capability_lifecycle.py` 工具挂在独立 `FastMCP("bos-capability-lifecycle")` 实例,
主网关 `/v1/tools/call` 调不到 → 能力 admit/retire 只能进程内操作。

### 方案
1. **工具迁移**: 将 `@mcp.tool()` 装饰改为挂主 mcp (从 `agora.server.mcp import mcp`),
   或 `register()` 时用主 mcp 注册工具 (FastMCP.add_tool API)。
2. **安全**: admit/retire 是写操作, 需 governance 身份校验 (复用 agora_role_ctx)。
3. **验证**: HTTP POST /v1/tools/call 调 bos_capability_admit 返回 active/admitted。

### 落地文件
- `src/agora/mcp/tools/bos_capability_lifecycle.py`: 工具挂主 mcp
- `src/agora/server/mcp.py`: 注册点接入

## P6: internal 契约统一

### 问题
- `memory/local/all-search` 签名 `(args: dict)` 但被 kwargs 展开 → 10/50 执行失败
- `capability/bus/event` 需要 `topic` 参数但调用传 payload
- registry lint 只查 func 可解析, 不查签名匹配

### 方案
1. **统一约定**: 所有 internal 函数签名 `async def fn(args: dict) -> dict` (首个参数 dict)。
2. **resolver 适配**: api.py 已有智能适配 (首参 args/arguments 传整体 dict),
   需**服务定义对齐** (services_internal/services.py 的 func_name 指向 dict 契约函数)。
3. **签名断言**: registry lint 加 `test_internal_service_signature_match` —
   校验 func 首参是 dict 类, 不匹配即 broken。
4. **修复 broken**: 逐个对齐 `memory/local/all-search`/`vault/search`/`bus/event` 等。

### 落地文件
- `src/agora/mcp/resolver/services.py` + `services_internal.py`: func_name 对齐
- `tests/unit/test_bos_registry_contract.py`: 加签名断言

## P7: 冷启动优化

### 问题
首轮 omo/audit 8.5s (真实审计计算), 后续 2-5ms (缓存)。首调延迟影响体验。

### 方案
1. **结果缓存**: internal 服务结果按 uri+args 缓存 (复用 bos_cache, 对审计等重计算设长 TTL)。
2. **预热**: SSE 启动后后台预热高频服务 (governance/omo/audit), 首个请求命中缓存。
3. **降级**: 预热失败不影响启动 (防御性)。

### 落地文件
- `src/agora/mcp/resolver/api.py`: internal 结果缓存
- `src/agora/server/mcp.py`: 启动预热钩子

## P8: 面板增强

### 问题
swarm-activity-dashboard 的 agora_health 只显示 backends/tools, 无契约健康/配额用量。

### 方案
`_agora_health()` 增加:
1. `bos_registry` (从 /health 读): func_resolvable_pct + broken
2. `quota_usage` (从 /metrics 读 bos_quota_usage_ratio): 用量比
3. 显示: `契约 86.7% | 配额 12% | backends 7/127`

### 落地文件
- `bin/gac/swarm-activity-dashboard.py` (主仓)

## 实施顺序与验证

| 阶段 | 动作 | 验证 |
|------|------|------|
| P5 | 工具挂主 mcp | HTTP admit → active/admitted |
| P6 | 契约统一 + lint 签名断言 | 全量 internal 可执行 (0 broken) |
| P7 | 缓存 + 预热 | 首轮调用 <100ms |
| P8 | 面板增强 | dashboard 显示契约健康+配额 |

## 风险

| 风险 | 缓解 |
|------|------|
| P5 挂主 mcp 工具冲突 | 独立命名空间 (bos_capability_*) 已隔离 |
| P6 服务定义大改 | registry lint 全量校验防回归 |
| P7 缓存过期数据 | TTL 按服务类型配置 |
| P8 面板读 /metrics 新增开销 | 缓存指标读取 (30s) |

## 落地状态 (2026-08-08 标注)

- **P5 能力网关化**: ✅ bos_capability_* 挂主 mcp + HTTP 可操作
- **P6 契约统一**: ✅ registry lint 签名断言
- **P7 冷启动**: ✅ internal 缓存 + 预热 (8.5s→0ms)
- **P8 面板增强**: ✅ bos_registry 契约健康上屏
