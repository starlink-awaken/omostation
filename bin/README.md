---
type: ssot
lifecycle: index
owner: governance-team
last_updated: 2026-06-29
---

# bin/ — 治理工具入口层

> 治理脚本入口. 本文件是**域归类导航 + 命名规范** (非脚本仓库).
> 脚本数见 `docs/project-registry.yaml`.
>
> 设计原则: **入口稳定** (路径不变, 全 repo 引用固化) + **可发现** (按域找, 不 grep).

## 域归类 (14 域)

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
| `check-cross-refs.py` | 交叉引用一致性（默认 tracked；`--scope workspace` 审计 ignored/运行态文档） |
| `doc-governance-check.py` | ownership/lifecycle/freshness/discoverability 统一检查（默认 tracked；`--no-new-warnings` 阻断新增 warning；`--scope workspace` 宽审计；支持区分 `review-state: metadata-only` 与内容复审） |
| `doc-governance-migrate.py` | 文档元数据迁移与 `metadata-only` → `content-reviewed` 批次升级 |
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

### 5b. 模型驱动治理闭环 (10) — L0↔MOF 模型驱动 (2026-08-09)
| 脚本 | 功能 |
|:-----|:-----|
| `consumer_index.py` | L0 约束 → 16 抽象族/规则反向索引（谁引用此约束） |
| `m0_feedback.py` | M0 运行时快照 → 派生面漂移检测（反向闭环） |
| `semantic_diff.py` | 约束变更语义 diff（added/removed/changed） |
| `model_graph_query.py` | 模型图查询：约束→族/规则 / 族→约束 / 规则→约束 |
| `corrosion_learner.py` | 漂移 → 高/中/低优先级 ontology 修正建议 |
| `onto_ekg_bootstrap.py` | OntoEKG 自举：文档/规则 → 候选概念（LLM 增强可注入） |
| `onto_reconcile.py` | 候选概念 vs ontology 缺口对比 + generalize 建议 |
| `export_mof_framework.py` | MOF 四层 + L0 约束 → 可复用框架包（Wave 3 平台化） |
| `owl_adapter.py` | L0 约束 → OWL-DL（HermiT/Pellet 标准化推理铺路） |
| `governance_closed_loop.py` | 串联 5 阶段闭环端到端验证（真实数据） |

### 6. 治理仪表盘 / 趋势 / 告警 (17) — 可视化 + history + alert + trend fusion + prediction
| 脚本 | 功能 |
|:-----|:-----|
| `swarm-activity-dashboard.py` | 多 agent 实时活动面板 (active runs/locks/worktree/claims/子模块 dirty/冲突) |
| `governance-dashboard.py` | P86 R4 dashboard wrapper |
| `cross-domain-trend.py` | Phase 9 跨域趋势融合 (governance/code_quality/test_health/knowledge) |
| `predictive-governance.py` | Phase 10 预测性治理 + 处方建议 (linear prediction + threshold simulation) |
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

### 11. 入口 / framework (6) — 高频, 留 bin/ 根
| 脚本 | 功能 | 调用方 |
|:-----|:-----|:-------|
| `agent-workflow.py` (1319L) | Agent Workflow Runner (framework 级) | CLAUDE/AGENTS §0 |
| `omo-status` | Multi-Agent Swarm 全景秒级 Rich Panel 诊断快照 | 开发者/CI/开工自检 |
| `omo-top` | Multi-Agent Swarm 4 象限实时互动大盘 (Textual 1.x) | 开发者/常驻监控 |
| `compass_radar.py` | health radar 计算/兼容刷新 | `omo state sync` broker |
| `state-stale-emit.py` | 发送 state_stale 事件 | post-commit / launchd WatchPaths |
| `change-lane-check.py` | commit lane 校验 (pre-commit/gac-local-gate) | GaC gate |
| `doc-ssot-lint.py` | 文档 SSOT 门禁 (CI) | gac-local-gate/CI |

