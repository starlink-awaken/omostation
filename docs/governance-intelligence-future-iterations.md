---
status: active
lifecycle: entry
owner: governance-team
last-reviewed: 2026-08-18
type: ssot
last_updated: 2026-09-03
---
# 治理智能未来迭代 — 全面架构设计与落地路径

> 本文档在 Phase 1-5 已合入 main 的基础上，设计后续迭代的架构方案、融合路径和可执行落地计划。
> 基线: PR #1086 (Phase 1-4) + PR #1098 (Phase 5) + commit 14c995b1b/b534b9fbb (docs registration)

---

## 1. 现状总览与架构定位

### 1.1 Phase 1-5 交付总结

| Phase | 组件 | 状态 | 核心文件 | 测试 |
|-------|------|------|---------|------|
| Phase 1 | Metrics Store | ✅ 已合入 | `bin/gac/metrics-store.py` | 5/5 |
| Phase 2 | Adaptive Gate | ✅ 已合入 | `bin/gac/adaptive-gate.py` | 5/5 |
| Phase 3 | Risk Profile | ✅ 已合入 | `bin/gac/risk-profile.py` | 5/5 |
| Phase 4 | Governance Summarizer | ✅ 已合入 | `bin/gac/governance-summarizer.py` | 5/5 |
| Phase 5 | Debt Predictor | ✅ 已合入 | `bin/gac/debt-predictor.py` | 3/3 |

### 1.2 当前架构定位

```
┌─────────────────────────────────────────────────────────────────────┐
│                     现有治理智能能力层 (Phase 1-5)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │ Metrics     │  │ Adaptive    │  │ Risk Profile                 │  │
│  │ Store       │  │ Gate        │  │ Router                       │  │
│  │ (JSONL)     │  │ (EWMA+z)    │  │ (path-based)                 │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────────┬──────────────┘  │
│         │                │                        │                   │
│  ┌──────┴────────────────┴────────────────────────┴──────────────┐  │
│  │              gac-local-gate.py (opt-in flags)                 │  │
│  │  --metrics --adaptive --risk-profile --summarize              │  │
│  └──────────────────────────────┬────────────────────────────────┘  │
│                                 │                                  │
│  ┌──────────────────────────────┴────────────────────────────────┐  │
│  │              Existing Governance Layer                        │  │
│  │  gac-validate / gac-drift / doc-governance / ...             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 与织星 5+4+1+1 架构的融合点

| 织星层 | 融合点 | Phase 1-5 利用方式 |
|--------|--------|-------------------|
| L4 自我层 | l4-kernel 信号总线 | 治理指标可注册为信号源 |
| L3 入口层 | cockpit CLI/Web | `--summarize` 输出可作为 cockpit 视图数据源 |
| I0 织层 | Agora BOS URI | Phase 1-5 工具已通过 `bos://governance/*` 可发现 |
| L2 治理面 | omo 任务/债务/审计 | `debt-predictor.py` 读取 `.omo/debt/items/*.yaml` |
| L1 运行时 | runtime Matrix/Cron | 可驱动 nightly 治理报告生成 |
| L0 协议层 | ecos MOF/SSB | `sgf-policy.yaml` 动态加载机制已复用 |
| X1 审计 | audit chain | metrics-store.jsonl 可作为审计证据 |
| X2 抗熵 | staleness/freshness | Phase 2 异常检测可增强 X2 监控 |
| X3 价值栈 | value/delivery | Phase 5 预测可纳入 X3 SLA 分析 |
| X4 一致性 | consistency checks | Phase 3 risk-profile 可增强 X4 过滤 |

---

## 2. 未来迭代架构设计

### 2.1 设计原则

1. **架构收敛** — 所有新能力必须映射到现有 5+4+1+1 层的某个职责面，不新增顶层入口
2. **SSOT 指针不复制** — 路径、配置、阈值全部通过 registry 引用，不硬编码
3. **BOS URI 优先** — 新能力优先暴露为 `bos://governance/*` 服务，而非新 CLI
4. **Local-first** — 不引入外部数据库依赖，JSONL + YAML SSOT 足够支撑
5. **Opt-in 进化** — 新能力通过 flag/registry toggle 启用，不破坏现有契约
6. **Evidence-close** — 每个预测/异常必须附带证据链（metrics 条目、时间窗口、置信度）

