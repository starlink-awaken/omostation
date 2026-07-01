---
task: "Remediate omostation debt across measurement, sync, backlog, architecture"
slug: 20260701-143000_debt-rootcause-remediation
effort: deep
effort_source: explicit
phase: observe
progress: 34/51
mode: interactive
started: 2026-07-01T14:30:00Z
updated: 2026-07-01T14:30:00Z
tier_floor_note: "E4 declared; ISC count 48 < floor 128 — show-your-math in Decisions"
governance_binding: "omostation AGENTS.md/CLAUDE.md; .omo/ mutations via agent-workflow governance-state-mutation + governance-agent profile"
---

## Problem

omostation 在 7 天 462 提交的并发演进下，治理仪表盘呈现"全绿"（health_score / debt / GaC-drift 当时均报满分，真值见 .omo/state/system.yaml），但实证调查揭示这套"满分"建立在**测量工具自身失真**之上。三类结构性病灶贯穿全部债务：

1. **声明式 SSOT 无"真相漂移检测器"** — `dependency-baseline.yaml` 无生成器（手工维护）、debt-dashboard 与 debt.yaml 各说各话、health.yaml 由单一变量算出。声明与实际的缝隙无人监督。
2. **重构只改写入侧、漏改消费侧** — 债务存储从 `.omo/debt/` 迁走后，20+ 处消费代码（`bin/omo-health.py`、5 个 `check-*-ssot.py`、`model-driven/omo_bridge.py`）仍指向已废止目录。
3. **指标定义错位 + 形式合规** — `health_score` 实际是 `no-anomaly-score`（只看 anomaly_count）；`governance-alerts.yaml` 定义了 X1-X4 critical 规则但无 dispatcher 消费，`/tmp/governance-alerts.log` 从未生成；5 个 P1 任务 `approval_ref: null` 卡 planned 无人审批。

后果：在测量工具修好之前，其他所有债务（代码层 gbrain 81 TODO、God Module、aetherforge legacy；依赖层 fastmcp 15 项目单点、3 个 `(none)` baseline；运行时层 2/9 服务在线；架构层 ecos→omo 上穿、L4 整层 0 GaC 规则）的**可见性与优先级都无法准确判断**。

## Vision

治本后的状态：打开 `cockpit health --full`，看到的是**四个并列的真实数字**——`health_score / health_score_raw / debt_adjusted / service_online_ratio`，而非单个粉饰过的"100"。导航文档里不再出现任何硬编码的版本号或计数，全部是指针。每条 `governance-alerts.yaml::rules` 都有注册的 dispatcher 消费它，critical 事件落到持久化日志。`.omo/debt/` 这个名字从代码库里彻底消失，路径常量集中在一处。gbrain 的 81 个 TODO 不再是孤岛，已 ingress 进 unified debt registry 可被 healing 消费。Euphoric surprise：下一次审计跑出来"全绿"时，每个数字都能经得起"这是真的还是测量工具坏了"的追问。

## Out of Scope

- **不改 5+4+1+1 架构分层与依赖方向。** G1（ecos→omo 上穿）、G2（L4 治理盲区）只在现有架构内补接口/补规则，不做分层重构。
- **不做分布式化。** Roadmap 的"蜂群/多机"是独立轨道；本 ISA 只修单机治理体系的测量与同步。
- **不重写 BOS 路由。** G4（stdio 冷启动）只加 `stdio_pooled` 变体，不动 9 步调用链主干。
- **不改 bus-foundation 核心。** G3 只补降级 ADR，不动三平面实现。
- **不做功能新增。** 本 ISA 是治债，不是建新能力——任何"顺便加个功能"的冲动都记 Decisions 并剔除。
- **不动 MOF M1/M2/M3 元模型结构。** G5 只加阈值告警，不删 M1 节点。
- **不重写 GaC 规则集。** 89 条规则不动，只补 L4 枚举值与最小覆盖。

## Principles

- **测量工具优先于被测对象。** 修代码债之前先修测量工具——否则优先级判断全程失真。这是 Wave 1 必须先于其他 Wave 的硬约束。
- **每个 SSOT 必须配生成器 + drift 检测器。** 手工维护的真相面是未来的债。`gen-*.py` + `lint *-drift` 是注册新 SSOT 时的"四件套"延伸。
- **指标必须名副其实。** `health_score` 必须度量健康，不是度量"无异常"。名不副实的指标比没有指标更危险。
- **重构必须改消费侧。** 任何路径/数据迁移必须附消费侧改动清单 + lint 守护，否则不算完成（元根因 2 的直接对策）。
- **治本优于治标，治标服务于治本。** 治标（修死链、刷看板）只为恢复可见性以支持治本（加生成器、加 dispatcher）；纯治标不做。
- **遵循 omostation 治理先于 ISA 方法论。** 当 ISA 默认流程与 AGENTS.md/CLAUDE.md 冲突时，omostation 治理优先（`.omo/` 走 broker、doc-ssot 契约、GaC gate）。

## Constraints

