# bus-foundation R89–R97 实施 Plan

> **配套 spec**: [`2026-07-10-bus-foundation-r89-r97-spec.md`](./2026-07-10-bus-foundation-r89-r97-spec.md) — 必读
> **执行模式**: 每 R 独立 worktree + PR, 严格 TDD, 频繁 commit
> **每个 R 步骤**: 写失败测试 → 跑测试确认红 → 写最小实现 → 跑测试确认绿 → commit

---

## 全局前置条件 (One-Time Setup)

```bash
# 1. 在父仓 omostation 起 worktree
cd /Users/xiamingxing/Workspace
bash bin/gac-worktree.sh claim bus-foundation-r89
cd /Users/xiamingxing/ws-bus-foundation-r89
git submodule update --init projects/bus-foundation

# 2. 在 bus-foundation 子模块内建工作分支
cd projects/bus-foundation
git checkout -b r89-metrics
git checkout 91355d67  # R82 末态
```

> 后续每个 R 用同样模式: `bus-foundation-r90` / `bus-foundation-r91` / ...

---

## R89 — Metrics & Health Endpoints (Week 1-2)

### 任务 R89.1: protocols/metrics-registry.yaml SSOT

**Files:**
- Create: `protocols/metrics-registry.yaml`
- Test: `protocols/test_metrics_registry.py` (新)

- [ ] **Step 1: 写失败测试 — registry 加载 + 名称唯一性**

```python
# protocols/test_metrics_registry.py
"""Verify metrics-registry.yaml schema and uniqueness."""
from pathlib import Path
import yaml
import pytest

REG = Path(__file__).parent / "metrics-registry.yaml"

@pytest.fixture
def registry():
    return yaml.safe_load(REG.read_text())

def test_registry_loads(registry):
    assert "metrics" in registry
    assert len(registry["metrics"]) >= 6

def test_metric_names_unique(registry):
    names = [m["name"] for m in registry["metrics"]]
    assert len(names) == len(set(names)), f"Duplicate: {names}"

def test_required_fields(registry):
    for m in registry["metrics"]:
        for k in ("name", "type", "description", "labels"):
            assert k in m, f"{m.get('name', '?')} missing {k}"
```

- [ ] **Step 2: 跑测试确认 red**
- [ ] **Step 3: 创建 metrics-registry.yaml 模板**
- [ ] **Step 4: 跑测试确认 green**
- [ ] **Step 5: commit** `git commit -m "chore(protocols): add metrics-registry SSOT"`

### 任务 R89.2: bus_foundation/metrics 抽象层

**Files:**
- Create: `bus_foundation/metrics/__init__.py`
- Create: `bus_foundation/metrics/registry.py`
- Test: `tests/test_metrics_registry.py`

- [ ] **Step 1: 写失败测试 — counter/histogram/gauge 抽象**
- [ ] **Step 2: 跑测试确认 red**
- [ ] **Step 3: 实现 Counter / Histogram / Gauge 类, 全局 Registry**
- [ ] **Step 4: 跑测试确认 green**
- [ ] **Step 5: commit**

### 任务 R89.3: 9 个 backend instrumentation

**Files:**
- Create: `bus_foundation/metrics/instrumentation.py`
- Modify: `bus_foundation/backends/{eventbus,asyncio,messagebus,croniter,persistent_bus,data_plane,control_plane,realtime,sse,ws}.py`
- Test: `tests/test_metrics_instrumentation.py`

- [ ] **Step 1: 写失败测试 — 每个 backend publish 触发 counter increment**
- [ ] **Step 2: 跑测试 red**
- [ ] **Step 3: 在每个 backend publish/subscribe 调用 metrics 记录**
- [ ] **Step 4: 跑测试 green**
- [ ] **Step 5: 跑全部 124+ existing tests 确认零破坏**
- [ ] **Step 6: commit**

### 任务 R89.4: HTTP /metrics server

**Files:**
- Create: `bus_foundation/metrics/server.py`
- Test: `tests/test_metrics_server.py`

- [ ] **Step 1: 写失败测试 — 启动 server, curl /metrics, 验证 Prometheus 格式**
- [ ] **Step 2: 跑测试 red**
- [ ] **Step 3: 用 aiohttp + prometheus_client 实现 server**
- [ ] **Step 4: 跑测试 green**
- [ ] **Step 5: 集成测试 — 1000 envelope publish, 验证 counter 值**
- [ ] **Step 6: commit**