### 2.2 迭代阶段划分

```
Phase 6: Anomaly Alerting    (1-2 周)  — 异常检测 + 告警路由
Phase 7: Governance Dashboard (2-3 周)  — 可视化 + cockpit 集成
Phase 8: BOS Service-ification (2-3 周)  — Phase 1-5 全部 BOS URI 化
Phase 9: Cross-Domain Fusion  (3-4 周)  — 跨域趋势融合 + BasePredictor
Phase 10: Predictive Governance (4-6 周) — 预测性治理 + 自动建议
```

### 2.3 总体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Phase 6: Anomaly Alerting                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────────┐  │
│  │ Anomaly     │  │ Alert       │  │ External Connection Fabric       │  │
│  │ Detector    │  │ Router      │  │ (Slack/飞书/Email/Cockpit)      │  │
│  │ (Phase 2)   │  │ (new)       │  │ (existing)                       │  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────────────────┘  │
│         │                │                                                │
│         └────────────────┼────────────────────────────────────────────┘  │
│                          ▼                                                │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              metrics-store.jsonl (existing)                       │  │
│  │              + anomaly-events.jsonl (new, append-only)            │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                     Phase 7: Governance Dashboard                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  cockpit-ui / Grafana / WPS 笔记                                  │  │
│  │  - 时间序列: metrics-store.jsonl                                  │  │
│  │  - 健康分趋势: health.yaml history                                │  │
│  │  - 债务预测: debt-predictor output                                │  │
│  │  - 风险分布: risk-profile 统计                                     │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  bin/gac/governance-dashboard.py (new)                            │  │
│  │  - 生成 dashboard 数据 JSON                                        │  │
│  │  - 支持 --output html/json                                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    Phase 8: BOS Service-ification                       │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  bos://governance/metrics/*       → metrics-store.py              │  │
│  │  bos://governance/adaptive/*      → adaptive-gate.py              │  │
│  │  bos://governance/risk/*          → risk-profile.py               │  │
│  │  bos://governance/summary/*       → governance-summarizer.py      │  │
│  │  bos://governance/prediction/*    → debt-predictor.py             │  │
│  │  bos://governance/anomaly/*       → anomaly-detector.py (new)     │  │
│  │  bos://governance/dashboard/*     → governance-dashboard.py (new) │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  projects/agora/etc/bos-services.yaml (existing)                   │  │
│  │  + Phase 1-5 + Phase 6-8 路由注册                                 │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                    Phase 9: Cross-Domain Trend Fusion                   │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  workspace/tools/base/base_predictor.py (existing)                 │  │
│  │  + GovernancePredictor (new adapter)                               │  │
│  │  + CodeQualityPredictor (new adapter)                              │  │
│  │  + TestHealthPredictor (new adapter)                               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  .omo/_truth/registry/trend-fusion.yaml (new)                      │  │
│  │  - 跨域指标映射表                                                  │  │
│  │  - 融合权重配置                                                    │  │
│  │  - 告警阈值                                                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  bin/gac/cross-domain-trend.py (new)                               │  │
│  │  - 读取各域 metrics                                                │  │
│  │  - 计算融合趋势                                                    │  │
│  │  - 输出跨域告警                                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                  Phase 10: Predictive Governance (Advanced)             │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  bin/gac/predictive-governance.py (new)                            │  │
│  │  - ML-based prediction (beyond linear regression)                  │  │
│  │  - Prescriptive recommendations                                    │  │
│  │  - Automated remediation suggestions                               │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │  .omo/_truth/registry/predictive-governance.yaml (new)             │  │
│  │  - 模型配置                                                        │  │
│  │  - 特征工程配置                                                    │  │
│  │  - 行动建议映射                                                    │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 6: Anomaly Alerting (异常告警)