### 12. 杂项单例 (13) — 待归域或留根
`cockpit-readiness.py` / `verify-spaces.py` / `venv-yaml-check.py` /
`ts-file-analyze.py` / `register-mcp.py` / `graphify-local-extract.py` / `fix-debts.py` /
`classify_planned.py` / `p0-event-listener.py` / `management-{categorize,cross-ref-check,migrate}.py`

> **已迁移** (2026-07-07): `omo-health.py` → `omo health dashboard`, `omo-manage` → `omo manage`, `omo-validate` → `omo validate`
> **已迁移** (2026-07-07): `scripts/omo/cards_x3_metrics.py` → `omo audit cards`, `scripts/omo/vault_x1_audit.py` → `omo audit vault`, `scripts/omo/x2_freshness_audit.py` → `omo audit freshness`

### 13. P74 Solidification (3, ADR-0130) — workflow 沉默治理
常态化机制: 检测 + 拦截 + 治理信号. 治 P71 三类声明/执行鸿沟复发.

| 脚本 | 功能 | 对应 GaC 规则 |
|:-----|:-----|:--------------|
| `omo-state-projection-guard.py` | runtime projection 路径一致性 (P71 类 A) | CR-P74-STATE-PROJECTION-GUARD (X4) |
| `omo-runtime-stamp-policy.py` | runtime 孤儿文件治理 (P71 类 B) | CR-P74-RUNTIME-STAMP-POLICY (X1) |
| `agent-workflow.py suggest` (sub) | advisory 路由建议 (P74 §3) | CR-P74-WORKFLOW-SUGGEST (X3) |
| `agent-workflow.py compliance` `p74_solidification` (sub) | workflow 沉默检测 (P71 类 C) | CR-P74-WORKFLOW-SILENCE (X1) |

> **已迁移** (2026-07-07): `omo-state-projection-guard.py` → `omo lint projection-guard`, `omo-runtime-stamp-policy.py` → `omo lint stamp-policy`
> 原脚本保留作为 backward-compat wrapper, 新功能请使用 omo CLI.

### 14. Bin Tool Registry (2, 工具盘点 + 依赖闭环) — 盘点 + 依赖闭环

> **已迁移** (2026-08-21): `scripts/bin/` 工具已迁移到 `bin/`，scripts 仓库已 archive。
> 并行收敛治理不再需要（scripts/bin 已不存在）。

| 入口 | 功能 |
|:-----|:-----|
| `make bin-tool-registry-audit` | 扫描 bin 工具调用图与命名债务 (缺省输出 stats) |
| `make bin-tool-registry-audit-strict` | 严格门禁 (脚本层) |
| `make bin-tool-registry-convergence` | 盘点收敛候选 (高出入度聚类) |
| `make bin-tool-registry-dependency-risks` | 输出依赖风险热点 |
| `make bin-tool-registry-weekly-governance-report` | 输出并落盘依赖风险周报 (owner/action/sink) |
| `python3 bin/ssot/root-directory-governance-scan.py --check` | 校验根目录 tracked/ignored/policy disposition，阻断未登记 shadow surface |

裸命令:
```bash
python3 bin/tool-registry-audit.py --scope both --parallel-manifest docs/operations/bin-scripts-convergence-manifest.json --snapshot artifacts/bin-tool-registry-audit.json
python3 bin/tool-registry-audit.py --scope both --parallel-manifest ... --json | jq '.findings.parallel_manifest_gaps'
```

SSOT: `docs/operations/bin-scripts-convergence-manifest.json` (entries: name/bin/scripts/status/action/owner/note/evidence).

根目录治理策略 SSOT: `docs/operations/root-directory-governance-policy.yaml`。
根目录分类契约: `docs/operations/root-directory-governance-contract.md`。扫描器会识别有效 linked worktree 为 `active-worktree`，本机客户端目录必须通过策略 `local_surfaces` 显式登记；未知 ignored/untracked 目录仍然阻断。
两项审计已接入 `gac-local-gate` 与 `ci-surfaces.yaml`，不再依赖人工记忆或单次报告。

### 15. Capability Federation（只读联合审计）

