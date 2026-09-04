---
lifecycle: plan
owner: governance-team
last_updated: 2026-08-18
type: ephemeral
---
# agora 用量计费/配额方案 (遗留-3, 2026-08-07)

> **状态: ✅ 全链路已落地 (2026-08-07, agora 77c8e9c)** — 配额检查器 + 配置 + resolve_bos_uri 接入 + 热加载 + 11 测试; **告警联动**: 超限/预警触发统一告警入口 `agora_alerts.py` (P4) + Prometheus 指标; **P3 能力目录写闭环**: capability_catalog add/retire/save 持久化 + 修复 admit/retire 死代码。本文档保留为设计参考。

> 网关 → 能力编排大脑 的关键一步: 从"仅 QPS 限流"升级到"按调用者配额计费"。

## 一、现状

| 能力 | 位置 | 状态 |
|---|---|---|
| 调用统计 (per-prefix calls/success/failure/latency) | `mcp/bos_metrics.py` BOSMetrics | ✅ SQLite + Prometheus |
| 成本估算 (token → USD) | `accounting.py estimate_cost()` | ✅ 已实现 |
| 调用记录 (caller_id/service/tool/cost) | `accounting.py ResourceAccountDB` | ✅ SQLite WAL, 未接入调用链 |
| 今日/累计消费查询 | `accounting.py get_quota()` | ✅ 已实现 |
| 配额检查 (今日是否超限) | **缺失** | ❌ 无 check 逻辑 |
| QPS 限流 (per URI) | `bos_middleware.py RateLimiter` | ✅ agora-bos-rates.yaml 热加载 |
| 配额配置 (per caller daily limit) | **缺失** | ❌ 无配置格式 |

## 二、方案

### 2.1 接入点: resolve_bos_uri (tools_bos/registration.py:137 限流后)

```python
# L137 限流后插入
if not bos_quota_checker.check(caller_id=current_caller, service=uri):
    return _error(f"Quota exceeded for: {uri} (daily cost limit reached)")
```

调用成功后记录:
```python
# L164 _bos_post_audit 后
bos_accounting.record(
    caller_id=current_caller, service_name=uri,
    tool_name=uri.split("/")[-1],
    input_tokens=..., output_tokens=..., cost_usd=estimate_cost(...),
)
```

### 2.2 配额配置格式 (扩展 agora-bos-rates.yaml)

```yaml
quotas:
  # per-caller daily cost limit (USD)
  default_daily_usd: 10.0
  callers:
    - id: "anonymous"
      daily_usd: 2.0
    - id: "agent-*"          # 支持通配
      daily_usd: 50.0
  services:
    - prefix: "bos://analysis/minerva/"
      daily_usd: 5.0        # 服务级配额
```

### 2.3 新增模块: bos_quota.py

- `QuotaConfig` — 从 agora-bos-rates.yaml 加载 (复用 ConfigWatcher 热加载)
- `QuotaChecker.check(caller_id, service)` — 查 accounting.get_quota() today_cost vs 配置上限
- `caller_id` 来源: `agora_role_ctx` (tools_auth.py 已设) 或 auth identity

### 2.4 caller_id 获取

`tools_auth.py agora_role_ctx` 已有 (admin/local/denied); 扩展为真实 identity:
```python
from agora.server.tools_auth import agora_role_ctx
caller = agora_role_ctx.get()  # 或 identity_from_auth_token()
```

## 三、依赖关系

- 依赖 accounting.py (已存在, 无需大改; 仅需确认 record() 接入调用链)
- 依赖 agora_role_ctx 提供 caller_id
- 与 bos_metrics.py 协同 (metrics 记频率, accounting 记成本)

## 四、实施步骤

1. **agora**: 新增 `mcp/bos_quota.py` (QuotaConfig + QuotaChecker)
2. **agora**: agora-bos-rates.yaml 加 `quotas:` 段
3. **agora**: resolve_bos_uri 接入 check + record
4. **agora**: ConfigWatcher 纳入 quotas 热加载
5. **测试**: quota 超限拒绝 + 正常调用记录 + 通配 caller
6. **主仓**: 文档同步 (I0-CALLCHAIN 补配额步骤)

## 五、风险

- caller_id 解析: anonymous 调用无身份 → 用默认配额 (安全默认)
- 缓存命中不记账: 缓存路径 (L147-157) 应跳过配额 (不产生实际成本)
- 与 omo budget_policy 的衔接: 后续 (P3) 将 agora quota 接入 omo 治理

## 落地状态 (2026-08-08 标注)

- **配额计费**: ✅ QuotaConfig + QuotaChecker + resolve 接入
- **配额告警**: ✅ warning/blocked 事件 + webhook + Prometheus
- **真实计费**: ✅ token 估算 + estimate_cost (成本非 0)
