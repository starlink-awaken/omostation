# AGENTS.md — Workspace Development Guide

> Root operating guide for AI coding agents and developers working in this workspace.
> Keep this file operational. Put runtime facts in SSOT files, not here.

## 1. Read This First

Before editing:

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check the current working tree with `git status --short`.
4. For multi-step work, run `uv run --with "pyyaml" python "bin/agent-workflow.py" lint` and choose a workflow from [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml).
5. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
6. For multi-file or high-risk changes, explain the edit surface before applying patches.

Project-specific instructions override this guide only within that project and only when they do not violate workspace governance.

## 2. Documentation SSOT Contract

| Document | Owns | Must Reference |
|----------|------|----------------|
| [`README.md`](README.md) | Front door and quick orientation | Architecture, registry, governance docs |
| [`CLAUDE.md`](CLAUDE.md) | AI session startup protocol | This file and target project docs |
| [`AGENTS.md`](AGENTS.md) | Workspace operating rules | SSOT registries for facts |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Stable architecture contracts | Registry files for counts and runtime values |
| [`LAYER-INDEX.md`](LAYER-INDEX.md) | Human-readable layer placement | `docs/project-registry.yaml` |
| [`docs/project-registry.yaml`](docs/project-registry.yaml) | Project metadata facts | Actual project metadata |
| [`.omo/_truth/registry/agent-workflows.yaml`](.omo/_truth/registry/agent-workflows.yaml) | Agent workflow facts | Executable workflow runner |
| [`.omo/state/system.yaml`](.omo/state/system.yaml) | Runtime state | Runtime probes and OMO state sync |

Do not hard-code current phase, health score, test counts, tool counts, service counts, source-file counts, port values, or generated rule inventories in Markdown. Use pointers.

The full documentation contract is [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md).

## 3. Architecture Summary

```
L4  Self       -> l4-kernel
L3  Entry      -> cockpit (cockpit-ui: 概念属 L3, 实际 layer=X, 挂载至 cockpit /hermes/*)
I0  Weave      -> agora
L2  Engine     -> kairon / gbrain / omo / metaos
L1  Runtime    -> runtime
L0  Protocol   -> ecos
M0  Lifecycle  -> model-driven
X   Frameworks -> aetherforge / c2g / bus-foundation / omo-debt / observability / family-hub
                spaces/ (配置仓, 非 git submodule, 纯 YAML 租户/系统空间策略)
```

Stable architecture details live in [`ARCHITECTURE.md`](ARCHITECTURE.md). Project metadata and counts live in [`docs/project-registry.yaml`](docs/project-registry.yaml).

## 4. Governance Boundaries

| Surface | Rule |
|---------|------|
| `.omo/` | State/evidence plane. Do not add long-lived execution logic here. |
| `projects/omo/` | Governance kernel: schema, audit, sync, broker, lint, task/debt lifecycle. |
| `projects/c2g/` | Strategy ingress: pitch/bet materialization into governed tasks. |
| `projects/ecos/` | Protocol and MOF layer. |
| `spaces/` | User/tenant-space manifests. Treat as governed configuration. |
| `scripts/` | Ops scripts (independent submodule). See [`scripts/AGENTS.md`](scripts/AGENTS.md). |
| `agent-runtime/` | Runtime execution logs. Do not edit manually. |
| `kos/` | Knowledge index (SQLite + snapshots). Runtime product, do not edit manually. |
| `bin/` | Governance tools (gac-*, doc-ssot-*, ssot-guardian). |

For `.omo` or `spaces` mutations, use the registered broker/CLI path. If a task truly needs direct manual edits, call that out and keep the patch minimal.

## 5. Essential Commands

```bash
make gac-local-gate
uv run --with "pyyaml" python "bin/agent-workflow.py" list
uv run --with "pyyaml" python "bin/agent-workflow.py" lint
uv run --with "pyyaml" python "bin/doc-ssot-lint.py" --json
uv run --with "pyyaml" python "bin/ssot-guardian.py"
uv run --with "pyyaml" python "bin/gac-validate.py" --gate
uv run --with "pyyaml" python "bin/gac-drift.py"
bash "tests/integration/run-all.sh"
cd "projects/kairon" && make test-diff
cd "projects/gbrain" && bun test
```

