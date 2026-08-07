# 智能化动态化治理 — 全面架构剖析

> 本文档是对现有治理架构的深度剖析，评估智能化/动态化建议的可行性、融合点和迭代路线图。

---

## 1. 现有治理架构概览

### 1.1 核心组件

```
┌─────────────────────────────────────────────────────────────┐
│                    Governance Execution Layer               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ gac-local-  │  │ governance- │  │ CI workflows        │  │
│  │ gate.py     │  │ check.yml   │  │ (governance-check,  │  │
│  │ (~50 gates) │  │ (3 jobs)    │  │  doc-freshness, etc)│  │
│  └──────┬──────┘  └──────┬──────┘  └─────────────────────┘  │
│         │                │                                  │
│         ▼                ▼                                  │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              SGF Policy Engine                        │   │
│  │  - Loads sgf-policy.yaml (dynamic)                    │   │
│  │  - Falls back to DEFAULT_POLICY (hardcoded)            │   │
│  │  - ci_only / ci_skip / agent_workflow_only flags       │   │
│  │  - SOFT_CHECKS (non-blocking)                         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    State & Evidence Plane                   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ system.yaml │  │ health.yaml │  │ runtime-projections │  │
│  │ (phase,     │  │ (health     │  │ .yaml (canonical    │  │
│  │  health)    │  │  score)     │  │  paths)             │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ debt.yaml   │  │ governance- │  │ agent-workflows/    │  │
│  │ (registry)  │  │ checks.yaml │  │ (workflow defs)     │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    BOS / Agora Layer                        │
│  bos://governance/* → OMO broker → state mutations          │
│  bos://memory/mos/* → Memory OS control plane               │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 关键数据流

1. **Gate Execution Flow**:
   ```
   pre-commit / CI
     → gac-local-gate.py
       → load SGF policy (or DEFAULT_POLICY)
       → filter gates by ci_only / ci_skip / agent_workflow_only
       → run each gate (subprocess, timeout=15s default)
       → extract finding_topics (A6)
       → return {ok, hard_fails, soft_warns, checks, finding_topics}
   ```

2. **State Sync Flow**:
   ```
   omo state sync
     → reads .omo/state/system.yaml
     → writes projections to .omo/state/runtime/*
     → updates .omo/_control/governance-data.json
   ```

3. **Debt Flow**:
   ```
   debt-auto-seed-tool
     → scans governance gaps
     → creates .omo/debt/items/*.yaml
     → updates .omo/_truth/registry/debt.yaml
   ```

### 1.3 现有智能化迹象

| 特征 | 位置 | 说明 |
|:---|:---|:---|
| POLICY 动态加载 | `gac-local-gate.py:17-25` | `sgf-policy.yaml` 可覆盖 DEFAULT_POLICY |
| SOFT_CHECKS | `gac-local-gate.py:188-191` | 非阻断门禁，降噪用 |
| finding_topics | `gac-local-gate.py:328-437` | A6 检查自动分类为 topic |
| ci_only / ci_skip | `gac-local-gate.py:182-186` | 按环境过滤检查 |
| health_score 复合 | `health.yaml:33-42` | governance/freshness/runtime 加权 |
| debt_metrics | `system.yaml:172-179` | 7 维熵指标 |

---

## 2. 智能化建议可行性评估

### 2.1 自适应阈值引擎 ✅ 高可行性

**现状**：阈值硬编码在检查脚本中（如 `check-submodule-rewind.py --warn-threshold 3`）。

**可行性**：高。已有 `runtime-projections.yaml` 和 `health.yaml` 作为状态平面，只需新增：
- `.omo/state/metrics-store.jsonl`：每次 gate 运行追加 metrics
- `MetricsStore` 类：读写 JSONL，计算滑动窗口统计
- `--adaptive` 模式：`gac-local-gate.py` 读取历史数据，动态调整阈值

**融合点**：
- `gac-local-gate.py:344-373` 的 `run_check()` 已返回 `{name, ok, returncode, stdout, stderr}`
- 只需在 `run_gate()` 后追加 metrics 写入
- `finding_topics` 机制可复用为 anomaly 分类

### 2.2 时间序列异常检测 ✅ 高可行性

**现状**：`health.yaml` 有 `governance_anomaly_score`、`anomaly_count`，但只记录当前快照。

**可行性**：高。只需：
- 在 `metrics-store.jsonl` 中记录时间序列
- 用简单统计（EWMA / z-score）检测跳变
- 输出 `[ANOMALY]` 格式，复用 `finding_topics` 机制

**融合点**：
- `health.yaml` 已有 `anomalies` 列表（第 44-47 行）
- `extract_finding_topics()` 已支持 severity=warn 的软信号
- 异常检测结果可直接写入 `finding_topics`

### 2.3 LLM 驱动的治理摘要 ⚠️ 中可行性

**现状**：CI 输出是原始 JSON/text，`print_human()` 只做 slim/full 切换。

**可行性**：中。需要：
- 新增 `GovernanceSummarizer` 类，调用 LLM API
- 输入：`run_gate()` 返回的完整 report + `health.yaml` + `debt.yaml`
- 输出：Markdown 摘要，按 severity 排序
- 触发：PR comment bot / nightly 治理报告

**约束**：
- 只读分析，不自动修改文件
- LLM 调用有延迟，必须异步或仅在 CI 严格模式运行
- 需要新增 `--summarize` flag，不破坏现有 CLI 契约

**融合点**：
- `run_gate()` 返回的 `report` dict 已是结构化数据
- `finding_topics` 可直接作为 LLM 输入摘要
- `governance-check.yml` 已有 `governance-verify` job，可在此加 summarization step

### 2.4 风险感知的动态 Gate ✅ 高可行性

**现状**：`gac-local-gate.py` 已有 `ci_only` / `ci_skip` / `agent_workflow_only` 分类。

**可行性**：高。只需新增：
- `risk_profile` 参数：`low` / `medium` / `high`
- 风险推断逻辑：基于 staged files 路径判断
  - `docs/**` → low
  - `bin/gac/**` → medium
  - `projects/*` / `.omo/**` → high
- 动态调整：`--risk-profile high` 时，降低 `warn-threshold`，启用 `ci_only` 检查

**融合点**：
- `gac-local-gate.py:216-245` 的 `gate_checks()` 已有 scope 过滤
- 新增 risk_profile 过滤只需在 `gate_checks()` 入口加一层
- `governance-check.yml` 的 paths 过滤已部分实现（但只针对 workflow trigger）

### 2.5 预测性债务预警 ⚠️ 中可行性

**现状**：`debt-auto-seed-tool` 只扫当前快照，`debt.yaml` 是静态注册表。

**可行性**：中。需要：
- 在 `metrics-store.jsonl` 中记录 `debt_items_open` 时间序列
- 线性/指数拟合预测突破阈值时间
- 输出 `[PREDICTION]` 格式

**融合点**：
- `system.yaml:172-179` 已有 `debt_metrics`
- `debt.yaml` 已有 `seed_items` 列表
- 预测结果可写入 `health.yaml` 的 `anomalies` 列表

---

## 3. 架构融合设计

### 3.1 新增：Metrics Store（指标持久层）

**位置**：`.omo/state/metrics-store.jsonl`

**格式**：
```jsonl
{"timestamp":"2026-08-07T14:00:00Z","check":"check-submodule-rewind","ok":true,"duration_ms":120,"reason":"default-branch:main"}
{"timestamp":"2026-08-07T14:05:00Z","check":"check-submodule-rewind","ok":true,"duration_ms":95,"reason":"any-ref:refs/heads/feature-x"}
```

**实现**：
- 新增 `bin/gac/metrics-store.py`：追加/查询/统计
- `gac-local-gate.py:448` 的 `run_check()` 后自动写入
- 不破坏现有 CLI 契约（默认关闭，`--metrics` 启用）

### 3.2 新增：Adaptive Gate Engine（自适应门禁）

**位置**：`bin/gac/adaptive-gate.py`

**功能**：
- 读取 `metrics-store.jsonl` 滑动窗口（默认最近 50 次）
- 计算 baseline：均值 + 2σ
- 动态调整阈值：`warn-threshold = max(3, baseline + 2σ)`
- 异常检测：EWMA 跳变检测

**CLI**：
```bash
python3 bin/gac/adaptive-gate.py --check check-submodule-rewind --window 50
python3 bin/gac/adaptive-gate.py --summary  # 输出所有检查的当前阈值
```

**融合点**：
- 调用 `MetricsStore` 查询历史数据
- 输出 `--warn-threshold` 值，供 `gac-local-gate.py` 使用
- 异常结果写入 `finding_topics`

### 3.3 新增：Risk Profile Router（风险感知路由）

**位置**：`bin/gac/risk-profile.py`

**功能**：
- 分析 staged files 路径
- 推断风险等级：`low` / `medium` / `high`
- 输出适配的 gate 配置

**CLI**：
```bash
python3 bin/gac/risk-profile.py --staged  # 输出 inferred risk profile
python3 bin/gac/gac-local-gate.py --risk-profile high  # 高风险模式
```

**融合点**：
- `gac-local-gate.py:216-245` 的 `gate_checks()` 已有 scope 过滤
- 新增 `--risk-profile` 参数，在过滤逻辑中叠加风险适配

### 3.4 新增：Governance Summarizer（治理摘要）

**位置**：`bin/gac/governance-summarizer.py`

**功能**：
- 读取 `run_gate()` 完整 report
- 调用 LLM API（如 `bos://analysis/governance/summarize`）
- 输出 Markdown 摘要

**触发**：
- `gac-local-gate.py --summarize`（本地）
- `governance-check.yml` 的 `governance-verify` job（CI）

**融合点**：
- `run_gate()` 返回的 report dict 已是结构化数据
- `finding_topics` 可直接作为 LLM 输入
- 输出写入 GitHub PR comment 或 artifact

---

## 4. 数据流融合图

```
                    ┌───────────────────┐
                    │   pre-commit / CI │
                    └────────┬──────────┘
                             │
                             ▼
                    ┌───────────────────┐
                    │  gac-local-gate.py │
                    │  (existing)       │
                    └────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
    ┌─────────────────┐ ┌──────────┐ ┌─────────────┐
    │ Adaptive Gate   │ │ Risk     │ │ Governance  │
    │ Engine (new)    │ │ Profile  │ │ Summarizer  │
    │                 │ │ Router   │ │ (new)       │
    │ - reads metrics │ │ (new)    │ │ - LLM call  │
    │ - adjusts       │ │ - infers │ │ - Markdown  │
    │   thresholds    │ │   risk   │ │   summary   │
    │ - anomaly detect│ │ - filters│ │ - PR comment│
    └────────┬────────┘ └────┬─────┘ └──────┬──────┘
             │                │               │
             ▼                ▼               ▼
    ┌─────────────────────────────────────────────────┐
    │              Metrics Store (new)                │
    │          .omo/state/metrics-store.jsonl         │
    │  - append-only time series                     │
    │  - sliding window queries                      │
    │  - baseline statistics                         │
    └─────────────────────────────────────────────────┘
                             │
                             ▼
                    ┌───────────────────┐
                    │ runtime-projections│
                    │ .yaml (existing)  │
                    └───────────────────┘
                             │
                             ▼
                    ┌───────────────────┐
                    │   health.yaml     │
                    │   (existing)      │
                    └───────────────────┘
```

---

## 5. 迭代路线图

### Phase 1：Metrics Store（1-2 天）

**目标**：建立治理指标持久层。

**交付**：
- `bin/gac/metrics-store.py`：JSONL 读写 + 滑动窗口查询
- `gac-local-gate.py` 集成：`--metrics` flag 启用写入
- `metrics-store.jsonl` 初始化

**验证**：
- `python3 bin/gac/gac-local-gate.py --metrics` 运行后，`metrics-store.jsonl` 有 N 条记录

### Phase 2：Adaptive Gate Engine（2-3 天）

**目标**：基于历史数据动态调整阈值。

**交付**：
- `bin/gac/adaptive-gate.py`：滑动窗口统计 + EWMA 异常检测
- `gac-local-gate.py` 集成：`--adaptive` flag 使用动态阈值
- `finding_topics` 扩展：支持 `[ANOMALY]` 类型

**验证**：
- `python3 bin/gac/adaptive-gate.py --check check-submodule-rewind --window 50` 输出当前建议阈值

### Phase 3：Risk Profile Router（1-2 天）

**目标**：根据 PR 变更范围动态调整检查强度。

**交付**：
- `bin/gac/risk-profile.py`：路径风险推断
- `gac-local-gate.py` 集成：`--risk-profile low|medium|high`
- `governance-check.yml` 集成：根据 `paths` 自动推断风险

**验证**：
- 修改 `docs/**` → 只跑 doc-governance check
- 修改 `projects/*` → 全量 gate

### Phase 4：Governance Summarizer（3-5 天）

**目标**：LLM 驱动的治理 triage 摘要。

**交付**：
- `bin/gac/governance-summarizer.py`：LLM 调用 + Markdown 生成
- `gac-local-gate.py` 集成：`--summarize` flag
- `governance-check.yml` 集成：PR comment / artifact

**验证**：
- `python3 bin/gac/gac-local-gate.py --summarize` 输出可读 Markdown

### Phase 5：预测性债务预警（2-3 天）

**目标**：基于趋势预测债务突破阈值。

**交付**：
- `bin/gac/debt-predictor.py`：时间序列拟合 + 预测
- `health.yaml` 集成：`predictions` 字段
- `finding_topics` 扩展：支持 `[PREDICTION]` 类型

**验证**：
- `python3 bin/gac/debt-predictor.py` 输出预测报告

---

## 6. 与现有架构的融合点总结

| 现有组件 | 融合点 | 新增内容 |
|:---|:---|:---|
| `gac-local-gate.py` | POLICY 驱动、gate_checks() 过滤、finding_topics | `--adaptive`、`--risk-profile`、`--summarize` |
| `runtime-projections.yaml` | 已注册 health、system_health、governance_data | 新增 metrics_store projection |
| `health.yaml` | 已有 anomaly_score、anomalies 列表 | 新增 predictions 字段 |
| `governance-checks.yaml` | X1-X4 检查注册表 | 新增 adaptive_threshold 字段 |
| `debt.yaml` | 已有 seed_items、dashboard_ref | 新增 trend_series 引用 |
| `governance-check.yml` | 已有 3 个 job | 新增 rewind-report、summarization |
| `sgf-policy.yaml` | 已有动态 POLICY 加载 | 新增 adaptive_rules 节 |

---

## 7. 设计原则与约束

### 7.1 必须遵守的约束

1. **不增加实时阻塞**：动态 gate 可以调阈值，不能取消已注册的 enforcement
2. **只读分析优先**：LLM 摘要只读，不自动修改文件
3. **本地优先**：metrics_store 用本地 JSONL，不依赖外部数据库
4. **向后兼容**：新增 flag 全为 optional，不破坏现有 CLI 契约
5. **SSOT 指针不复制**：所有数据平面引用通过 `runtime-projections.yaml`，不硬编码路径

### 7.2 不建议做的

- **不要全自动修复**：治理 triage 可以 LLM 辅助，但修复决策必须留给人 / agent-workflow
- **不要增加外部依赖**：metrics_store 用本地 JSONL，不依赖额外数据库
- **不要替换现有检查**：自适应阈值是补充，不是替换 `DEFAULT_POLICY`
- **不要实时 LLM 调用**：LLM 摘要只在 CI / nightly 运行，不阻塞 pre-commit

---

## 8. 未来迭代方向

### 8.1 短期（1-2 个月）

- [ ] Phase 1-3 落地（Metrics Store + Adaptive Gate + Risk Profile）
- [ ] 在 `governance-check.yml` 中集成 adaptive gate
- [ ] 为 `check-submodule-rewind` 启用自适应阈值

### 8.2 中期（2-3 个月）

- [ ] Phase 4 落地（Governance Summarizer）
- [ ] PR comment bot 自动评论治理摘要
- [ ] Nightly 治理报告（Markdown → WPS 笔记 / email）

### 8.3 远期（3-6 个月）

- [ ] Phase 5 落地（预测性债务预警）
- [ ] 基于 `metrics-store.jsonl` 的治理仪表盘
- [ ] 与 `BasePredictor`（workspace/tools/base/）集成，实现跨域趋势预测

---

## 9. 结论

**可行性**：5 项建议全部可行，其中 3 项（自适应阈值、动态 Gate、Metrics Store）高可行性，2 项（LLM 摘要、预测性预警）中可行性。

**融合策略**：充分利用现有 `gac-local-gate.py` 的 POLICY 驱动架构、`finding_topics` 机制、`runtime-projections.yaml` 注册表，最小化侵入。

**落地建议**：从 Phase 1（Metrics Store）开始，每 phase 独立可验证，逐步叠加智能化能力。