### 任务 R89.5: 公共 API 接入 + 默认 OFF

**Files:**
- Modify: `bus_foundation/__init__.py`

- [ ] **Step 1: 加 `enable_metrics(port=8745)`, `disable_metrics()`, `metrics.snapshot()`**
- [ ] **Step 2: 测试 — 默认 metrics.snapshot() 返回空 registry**
- [ ] **Step 3: 测试 — enable_metrics 后 snapshot 包含 counter**
- [ ] **Step 4: commit**

### 任务 R89.6: Bench overhead 验证

**Files:**
- Create: `benchmarks/test_metrics_overhead.py`

- [ ] **Step 1: 写测试 — disable vs enable mode, 100K publish, 对比 throughput**
- [ ] **Step 2: 跑测试, 验证 overhead < 5%**
- [ ] **Step 3: commit**

### 任务 R89.7: 集成 + 跨项目 PR

- [ ] **Step 1: 跑 `cd projects/bus-foundation && make test-diff` 全绿**
- [ ] **Step 2: 跑父仓 `make gac-local-gate`**
- [ ] **Step 3: 提交 bus-foundation 子模块 PR (`r89-metrics` branch)**
- [ ] **Step 4: 父仓 worktree bump submodule pointer, 开 PR**
- [ ] **Step 5: 抄送 aetherforge 维护者 (R94 联动准备)**

---

## R90 — Retry Middleware & Circuit Breaker (Week 3-4)

### 任务 R90.1: RetryPolicy 抽象

**Files:**
- Create: `bus_foundation/retry/__init__.py`
- Create: `bus_foundation/retry/policy.py`
- Test: `tests/test_retry_policy.py`

- [ ] **Step 1: 写失败测试 — backoff math (exponential + jitter)**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 RetryPolicy dataclass + compute_backoff(attempt)**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: 测试 — 1000 次 backoff 抽样, 验证 jitter ±10%**
- [ ] **Step 6: commit**

### 任务 R90.2: CircuitBreaker 3 状态机

**Files:**
- Create: `bus_foundation/retry/circuit_breaker.py`
- Test: `tests/test_circuit_breaker.py`

- [ ] **Step 1: 写失败测试 — closed → open (5 fails) → 30s 后 half_open → 探针成功 → closed**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 CircuitBreaker + state transitions + threading.Lock**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: commit**

### 任务 R90.3: RetryMiddleware

**Files:**
- Create: `bus_foundation/middleware/__init__.py`
- Create: `bus_foundation/middleware/retry.py`
- Test: `tests/test_retry_middleware.py`

- [ ] **Step 1: 写失败测试 — 注入 fail-then-succeed backend, 验证重试 3 次最终成功**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 RetryMiddleware (policy + circuit breaker per backend)**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: 集成测试 — 9 backend × fail-then-succeed × 4 配置 = 36 场景**
- [ ] **Step 6: commit**

### 任务 R90.4: 接入 Router + 默认 OFF

**Files:**
- Modify: `bus_foundation/router.py`
- Modify: `bus_foundation/__init__.py`

- [ ] **Step 1: Router 默认 disable retry, 显式 opt-in**
- [ ] **Step 2: data_plane / croniter 强制 no-retry (用 PER_BACKEND_OVERRIDES)**
- [ ] **Step 3: commit**

### 任务 R90.5: Metric 暴露

- [ ] **Step 1: 加 `bus_retry_attempted_total{backend, outcome}` counter**
- [ ] **Step 2: 加 `bus_circuit_breaker_state{backend, state}` gauge**
- [ ] **Step 3: 跑 R89 metrics 测试确认新指标出现**
- [ ] **Step 4: commit**

### 任务 R90.6: Bench + 跨项目 PR

- [ ] **Step 1: retry_on 注入开销 bench (目标: 启用 retry 时额外延迟 < 1ms)**
- [ ] **Step 2: 全集成测试 PASS**
- [ ] **Step 3: 提交 bus-foundation PR + 父仓 submodule bump PR**
- [ ] **Step 4: 抄送 agora/omo/metaos (他们用 Router, 确认默认 OFF 不破坏)**

---

## R91 — DLQ Admin CLI + Redaction + Metrics (Week 5-6)

### 任务 R91.1: Redaction hook

**Files:**
- Create: `bus_foundation/dlq/redaction.py`
- Test: `tests/test_dlq_redaction.py`