### 3.1 架构设计

**目标**: 将 Phase 2 的异常检测从"被动查询"升级为"主动告警"。

**核心组件**:

| 组件 | 职责 | 文件 |
|------|------|------|
| Anomaly Detector | 实时/定时扫描 metrics-store.jsonl，检测异常 | 扩展现有 `adaptive-gate.py` |
| Alert Router | 根据异常严重度路由到不同通道 | 新建 `bin/gac/alert-router.py` |
| Anomaly Event Store | 追加异常事件到 JSONL | 新建 `.omo/state/anomaly-events.jsonl` |
| Alert Config | 告警阈值和路由配置 | 扩展现有 `governance-alerts.yaml` |

**数据流**:

```
metrics-store.jsonl
    │
    ▼
Anomaly Detector (EWMA + z-score, 可配置窗口)
    │
    ▼
anomaly-events.jsonl (append-only)
    │
    ▼
Alert Router
    │
    ├──→ cockpit-ui (WebSocket/SSE)
    ├──→ Slack/飞书 (via External Connection Fabric)
    ├──→ Email (via External Connection Fabric)
    └──→ GitHub PR comment (via CI)
```

**与现有架构的融合**:

1. **External Connection Fabric**: 复用 `external-connection-fabric.yaml` 的 channel 配置，不新建通知基础设施
2. **governance-alerts.yaml**: 扩展现有告警配置，添加 anomaly-specific 规则
3. **finding_topics**: 异常结果继续映射到 `finding_topics` 机制，保持 gate 输出契约不变
4. **BOS URI**: 新增 `bos://governance/anomaly/*` 路由

**SSOT 注册**:

```yaml
# .omo/_truth/registry/runtime-projections.yaml
projections:
  anomaly_events:
    description: Governance anomaly events (append-only JSONL)
    canonical: .omo/state/runtime/anomaly-events.jsonl
    legacy: .omo/state/anomaly-events.jsonl
    generator: anomaly-detector / gac-local-gate --adaptive
    lane: runtime_snapshot
```

### 3.2 落地路径

| 步骤 | 任务 | 工时 | 验收 |
|------|------|------|------|
| 6.1 | 扩展现有 `adaptive-gate.py` 支持 `--anomalies` 输出 JSON | 2h | 输出包含 anomaly 列表 |
| 6.2 | 新建 `alert-router.py` 读取 anomaly-events.jsonl | 3h | 支持 `--config governance-alerts.yaml` |
| 6.3 | 扩展现有 `governance-alerts.yaml` 添加 anomaly rules | 1h | YAML 解析通过 |
| 6.4 | 在 `gac-local-gate.py` 中集成 `--alert` flag | 2h | `--adaptive --alert` 触发告警 |
| 6.5 | 注册 BOS URI 路由 | 1h | `bos://governance/anomaly/list` 可解析 |
| 6.6 | 添加 5 个测试用例 | 2h | pytest 全绿 |
| **合计** | | **11h** | |

---

## 4. Phase 7: Governance Dashboard (治理仪表盘)

### 4.1 架构设计

**目标**: 将 Phase 1-5 的指标和预测可视化，提供"治理健康度时间机器"。

**核心组件**:

| 组件 | 职责 | 文件 |
|------|------|------|
| Dashboard Data Generator | 从 metrics-store.jsonl + health.yaml + debt-predictor 输出生成 dashboard JSON | 新建 `bin/gac/governance-dashboard.py` |
| HTML Report | 生成自包含 HTML 仪表盘（可选 Chart.js） | 新建 `bin/gac/governance-dashboard.py --format html` |
| cockpit-ui Integration | 在 cockpit 中嵌入 dashboard 视图 | 新建 `projects/cockpit/src/cockpit/commands/governance_dashboard.py` |
| WPS Note Sync | 每日自动同步到 WPS 笔记 | 新建 `bin/gac/governance-dashboard.py --sync-wps` |

**数据流**:

```
metrics-store.jsonl    health.yaml    debt-predictor output
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                  governance-dashboard.py
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    dashboard.json    dashboard.html   WPS 笔记
```