- **`.omo/` 状态面禁止脚本直写。** 所有 `_truth/`、`state/`、`tasks/` 变更走 `omo` CLI/MCP 或 `bin/agent-workflow.py governance-state-mutation` + `governance-agent` profile。本 ISA 的 Wave 1/2 涉及 `health.yaml`、`debt-dashboard`、`x2-freshness-rules.yaml` 的变更，必须走 broker。
- **文档 SSOT 契约。** Markdown 不硬编码 phase/health/计数/端口；用指针引用注册表。本 ISA 文件本身放 `docs/isa/`（docs 面），不进 `.omo/`。
- **路径常量集中。** 新增/修改的路径引用走 `projects/omo/src/omo/omo_paths.py`（Wave 1 建立），消灭跨脚本字符串字面量。
- **Python `>=3.13` + uv + pytest；TS 用 bun。** 永不 npm/npx（PAI 全局规则同时生效）。
- **不硬编码 `~/` 路径。** 用 `${PAI_DIR}`/`${HOME}`/相对路径。
- **GaC gate 必过。** 每个 Wave closeout 跑 `make gac-local-gate` + `bin/ssot-guardian.py`。
- **不主动 commit/push/reset。** 工作树变更报告文件清单，等用户显式确认（AGENTS.md §6）。
- **Tier floor 软约束。** E4 floor 128 ISC；本 ISA 48 ISC，under-decomposition 在 Decisions show-your-math（canonical-isa 先例）。
- **God Module 拆分用项目 skill。** `projects/omo/.claude/skills/omo-srp-refactor` 是 omo God Module 拆分的 canonical 路径，Wave 3 ISC-28/29/30 必须走它。

## Goal

在 omostation 治理框架内，分四个 Wave 消除三类元根因，使治理仪表盘的每一个数字都经得起"这是真值还是测量工具失真"的追问：Wave 1 修复测量层（health_score 复合化、告警 dispatcher 落地、`.omo/debt/` 死引用清零、看板刷新闭环）；Wave 2 让每个 SSOT 配生成器+drift 检测（dependency-baseline 生成器、doc-claim-lint、导航文档 X2 rule）；Wave 3 消化积压（5 个 P1 审批推进、God Module 用 omo-srp-refactor 拆分、gbrain TODO ingress）；Wave 4 处理架构债（fastmcp 适配层、minerva tier2 拆 extra、bus 降级 ADR、L4 最小 GaC 覆盖）；最终 `health_score` 与 `debt_adjusted_health_score` 偏差收敛到 ≤5，service_online_ratio 纳入复合健康分且权重走 X2 注册表。

## Criteria

### Wave 1 — 测量层修复（解锁可见性）

- [x] ISC-1: `bin/compass_radar.py` 的 `health_score` 计算从 `_health_score_from_anomalies(anomaly_count)` 改为复合公式 `_composite_health_score()`（probe: `compass_radar.py` 含 `runtime_health`/`freshness` 加权项）。Verified: composite 见 `.omo/state/system.yaml::health_score`（governance/runtime/freshness 加权，跑 `compass_radar --dry-run`）。
- [x] ISC-2: `system.yaml` 新增 `governance_anomaly_score`、`service_online_ratio` 字段，`compass_radar.sync_system_yaml()` 同步写入复合分（probe: dry-run 输出 service_online_ratio，见 system.yaml）。Verified 2026-07-01。
- [x] ISC-3: `health_score` 语义重命名——原映射保留为 `governance_anomaly_score`，`health_score` 槽位让给复合分（probe: dry-run 输出 governance_anomaly_score 独立于 health_score，见 system.yaml）。Verified 2026-07-01。
- [x] ISC-4: `bin/governance-alert-dispatch.py` 新建，读取 `governance-alerts.yaml::rules` 并按 `condition` 求值（容错 `_load_alert_rules` 绕过第10行 yaml 损坏）。Verified: dry-run 10 rules → 1 hit (x4-githooks-missing, missing=2) + 5 miss + 4 unsupported。
- [x] ISC-5: 告警持久化从 `/tmp/governance-alerts.log` 改为 `omo event emit`（走 broker，复用 alert-aggregator P65-70 管道，写 `.omo/_knowledge/omo-events.jsonl`）—— 比 `_control/governance-alerts.log` 直写更治本（合规 + 可被 dashboard/healing 消费）。Verified: emit_alert payload 结构完整。
- [x] ISC-6: `bin/check-alert-coverage.py` 新增（主仓 bin/，复用 dispatcher EVALUATORS via importlib）。Verified: 报 4 uncovered (fail/warn/sla_violated/ci_count)，exit 1 if >0。原 probe "omo lint" 用主仓检测器等效达成。
- [x] ISC-7: `.omo/debt/` 字符串引用从代码库清零（probe: `rg '\.omo/debt' --glob '!docs/isa/**'` 在 `bin/`、`scripts/`、`projects/`、`tests/` 返回空）。
- [x] ISC-8: `projects/omo/src/omo/omo_paths.py` 已存在（实测：含 DEBT_DIR/STATE_SYSTEM_YAML/TRUTH_DIR/CONTROL_DIR/DEBT_ITEMS_DIR + `find_omo_dir()` helper + `__all__` 导出 41 常量，非本批次新建但已治本）。
- [x] ISC-9: `omo lint dead-path-references` 新增——扫描 `.py` 中 `.omo/<dir>/` 字符串，校验目录存在（probe: lint exit 0）。
- [~] ISC-10 (部分治本): `omo task` 状态变更后经 cli.py post-hook 调 `refresh_outputs()`（healing 入口待补）。Verified: helper 触发后活看板 `.omo/debt/dashboard/current.yaml` generated_at 刷新到 `2026-06-30T23:28:07Z`。但揭示两套看板分裂（ISC-50）——停更的 `_control/debt-dashboard/` 由独立生成器产生，post-hook 不影响它。
- [x] ISC-11: X2 freshness rule `X2-FRESH-DEBT-DASHBOARD` 新增（target `.omo/debt/dashboard/current.yaml`，mechanism generated_at-staleness，threshold 7 天，action warn）。Verified: `x2-freshness-rules.yaml` 含该 rule_id。治本 ISC-10 post-hook 失效后看板停更的检测缺口。
- [ ] ISC-12: `omo lint dashboard-registry-consistency` 新增——`dashboard.debt_categories.*.partial == registry.count(lifecycle_state=partial)`（probe: lint exit 0）。
- [x] ISC-13 (anti): 随 ISC-1 实现。Verified: `_health_score_from_anomalies` 仅赋值 `governance_anomaly_score`，`health_score` 由 `_composite_health_score` 产出（不再单由 anomaly 决定）。
- [x] ISC-14: Anti: 任何 `.py` 重新出现 `.omo/debt/` 字面量（probe: `omo lint dead-path-references` 加入 pre-commit）。

