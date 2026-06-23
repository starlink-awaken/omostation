---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 7.2 — 成本可见 (7天)

> 类型: P8 Task | 预估: 7天 | Wave: 7.2 | Phase: 7
> 可与7.3并行

## T104: token计数器 (2天)

在`agentmesh/packages/model-orchestrator/`中创建`accounting.py`。

**核心逻辑**:
- 每次MCP工具调用后记录token数
- 通过LLM响应中的`usage`字段获取 (input_tokens, output_tokens)
- 如果API不返回token数→估算 (字符数/4)

**验收**:
```
☐ 每次MCP调用记录token消耗
☐ 记录含caller/service/input/output/cost
☐ 不影响正常MCP调用性能
```

## T105: usage.db (2天)

在`~/.kos/accounting/usage.db`创建SQLite。

**表结构**:
```sql
CREATE TABLE IF NOT EXISTS resource_usage (
    call_id TEXT PRIMARY KEY,
    caller TEXT NOT NULL,
    service TEXT NOT NULL,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_usage_caller ON resource_usage(caller);
CREATE INDEX IF NOT EXISTS idx_usage_service ON resource_usage(service);
CREATE INDEX IF NOT EXISTS idx_usage_time ON resource_usage(timestamp);
```

**验收**:
```
☐ 数据库创建成功
☐ 写入后查询正常
☐ 有索引
```

## T106: cost summary CLI (2天)

```bash
cost summary --today
# 今日总消耗: $0.37 (12,345 tokens)
# ── 按服务 ──
# minerva.research_now    8,000 tokens  $0.25
# kos.search_knowledge    3,000 tokens  $0.08
# self.get_profile         1,345 tokens  $0.04
# ── 按调用者 ──
# agent:hermes           10,000 tokens  $0.30
# cron:freshness          2,345 tokens  $0.07
```

**验收**:
```
☐ --today, --week, --month 都可用
☐ --by-service <name> 过滤
☐ --by-caller <name> 过滤
☐ 无参数时输出当日摘要
```

## T107: 日报cron (1天)

```bash
# 每天早上8:45推送
schedule: "45 8 * * *"
script: "~/.hermes/scripts/cost_digest.sh"
# 内容: 昨日token消耗汇总
```

**验收**:
```
☐ 每天早上推送token消耗
☐ 无异常时静默
☐ 有异常（如突增）时告警
```