- [ ] **Step 1: 写失败测试 — 3 类敏感字段 (password/secret/token) 替换为 `***`**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 Redactor + 默认规则 (Luhn 信用卡 / 邮箱 / IP)**
- [ ] **Step 4: 用户配置加载: `~/.config/bus-foundation/redaction.yaml`**
- [ ] **Step 5: 跑 green**
- [ ] **Step 6: commit**

### 任务 R91.2: DLQ Admin Python API

**Files:**
- Create: `bus_foundation/dlq/admin.py`
- Test: `tests/test_dlq_admin.py`

- [ ] **Step 1: 写失败测试 — admin.list / admin.ack / admin.retry / admin.purge**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 DLQAdmin 包装现有 DLQ 类**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: commit**

### 任务 R91.3: bin/bus-dlq CLI

**Files:**
- Create: `bin/bus-dlq`
- Modify: `pyproject.toml` (加 `[project.scripts]`)

- [ ] **Step 1: 写 shell 脚本: list / stats / ack / retry / purge / watch 子命令**
- [ ] **Step 2: 测试 — 每个子命令独立 smoke test**
- [ ] **Step 3: 加 entry point `bus-dlq = "bus_foundation.dlq.admin:main"`**
- [ ] **Step 4: 跑 `uv run --project projects/bus-foundation bus-dlq list` 验证**
- [ ] **Step 5: commit**

### 任务 R91.4: 接入 redaction + DLQ depth metric

**Files:**
- Modify: `bus_foundation/dlq.py`

- [ ] **Step 1: enqueue 前调 redactor.redact(envelope_json)**
- [ ] **Step 2: 每次 enqueue 触发 `bus_dlq_depth` gauge 更新 (复用 R89)**
- [ ] **Step 3: 跑 redaction 测试 + 124+ existing tests 确认零破坏**
- [ ] **Step 4: commit**

### 任务 R91.5: Agent workflow 注册

**Files:**
- Modify: `.omo/_truth/registry/agent-workflows.yaml`

- [ ] **Step 1: 加 workflow `bus-foundation-dlq-ops` (dormant 状态)**
- [ ] **Step 2: 写最小 gate (lint only, no actions)**
- [ ] **Step 3: commit + 等 P74 1 周内有 caller**

### 任务 R91.6: 跨项目 PR

- [ ] **Step 1: 全测试 PASS**
- [ ] **Step 2: PoC 集成: aetherforge cockpit 加 "DLQ Depth" 面板, 调 bus-dlq stats**
- [ ] **Step 3: 提交 bus-foundation PR + 父仓 submodule bump PR**
- [ ] **Step 4: 抄送 agora / omo / metaos 维护者**

---

## R97 — Property-Based + Chaos Testing (Week 7) [前置]

> R97 在 R92/R94/R96 之前, 因为它的 property test 框架会被 R92 / R94 复用.

### 任务 R97.1: hypothesis 依赖

**Files:**
- Modify: `pyproject.toml` (加 dev 依赖)
- Modify: `uv.lock`

- [ ] **Step 1: 加 `hypothesis>=6.0` 到 `[project.optional-dependencies].dev`**
- [ ] **Step 2: `uv lock` 重新生成**
- [ ] **Step 3: commit**

### 任务 R97.2: Envelope property tests

**Files:**
- Create: `tests/property/__init__.py`
- Create: `tests/property/test_envelope_properties.py`

- [ ] **Step 1: 写 property test — 随机字段 round-trip serialize/deserialize 不丢失**
- [ ] **Step 2: 跑测试, 验证 1000+ examples 无 fail**
- [ ] **Step 3: 故意引入 bug (改 pydantic 验证), 验证 hypothesis 抓到**
- [ ] **Step 4: revert bug, commit**

### 任务 R97.3: Pattern match property tests

**Files:**
- Create: `tests/property/test_pattern_match.py`

- [ ] **Step 1: 写 property test — pattern_match 边界 (R80 那类 bug 提前发现)**
- [ ] **Step 2: 跑 1000+ examples, 确认现有逻辑对**
- [ ] **Step 3: commit**

### 任务 R97.4: Chaos test 框架

**Files:**
- Create: `tests/chaos/__init__.py`
- Create: `tests/chaos/test_backend_chaos.py`