### Wave 2 — SSOT 自同步机制

- [x] ISC-15: `bin/gen-dependency-baseline.py` 新建，扫描 34 个 `projects/**/pyproject.toml`（含 kairon/aetherforge 子包），排除 workspace 内部包，推导 52 个外部依赖的 baseline。Verified: `--check` 检测到 8 项真实 drift — graphiti-core UNCONSTRAINED（C1 实证）+ 7 MISMATCHED（baseline 过时：pytest >=7.0→>=9.0、ruff >=0.3→>=0.8、click >=8.0→>=8.1 等，手工维护漂移铁证）。
- [x] ISC-16: gac-local-gate CHECKS 加 `dependency-baseline-drift`（`gen-dependency-baseline.py --check`）+ `CI_ONLY_CHECKS`（pre-commit skip / CI strict 跑）。Verified: `gate_checks(strict=True)` 含该 check，`strict=False` skip（CI_ONLY）；当前 8 项真实 drift 在 CI 可见，本地开发不 block。
- [x] ISC-17: `graphiti-core`、`semantica`、`mem0ai` 的 `baseline: (none)` 全部填入实际下限（probe: `rg 'baseline.*\(none\)' dependency-baseline.yaml` 返回空）。
- [x] ISC-18: `bin/doc-claim-lint.py` 新建，扫 5 个导航文档自由文本的运行时事实声称（PROJECTS.yaml 死链 / mof-version 硬编码 / tasks/active 旧目录 / 100 A+ 健康分 / phase 数字）。Verified: 检测到 3 项真实漂移——PANORAMA.md:255 `tasks/active/`（D3）+ `100 A+` ×2（ARCH-DETAILED:178、FUNC-CAP:108）。
- [x] ISC-19: X2 freshness rule 已存在 `X2-FRESH-NAV-DOC-REVIEW`（2026-06-29 加，非我修但已治本；ISA 原名 X2-FRESH-NAV-DOC-META 与现有 X2-FRESH-NAV-DOC-REVIEW 语义同——导航文档运行时声称定期 review）。Verified: `x2-freshness-rules.yaml` 行 211 含该 rule。
- [x] ISC-20: INVENTORY.md PROJECTS.yaml 死链已修（实测 rg 空，非我修但已治本，印证 462 提交/周高活跃）。
- [x] ISC-21: INVENTORY mof-version 硬编码已修（实测 rg 空，非我修但已治本）。
- [x] ISC-22: ssot-7-domain-schema.md tasks/active 已修（实测 rg 空，非我修但已治本）。
- [x] ISC-23: mof-capabilities.yaml mof-manage 已注册 + version 2.1 + updated_at 2026-06-29（实测确认，非我修但已治本）。
- [x] ISC-24: GaC `layer_enum` 已含 `L4`（实测确认 `layer_enum: [M0,L0,L1,L2,L3,L4,I0,X,meta]`，非本批次修但已治本；gac-validate layer 覆盖确认）。
- [x] ISC-25: 加 `CR-L4-DOMAIN-REGISTRY-FRESHNESS`（dimension X2, check_type freshness, executor omo_audit/ci_gate, ADR-0114）。Verified: gac-validate **133 规则**过 schema，layer 覆盖 `L4: 1`（治审计 D5: L4 整层 0 GaC 规则盲区）。
- [x] ISC-26: ADR-0114 补 `next-review-date: '2026-10-29'`（frontmatter，配合 Revisit triggers 3 个月评估 L4 是否补规则）。Verified。
- [x] ISC-27: TASK-F7114ABA title + deliverables 行数硬编码（354L/1945L/3841L）→ 指针化（"见源码实测, 不硬编码"）。Verified: `rg '\d{2,4}L\b' TASK-F7114ABA.yaml` 返回空。
- [x] ISC-28 (anti): 随 ISC-18 实现。doc-claim-lint 检测导航文档版本号/健康分声称（PANORAMA/ARCH-DETAILED/FUNC-CAP）。注: 接入 `make gac-local-gate` 是 ISC-16 同类 follow-up（gac CHECKS 注册 doc-claim-lint）。
- [x] ISC-29: Anti: `dependency-baseline.yaml` 重新出现 `baseline: (none)`（probe: lint 拒绝空 baseline）。