**与现有架构的融合**:

1. **runtime-projections.yaml**: 注册 dashboard 输出路径
2. **cockpit**: 新增 `governance dashboard` 子命令，复用 cockpit 的 Web 框架
3. **WPS 笔记**: 复用 `content-digest` 或 `web-importer`  skill 的同步机制
4. **health.yaml**: 读取历史 health score（需要先支持历史存储）

**SSOT 注册**:

```yaml
# .omo/_truth/registry/runtime-projections.yaml
projections:
  governance_dashboard:
    description: Governance dashboard data (JSON + HTML)
    canonical: .omo/state/runtime/governance-dashboard.json
    legacy: .omo/state/governance-dashboard.json
    generator: governance-dashboard.py
    lane: runtime_snapshot
```

### 4.2 落地路径

| 步骤 | 任务 | 工时 | 验收 |
|------|------|------|------|
| 7.1 | 新建 `governance-dashboard.py` 基础版 (JSON 输出) | 4h | 输出包含 checks/time/risk 三部分 |
| 7.2 | 添加 `--format html` 支持 Chart.js 可视化 | 4h | 浏览器打开可交互 |
| 7.3 | cockpit-ui 集成 (可选) | 4h | cockpit 中可查看 |
| 7.4 | WPS 笔记同步 (可选) | 3h | 每日自动同步 |
| 7.5 | 注册 runtime projection | 1h | SSOT 更新 |
| 7.6 | 添加 5 个测试用例 | 2h | pytest 全绿 |
| **合计** | | **18h** | |

---

## 5. Phase 8: BOS Service-ification (BOS 服务化)

### 5.1 架构设计

**目标**: 将 Phase 1-5 + Phase 6-7 全部能力暴露为 BOS URI 服务，实现 Agent 原生发现和调用。

**核心组件**:

| BOS URI | 后端工具 | 功能 |
|---------|---------|------|
| `bos://governance/metrics/append` | metrics-store.py append | 追加指标 |
| `bos://governance/metrics/query` | metrics-store.py query | 查询指标 |
| `bos://governance/metrics/stats` | metrics-store.py stats | 指标统计 |
| `bos://governance/adaptive/threshold` | adaptive-gate.py --check | 获取自适应阈值 |
| `bos://governance/adaptive/anomalies` | adaptive-gate.py --anomalies | 获取异常列表 |
| `bos://governance/risk/profile` | risk-profile.py | 获取风险等级 |
| `bos://governance/summary/generate` | governance-summarizer.py | 生成摘要 |
| `bos://governance/prediction/trend` | debt-predictor.py | 获取趋势预测 |
| `bos://governance/anomaly/list` | anomaly-detector.py | 获取异常事件 |
| `bos://governance/dashboard/data` | governance-dashboard.py | 获取仪表盘数据 |

**与现有架构的融合**:

1. **agora BOS registry**: 在 `projects/agora/etc/bos-services.yaml` 注册所有路由
2. **external-connection-fabric.yaml**: 新增 `governance_tool` resource_kind
3. **memory-recall skill**: Agent 可通过 `memory-recall` 发现这些 BOS 服务
4. **cockpit**: 现有 cockpit BOS 解析器可直接调用

**BOS 服务契约**:

```yaml
# projects/agora/etc/bos-services.yaml 新增条目
services:
  - id: governance-metrics-append
    domain: governance
    path: /metrics/append
    method: POST
    input_schema:
      check: string
      ok: boolean
      duration_ms: integer
    output_schema:
      status: string
  - id: governance-adaptive-threshold
    domain: governance
    path: /adaptive/threshold
    method: GET
    input_schema:
      check: string
      window: integer
    output_schema:
      recommended_warn_threshold: integer
```

### 5.2 落地路径