- [ ] **Step 1: 写 chaos test — mock backend 模拟 random ConnectionError / slow / kill**
- [ ] **Step 2: 跑测试, 验证 Router / DLQ / R90 retry 协同工作**
- [ ] **Step 3: commit**

### 任务 R97.5: CI 集成

- [ ] **Step 1: `pyproject.toml` 加 `pytest --hypothesis-show-statistics` 配置**
- [ ] **Step 2: 父仓 `.github/workflows/gac-gate.yml` 加 property test 步骤 (跟 pytest 一起跑)**
- [ ] **Step 3: commit**

---

## R92 — Schema Registry & Compatibility Matrix (Week 8-9)

### 任务 R92.1: Schema registry 抽象

**Files:**
- Create: `bus_foundation/schema/__init__.py`
- Create: `bus_foundation/schema/registry.py`
- Test: `tests/test_schema_registry.py`

- [ ] **Step 1: 写失败测试 — register("v1", V1) / register("v2", V2, compat="additive") / get("v1")**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 SchemaRegistry + 兼容性策略**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: commit**

### 任务 R92.2: Compatibility check

**Files:**
- Create: `bus_foundation/schema/compatibility.py`
- Test: `tests/test_schema_compatibility.py`

- [ ] **Step 1: 写失败测试 — strict / additive / breaking 三档**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 compatibility check 用 pydantic v1 / v2 模型对比**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: commit**

### 任务 R92.3: 集成到 envelope validate

**Files:**
- Modify: `bus_foundation/envelope.py`
- Modify: `bus_foundation/__init__.py` (启动时注册 v1 / v2)

- [ ] **Step 1: 启动时 `register("v1", OmniEnvelope)`, `register("v2", OmniEnvelope)` (additive)**
- [ ] **Step 2: 验证 `OmniEnvelope(schema_version="v999")` 抛 ValidationError**
- [ ] **Step 3: 跑 124+ existing tests 确认零破坏**
- [ ] **Step 4: commit**

### 任务 R92.4: JSON Schema 导出

**Files:**
- Create: `bus_foundation/schema/codegen.py`
- Test: `tests/test_schema_codegen.py`

- [ ] **Step 1: 写失败测试 — `export_json_schema("v2")` 返回 pydantic 生成的 schema**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 用 `OmniEnvelope.model_json_schema()` 实现**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: commit**

### 任务 R92.5: PoC — TypeScript codegen 验证

- [ ] **Step 1: `bus-foundation export-schema --version=v2 --output=schema.json`**
- [ ] **Step 2: `npx json-schema-to-typescript schema.json -o envelope.ts`**
- [ ] **Step 3: 在 aetherforge-ui 写一个 demo 验证 round-trip**
- [ ] **Step 4: 跨项目 PR 提交 + 抄送 aetherforge 维护者**

---

## R94 — OpenTelemetry Integration (Week 10-11)

### 任务 R94.1: OTel 依赖

**Files:**
- Modify: `pyproject.toml` (加 `[otel]` extra)

- [ ] **Step 1: 加 `opentelemetry-api>=1.20`, `opentelemetry-sdk>=1.20` 到 `[project.optional-dependencies].otel`**
- [ ] **Step 2: `uv lock`**
- [ ] **Step 3: commit**

### 任务 R94.2: OTel tracer 抽象

**Files:**
- Create: `bus_foundation/observability/__init__.py`
- Create: `bus_foundation/observability/traces.py`
- Test: `tests/test_otel_integration.py`

- [ ] **Step 1: 写失败测试 — publish envelope 创建 span, `span.context.trace_id` 跟 envelope.trace_id 一致**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 OTLP exporter + tracer 抽象**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: commit**

### 任务 R94.3: 接入 publish / subscribe

**Files:**
- Modify: `bus_foundation/router.py`
- Modify: `bus_foundation/middleware/metrics.py` (R89)

- [ ] **Step 1: router.publish() 启 span "bus.publish {backend}"**
- [ ] **Step 2: subscriber callback 启子 span "bus.deliver {pattern}"**
- [ ] **Step 3: trace_id 透传: envelope.trace_id → span.parent_context**
- [ ] **Step 4: 跑全部现有测试 + R89/R90/R91 + R97 property tests**
- [ ] **Step 5: commit**

### 任务 R94.4: aetherforge 联动