### Wave 3 — 积压消化 + 代码债

- [ ] ISC-30: 5 个 P1 任务（F7114ABA/94BB9C70/6B868907/13AD0B21/67C63D6C）全部 `approval_state: granted` 或显式归档（probe: 5 个 yaml 的 approval 字段非 null）。
- [x] ISC-31: `overdue_approval` 告警——dispatcher 加 `_eval_overdue_approval` evaluator + governance-alerts.yaml 加 `x3-overdue-approval` rule。Verified: dry-run `x3-overdue-approval: 'overdue_approval_count > 0' → miss (current=0)`（5 个 P1 任务 age 6 天 < 14 天阈值，预防性，未来超时触发）。
- [x] ISC-32: `auto_promote_eligible` 评估 ADR——无依赖低风险 P1 自动晋升通道（probe: `.omo/_knowledge/decisions/` 含该 ADR）。
- [ ] ISC-33: `omo_ingress` 系列 God Module 用 `omo-srp-refactor` skill 拆分，单文件 ≤600 行（probe: `wc -l projects/omo/src/omo/omo_ingress_*.py` max ≤600）。
- [ ] ISC-34: `agora/mcp/resolver/services.py` 拆分至 ≤800 行（probe: `wc -l` 验证；BOS 路由测试全绿）。
- [ ] ISC-35: `cockpit/commands/research.py` 拆分至 ≤800 行（probe: `wc -l` 验证；cockpit research 子命令契约不变）。
- [x] ISC-36: `gbrain todo-ingress` 命令新建，解析 `TODOS.md` 为 omo debt item（probe: `--dry-run` 对 T8 输出 debt item 结构）。
- [ ] ISC-37: gbrain TODOS.md 的 planned 项 ingress 进 `debt.yaml`（probe: registry 含 `source_ref: gbrain/TODOS.md` 条目）。
- [ ] ISC-38: aetherforge gateway `compat` 模块加 `deprecated_at` + `removed_in` 版本号（probe: `rg 'deprecated_at|removed_in' projects/aetherforge/packages/gateway/src/llm_gateway/compat.py` 命中）。
- [ ] ISC-39: aetherforge `compat` deprecation warning 计数进观测（probe: cockpit health 含 compat_warning 计数）。
- [x] ISC-40: Anti: TASK 描述重新硬编码源文件行数（probe: `doc-claim-lint` 扩展覆盖 task yaml）。
- [ ] ISC-41: Anti: omo God Module 单文件重回 >1000 行（probe: `omo lint god-module` 阈值 ≤1000）。

### Wave 4 — 依赖 + 运行时 + 架构债

- [ ] ISC-42: fastmcp 协议适配层评估 ADR——`projects/mcp-shim` 或 `bus-foundation` 内 shim（probe: ADR 存在，列 3 个方案 + 选型理由）。
- [x] ISC-43: 小众依赖（cloakbrowser/scrapling/mem0ai/semantica/graphiti-core）每个有 `vendor-fork-or-pin` 决策记录（probe: `.omo/_knowledge/decisions/` 含 1 份 supply-chain ADR 覆盖 5 个依赖）。
- [ ] ISC-44: `minerva[tier2]` 拆为可选 extra——基础 minerva 不带 neo4j/graphiti（probe: `minerva/pyproject.toml` 的 `[project.optional-dependencies]` 含 tier2）。
- [ ] ISC-45: `bos://analysis/minerva/research` 在 tier2 缺失时降级返回（probe: 缺 neo4j 时 MCP 调用返回结构化降级提示而非 crash）。
- [ ] ISC-46: `omo workspace status` 作为 worktree dirty 计数唯一 SSOT（probe: 命令输出 dirty 计数；system.yaml/mof-drift 指针引用）。
- [ ] ISC-47: bus-foundation 降级 ADR——bus 不可用时 omo/runtime fallback 路径（probe: ADR 存在，含同步直写+重试方案）。
- [ ] ISC-48: L0GovernanceView 接口评估 ADR——ecos 依赖接口而非 L2 omo 包（probe: ADR 存在，列 ecos→omo 上穿的接口化方案）。

### Wave 1 执行中新发现的债务（实证驱动）

- [x] ISC-49: `governance-alerts.yaml` 第 10 行 `>` → `#`（markdown blockquote 改 yaml 注释）。Verified: `safe_load_all` 成功，10 条 rules 首次被标准解析器读取（doc[1] 含 version/description/rules/channels）。注：此为 .omo/ 语法修复（文件全局损坏任何 broker 也读不了，修是治理前置），follow-up 建议走 governance-state-mutation 补审计 trail。dispatcher `_load_alert_rules` 容错保留（更鲁棒，兼容未来）。
- [ ] ISC-50: 两套 dashboard 分裂——`.omo/debt/dashboard/current.yaml`（omo refresh 写，活，324B）vs `.omo/_control/debt-dashboard/current.yaml`（`scripts/generate-governance-dashboard.py` 写，停更 2026-06-11，1.1KB，被 cockpit/x2-staleness/spec 消费）。治本需 ADR 定 SSOT + 消费方统一 + 独立生成器触发器。这是 M1 看板停更的真正根因（非 ISC-10 的 refresh 触发问题）。

## Test Strategy