| 步骤 | 任务 | 工时 | 验收 |
|------|------|------|------|
| 8.1 | 在 `bos-services.yaml` 注册 Phase 1-5 路由 | 2h | `agora resolve bos://governance/metrics/query` 返回结果 |
| 8.2 | 实现 BOS handler wrapper (统一错误处理 + JSON) | 4h | 所有路由返回标准 JSON |
| 8.3 | 添加 authentication/authorization (可选) | 2h | 仅本地/agent 可调用 |
| 8.4 | 更新 `external-connection-fabric.yaml` | 1h | governance_tool kind 注册 |
| 8.5 | 更新 `memory-recall` skill 路由表 | 1h | Agent 可发现新 BOS 服务 |
| 8.6 | 添加 10 个 BOS 集成测试 | 4h | pytest + agora test 全绿 |
| **合计** | | **14h** | |

---

## 6. Phase 9: Cross-Domain Trend Fusion (跨域趋势融合)

### 6.1 架构设计

**目标**: 将治理指标与代码质量、测试健康度、KOS 活动等跨域指标联合分析，提供系统性健康视图。

**核心组件**:

| 组件 | 职责 | 文件 |
|------|------|------|
| Trend Fusion Registry | 跨域指标映射表、融合权重、告警阈值 | 新建 `.omo/_truth/registry/trend-fusion.yaml` |
| Cross-Domain Trend Analyzer | 读取各域 metrics，计算融合趋势 | 新建 `bin/gac/cross-domain-trend.py` |
| Governance Predictor Adapter | 将 Phase 5 预测适配到 BasePredictor 接口 | 新建 `workspace/tools/governance/governance-predictor.py` |

**融合维度**:

| 域 | 数据源 | 指标 |
|---|--------|------|
| 治理 | metrics-store.jsonl | gate pass rate, check duration, debt trend |
| 代码质量 | pyright/ruff output | type error count, lint warning count |
| 测试健康 | pytest output | coverage %, test count, failure rate |
| KOS 活动 | KOS metrics | search hit rate, knowledge update frequency |
| 外部连接 | external-connection-fabric.yaml | resource health, adapter availability |

**与现有架构的融合**:

1. **workspace/tools/base/base_predictor.py**: 实现统一的 `Predictor` 接口
2. **trend-fusion.yaml**: 新增 SSOT registry，配置跨域映射
3. **BOS URI**: 新增 `bos://analysis/trend/*` 路由（通过 Agora）
4. **cockpit**: 跨域趋势可集成到 cockpit 仪表盘

**SSOT 注册**:

```yaml
# .omo/_truth/registry/trend-fusion.yaml
domains:
  governance:
    source: metrics-store.jsonl
    adapter: governance-predictor
    metrics:
      - gate_pass_rate
      - check_duration_trend
      - debt_volume_trend
  code_quality:
    source: pyright-report.jsonl
    adapter: code-quality-predictor
    metrics:
      - type_error_count
      - lint_warning_count
  test_health:
    source: pytest-report.jsonl
    adapter: test-health-predictor
    metrics:
      - coverage_percent
      - failure_rate

fusion:
  weights:
    governance: 0.4
    code_quality: 0.3
    test_health: 0.3
  alert_threshold: 0.3  # 融合趋势下降 30% 触发告警
```

### 6.2 落地路径

| 步骤 | 任务 | 工时 | 验收 |
|------|------|------|------|
| 9.1 | 设计 trend-fusion.yaml schema | 2h | SSOT 文档通过 |
| 9.2 | 实现 GovernancePredictor adapter | 4h | 实现 BasePredictor 接口 |
| 9.3 | 实现 CrossDomainTrendAnalyzer | 4h | 读取多源 metrics 并融合 |
| 9.4 | 集成到 governance-dashboard.py | 2h | dashboard 包含跨域视图 |
| 9.5 | 注册 BOS URI 路由 | 2h | `bos://analysis/trend/fusion` 可调用 |
| 9.6 | 添加 5 个测试用例 | 3h | pytest 全绿 |
| **合计** | | **17h** | |

---

## 7. Phase 10: Predictive Governance (Advanced) (预测性治理)

### 7.1 架构设计

**目标**: 从"描述性分析"升级到"预测性建议"和"处方性行动"。

**核心能力**:

