---
status: active
lifecycle: index
owner: governance-team
last-reviewed: 2026-06-29
---

# bin/ — 治理工具入口层

> 治理脚本入口. 本文件是**域归类导航 + 命名规范** (非脚本仓库).
> 脚本数见 `docs/project-registry.yaml`.
>
> 设计原则: **入口稳定** (路径不变, 全 repo 引用固化) + **可发现** (按域找, 不 grep).

## 域归类 (12 域)

### 1. GaC 治理即代码 (15) — 规则注册 / drift / gate / healthcheck
规则声明式注册 + 执行器绑定 + drift 检测 + 元治理自检.

| 脚本 | 功能 |
|:-----|:-----|
| `gac-validate.py` | 规则结构校验 |
| `gac-drift.py` | 声明 vs 实际 drift 检测 |
| `gac-local-gate.py` | 本地 gate (CI 入口, 含多检查) |
| `gac-healthcheck.py` | **体系健康** (元治理递归自检, doc_ssot 块) |
| `gac-hygiene-check.py` | **工作区卫生** (CR-HYG 零字节/大小写, ≠ healthcheck) |
| `gac-executor.py` | executor 注册 drift (CR-X2-GAC-EXEC-DRIFT) |
| `gac-bootstrap.py` | GaC 自举 (4 层检测) |
| `gac-export-agents.py` | 生成 agent-gac-rules digest + AGENTS pointer |
| `gac-m1-sync.py` | GaC 规则 ↔ M1 实例同步 |
| `gac-mof-validate.py` | MOF 视角 GaC 校验 |
| `gac-gc.py` | 规则垃圾回收 |
| `gac-daemon.py` | 后台 drift 监控 |
| `gac-dashboard.py` | GaC 仪表盘数据 |
| `gac-hook-pre-edit.py` | 编辑前 hook |
| `gac-ingest-legacy.py` | legacy 规则摄入 |

### 2. ADR 治理 (8) — drift 流水线 + typo + coverage
`check → classify → apply/auto-fix` 流水线 + trend + typo.

| 脚本 | 功能 |
|:-----|:-----|
| `adr-coverage.py` | ADR 编号连续性 + INDEX 一致 |
| `adr-drift-check.py` | P89 R2 drift 检测 (流水线第 1 步) |
| `adr-drift-classify.py` | P90 R1 drift 归类 (第 2 步) |
| `adr-drift-auto-fix.py` | P93 R1 自动修复建议 (第 3 步, Levenshtein) |
| `adr-drift-apply.py` | P94 R1 touch SUBDIR_MISSING (应用) |
| `adr-trend-insight.py` | drift 趋势洞察 |
| `adr-typo-fix.py` | ⚠️ P95 占位 (27 行, YAGNI 待评) |
| `adr-typo-real-fix.py` | ⚠️ P96 占位 (27 行, YAGNI 待评) |

### 3. SSOT 守护 (6) — 文档/边界/交叉引用一致性
| 脚本 | 功能 |
|:-----|:-----|
| `doc-link-check.py` | 文档链接有效性 |
| `ssot-guardian.py` | task_count + workspace_hygiene 守护 |
| `ssot-writeback.py` | SSOT 回写 |
| `check-boundary.py` | 项目边界校验 |
| `check-cross-refs.py` | 交叉引用一致性 |
| `check_health_ssot.py` | health SSOT 一致 (snake_case, 待渐进改) |

### 4. God Module (3) — F7114ABA 拆分支持
| 脚本 | 功能 |
|:-----|:-----|
| `check-god-module.py` | 检测 (>800L warn, >1500L error) |
| `god-module-13-error-list.py` | error 清单 + 拆解建议 |
| `god-module-roadmap.py` | 拆分路线图 |

> ⚠️ 前缀不一 (`check-god-module` vs `god-module-*`), 待渐进统一.

### 5. 证据与反馈 (2) — BOS 鸿沟 + 回路存活
| 脚本 | 功能 |
|:-----|:-----|
| `evidence-smoke.py` | BOS 声明/执行鸿沟量化 + 反馈回路维度 (综合 smoke) |
| `feedback-loop-guard.py` | 自反馈回路存活监控 + escalation (专精, cron 友好) |

### 6. 治理仪表盘 / 趋势 / 告警 (15) — 可视化 + history + alert
| 脚本 | 功能 |
|:-----|:-----|
| `governance-dashboard.py` | P86 R4 dashboard wrapper |
| `governance-readiness.py` | P60 治理就绪度 (5 维度) |
| `governance-readiness-trend.py` | 就绪度趋势 |
| `governance-history-insight.py` | history 洞察 |
| `governance-history-stats.py` | P91 R1 history 趋势深化 (ADR-0115 Phase 2 rename) |
| `governance-trend-report.py` | 趋势报告 (ADR-0115 Phase 2 rename) |
| `dashboard-readiness-summary.py` | 就绪度摘要 |
| `dashboard-ui-render.py` | UI 渲染 |
| `alert-aggregator.py` | 告警聚合 |
| `alert-history.py` | 告警历史 |
| `alert-mock-p0-notify.py` | P0 告警 mock |
| `drift-history-insight.py` | drift history 洞察 |
| `rule-history-insight.py` | 规则 history 洞察 |
| `status-distribution.py` / `dim-weight.py` | 状态分布 / 维度权重 |