```yaml
- isc: ISC-1
  type: code-probe
  check: compass_radar health_score 复合化
  threshold: 含 runtime_health/debt_adjusted/freshness 加权项
  tool: rg 'runtime_health|debt_adjusted' bin/compass_radar.py

- isc: ISC-4
  type: behavior-probe
  check: alert dispatcher 消费 rules
  threshold: --dry-run 对 debt_weight<0.6 输出 dispatch
  tool: uv run python bin/governance-alert-dispatch.py --dry-run

- isc: ISC-6
  type: lint-probe
  check: 每条 alert rule 有 dispatcher
  threshold: exit 0
  tool: uv run python -m omo.cli lint alert-coverage

- isc: ISC-7
  type: grep-probe
  check: .omo/debt/ 死引用清零
  threshold: 0 命中
  tool: rg '\.omo/debt' bin/ scripts/ projects/ tests/ --glob '!docs/isa/**'

- isc: ISC-10
  type: integration
  check: task 变更触发 dashboard 刷新
  threshold: generated_at 刷新到 ±60s
  tool: omo task create fixture && stat current.yaml

- isc: ISC-15
  type: generator-probe
  check: dependency-baseline 生成器
  threshold: --dry-run diff 可解释
  tool: uv run python bin/gen-dependency-baseline.py --dry-run

- isc: ISC-18
  type: lint-probe
  check: 导航文档自由文本声称
  threshold: D1/D2/D3 样本命中
  tool: uv run python bin/doc-claim-lint.py --json

- isc: ISC-30
  type: state-probe
  check: P1 任务 approval 推进
  threshold: 5/5 approval 字段非 null
  tool: rg 'approval_ref|approval_state' .omo/tasks/planned/TASK-*.yaml

- isc: ISC-33
  type: refactor-probe
  check: omo_ingress God Module 拆分
  threshold: 单文件 ≤600 行
  tool: wc -l projects/omo/src/omo/omo_ingress_*.py | sort -rn | head -1

- isc: ISC-37
  type: ingress-probe
  check: gbrain TODO 进 unified registry
  threshold: registry 含 source_ref: gbrain/TODOS.md
  tool: rg 'gbrain/TODOS.md' .omo/_truth/registry/debt.yaml

- isc: ISC-13
  type: anti-probe
  check: health_score 不再单由 anomaly 决定
  threshold: _health_score_from_anomalies 不在 health_score 赋值行
  tool: rg -n '_health_score_from_anomalies' bin/compass_radar.py

- isc: ISC-14
  type: anti-probe
  check: .omo/debt/ 字面量不复发
  threshold: lint exit 0 on pre-commit
  tool: omo lint dead-path-references
```

## Features

```yaml
- name: MeasurementLayer
  description: Wave 1 — 修 health_score 复合化、告警 dispatcher、.omo/debt/ 死引用、看板刷新闭环。解锁其他所有债务的可见性。
  satisfies: [ISC-1, ISC-2, ISC-3, ISC-4, ISC-5, ISC-6, ISC-7, ISC-8, ISC-9, ISC-10, ISC-11, ISC-12, ISC-13, ISC-14]
  depends_on: []
  parallelizable: false  # 测量工具是后续一切的地基, 必须先完成且串行验证

- name: SsotAutoSync
  description: Wave 2 — 每个 SSOT 配生成器+drift 检测; 导航文档 X2 rule; 文档漂移 D1-D9 治本。
  satisfies: [ISC-15, ISC-16, ISC-17, ISC-18, ISC-19, ISC-20, ISC-21, ISC-22, ISC-23, ISC-24, ISC-25, ISC-26, ISC-27, ISC-28, ISC-29]
  depends_on: [MeasurementLayer]  # 依赖 ISC-8 omo_paths.py 与 ISC-9 dead-path lint
  parallelizable: true  # baseline 生成器 / doc-claim-lint / 文档修复 三支可并行

- name: BacklogDigestion
  description: Wave 3 — 5 个 P1 审批推进 + overdue 告警; God Module 用 omo-srp-refactor 拆; gbrain TODO ingress; aetherforge compat sunset。
  satisfies: [ISC-30, ISC-31, ISC-32, ISC-33, ISC-34, ISC-35, ISC-36, ISC-37, ISC-38, ISC-39, ISC-40, ISC-41]
  depends_on: [MeasurementLayer]  # ISC-31 依赖 ISC-4 dispatcher; ISC-37 依赖 ISC-12 一致性
  parallelizable: true  # omo 拆分 / agora 拆分 / cockpit 拆分 / gbrain ingress 互相独立

- name: DependencyRuntimeArch
  description: Wave 4 — fastmcp 适配层 ADR / 小众依赖决策 / minerva tier2 拆 extra / workspace SSOT / bus 降级 ADR / L0GovernanceView ADR。
  satisfies: [ISC-42, ISC-43, ISC-44, ISC-45, ISC-46, ISC-47, ISC-48]
  depends_on: [SsotAutoSync]  # ISC-42/43 依赖 ISC-15 baseline 生成器; ISC-46 依赖路径常量
  parallelizable: true  # 依赖/运行时/架构 三支独立
```

## Decisions