| 能力 | 说明 | 技术方案 |
|------|------|---------|
| ML-based Prediction | 超越线性回归的复杂趋势预测 | Prophet / ARIMA / LSTM (可选) |
| Prescriptive Recommendations | 不仅预测"会发生什么"，还建议"应该做什么" | 规则引擎 + LLM 辅助 |
| Automated Remediation Suggestions | 自动生成修复建议 | 模板库 + 上下文感知 |
| Policy Simulation | 模拟"如果调整阈值会怎样" | What-if 分析引擎 |

**与现有架构的融合**:

1. **workspace/tools/base/base_predictor.py**: 实现 ML-based predictor
2. **sgf-policy.yaml**: 预测结果可自动调整 policy 阈值（需人工审批）
3. **C2G**: 预测性债务可转化为 C2G 提案
4. **omo debt**: 预测结果可自动创建 debt items（需人工审批）

**处方引擎设计**:

```python
class PrescriptiveEngine:
    def recommend(self, prediction: dict, context: dict) -> list[Recommendation]:
        """
        基于预测结果和当前上下文生成行动建议。
        
        示例输出:
        [
            {
                "action": "increase_threshold",
                "target": "check-submodule-rewind",
                "current": 3,
                "recommended": 5,
                "reason": "异常检测显示近期误报率上升",
                "confidence": 0.85,
                "evidence": ["metrics-store.jsonl:2026-08-*"]
            },
            {
                "action": "create_debt",
                "title": "Submodule rewind false positive rate increasing",
                "priority": "P2",
                "reason": "Predicted 7 days until threshold breach"
            }
        ]
        """
```

### 7.2 落地路径

| 步骤 | 任务 | 工时 | 验收 |
|------|------|------|------|
| 10.1 | 评估 ML 库依赖 (Prophet/ARIMA) | 2h | 确定技术方案 |
| 10.2 | 实现 ML-based predictor (可选 Prophet) | 8h | 预测精度 > 线性回归 20% |
| 10.3 | 实现 PrescriptiveEngine | 6h | 生成可执行建议 |
| 10.4 | 集成到 gac-local-gate.py (--predict flag) | 4h | gate 输出包含 recommendations |
| 10.5 | 添加 policy simulation | 4h | `--simulate-threshold 5` 输出影响分析 |
| 10.6 | 添加 5 个测试用例 | 3h | pytest 全绿 |
| **合计** | | **27h** | |

---

## 8. 与现有架构的完整融合矩阵