> ⚠️ 前缀不一 (`governance-` vs `gov-` vs `dashboard-`), 同域历史碎片, 待渐进归并.

### 7. X2 抗熵 (3) — freshness 规则
`x2-freshness-check.py` / `x2-rule-add.py` / `x2-rule-lint.py`

### 8. MOF (1) — 模型覆盖
`mof-m2-coverage.py` (M2 覆盖率; GaC 视角见 `gac-mof-validate.py`)

### 9. Submodule 治理 (3)
`submodule-reachability-gate.py` / `cross-submodule-check.py` / `cross-submodule-events.py`

### 10. Project / Registry 生成 (2)
`gen-project-registry.py` (registry 派生) / `project-layer-index.py` (layer digest)

### 11. 入口 / framework (4) — 高频, 留 bin/ 根
| 脚本 | 功能 | 调用方 |
|:-----|:-----|:-------|
| `agent-workflow.py` (1319L) | Agent Workflow Runner (framework 级) | CLAUDE/AGENTS §0 |
| `compass_radar.py` | health radar 刷新 | cockpit/sync |
| `change-lane-check.py` | commit lane 校验 (pre-commit/gac-local-gate) | GaC gate |
| `doc-ssot-lint.py` | 文档 SSOT 门禁 (CI) | gac-local-gate/CI |

### 12. 杂项单例 (13) — 待归域或留根
`omo-health.py` / `cockpit-readiness.py` / `verify-spaces.py` / `venv-yaml-check.py` /
`ts-file-analyze.py` / `register-mcp.py` / `graphify-local-extract.py` / `fix-debts.py` /
`classify_planned.py` / `p0-event-listener.py` / `management-{categorize,cross-ref-check,migrate}.py`

---

## 命名规范 (新脚本强制)

1. **case**: `kebab-case` (禁 snake_case; 存量 `compass_radar`/`check_health_ssot`/`classify_planned`/`p0_event_listener` 渐进改)
2. **前缀**: 域前缀 + `-` (如 `gac-` / `adr-` / `ssot-` / `god-module-`); 单例无域前缀留根
3. **动词**: 检测类 `-check` / `-lint`, 修复类 `-fix` / `-apply`, 生成类 `-gen` / `-export`, 报告类 `-report` / `-insight`
4. **域归并规则** (理清历史碎片):
   - 治理趋势/dashboard: 统一 `governance-` (淘汰 `gov-`, `gov-*` 渐进改名)
   - God Module: 统一 `god-module-` (`check-god-module` → `god-module-check`)
   - 健康/卫生区分: `gac-healthcheck` (体系) vs `gac-hygiene-check` (工作区), 不混

---

## 域边界说明 (README = 子目录化试验)

本 README 的域归类是**子目录化的低成本试验** — 用 6-12 个月验证归类是否自然:
- 若顺畅 → 未来子目录化照搬 (bin/{gac,adr,ssot,...}/)
- 若不顺畅 → 调整域边界 (改 README 比改目录便宜 100×)

**已知边界模糊** (待观察):
- `governance-` / `gov-` / `dashboard-` 三前缀同域 (治理可视化) — 归并规则已定, 待渐进
- `evidence-smoke` 含反馈回路维度 vs `feedback-loop-guard` 专反馈 — 相关但职责不同 (综合 smoke vs 专精 guard)
- 杂项 18 单例无域 — 观察是否涌现新域

---

## 触发子目录化的指标 (数据驱动, 非预测)

| 指标 | 阈值 | 当前 | 动作 |
|:-----|:-----|:-----|:-----|
| 脚本总数 | > 100 | 75 | 评估子目录化 |
| 本 README 域表行 | > 200 | ~90 | 拆 README → 子目录 INDEX |
| 单域脚本数 | > 12 | gac=15 ✅ | 该域先迁子目录 |
| "找不着"抱怨 | > 2/月 | 0 | 导航失效, 必须分类 |

**当前**: gac 域 (15) 已过单域阈值, 但总数 75 < 100, README 刚建立 (导航未验证). **阶段 1 (本 README) 先理域边界, 阶段 2 (触发后) 再子目录化**.

---

## 关联

- 契约: [`../.omo/standards/doc-ssot-contract.md`](../.omo/standards/doc-ssot-contract.md) (SSOT 正交)
- 模式: [`../.omo/standards/doc-presentation-pattern.md`](../.omo/standards/doc-presentation-pattern.md) (digest+pointer+lint)
- 架构推演: 本 README = 阶段 1 (KISS 导航 + 域边界试验), 阶段 2 触发指标驱动