Prefer targeted checks for narrow edits. Broaden verification when the change touches shared contracts, generated registries, public entry points, or cross-project behavior.

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, destructive checkout, or branch switching unless the user explicitly asked or confirmed.
- Root repository tracks submodule pointers and workspace metadata.
- Most `projects/*` directories are independent repositories. Commit inside the submodule first only when the user requested commits, then update the root pointer.
- Never revert unrelated dirty files. Treat them as user or concurrent-agent work.

## 7. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Root governance docs | `make gac-local-gate` plus `uv run --with "pyyaml" python "bin/ssot-guardian.py"` |
| Python code (generic) | Targeted `uv run pytest` or project Makefile `test` target |
| kairon package | `make test-diff` from `projects/kairon` |
| gbrain | `bun test` or targeted Bun test |
| cockpit-ui (TypeScript) | `npm run build` or `bun run build` from `projects/cockpit-ui` |
| observability (Docker) | `docker compose config -q` from `projects/observability` |
| Cross-project contract | Targeted tests on every touched consumer plus relevant integration smoke |

If a test cannot run, report why and what risk remains.

## 8. Historical Patterns

Historical closeout details are useful evidence but should not be pasted into this file. Use pointers:

| Pattern | Read |
|---------|------|
| Agent mutation protocol | [`.omo/standards/agent-mutation-protocol.md`](.omo/standards/agent-mutation-protocol.md) |
| OMO governance surfaces | [`.omo/standards/omo-governance-surfaces.md`](.omo/standards/omo-governance-surfaces.md) |
| GaC North Star | [`.omo/_knowledge/gac/NORTH-STAR.md`](.omo/_knowledge/gac/NORTH-STAR.md) |
| P43 closed-loop pattern | [`.omo/_knowledge/patterns/p43-closed-loop-pattern.md`](.omo/_knowledge/patterns/p43-closed-loop-pattern.md) |
| Executable agent workflows | [`.omo/standards/agent-workflow-contract.md`](.omo/standards/agent-workflow-contract.md) |

## 9. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Mention files changed and checks run.
4. Mention any checks skipped or blocked.
5. Do not create commits unless explicitly requested and confirmed.

<!-- GaC-RULES-START -->
<!-- AUTO-GENERATED by bin/gac-export-agents.py — do not edit manually -->
<!-- Run: python3 bin/gac-export-agents.py to regenerate. Source: governance-checks.yaml (132 rules) -->

### GaC 规则速览 (132 条)

> SSOT: `.omo/_truth/registry/governance-checks.yaml::gac.rules`
> 校验: `python3 bin/gac-validate.py --gate` | 漂移: `python3 bin/gac-drift.py`
> legacy_index 规则描述从 source_ref 源文件拉取 (x1-policies / x2-freshness / x4-consistency / L0-constraints)

#### X1 审计 (29 条)