| 现有组件 | Phase 6 | Phase 7 | Phase 8 | Phase 9 | Phase 10 |
|---------|---------|---------|---------|---------|----------|
| `gac-local-gate.py` | `--alert` flag | 读取 dashboard 数据 | 调用 BOS handler | 跨域指标输入 | `--predict` flag |
| `metrics-store.jsonl` | 异常检测输入 | dashboard 数据源 | BOS 服务后端 | 跨域数据源 | 预测输入 |
| `health.yaml` | 告警触发条件 | 健康分趋势 | BOS 服务后端 | 融合权重参考 | 处方输入 |
| `runtime-projections.yaml` | 注册 anomaly_events | 注册 dashboard | 已有 metrics_store | 注册 trend-fusion | 注册 predictions |
| `governance-alerts.yaml` | 扩展 anomaly rules | - | - | - | 扩展 prediction rules |
| `external-connection-fabric.yaml` | 复用 channel | - | - | - | 新增 governance_tool |
| `projects/agora/etc/bos-services.yaml` | 注册 anomaly/* | - | 注册 dashboard/* | 注册 trend/* | 注册 predict/* |
| `workspace/tools/base/` | - | - | - | 新增 adapter | 新增 ML predictor |
| `cockpit` | 告警通知 | dashboard 视图 | - | 跨域趋势视图 | 处方建议视图 |
| `C2G` | - | - | - | - | 预测性债务 → 提案 |

---

## 9. 实施路线图（时间盒）

```
Phase 6: ████████████████████ 1-2 周 (11h)
Phase 7: ████████████████████████████████ 2-3 周 (18h)
Phase 8: ████████████████████████ 2-3 周 (14h)
Phase 9: ████████████████████████████████████ 3-4 周 (17h)
Phase 10: ██████████████████████████████████████████████████ 4-6 周 (27h)
         ↑ 可并行阶段

关键路径:
  Phase 6 (Anomaly Alerting)
      ↓
  Phase 8 (BOS Service-ification) ← Phase 6 依赖
      ↓
  Phase 7 (Dashboard) ← Phase 8 依赖 (BOS data source)
      ↓
  Phase 9 (Cross-Domain Fusion) ← Phase 7 依赖 (dashboard integration)
      ↓
  Phase 10 (Predictive Governance) ← Phase 9 依赖 (cross-domain data)
```

### 9.1 快速胜利（Quick Wins）

| 快速胜利 | 预估工时 | 价值 |
|---------|---------|------|
| Phase 6 Anomaly Alerting | 11h | 主动告警，减少人工巡检 |
| Phase 8 BOS Service-ification | 14h | Agent 可发现和调用治理能力 |
| Phase 7 Governance Dashboard | 18h | 可视化治理健康度趋势 |

**合计**: 43h (~1 周) 可实现 3 个高价值能力。

### 9.2 中期建设（Medium-term）

| 建设项 | 预估工时 | 价值 |
|--------|---------|------|
| Phase 9 Cross-Domain Fusion | 17h | 系统性健康视图 |
| Phase 10 Predictive Governance | 27h | 预测性治理能力 |

**合计**: 44h (~1.5 周) 实现预测性和处方性治理。

---

## 10. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Phase 1-5  adoption 不足 | 后续 Phase 数据不足 | 先在 CI/nightly 强制启用 `--metrics --adaptive` |
| metrics-store.jsonl 过大 | 查询性能下降 | 实现 JSONL rotation (按日期/大小) |
| BOS URI 爆炸 | 路由表维护困难 | 按域分组，自动注册机制 |
| ML 预测精度不足 | 误导决策 | 保留线性回归 baseline，ML 为 optional |
| cockpit-ui 集成成本高 | Phase 7 延期 | Phase 7 先做独立 HTML， cockpit 延后 |
| 跨域数据源不一致 | 融合结果不可靠 | 定义统一 metrics schema + 适配器接口 |

---

## 11. ADR 建议

| ADR | 标题 | 触发阶段 |
|-----|------|---------|
| ADR-0390 | Governance Intelligence Phase 6-10 Architecture | Phase 6 前 |
| ADR-0391 | Anomaly Event Store Schema | Phase 6 |
| ADR-0392 | BOS URI Service-ification for Governance Intelligence | Phase 8 |
| ADR-0393 | Cross-Domain Trend Fusion Registry | Phase 9 |
| ADR-0394 | Predictive Governance Prescriptive Engine | Phase 10 |

---

## 12. 结论

Phase 1-5 已完成基础设施层建设（Metrics Store + Adaptive Gate + Risk Profile + Summarizer + Debt Predictor）。后续迭代的核心思路是：

1. **Phase 6 (Anomaly Alerting)**: 从被动查询升级为主动告警， Immediate value
2. **Phase 7 (Dashboard)**: 可视化治理健康度，降低认知负担
3. **Phase 8 (BOS Service-ification)**: 让 Agent 原生发现和调用治理能力
4. **Phase 9 (Cross-Domain Fusion)**: 从单一治理域扩展到系统级健康视图
5. **Phase 10 (Predictive Governance)**: 从描述性分析升级到预测性和处方性治理

所有阶段均遵循**架构收敛原则**：不新增顶层入口、复用现有 SSOT 注册表、通过 BOS URI 暴露能力、保持 opt-in 向后兼容。

**推荐执行顺序**: Phase 6 → Phase 8 → Phase 7 → Phase 9 → Phase 10
**快速胜利组合**: Phase 6 + Phase 8 + Phase 7 (43h, ~1 周)
**完整交付**: Phase 6-10 全部 (~87h, ~2.5 周)