| 入口 | 功能 |
|:-----|:-----|
| `make capability-federation-audit` | 读取原生 registry 与能力投影，审计 provider/worker/workflow 的悬挂引用、重复权威、部分 clone 与准入矛盾 |
| `python3 bin/capability-sync.py federation-audit --json` | 通过既有 capability 入口输出确定性、脱敏的 `capability-federation-audit/v1` 报告 |

审计实现是 `lib/capability_federation_audit.py` 共享库，不新增活动脚本入口。
该工具不生成新的能力注册表，不执行 registry 中的 command/argv/entrypoint，
也不把 discovery、`exists` 或 runtime online 推断为 admission/completion。
架构合同见 [`../docs/architecture/capability-federation-contract-v1.md`](../docs/architecture/capability-federation-contract-v1.md)。

> **并行 gap 语义** (2026-08-16 固化): `missing_manifest_entry` = bin/scripts 同名镜像未登记; 内部模块 (`__init__.py` / `_lib.py` / `_*.py`) 由 `_is_internal_module()` 排除, 非命令不计 gap. 5 个多文件条目 (control_experiment / git_health_hook / physical_recovery / submodule_reachability_gate / sync_submodules_push) 是 root-wrapper→ssot 合法模式, 登记 bin 取 ssot 主路径.
> **并发风险** (2026-08-16): 该域是多 agent 高频并行域, 并发 agent 会把共享 checkout 上 staged 改动直接 commit 成混合 commit (见 memory `feedback_shared_checkout_concurrent_absorb_20260816.md`); 动工前查 `git worktree list` + `agent-workflow status`.

---

## 命名规范 (新脚本强制)

1. **case**: `kebab-case` (禁 snake_case; 存量 `compass_radar`/`check_health_ssot`/`classify_planned`/`p0_event_listener` 渐进改)
2. **前缀**: 域前缀 + `-` (如 `gac-` / `adr-` / `ssot-` / `god-module-`); 单例无域前缀留根
3. **动词**: 检测类 `-check` / `-lint`, 修复类 `-fix` / `-apply`, 生成类 `-gen` / `-export`, 报告类 `-report` / `-insight`
4. **域归并规则** (理清历史碎片):
   - 治理趋势/dashboard: 统一 `governance-` (淘汰 `gov-`, `gov-*` 渐进改名)
   - God Module: 统一 `god-module-` (`check-god-module` → `god-module-check`)
   - 健康/卫生区分: `gac-healthcheck` (体系) vs `gac-hygiene-check` (工作区), 不混


## 治理自进化工具集 (2026-08-22)

| 工具 | 职责 | 用法 |
|------|------|------|
| `gac/meta-doctor.py` | 治理机制活性巡检 (M1 心跳 SLA + M2 引用活性 + scheduler-drift) | `python3 bin/gac/meta-doctor.py --workspace . --json` |
| `scheduler-compile.py` | 调度编译器: 登记↔安装一致性校验 (ADR-A) | `python3 bin/scheduler-compile.py --check` |
| `session-handoff.py` | 会话交接协议: 机器可读 handoff.json (R6) | `python3 bin/gac/session-handoff.py --session <id> --agent <name> --summary "..."` |
| `heartbeat-wrapper.sh` | cron job 心跳包装器: 运行后写 heartbeats/<job>.json (ADR-D) | `bash bin/gac/heartbeat-wrapper.sh <job_name> <command...>` |

> SSOT 契约: [`.omo/_truth/vocabulary.yaml`](../.omo/_truth/vocabulary.yaml) (lifecycle 终结态/活跃态枚举)


---

## 域边界说明

本 README 的域归类是**子目录化的低成本试验**（6–12 个月验证归类是否自然）。**已知边界模糊**：`governance-` / `gov-` / `dashboard-` 三前缀同域（归并规则已定，待渐进）；杂项 13 单例留根观察。

---

## 关联

- 契约: [`../.omo/standards/doc-ssot-contract.md`](../.omo/standards/doc-ssot-contract.md) (SSOT 正交)
- 模式: [`../.omo/standards/doc-presentation-pattern.md`](../.omo/standards/doc-presentation-pattern.md) (digest+pointer+lint)
- 架构推演: 本 README = 阶段 1 (KISS 导航 + 域边界试验), 阶段 2 触发指标驱动