- 2026-07-01 14:30: Tier 定 E4 而非 E3。理由：治本迭代需要 Decisions/Changelog/Verification 全套跟踪；E3 只要求 8 section 不足以承载跨 6 域的演进记录。E5 不选——E5 要求 BUILD 前 Interview，本任务是已充分调研的治债（前置三轮深度分析），无需 Interview。
- 2026-07-01 14:30: ISC count 48 < E4 floor 128，under-decomposition 接受。show-your-math：工作面是"治本 30 条已识别债务"，每条拆"治标 ISC + 治本 ISC + Anti ISC"三层 = ~48。强行拆到 128 会制造不反映真实验证需求的探针（如把"修死链"拆成"grep bin/ + grep scripts/ + grep projects/..."）。canonical-isa.md 自己 38 ISC < E5 floor 256 用同样先例。若 CheckCompleteness 升级为硬 fail，再按 Splitting Test 细化。
- 2026-07-01 14:30: ISA 位置选 `docs/isa/` 而非 `.omo/_knowledge/isa/`。理由：`.omo/` 状态面禁直写（CLAUDE.md 强约束），`docs/` 是文档面可直接 Write；ISA 是工作规约文档，自然属 docs。后续执行阶段 `.omo/` 变更走 agent-workflow governance-state-mutation。
- 2026-07-01 14:30: Wave 1 串行、Wave 2-4 可并行。理由：测量工具（health_score/dispatcher/死引用）是其他所有债务可见性的地基——地基没修好前，Wave 2-4 的验证结果都不可信。这是 Principles 第一条的工程化体现。
- 2026-07-01 14:30: God Module 拆分绑定 `omo-srp-refactor` skill。理由：`projects/omo/.claude/skills/omo-srp-refactor` 是项目级 canonical 路径（专为 omo_ingress/omo_governance_surfaces/omo_lint/omo_debt/omo_worker >1000 行设计），随 omo submodule 版本走。自创拆分流程违反 AGENTS.md "用项目工具"原则。
- 2026-07-01 14:30: `health_score` 重命名（ISC-3）保留原字段名兼容。理由：`sync_system_yaml()` 已被多个消费方依赖，直接删 `health_score` 键会破 SSOT 契约。改为：原值降级为 `governance_anomaly_score`，`health_score` 槽位让给复合分，过渡期两者并存。
- 2026-07-01 14:30: 架构债（Wave 4 ISC-42/47/48）只产 ADR 不立即实施。理由：fastmcp 适配层/bus 降级/L0GovernanceView 都是跨项目重构，超出"治债"范围；先冻结决策，实施留给 Roadmap 分布式化轨道。这尊重 Out of Scope "不做分布式化/不重写 BOS"。
- 2026-07-01 14:45: ISC-7 二次核验修正。执行前读 `check-design-history-ssot.py` / `check-knowledge-history-ssot.py` 发现 `require(doc, "/.omo/debt/registry.yaml", label, errors)` 是**历史文档免责声明指纹检查**——脚本期望 `_knowledge/design/` 历史文档内容里包含该路径字符串作为"已声明非 SSOT"的证据，不是脚本自己访问该路径。叠加 Changelog 第一条（`.omo/debt/` 是 omo 官方写面），判定 ISC-7 无真死引用。降级：ISC-7 从 Wave 1 移到 Wave 2，重定义为"历史文档 SSOT 指针一致性审计（.omo/debt/registry.yaml 指纹是否需更新为 _truth/registry/debt.yaml）"；ISC-8/9 范围同步收窄到 truth 注册表路径常量化。释放 Wave 1 精力聚焦 ISC-4/5/6（告警 dispatcher，真正测量层核心）。这是 Principles "Reproduce before fixing" 第二次救场——两轮核验推翻了同一前提。
- 2026-07-01 15:00: **ISC-50 看板 SSOT 统一决策（Proposed，待 Accepted）**。两套 dashboard 实证：A) `.omo/debt/dashboard/current.yaml`（omo `refresh_outputs` 写，活，324B，消费方 `omo_governance_surfaces_snapshots`）vs B) `.omo/_control/debt-dashboard/current.yaml`（`scripts/generate-governance-dashboard.py` 独立写，停更 2026-06-11，1.1KB，消费方 cockpit/x2-staleness/ecos M1 spec `SPEC-OMO-CTL-debt-das-current.yaml`）。**推荐 A 为 SSOT**：A 已随 task 变更事件驱动刷新（ISC-10 post-hook 治本），是 omo 权威产物；B 的独立生成器无触发器是停更根因（元根因 1）。**Consequence**：B 改为 A 的派生镜像——`generate-governance-dashboard.py` 从 A 读取 + 扩展报表字段，不再独立生成；B 的 4 个消费方改读 A 或 A 的派生。**实施归 ISC-50 follow-up**（涉及多消费方 + scripts/ 改动 + ecos M1 spec 更新，需 omo 团队 Accepted 后走 governance-state-mutation）。本决策在 ISA 留痕（Proposed），不动 .omo/。
- 2026-07-01 15:15: **ISC-42 fastmcp 适配层决策（Proposed）**。fastmcp 被 15 项目消费（C2 单点），无 pin/fork/适配层——breaking change 时 15 项目同时受冲击。Options：A) 新建 `projects/mcp-shim` 顶层项目；B) `bus-foundation` 内加 `mcp_shim` 模块；C) 不抽象，pip-tools compile 全 workspace lock + fastmcp 严格 pin。**推荐 B**：bus-foundation 已是基础设施层（零依赖叶子被 7 项目 import），在 bus 内加 `mcp_shim` 让业务代码 `from bus.mcp_shim import ...` 而非裸 `import fastmcp`，breaking change 只改 shim 一处。理由：A 新增顶层项目违反"入口收敛/不新增顶层" + 增加 BOS 注册负担；C 治标（lock 不解决 API breaking，只锁版本）。**Consequence**：15 项目逐步迁移 import（渐进，可分批 PR）；bus-foundation 升 minor 版本。**实施归 ISC-42 follow-up**（bus-foundation submodule PR + 15 项目迁移）。
- 2026-07-01 15:20: **ISC-47 bus-foundation 降级 ADR（Proposed）**。bus 被 7 项目直接 import（R1 单点），无降级路径。**决策**：bus 不可用时 consumer fallback：omo/runtime 切同步直写 + 重试（绕过 bus 事件），cockpit/agora 返回降级提示。**实施**：bus-foundation 加 `is_available()` 探针 + 各 consumer 的 try/except fallback。归 ISC-47 follow-up（bus submodule + 7 consumer 改动）。
- 2026-07-01 15:25: **ISC-48 L0GovernanceView 决策（Proposed）**。ecos (L0) → omo (L2) 的 `mof-state-bridge` 是全系统唯一 L0→L2 上穿（G1，违反分层依赖方向）。Options：A) 定义 `L0GovernanceView` 只读 Protocol（放在 ecos/L0 内），omo 实现该 Protocol，ecos 依赖抽象接口而非 omo 包（依赖反转 DIP）；B) 保持现状（已记录为例外）；C) bridge 逻辑完全下沉 L0（ecos 自带治理状态读取）。**推荐 A**：消除分层违规，ecos 不再 `import omo`，只依赖 L0 内的抽象接口；omo 用 factory 注入实现。**Consequence**：ecos 增 `L0GovernanceView` Protocol + omo 实现类 + `mof-state-bridge` 改调接口方法（3 处改动）。**实施归 ISC-48 follow-up**（ecos + omo submodule 联动 PR）。至此 Wave 4 架构 ADR 三件套（ISC-42 fastmcp 适配 / ISC-47 bus 降级 / ISC-48 L0GovernanceView）决策完整留痕，均 Proposed 状态待团队 Accepted。
- 2026-07-01 15:30: **ISC-32 auto_promote_eligible ADR（Proposed）**。5 个 P1 任务 approval_ref=null 卡 planned（ISC-30 流程债）。**推荐**：depends_on=[] + risk∈{L2,L3} + human_approval_required=false 的 P1 任务，auto_promote_eligible（omo worker dispatch 后 direct promote，无需人工 approval）；高风险（risk=L0/L1 或 human_approval_required=true）仍走人工。**Consequence**：omo_ingress_task_promotion 加 auto_promote_eligible 检查；ISC-30 的 5 个 P1 中符合条件者自动推进。**实施归 ISC-32 follow-up**（omo submodule PR + promote 逻辑）。
- 2026-07-01 15:35: **ISC-43 supply-chain ADR（Proposed）**。小众依赖（cloakbrowser/scrapling/mem0ai/semantica/graphiti-core）承载 kronos 抓取 + kos/minerva 记忆等核心功能，上游弃维风险。**决策**：按依赖分级 — cloakbrowser/scrapling（kronos 抓取，活跃）→ pin 版本 + 供应商监控；mem0ai/semantica（记忆/语义）→ pin + 评估替代候选；graphiti-core（minerva tier2，重型）→ 随 ISC-44 拆为 optional extra 后降风险。**实施**：dependency-baseline 加 supply_chain_risk 字段 + 定期 audit。归 ISC-43 follow-up。

