# 未来方向 1-3 方案规划 (2026-08-08)

> 基于全面调研 (能力市场 P2 / T6 治理减法 / doc-governance 预算)。
> 覆盖: 能力市场 P2 采购 / T6-01 GaC 规则减法 / T6-02 ADR 分层 / doc-governance 预算。

## 一、能力市场 P2: 采购 (admit + 账单聚合)

### 1.1 现状 (调研确认)
- P0 定价 (resolve_pricing 混合三层) + P1 发现 API (bos_capability_list 返回 pricing) 已完成
- `bos_capability_admit(uri, description)`: 身份校验 (admin/local) + capability_catalog.add + admission_catalog.register(lifecycle="admitted")
- `ResourceAccountDB`: `get_top_callers(period)` / `get_report(period)` / `get_quota(caller)` — **缺按 caller×service 的月度账单明细查询**
- lifecycle 状态机: discovered→sandbox→admitted→active→...→retired (显式迁移表)

### 1.2 实现方案 (P2)
| 步骤 | 动作 | 价值 |
|------|------|------|
| P2-1 | **accounting.py 加 `get_calls(caller_id, service=None, period="month")`** 明细查询 | 采购账单 (谁买了什么花了多少) |
| P2-2 | **新 MCP 工具 `bos_billing_statement(caller_id, period)`**: 返回该 caller 的采购账单 (服务×成本聚合) | 客户端可查账单 |
| P2-3 | **admit 记录采购** (复用现有 CallRecord): admit 动作本身记一笔 (可选) | 采购可审计 |

### 1.3 不做的事 (防过度工程)
- 不加 subscribed/purchased 新状态 (lifecycle 已有 admitted)
- 不做订阅管理 (留着后续)
- 不强制付费门槛 (采购 = admit 语义, 记账反映成本)

## 二、T6-01: GaC 规则减法 (136 → ≤100)

### 2.1 现状 (调研确认)
- `gac.rules` 共 136 条 (SSOT), enforcement: required 24 / error 2 / advisory 105
- **4 条 superseded 可直接归档**: CR-P76-6-2 / CR-P76-6-5 / CR-P77-2-1 / CR-P77-2-2
- 工具: `bin/gac/gate-roi-report.py` (gate 价值报告 + 趋势 + 减法建议) 已存在 (ADR-0389)
- 规则文件无 use_metrics (需从 gate-roi 或 CI 历史取违规数据)

### 2.2 实现方案
| 步骤 | 动作 | 目标 |
|------|------|------|
| T6-01-1 | **归档 4 条 superseded 规则** (lifecycle → archived) | 136→132 |
| T6-01-2 | **跑 gate-roi-report.py** 产出 26 条 required/error 的违规历史 | 减法决策输入 |
| T6-01-3 | 无违规历史 + 无 executor 的规则降级 advisory | 132→≤100 |
| T6-01-4 | 验证 gac-local-gate 仍全绿 | 不破坏门禁 |

## 三、T6-02: ADR 分层 (361 → active/historical 两分)

### 3.1 现状 (调研确认)
- 361 个 ADR 文件, 状态: accepted 252 / active 80 / archived 8 / proposed 9 / superseded 2
- 无 active/historical 分层机制, 0001-0008 已有 archived-since 先例
- T6-02 设计 = **只分层不裁剪** (active 进 RAG/onboarding, historical 不进, 文件不删)
- 9 条 proposed 待裁定: 0128/0129/0388/0391 (双号冲突) 优先

### 3.2 实现方案
| 步骤 | 动作 | 目标 |
|------|------|------|
| T6-02-1 | **建 active/historical 分层标记** (frontmatter 加 layer: active/historical 或目录分层) | 分两层 |
| T6-02-2 | **裁定 9 条 proposed** (0128/0129/0388/0391 → ACCEPTED/归档/SUPERSEDED) | 消除悬空 |
| T6-02-3 | **adr-coverage.py 加分层统计** (active 数 / historical 数) | 可观测 |
| T6-02-4 | 验证 RAG/onboarding 只消费 active | 不裁剪但降负载 |

## 四、doc-governance 预算 (legacy-omo-standards-frontmatter)

### 4.1 现状 (调研确认)
- 配置: warning_exceptions.entries 的 `legacy-omo-standards-frontmatter` max_findings: 2, expires 2026-10-31
- **main 上实际 0 违反** (external-connection-fabric.md 已补 lifecycle) — CI 报超限是旧分支 pre-existing
- 违反: `.omo/standards/external-connection-fabric.md` 缺 lifecycle 字段 (旧分支状态)

### 4.2 修复方案
| 步骤 | 动作 | 目标 |
|------|------|------|
| DG-1 | **补 external-connection-fabric.md frontmatter** (lifecycle: contract) | 消除违反 |
| DG-2 | 验证 doc-governance-check 0 errors | 预算不超 |
| DG-3 | (可选) 预算到期前 review: 若持续 0 违反可移除 exception | 治本 |

## 五、分步推进路线

| 轮次 | 动作 | 验证 |
|------|------|------|
| 1 | doc-governance 修复 (DG-1/2) + T6-01-1 (4 superseded 归档) | doc-governance 0 errors + gac 132 |
| 2 | 能力市场 P2-1/2 (get_calls + bos_billing_statement) | 账单查询 + 真实调用 |
| 3 | T6-01-2/3 (gate-roi 减法) + T6-02 (ADR 分层) | gac ≤100 + ADR 两分 |

## 六、风险与缓解

| 风险 | 缓解 |
|------|------|
| 规则减法误伤 (去掉仍有用的 required) | gate-roi 数据驱动, 无违规+无 executor 才降级 |
| ADR 分层影响 RAG | 只降 historical 不进 RAG, active 保留 |
| 账单 API 过大 | period 默认 month + caller_id 必填 |
| doc-governance 预算反复 | main 已 0 违反, 补 frontmatter 治本 |

## 七、结论

三方向调研完成, 方案明确:
- **能力市场 P2**: 加 get_calls + bos_billing_statement (采购账单)
- **T6-01**: 先归档 4 superseded + gate-roi 数据驱动减法
- **T6-02**: active/historical 分层 + proposed 裁定
- **doc-governance**: 补 frontmatter 治本 (main 已 0 违反)
- **T6-04 已 done** (并发完成), 方案仅标注