- [ ] **Step 1: aetherforge gateway 拉 bus-foundation OTel spans**
- [ ] **Step 2: cockpit 端到端 trace: agent 调用 → agora → bus_foundation publish → subscriber → 回包**
- [ ] **Step 3: 截图 / 录屏 evidence → `.omo/_delivery/r94-evidence.md`**

### 任务 R94.5: 跨项目 PR

- [ ] **Step 1: 全测试 PASS + property tests green**
- [ ] **Step 2: 提交 bus-foundation PR + aetherforge PR + 父仓 submodule bump**
- [ ] **Step 3: 抄送 omo / agora / cockpit 维护者**

---

## R96 — Croniter 完整表达式 (Week 12)

### 任务 R96.1: croniter PyPI 库接入

**Files:**
- Modify: `pyproject.toml`
- Modify: `bus_foundation/backends/croniter.py`

- [ ] **Step 1: 加 `croniter>=2.0` 到 dependencies (或可选 extra)**
- [ ] **Step 2: 跑测试 red (现有 `every` 语法回归)**
- [ ] **Step 3: 重构 croniter.py: 保留 `every` 解析, 优先用 croniter 库**
- [ ] **Step 4: 跑测试 green**
- [ ] **Step 5: commit**

### 任务 R96.2: 完整 cron + timezone

- [ ] **Step 1: 写失败测试 — `subscribe("0 9 * * 1", cb)` (周一 9 点) 触发**
- [ ] **Step 2: 跑 red**
- [ ] **Step 3: 实现 croniter 库 + timezone 处理 (`pytz` 或 `zoneinfo`)**
- [ ] **Step 4: 跑 green**
- [ ] **Step 5: 边界测试 — DST 切换 / 闰年**
- [ ] **Step 6: commit**

### 任务 R96.3: 向后兼容 + 文档

- [ ] **Step 1: 跑 124+ existing tests, 确认 `every` 语法仍工作**
- [ ] **Step 2: 更新 `docs/CRON-EXPRESSIONS.md` 加完整 cron 文档**
- [ ] **Step 3: 跨项目 PR 提交**

---

## 收尾: 0.3.0 Release

### 任务 REL.1: CHANGELOG + version bump

- [ ] **Step 1: `pyproject.toml` version 0.2.0 → 0.3.0**
- [ ] **Step 2: `CHANGELOG.md` 加 `## [0.3.0] - 2026-...` section, 列 R89-R97 全部**
- [ ] **Step 3: commit**

### 任务 REL.2: Arch doc 更新

- [ ] **Step 1: `docs/ARCHITECTURE-DETAILED-MAP.md` §3.3 bus-foundation 部分更新, 反映新 middleware**
- [ ] **Step 2: `projects/bus-foundation/ARCHITECTURE.md` 同步**

### 任务 REL.3: OMO 治理审计

- [ ] **Step 1: 跑 `make ci-local`**
- [ ] **Step 2: 跑 `uv run --with "pyyaml" python "bin/governance-evolution.py" status --json`**
- [ ] **Step 3: 提交 evidence → `.omo/_delivery/r89-r97-closeout.md`**

---

## 跟踪与状态

| R | 状态 | Worktree | 子模块 PR | 父仓 PR | 合并时间 |
|---|------|----------|----------|---------|----------|
| R89 | ⏳ pending | - | - | - | - |
| R90 | ⏳ pending | - | - | - | - |
| R91 | ⏳ pending | - | - | - | - |
| R97 | ⏳ pending | - | - | - | - |
| R92 | ⏳ pending | - | - | - | - |
| R94 | ⏳ pending | - | - | - | - |
| R96 | ⏳ pending | - | - | - | - |

> 每周一更新进度. 任何 R 阻塞超过 1 周, 升级到 OMO 治理审计.

---

## 参考与上游

- [bus-foundation R82 envelope PR 模式](https://github.com/starlink-awaken/omostation/pulls?q=is%3Apr+bus-foundation+merged%3A2026) — pydantic 迁移是好的参考
- [ADR-0130 P74 workflow solidification](.omo/_knowledge/decisions/0130-p74-workflow-solidification.md) — 新 workflow 不能沉默
- [P71 baseline recovery pattern](.omo/_knowledge/patterns/p71-baseline-recovery-pattern.md) — 工具未接 (类 B) 治本
- [writing-plans skill](../../.agents/skills/writing-plans/SKILL.md) — 本 plan 格式来源
- [brainstorming skill](../../.agents/skills/brainstorming/SKILL.md) — spec 流程来源