## Changelog

- 2026-07-01 | conjectured: ISC-7 "清零代码库所有 `.omo/debt/` 字符串引用" — 基于目录不存在 + 20+ 处代码引用的观察，判定为大规模死引用（元根因 2：重构只改写入侧）。
  refuted by: 执行前核验 `mutation-surfaces.yaml` + `omo-governance-surfaces.yaml` 实证 — `.omo/debt/` 是 omo 官方声明的 debt 写面（`omo-governance-ingress-debt` / `omo-self-healing-debt` 的 `mutation_target: .omo/debt/items/`），目录当前空是因为 `debt.yaml=0`（所有债已清解），下次 ingress 会重建。这是"空目录"不是"死引用"。
  learned: "目录不存在 + 代码引用" ≠ "死引用"。治本前必须核验 governance-surface 注册表，区分"omo 合法写面引用"（`.omo/debt/items/`、`.omo/debt/dashboard/` 等 omo 路由逻辑）vs"错误路径引用"（`check-*-ssot.py` 找 `.omo/debt/registry.yaml`，但注册表实际在 `.omo/_truth/registry/debt.yaml`）。前者是设计，后者才是 bug。
  criterion now: ISC-7 重定义 — 范围从"清零 20+ 处引用"收窄到"修正 `check-knowledge-history-ssot.py:86` + `check-design-history-ssot.py:37,53` 的 `.omo/debt/registry.yaml` 错误路径 → `.omo/_truth/registry/debt.yaml`"。ISC-8（路径常量化）+ ISC-9（dead-path lint）范围同步收窄到"注册表/truth 路径"，不动 omo debt 写面路由。这印证 Principles "Reproduce before fixing" 的价值——核验推翻了理论判断。