| 规则 ID | 层 | 检查类型 | 描述 |
|---------|:--:|---------|------|
| `CR-ADMISSION-01` | L0 | legacy_index | agora.ProxyManager 注册新路由前，必须通过 metaos 颁发的五大部件准入控制 |
| `CR-C2G-INGRESS-01` | L0 | legacy_index | `projects/c2g` 只能向 `.omo/tasks/planned/` 物化任务，不得直写 active/done |
| `CR-DEBT-CLOSURE-EVIDENCE-01` | L0 | legacy_index | lifecycle_state=closed 的 DEBT yaml 必须携带 ≥ 20 字符的 resolution_evidence;
lifecycle_state=deferred 的 DEBT yaml 必须携带 next_... |
| `CR-ENG-MYPY-TRUTH-01` | L0 | legacy_index | mypy 验证必须用真相调法 MYPYPATH=src (禁裸 mypy src 假绿).
假绿机制: 裸 mypy 无 MYPYPATH 时跨包 import 解析不出, 当 Any 静默通过, 退出 0.
真相: MYPYPATH... |
| `CR-ENG-TEST-ISOLATION-01` | L0 | legacy_index | 单元测试必须隔离外部依赖 (网络/Ollama/MCP/subprocess), 用 monkeypatch/mock.
禁: 测试依赖外部服务是否在跑 (flaky). 禁: 无条件 xfail (该用 conditional + ... |
| `CR-GOV-CLOSED-LOOP-01` | L0 | legacy_index | 强制闭环原则 (mandatory commit)。
P59 暴露的核心问题: mof-version 记录后未 git commit, 导致知识萃取引擎 (mof-extract post-commit hook) 失效, 治理漂移... |
| `CR-GOV-COMMIT-FREQUENCY-01` | L0 | legacy_index | commit 频率与文件改动同步。
工作树累积未提交 > 100 文件触发警告, > 500 触发 error。
防止 P59 类失闭环事件再次发生 (571 文件未提交)。
检测: git status --short | wc -... |
| `CR-L0-BOS-RESOLVE` | L0 | bos_resolve | BOS URI 声明必须 resolve (evidence-smoke 防 alive 标志假阳) |
| `CR-L2-DIRECT-IO` | L2 | direct_io_gate | 禁止绕过 omo ingress 直写 .omo (防状态竞态死锁, 报告债务① Critical) |
| `CR-L2-MUTATION-BROKER` | L2 | audit_chain | mutation-surfaces.yaml broker 注册权威 (entrypoint+target+mode), workspace governance verify 校验; 非 broker 写 .omo = 违规 |
| `CR-MCP-LAZY-01` | L0 | legacy_index | Agora Proxy 必须采用 lazy initialization 避免循环依赖锁死 |
| `CR-OMO-DIRECT-IO-01` | L0 | legacy_index | 非 broker 不得直接以文件系统方式改写 `.omo/` 或 `spaces/` |
| `CR-OMO-SURFACE-01` | L0 | legacy_index | `.omo` 顶层治理资产必须登记到 omo governance surfaces registry |
| `CR-OMO-SURFACE-02` | L0 | legacy_index | `.omo` 只能被视为治理状态面，不得替代 `projects/omo` 治理内核 |
| `CR-RBAC-01` | L0 | legacy_index | bos://capability/evaluator 及其子域工具，拒绝任何 role != evaluator 的请求 |
| `CR-VIBEOPS-01` | L0 | legacy_index | 混合裁判测试用例必须使用 @pytest.mark.vibeops 隔离 |
| `CR-VIBEOPS-02` | L0 | legacy_index | DeepEval/Ragas 等 LLM 裁判调用必须走 Agora LLM Gateway 进行计费与路由 |
| `CR-X1-AGENT-AUDIT` | meta | audit_chain | agent 编辑经 MCP/omo CLI, 自动记 AppendOnlyLog (可追溯) |
| `CS-10` | L0 | legacy_index | BOS URI 路由表注册必须提供 domain 和 cross_references.realized_by 元数据 |
| `X1-ARCH-MERGE-LLMGATEWAY-20260616` | meta | legacy_index | 将独立项目 projects/llm-gateway/ 的代码与能力迁移到 projects/aetherforge/packages/gateway/，作为 AetherForge 三位一体 （gateway / mesh / sw... |
| `X1-AUD-COMMIT-LOOP` | meta | legacy_index | mof-version.yaml 中每条 history entry 必须有对应的 git commit 在同一会话内。 P59 治理闭环修复后, 此规则持续维护。 检测: 反向校验最近 N 个 mof-version history... |
| `X1-C01` | L0 | legacy_index | 所有跨层协议映射必须在 L0 Protocol Registry 中注册 |
| `X1-C02` | L0 | legacy_index | 跨层 MCP 调用必须经过 I0/Agora 路由 |
| `X1-C03` | L0 | legacy_index | Agora register 是唯一写操作入口 |
| `X1-CROSS-PROJECT-LINT-ENFORCE-20260620` | meta | legacy_index | 所有子项目 (kairon/agora/cockpit/runtime/omo/metaos/aetherforge/c2g/ecos) 的 ruff check 必须保持 0 errors。`omo governance` 通过 k... |
| `X1-DEBT-EVIDENCE-CLOSURE-20260620` | meta | legacy_index | 所有 closed 状态的 DEBT yaml 必须携带 ≥ 20 字符的 resolution_evidence 字段； 所有 deferred 状态的 DEBT yaml 必须携带 next_review_at + gate_le... |
| `X1-OMNI-BUS-ROUTING-20260617` | meta | legacy_index | 全系统内异步任务、事件派发、日志埋点必须通过 Omni-Bus (bos://capability/bus/*) 进行投递。 所有旧式的自定义消息队列、直接文件写入日志、硬编码定时器应逐步废弃并迁移至三大 Facade 切面 (dat... |
| `X1-OMO-DIRECT-MUTATION-GATE-20260617` | meta | legacy_index | `.omo/` 与 `spaces/` 的文件系统改写必须通过 OMO 内核、C2G ingress 或等价受审计 broker 完成。非 broker Python 代码不得直接 write_text、 open(..., "w")... |
| `X1-OMO-GOVERNANCE-SURFACES-20260616` | meta | legacy_index | `.omo/` 只能被视为治理状态面；`projects/omo/` 是治理执行内核； `projects/c2g/` 是战略入口。所有 `.omo` 顶层资产必须登记， 所有上游任务导入必须通过 c2g/omo 契约收口。
 |

#### X2 抗熵 (25 条)

| 规则 ID | 层 | 检查类型 | 描述 |
|---------|:--:|---------|------|
| `CR-CROSS-PROJECT-LINT-01` | L0 | legacy_index | 所有子项目 (kairon/agora/cockpit/runtime/omo/metaos/aetherforge/c2g/ecos) 的
ruff check 必须保持 0 errors。P43 R5 baseline 已确立。任... |
| `CR-ENG-SSOT-POINTER-01` | L0 | legacy_index | 易变值 (health_score / phase / task_count) 禁硬编码多处, 必须用 SSOT 指针.
真源: .omo/state/system.yaml (health) / goals/current.yaml... |
| `CR-GOV-DOC-CATEGORY-01` | L0 | legacy_index | 文档 4 类生命周期 (ssot/contract/pattern/history)。
.omo/ 文档必须按 4 类分类, status 必填 (active/deprecated/archived/experimental)。
历... |
| `CR-GOV-FRONTMATTER-SCHEMA-01` | L0 | legacy_index | frontmatter 4 字段契约。
.omo/_knowledge/ 任何 .md 必须含 status + lifecycle + owner + last-reviewed 4 字段。
P56 100% 覆盖是基础, 新文件必... |
| `CR-L1-RUNTIME-HEALTH` | L1 | freshness | runtime 健康监控数据新鲜 (不超 24h, X2 抗熵) |
| `CR-X2-GAC-BOOTSTRAP` | meta | drift_audit | GaC 治一切, GaC 自己也要被治 (NORTH-STAR 元治理递归); bin/gac-bootstrap.py 检测 4 层: 工具活/死 + indexed source_ref 完整 + executor 执行有效 + ... |
| `CR-X2-GAC-DRIFT` | meta | drift_audit | 防 GaC 自己走偏: 注册表规则 vs hook/mcp/gate 实际注册, drift 告警 + 自愈 |
| `CR-X2-GAC-EXEC-DRIFT` | meta | drift_audit | GaC 规则声明 executor (ci_gate/omo_audit/evidence_smoke 等), 验证实际存在 (文件/命令/CI workflow); bin/gac-executor.py 检测 missing ex... |
| `X2-C01` | L0 | legacy_index | 协议版本必须声明——未版本化协议不可进入注册表 |
| `X2-C02` | L0 | legacy_index | 协议版本超过 2 个 MAJOR 版本应触发升级审查 |
| `X2-C03` | L0 | legacy_index | CLAUDE.md 超过 60 天未更新应触发保鲜告警 |
| `X2-C04` | L0 | legacy_index | 协议引入超过 half_life_days 后应触发老化审查 |
| `X2-C05` | L0 | legacy_index | omo governance surfaces registry 超过 14 天未复核应触发保鲜告警 |
| `X2-FRESH-ADR-DRIFT` | meta | legacy_index | P96 ADR drift 持续监督 (15 P50+ issues 待清, threshold 30 天) |
| `X2-FRESH-ARCHIVED-LLMGATEWAY` | meta | legacy_index | llm-gateway 已归档，禁止产生新的活跃任务 |
| `X2-FRESH-COMMIT-FATIGUE` | meta | legacy_index | 工作树累积预警 (commit fatigue detector) |
| `X2-FRESH-CROSS-PROJECT-LINT` | meta | legacy_index | 全子项目 ruff 0 errors 7 天巡检 |
| `X2-FRESH-DEBT-EVIDENCE-INTEGRITY` | meta | legacy_index | DEBT closure evidence 完整性 14 天巡检 |
| `X2-FRESH-DOC-LIFECYCLE` | meta | legacy_index | 文档生命周期健康度必须持续维护 |
| `X2-FRESH-EVIDENCE-ALIAS` | meta | legacy_index | evidence 兼容别名必须持续收敛 |
| `X2-FRESH-GOV-DASHBOARD` | meta | legacy_index | P91 governance-dashboard cron 持续运行监控 (确保 7 天内 dashboard 跑过) |
| `X2-FRESH-MERGE-CHECKLIST` | meta | legacy_index | MERGE-CHECKLIST 必须按计划推进 |
| `X2-FRESH-MOF-VERSION-BUMP` | meta | legacy_index | MOF 模型版本变更 30 天巡检 |
| `X2-FRESH-OMO-GOVERNANCE-SURFACES` | meta | legacy_index | OMO 三层治理契约必须持续保鲜 |
| `X2-FRESH-OMO-LINT-SIZE` | meta | legacy_index | P90 omo_lint.py 抗 god-module 拆解监控 (P89-A 待拆 schemas 432L) |

#### X3 价值 (20 条)

| 规则 ID | 层 | 检查类型 | 描述 |
|---------|:--:|---------|------|
| `CR-ENG-SRP-INCREMENTAL-01` | L0 | legacy_index | God Module (>1000 行) 拆分必须渐进: 低风险先 (纯函数/paths/trail), 核心后 (task lifecycle).
每步验证 (import + test) 才下一步 — 地基不过别盖楼.
拆分蓝图先... |
| `CR-X3-DEBT-TIER` | L2 | value_roi | debt items 必声明 x3_tier (价值分级, 投入产出可量化) |
| `CR-X3-I0-AGORA-UPTIME` | I0 | value_roi | agora BOS 服务可用性 ≥ 99% (路由层 = 价值命脉, X3 产出) |
| `CR-X3-I0-MCP-COVERAGE` | I0 | value_roi | agora MCP 工具覆盖 ≥ 90% BOS 服务 (工具缺失 = 价值缺口, X3) |
| `CR-X3-L0-DOC-SSOT` | L0 | value_roi | doc-ssot-lint 0 冲突 (文档一致性 = 减少误导成本, X3 投入产出) |
| `CR-X3-L0-GAC-COVERAGE` | L0 | value_roi | GaC 规则覆盖 4 dimension × 5+ layer (规则缺口 = 治理盲区, X3 价值) |
| `CR-X3-L1-HEALTH-COST` | L1 | value_roi | runtime 健康监控必须有成本标记 (探针开销 ≤ 总资源 5%, X3 投入产出) |
| `CR-X3-L1-PORT-CONSOLIDATION` | L1 | value_roi | runtime 暴露端口数 ≤ 注册表上限 (每多一个端口 = +1 运维成本, X3 投入) |
| `CR-X3-L2-DEBT-VELOCITY` | L2 | value_roi | debt items 关闭速率 ≥ 新增速率 (债务不增长, X3 价值流) |
| `CR-X3-L2-LINT-CLEAN` | L2 | value_roi | 全项目 ruff check 0 错误 (代码质量 = 产出质量, X3 价值) |
| `CR-X3-L2-MYPY-CLEAN` | L2 | value_roi | kairon mypy 类型检查 0 错误 (类型安全 = 产出质量, X3 价值) |
| `CR-X3-L2-TEST-ROI` | L2 | value_roi | 每个 L2 项目测试/代码比 ≥ 0.5 (测试投入 ≤ 代码量 2x, X3 产出) |
| `CR-X3-L3-COCKPIT-COVERAGE` | L3 | value_roi | cockpit 命令覆盖 ≥ 80% L2 功能 (用户入口完整性, X3 价值) |
| `CR-X3-L3-COCKPIT-LATENCY` | L3 | value_roi | cockpit CLI 命令 P95 延迟 ≤ 2s (用户价值 = 响应速度, X3 产出) |
| `CR-X3-X-DEBT-SCORING` | X | value_roi | omo-debt 评分覆盖所有 L2 项目 (债务可量化 = 投入可决策, X3 价值) |
| `CR-X3-X-OBSERVABILITY` | X | value_roi | observability 部署覆盖所有 L2 项目 (追踪覆盖 = 价值可见, X3 产出) |
| `CR-X3-X-SUBMODULE-FRESH` | X | value_roi | submodule 滞后 ≤ 3 天 (滞后 = 价值流失, X3 投入产出) |
| `X3-C01` | L0 | legacy_index | 每个功能域应声明 value_tier |
| `X3-C02` | L0 | legacy_index | value_tier=1 的域应有 cost_attribution |
| `X3-C03` | L0 | legacy_index | `.omo` 状态面、`projects/omo` 内核、`projects/c2g` 入口应具备分层价值归因 |

#### X4 一致性 (58 条)

| 规则 ID | 层 | 检查类型 | 描述 |
|---------|:--:|---------|------|
| `A2A` | L0 | legacy_index | Agent-to-Agent 任务协议— v2.0 运行时实现中 (DEC-2026-06-06-ACP-A2A) |
| `ACP` | L0 | legacy_index | Agent Communication Protocol — v2.0 运行时实现中 (DEC-2026-06-06-ACP-A2A) |
| `BOS_URI` | L0 | legacy_index | 全域 BOS URI 挂载方案 (Phase 33: DEL-006-004 进行中) |
| `CR-AUDIT-5REPOS-01` | L0 | legacy_index | 5repos.py 写入 §17 metrics 必须落到 .omo/_delivery/audit-rollout/{date}-5repos.json, 路径唯一 |
| `CR-C2G-V3-01` | L0 | legacy_index | 当含有 context_uri 的 OMO 任务流转为 done 时，必须顺着 context_uri 将执行结果追加到原始 Markdown 文档底部，防止高维降维及上下文丢失 |
| `CR-C2G-V3-02` | L0 | legacy_index | Worker GC 执行时必须触发微观碎片（FAST-* 任务）的聚变，生成统一 Markdown 报告，然后归档原始 yaml |
| `CR-C2G-V3-03` | L0 | legacy_index | 当 Agent 在执行长尾微观任务时遇到阻塞或陷入死胡同时，禁止暴力破解，必须显式调用 yield_task 工具返回原因并释放任务 |
| `CR-CADENCE-01` | L0 | legacy_index | 所有 OPC cron wrapper 必须显式注入 INVOCATION_ID + OPC_TRIGGER 环境变量, 禁止 daemon 兜底推断 |
| `CR-DEBT-GATE-ENUM-01` | L0 | legacy_index | 所有 omo debt item 的 gate_level 字段必须取自合法枚举 {gate, watchlist, none}, 禁止 X1-X4 dimension 名 (x1_audit/x2_freshness/x3_valu... |
| `CR-DRIFT-LOOP-01` | L0 | legacy_index | Drift detector 检测到非零 drift 必须生成 self-evolution task 落 planned/, 且 task approval_required=true, 永不入 active/ |
| `CR-ENG-BUG-CHAIN-01` | L0 | legacy_index | bug 修复必须治本 (消除错误路径), 禁加 fallback/workaround 层 (slop).
洋葱模型: bug 互相掩盖 (radar None 掩盖 get_omo_dir home, 后者掩盖 frontmatte... |
| `CR-ENG-CWD-ABSOLUTE-01` | L0 | legacy_index | Bash 工具调用跨项目必须用绝对路径 (防 cwd 漂移).
坑: cd projects/X 改 Bash cwd (persists across calls), 后续相对路径 (find/ls projects/Y)
相对 X... |
| `CR-ENG-LOOP-HONESTY-01` | L0 | legacy_index | Agent 元认知纪律: 同一操作反复 3+ 次不执行 → 思维循环, 必须 stop/compact.
禁: 装懂/原地反复/想跑不执行. 诚实承认上下文疲劳, 新上下文清爽执行.
这是最特殊的 CR — 防"认知坑" (非技术坑)... |
| `CR-ENG-TOOL-GREP-01` | L0 | legacy_index | 调用不熟悉的 CLI 工具前必须 grep 用法/argparse (防 --help 误触发副作用).
坑: bin/mof-version record --help 把 --help 当 description 录入 (无 --... |
| `CR-GAC-M1-INSTANCE-DRIFT-01` | meta | drift_audit | GaC 治理规则 (governance-checks.yaml::gac.rules) 必须有对应 M1 GAC-RULE-*.yaml 实例节点.
SSOT 仍在 governance-checks.yaml, M1 节点是 de... |
| `CR-GOV-DIMENSION-SATURATION-01` | L0 | legacy_index | linter 维度饱和预警。
当 omo lint 维度 ≥ 15 时, 新增能力应以独立 bin 工具形式实现, 不得再增 linter 子命令。
P57 ADR-0053 记录此铁律; P58 沿用 (check-cross-re... |
| `CR-HYG-01` | meta | hygiene_zero_byte | pre-commit 扫描 0 字节文件 (报告建议3 CR-HYG-01) |
| `CR-HYG-02` | meta | hygiene_case | pre-commit 大小写拼写一致性 (报告建议3 CR-HYG-02, APFS case-insensitive) |
| `CR-INDEX-LOCK-01` | L0 | legacy_index | 所有 *.omo/_control/evolution/{loop,drift,radar,self-evolve}/index.json 写入必须使用 fcntl.flock 互斥锁, 禁止裸 write |
| `CR-L0-PROTOCOLS-SSOT` | L0 | ssot_pointer | protocols/{port,vault-paths,x-axis}-registry.yaml 协议层 SSOT, markdown/代码禁硬编码端口号; scripts/check-vault-paths.py CI 校验 |
| `CR-L2-SURFACES-INTEGRITY` | L2 | ssot_pointer | omo-governance-surfaces.yaml 面定义权威 (plane 资产归属), GaC 引用不复制; omo governance surfaces 校验完整 |
| `CR-L2-TASK-DELIVERABLE` | L2 | task_field | OMO 任务必声明 deliverables (task-yaml-rules 规则 1) |
| `CR-L3-COCKPIT-ENTRY` | L3 | ssot_pointer | cockpit 是唯一人类 CLI/Web 入口 (其他 CLI 程序接口, X4 一致) |
| `CR-M0-STAGE-GATE` | M0 | mof_stage_gate | M1→M2→M3 派生必走 mof Stage/Gate (零风险派生) |
| `CR-MODE-COPY-01` | L0 | legacy_index | {date}-{mode}.json 副本必须由唯一 owner 脚本 (5repos.py) 写入, daemon 不得双写 |
| `CR-MODE-ENV-01` | L0 | legacy_index | OPC 模式 (weekly/monthly/pre-release) 必须通过 OPC_MODE env 透传, 禁止 daemon 内部硬编码 mode-specific 路径 |
| `CR-MOF-ALIAS-01` | L0 | legacy_index | M1 节点 type 字段必须命中 M2 m2_type, 容许 PascalCase / snake_case / section key 双向 alias, 但禁止 type 在 M2 中完全缺 |
| `CR-MOF-BIDIR-01` | L0 | legacy_index | M2 requiredProperties 字段必须出现在 M1 节点的 properties 或 top-level, 校验脚本双向查找避免历史节点字段位置不一致导致的虚报 |
| `CR-MOF-BRIDGE-01` | L0 | legacy_index | 任何 M1 lifecycle/ 节点新增/修改后必跑 mof-bridge-sync.py --strict, 验证 model-driven STANDARD_STAGES/STANDARD_GATES ↔ M1 lifecycl... |
| `CR-MOF-STATE-BRIDGE-01` | L0 | legacy_index | 任何 M1 omo_layer/OMOTASK-*.yaml 节点新增/修改后必跑 mof-state-bridge.py --strict, 验证 .omo/tasks/{active,planned,done}/*.yaml ↔ ... |
| `CR-MOF-VALIDATE-01` | L0 | legacy_index | 任何 M1 节点新增/修改后必跑 mof-schema-validate.py 校验, 0 drift / 0 missing / 0 state machine invalid 才能 commit |
| `CR-MOF-VERSION-COUPLED-01` | L0 | legacy_index | MOF 模型版本变更必须同步 (a) commit message 含 governance_refs (b) mof-version.yaml
更新 (c) bin/mof-version record (d) mof-extrac... |
| `CR-OMNIBUS-01` | L0 | legacy_index | 所有基于 bus-foundation 的跨域消息必须使用统一的 OmniEnvelope 格式，禁止隐式投递和私有格式。 |
| `CR-OMNIBUS-02` | L0 | legacy_index | Control Plane 的所有执行任务必须落入 SQLite WAL 持久化队列表 (control_tasks)，并要求显式 ACK/NACK，达到重试上限进入 DLQ。 |
| `CR-OMNIBUS-03` | L0 | legacy_index | Data Plane (日志、遥测、观测) 必须采用无锁异步内存队列 (Ring Buffer) 分发，满载时 Drop-Tail，绝对禁止阻塞主业务逻辑。 |
| `CR-STRATEGY-01` | L0 | legacy_index | 所有的 Pitch 下注转化为 Task 时，必须声明 Upstream 锚点 (如 Target Milestone)。omo_bridge 必须进行解析，无 Upstream 的需求直接阻断。 |
| `CR-STRATEGY-02` | L0 | legacy_index | 愿景必须提供 3 个维度的 Vector，所有的 Pitch 下注时，必须携带 Vector 权重。以对抗偏离。 |
| `CR-STRATEGY-03` | L0 | legacy_index | Sandbox 中的 Pitch 超过 4 周未被端上下注桌 (Bet)，将由 daemon 或 cron 自动挪入 decayed/ 归档。 |
| `CR-TIME-ENV-01` | L0 | legacy_index | OPC 生成的语义时间戳 (generated_at/today) 必须可通过 OPC_GENERATED_AT / OPC_TODAY env 覆盖, 禁止仅用 datetime.now() |
| `CR-TRIGGER-01` | L0 | legacy_index | 所有异步触发机制必须在 L0 Trigger Registry 注册为 M1 节点 |
| `CR-TRIGGER-02` | L0 | legacy_index | 所有触发机制必须通过标准五步 Pipeline (pre-check → execute → post-validate → audit → heal) |
| `CR-TRIGGER-03` | L0 | legacy_index | 触发机制之间的依赖必须显式声明在 dependencies 字段 |
| `CR-TRIGGER-04` | L0 | legacy_index | 每次触发执行必须记录审计日志 |
| `CR-TRIGGER-05` | L0 | legacy_index | 触发机制必须有 health_check 或 freshness 指标 |
| `CR-TRIGGER-06` | L0 | legacy_index | Trigger 必须有 M0 运行时快照 (TriggerM0Manager) |
| `CR-X4-ADR-LINKS` | L2 | doc_lifecycle | ADR INDEX.md 引用的所有 ADR 文件必须存在 (omo_audit 检查 #4) |
| `CR-X4-DOC-SSOT` | meta | ssot_pointer | markdown 禁硬编码 (包数/版本/Phase/健康分), 引用 docs/project-registry.yaml (bin/doc-ssot-lint.py 扫描) |
| `CR-X4-HEALTH-SSOT` | L2 | ssot_pointer | health_score 唯一源 system.yaml, 文档用指针不复制 |
| `CR-X4-TEST-COVERAGE` | L2 | test_coverage | 每个非归档 kairon 包至少 1 个 test_*.py (omo_audit 检查 #2) |
| `L0_YAML` | L0 | legacy_index | L0 协议约束 YAML 格式 |
| `MCP` | L0 | legacy_index | Model Context Protocol — 工具协议 (cockpit/agora 活跃使用中) |
| `X4-C01` | L0 | legacy_index | `.omo` INDEX、governance standard、registry、`projects/omo` 路径常量必须口径一致 |
| `X4-C02` | L0 | legacy_index | 由 `projects/c2g` 物化的 planned task 应携带 governance_refs |
| `X4-CONS-DEBT-GITIGNORE-BOUNDARY` | meta | legacy_index | .omo/debt/ 整目录在 .gitignore 中, yaml 状态不进入 git history; 但治理审计必须保持可达。审计留痕路径: (a) OMO runtime: .omo/debt/items/*.yaml (li... |
| `X4-CONS-DRIFT-VS-GOVERNANCE` | meta | legacy_index | 漂移 vs 治理评分一致性 |
| `X4-CONS-LLMGATEWAY-ARCHIVED` | meta | legacy_index | 自 2026-06-16 起，llm-gateway 能力已并入 aetherforge/packages/gateway/。 所有文档、MOF 节点、BOS 路由、依赖声明必须保持一致。
 |
| `X4-CONS-OMO-GOVERNANCE-SURFACES` | meta | legacy_index | `.omo` 顶层目录分类、`projects/omo` 路径常量、`projects/c2g` 产物治理引用 必须共享同一套目录治理口径，禁止文档、内核、入口三套说法。
 |
| `X4-CONS-P43-CLOSED-LOOP-SSOT` | meta | legacy_index | P43 (2026-06-20) 收口的 c2g → omo → mof 闭环链路在以下 4 处必须口径一致: (a) Pitch 入口: c2g brainstorm / runtime/sandbox/pitches/*.md (... |

<!-- GaC-RULES-END -->