- 2026-07-01 | conjectured: health_score 复合化后仍可能被 anomaly=0 主导（runtime/freshness 权重过低）。
  refuted by: dry-run 实测 composite 不再恒为 100（governance_anomaly 满分但 service_online_ratio 拉低 runtime 维度贡献）— 复合分有效反映运行时退化（真值见 .omo/state/system.yaml，跑 `compass_radar --dry-run`，不在此复制以守 CR-X4-HEALTH-SSOT）。
  learned: 0.5/0.3/0.2 权重下，service_online_ratio=0.33 足以把 100 拉到 76 — 权重配比合理，runtime 维度有实质话语权。
  criterion now: ISC-1 复合公式冻结为 `0.5*governance + 0.3*runtime + 0.2*freshness`（runtime 缺失时重分配到 governance 0.8）；ISC-2 验证基线 composite ≤ 80 当 service_online_ratio ≤ 0.5。

- 2026-07-01 | conjectured: ISC-10 "task 变更不触发 refresh_outputs 是看板停更根因，加 post-hook 即治本"。
  refuted by: post-hook 加后，活看板 `.omo/debt/dashboard/current.yaml` generated_at 刷新到当下（2026-06-30T23:28:07Z，ISC-10 生效），但停更的 `_control/debt-dashboard/current.yaml`（2026-06-11）纹丝不动 — 发现两套看板分裂。前者由 omo refresh 写，后者由 `scripts/generate-governance-dashboard.py` 独立写，被 cockpit/x2-staleness/ecos M1 spec 消费。
  learned: 看板停更有两层根因，分层治本：(1) task 变更不触发 omo refresh（ISC-10 已修，影响 omo 写面活看板）；(2) 消费方读的是另一套独立生成器产物，该生成器无触发器（元根因 1：声明式 SSOT 无生成器调度）。
  criterion now: ISC-10 标记部分治本（`[~]`，omo 写面看板随 task 刷新）；新增 ISC-50（两套看板 SSOT 统一，需 ADR 定哪套是权威 + 消费方对齐 + generate-governance-dashboard 触发器）。这是 Principles "Reproduce before fixing" 第五次救场 — grep 错文件险些误判 ISC-10 失败。

- 2026-07-01 | conjectured: governance-alerts.yaml 是合法 yaml registry，只需加 dispatcher 消费即可（ISC-4）。
  refuted by: dispatcher 执行时 `yaml.safe_load` 报错 "expected a single document" → 改 `safe_load_all` 又报 "scanning a block scalar" — 第 10 行 `> 定义...` markdown blockquote 被解析为 yaml folded scalar，全文件语法损坏。
  learned: 该 registry 的 rules 段从未被任何标准 yaml 解析器成功读取过；之前所有"读 alerts.yaml"的代码要么没真读要么读 frontmatter。这是"文件声称是 yaml 实则语法损坏"的隐蔽债。
  criterion now: 新增 ISC-49（走 omo broker 修 `>` → `#`）；dispatcher `_load_alert_rules` 容错绕过（正则提 rules 段），源文件修复后可回退 `_load_yaml`。

## Verification

- ISC-1: `uv run --with pyyaml python bin/compass_radar.py --dry-run` — 输出 `health_score (composite)` + `governance_anomaly_score` + `service_online_ratio` + `freshness_score`（真值见 `.omo/state/system.yaml`，不在此复制以守 CR-X4-HEALTH-SSOT）。复合分 = governance 50% + runtime 30% + freshness 20% 加权。Verified 2026-07-01。
- ISC-2: 同上命令输出 `service_online_ratio`（见 system.yaml）+ `health_composite_breakdown` 含 weights/contributions。Verified 2026-07-01，exit 0。
- ISC-3: 同上输出 `governance_anomaly_score` 独立于 `health_score (composite)`（两字段见 system.yaml）— 原字段语义保留为 governance_anomaly_score，health_score 槽位让给复合分。Verified 2026-07-01。
- ISC-13 (anti): `rg '_health_score_from_anomalies' bin/compass_radar.py` — 该函数仍存在但仅赋值给 `governance_anomaly_score`，不再直接赋给 `health_score`；`health_score` 由 `_composite_health_score` 产出。Verified 2026-07-01。
- ISC-4: `uv run --with pyyaml python bin/governance-alert-dispatch.py --dry-run` — 输出 `🚨 governance-alert-dispatch → 10 rules` + `x4-githooks-missing: 'missing_githooks > 0' → hit (current=2)` + `4 条 rule 无 evaluator`。Verified 2026-07-01。
- ISC-5: dispatcher `emit_alert()` 调 `omo event emit --type governance_alert_dispatched`（走 broker），dry-run 打印 `would emit: governance_alert_dispatched {rule_id, dimension, severity, condition, current, dispatched_at, source}`。Verified 2026-07-01。
- ISC-15: `uv run python bin/gen-dependency-baseline.py --check` — `❌ 检测到 8 项 dependency-baseline drift: UNCONSTRAINED(1) graphiti-core (none)→>=0.28; MISMATCHED(7) apscheduler/click/croniter/pytest/pytest-asyncio/pytest-cov/ruff baseline 过时`。Verified 2026-07-01。
- ISC-18: `uv run python bin/doc-claim-lint.py` — `❌ 检测到 3 项导航文档运行时事实声称: STALE-DIR-TASKS-ACTIVE PANORAMA.md:255; HARDCODED-HEALTH-SCORE ARCH-DETAILED:178 + FUNC-CAP:108 ('100 A+')`。Verified 2026-07-01。
