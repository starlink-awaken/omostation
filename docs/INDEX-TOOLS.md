---
status: active
lifecycle: generated
owner: governance-team
last-reviewed: 2026-09-24
---

# INDEX-TOOLS.md — 治理工具统一目录

> **维护规则**
> - owner: governance-team
> - trigger: 新增 bin/ 工具 / 新增脚本 / 新增 skill
> - method: 脚本生成 (bin/ssot/gen-tools-index.py)
> - validation: 工具数与实际扫描结果一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: 2026-09-24T12:01:19.693728+00:00

---


---

## 0. Cockpit CLI 顶层命令 (L3 入口)

> 从 `projects/cockpit/src/cockpit/_subcommands.py` 解析 (T6-10 起注册由 cli.py 拆出; cli.py 仅回退)。人类/Agent 统一入口。
> 接入说明：`docs/operations/external-agent-attach-card.md`

| 命令 | 调用 |
|------|------|
| `import` | `uv run --project projects/cockpit cockpit import --help` |
| `status` | `uv run --project projects/cockpit cockpit status --help` |
| `org-relation` | `uv run --project projects/cockpit cockpit org-relation --help` |
| `readiness` | `uv run --project projects/cockpit cockpit readiness --help` |
| `omo` | `uv run --project projects/cockpit cockpit omo --help` |
| `resident` | `uv run --project projects/cockpit cockpit resident --help` |
| `bcos` | `uv run --project projects/cockpit cockpit bcos --help` |
| `debt` | `uv run --project projects/cockpit cockpit debt --help` |
| `runtime` | `uv run --project projects/cockpit cockpit runtime --help` |
| `demo` | `uv run --project projects/cockpit cockpit demo --help` |
| `gac` | `uv run --project projects/cockpit cockpit gac --help` |
| `daily` | `uv run --project projects/cockpit cockpit daily --help` |
| `data` | `uv run --project projects/cockpit cockpit data --help` |
| `memory-distill` | `uv run --project projects/cockpit cockpit memory-distill --help` |
| `audit-ledger` | `uv run --project projects/cockpit cockpit audit-ledger --help` |
| `fabric-mesh` | `uv run --project projects/cockpit cockpit fabric-mesh --help` |
| `contracts` | `uv run --project projects/cockpit cockpit contracts --help` |
| `dashboard` | `uv run --project projects/cockpit cockpit dashboard --help` |
| `help` | `uv run --project projects/cockpit cockpit help --help` |
| `quickstart` | `uv run --project projects/cockpit cockpit quickstart --help` |
| `init` | `uv run --project projects/cockpit cockpit init --help` |
| `profile` | `uv run --project projects/cockpit cockpit profile --help` |
| `product-health` | `uv run --project projects/cockpit cockpit product-health --help` |
| `audit` | `uv run --project projects/cockpit cockpit audit --help` |
| `mcp` | `uv run --project projects/cockpit cockpit mcp --help` |
| `gongwen` | `uv run --project projects/cockpit cockpit gongwen --help` |
| `finance` | `uv run --project projects/cockpit cockpit finance --help` |
| `governance` | `uv run --project projects/cockpit cockpit governance --help` |
| `context` | `uv run --project projects/cockpit cockpit context --help` |
| `cards` | `uv run --project projects/cockpit cockpit cards --help` |
| `vault` | `uv run --project projects/cockpit cockpit vault --help` |
| `domains` | `uv run --project projects/cockpit cockpit domains --help` |
| `domain-status` | `uv run --project projects/cockpit cockpit domain-status --help` |
| `facts-audit` | `uv run --project projects/cockpit cockpit facts-audit --help` |
| `facts-validation` | `uv run --project projects/cockpit cockpit facts-validation --help` |
| `model-freshness` | `uv run --project projects/cockpit cockpit model-freshness --help` |
| `sanyi-status` | `uv run --project projects/cockpit cockpit sanyi-status --help` |
| `controller-shadow` | `uv run --project projects/cockpit cockpit controller-shadow --help` |
| `skill` | `uv run --project projects/cockpit cockpit skill --help` |
| `health` | `uv run --project projects/cockpit cockpit health --help` |
| `brief` | `uv run --project projects/cockpit cockpit brief --help` |
| `search` | `uv run --project projects/cockpit cockpit search --help` |
| `discover` | `uv run --project projects/cockpit cockpit discover --help` |
| `capabilities` | `uv run --project projects/cockpit cockpit capabilities --help` |
| `events` | `uv run --project projects/cockpit cockpit events --help` |
| `version` | `uv run --project projects/cockpit cockpit version --help` |
| `tui` | `uv run --project projects/cockpit cockpit tui --help` |
| `bos-capability` | `uv run --project projects/cockpit cockpit bos-capability --help` |
| `bos-inbox` | `uv run --project projects/cockpit cockpit bos-inbox --help` |
| `events-watch` | `uv run --project projects/cockpit cockpit events-watch --help` |
| `quickstart-check` | `uv run --project projects/cockpit cockpit quickstart-check --help` |
| `ssb` | `uv run --project projects/cockpit cockpit ssb --help` |
| `mof` | `uv run --project projects/cockpit cockpit mof --help` |
| `agora` | `uv run --project projects/cockpit cockpit agora --help` |
| `model-driven` | `uv run --project projects/cockpit cockpit model-driven --help` |
| `brain` | `uv run --project projects/cockpit cockpit brain --help` |
| `gbrain` | `uv run --project projects/cockpit cockpit gbrain --help` |
| `kairon` | `uv run --project projects/cockpit cockpit kairon --help` |
| `bus` | `uv run --project projects/cockpit cockpit bus --help` |
| `observe` | `uv run --project projects/cockpit cockpit observe --help` |
| `family-hub` | `uv run --project projects/cockpit cockpit family-hub --help` |
| `mesh` | `uv run --project projects/cockpit cockpit mesh --help` |
| `spine` | `uv run --project projects/cockpit cockpit spine --help` |
| `dlp-guard` | `uv run --project projects/cockpit cockpit dlp-guard --help` |
| `render` | `uv run --project projects/cockpit cockpit render --help` |
| `im-triage` | `uv run --project projects/cockpit cockpit im-triage --help` |
| `bos` | `uv run --project projects/cockpit cockpit bos --help` |
| `channels` | `uv run --project projects/cockpit cockpit channels --help` |
| `swarm` | `uv run --project projects/cockpit cockpit swarm --help` |
| `scenario` | `uv run --project projects/cockpit cockpit scenario --help` |
| `workflow` | `uv run --project projects/cockpit cockpit workflow --help` |
| `agent-workflow` | `uv run --project projects/cockpit cockpit agent-workflow --help` |
| `agent` | `uv run --project projects/cockpit cockpit agent --help` |
| `agent-onboard` | `uv run --project projects/cockpit cockpit agent-onboard --help` |
| `agent-runtime` | `uv run --project projects/cockpit cockpit agent-runtime --help` |
| `iterate` | `uv run --project projects/cockpit cockpit iterate --help` |
| `compass` | `uv run --project projects/cockpit cockpit compass --help` |
| `wave2` | `uv run --project projects/cockpit cockpit wave2 --help` |
| `bdsk` | `uv run --project projects/cockpit cockpit bdsk --help` |
| `calendar` | `uv run --project projects/cockpit cockpit calendar --help` |
| `voice-memo` | `uv run --project projects/cockpit cockpit voice-memo --help` |
| `strategy` | `uv run --project projects/cockpit cockpit strategy --help` |
| `journey` | `uv run --project projects/cockpit cockpit journey --help` |
| `panorama` | `uv run --project projects/cockpit cockpit panorama --help` |
| `project` | `uv run --project projects/cockpit cockpit project --help` |
| `monitor` | `uv run --project projects/cockpit cockpit monitor --help` |
| `code` | `uv run --project projects/cockpit cockpit code --help` |
| `compute` | `uv run --project projects/cockpit cockpit compute --help` |
| `ask` | `uv run --project projects/cockpit cockpit ask --help` |
| `proxy-env` | `uv run --project projects/cockpit cockpit proxy-env --help` |
| `knowledge` | `uv run --project projects/cockpit cockpit knowledge --help` |
| `memory` | `uv run --project projects/cockpit cockpit memory --help` |
| `kems` | `uv run --project projects/cockpit cockpit kems --help` |
| `c2g` | `uv run --project projects/cockpit cockpit c2g --help` |
| `intent` | `uv run --project projects/cockpit cockpit intent --help` |
| `decide` | `uv run --project projects/cockpit cockpit decide --help` |
| `challenge` | `uv run --project projects/cockpit cockpit challenge --help` |
| `cartridge` | `uv run --project projects/cockpit cockpit cartridge --help` |
| `cell` | `uv run --project projects/cockpit cockpit cell --help` |
| `fabric` | `uv run --project projects/cockpit cockpit fabric --help` |
| `watchdog` | `uv run --project projects/cockpit cockpit watchdog --help` |
| `policy` | `uv run --project projects/cockpit cockpit policy --help` |
| `ops` | `uv run --project projects/cockpit cockpit ops --help` |
| `system` | `uv run --project projects/cockpit cockpit system --help` |
| `scene` | `uv run --project projects/cockpit cockpit scene --help` |
| `user` | `uv run --project projects/cockpit cockpit user --help` |
| `telemetry` | `uv run --project projects/cockpit cockpit telemetry --help` |
| `completion` | `uv run --project projects/cockpit cockpit completion --help` |
| `docs` | `uv run --project projects/cockpit cockpit docs --help` |

**合计**: 109 个顶层命令

关键通道：`bos` · `bos list --all` · `channels` · `kems` · `agent-onboard` · `mcp` · `agent-workflow`
## 工具分类目录

### 1. GaC 治理即代码 (bin/gac/)

| 工具 | 功能 | 调用方式 |
|:-----|:-----|:---------|
| gac-validate.py | 规则结构校验 | `python3 bin/gac/gac-validate.py --gate` |
| gac-drift.py | 声明 vs 实际 drift 检测 | `python3 bin/gac/gac-drift.py` |
| gac-local-gate.py | 本地 gate (CI 入口) | `make gac-local-gate` |
| gac-healthcheck.py | 体系健康 (元治理递归自检) | `python3 bin/gac/gac-healthcheck.py` |
| gac-hygiene-check.py | 工作区卫生 | `python3 bin/gac/gac-hygiene-check.py` |
| gac-executor.py | executor 注册 drift | `python3 bin/gac/gac-executor.py` |
| gac-bootstrap.py | GaC 自举 (4 层检测) | `python3 bin/gac/gac-bootstrap.py` |
| gac-export-agents.py | 生成 agent-gac-rules digest | `python3 bin/gac/gac-export-agents.py` |
| gac-m1-sync.py | GaC 规则 ↔ M1 实例同步 | `python3 bin/gac/gac-m1-sync.py` |
| gac-mof-validate.py | MOF 视角 GaC 校验 | `python3 bin/gac/gac-mof-validate.py` |
| gac-gc.py | 规则垃圾回收 | `python3 bin/gac/gac-gc.py` |
| gac-daemon.py | 后台 drift 监控 | `python3 bin/gac/gac-daemon.py` |
| gac-dashboard.py | GaC 仪表盘数据 | `python3 bin/gac/gac-dashboard.py` |
| gac-hook-pre-edit.py | 编辑前 hook | `python3 bin/gac/gac-hook-pre-edit.py` |
| gac-ingest-legacy.py | legacy 规则摄入 | `python3 bin/gac/gac-ingest-legacy.py` |

### 2. ADR 治理 (bin/adr/)

| 工具 | 功能 | 调用方式 |
|:-----|:-----|:---------|
| adr-coverage.py | ADR 编号连续性 + INDEX 一致 | `python3 bin/adr/adr-coverage.py` |
| adr-drift-check.py | P89 R2 drift 检测 (流水线第 1 步) | `python3 bin/adr/adr-drift-check.py` |
| adr-drift-classify.py | P90 R1 drift 归类 (第 2 步) | `python3 bin/adr/adr-drift-classify.py` |
| adr-drift-auto-fix.py | P93 R1 自动修复建议 (第 3 步) | `python3 bin/adr/adr-drift-auto-fix.py` |
| adr-drift-apply.py | P94 R1 touch SUBDIR_MISSING (应用) | `python3 bin/adr/adr-drift-apply.py` |
| adr-trend-insight.py | drift 趋势洞察 | `python3 bin/adr/adr-trend-insight.py` |

### 3. SSOT 守护 (bin/ssot/)

| 工具 | 功能 | 调用方式 |
|:-----|:-----|:---------|
| doc-link-check.py | 文档链接有效性 | `python3 bin/ssot/doc-link-check.py` |
| ssot-guardian.py | task_count + workspace_hygiene 守护 | `python3 bin/ssot/ssot-guardian.py` |
| ssot-writeback.py | SSOT 回写 | `python3 bin/ssot/ssot-writeback.py` |
| check-boundary.py | 项目边界校验 | `python3 bin/ssot/check-boundary.py` |
| check-cross-refs.py | 交叉引用一致性 | `python3 bin/ssot/check-cross-refs.py` (tracked; `--scope workspace` 做全量审计) |
| doc-governance-check.py | 文档治理检查（ownership/lifecycle/freshness/discoverability；支持 warning signature baseline） | `python3 bin/ssot/doc-governance-check.py --no-new-warnings` |
| doc-governance-migrate.py | 文档元数据迁移与 review-state 批次升级 | `python3 bin/ssot/doc-governance-migrate.py --scope tracked` |
| check_health_ssot.py | health SSOT 一致 | `python3 bin/ssot/check_health_ssot.py` |
| doc-ssot-lint.py | 文档 SSOT 门禁 (CI) | `python3 bin/ssot/doc-ssot-lint.py` |
| gen-project-registry.py | registry 派生 | `python3 bin/ssot/gen-project-registry.py` |
| project-layer-index.py | layer digest | `python3 bin/ssot/project-layer-index.py` |
| gen-projects-index.py | 项目索引生成 | `python3 bin/ssot/gen-projects-index.py` |
| gen-tools-index.py | 工具索引生成 | `python3 bin/ssot/gen-tools-index.py` |
| gen-knowledge-index.py | 知识索引生成 | `python3 bin/ssot/gen-knowledge-index.py` |
| gen-agents-index.py | Agent索引生成 | `python3 bin/ssot/gen-agents-index.py` |
| gen-capability-registry.py | 三通道能力注册表 | `python3 bin/ssot/gen-capability-registry.py` |
| mcp-attach-smoke.py | 外部 agent 接入烟测 | `python3 bin/ssot/mcp-attach-smoke.py` |
| gen-external-channels-inventory.py | ECCP 外通道 inventory | `python3 bin/ssot/gen-external-channels-inventory.py` |
| check-index-drift.py | 索引漂移检测 | `python3 bin/ssot/check-index-drift.py` |

### 3.1 场景卡工具族 (bin/ssot/scene-*)

> 场景卡 (Scene Card) 全生命周期工具。卡片定义 SSOT: `docs/scene-cards/*.yaml`。
> 分工: 家族 A (卡片定义/候选/生命周期) 只读无副作用; 家族 B (决策收件箱/审批/连接/复盘) 写 `.omo`。

| 工具 | 功能 | 调用方式 |
|:-----|:-----|:---------|
| scene-card-candidates.py | 场景卡候选生成 (proposal_only) | `python3 bin/ssot/scene-card-candidates.py` |
| scene-card-intake.py | 场景卡摄入 (proposal_only) | `python3 bin/ssot/scene-card-intake.py` |
| scene-card-lifecycle.py | 场景卡生命周期管理 (激活/就绪检查) | `python3 bin/ssot/scene-card-lifecycle.py` |
| scene-chain-validator.py | 场景链校验 (journey chain 闭环) | `python3 bin/ssot/scene-chain-validator.py` |
| scene-feedback-collector.py | 场景反馈收集 (feedback loop) | `python3 bin/ssot/scene-feedback-collector.py` |
| scene-card-decision-inbox.py | 决策收件箱核心引擎 (写 .omo/_inbox) | `python3 bin/ssot/scene-card-decision-inbox.py` |
| scene-card-intake-pipeline.py | 摄入流水线 (写 .omo/_inbox) | `python3 bin/ssot/scene-card-intake-pipeline.py` |
| scene-card-approval-flow.py | 审批流 (pending→approved/rejected) | `python3 bin/ssot/scene-card-approval-flow.py` |
| scene-card-connector.py | 场景卡连接器 (能力接线) | `python3 bin/ssot/scene-card-connector.py` |
| scene-card-task-bridge.py | 任务桥接 (写 .omo/_bindings) | `python3 bin/ssot/scene-card-task-bridge.py` |
| scene-card-review.py | 每周复盘统计引擎 | `python3 bin/ssot/scene-card-review.py` |
| gen-scene-card-lineage.py | 场景卡谱系生成 (N8) | `python3 bin/ssot/gen-scene-card-lineage.py` |
| external-scene-trial.py | 外部场景试运行 | `python3 bin/ssot/external-scene-trial.py` |
| internal-scene-preflight.py | 内部场景前置检查 | `python3 bin/ssot/internal-scene-preflight.py` |
| internal-scene-trial.py | 内部场景试运行 | `python3 bin/ssot/internal-scene-trial.py` |

### 4. MOF 工具 (bin/mof/)

| 工具 | 功能 | 调用方式 |
|:-----|:-----|:---------|
| mof-m2-coverage.py | M2 覆盖率 | `python3 bin/mof/mof-m2-coverage.py` |

### 5. 根目录高频工具

| 工具 | 功能 | 调用方 |
|:-----|:-----|:-------|
| agent-workflow.py | Agent Workflow Runner (framework 级) | CLAUDE/AGENTS §0 |
| compass_radar.py | health radar 计算/兼容刷新 | `omo state sync` broker |
| state-stale-emit.py | 发送 state_stale 事件 | post-commit / launchd WatchPaths |
| change-lane-check.py | commit lane 校验 (pre-commit/gac-local-gate) | GaC gate |
| commit-assist.py | 提交辅助脚本 | `python3 bin/commit-assist.py` |
| cockpit-readiness.py | Cockpit 就绪度检查 | `python3 bin/cockpit-readiness.py` |

### 6. P74 Solidification (工作流沉默治理)

| 工具 | 功能 | 对应 GaC 规则 |
|:-----|:-----|:--------------|
| omo lint projection-guard | runtime projection 路径一致性 | CR-P74-STATE-PROJECTION-GUARD |
| omo lint stamp-policy | runtime 孤儿文件治理 | CR-P74-RUNTIME-STAMP-POLICY |
| agent-workflow.py suggest | advisory 路由建议 | CR-P74-WORKFLOW-SUGGEST |
| agent-workflow.py compliance | workflow 沉默检测 | CR-P74-WORKFLOW-SILENCE |


---

## 项目级 Skills (.agents/skills/)

| Skill | 用途 |
|-------|------|
| a2a-coordination | a2a coordination |
| agent-onboarding | agent onboarding |
| agent-quickstart | agent quickstart |
| architecture-perception | architecture perception |
| bdsk-virtual-board | bdsk virtual board |
| bet-closeout-chain | bet closeout chain |
| bet-execution | bet execution |
| bos-contract-fix | bos contract fix |
| bos-service-discovery | bos service discovery |
| ci-red-triage | ci red triage |
| closeout-retro | closeout retro |
| cognitive-governance | cognitive governance |
| delegation-guardrails | delegation guardrails |
| domain-cartridge-governance | domain cartridge governance |
| ecos-test-cycle | ecos test cycle |
| external-agent-attach | external agent attach |
| git-discipline | git discipline |
| git-safety-check | git safety check |
| governance-phase-orchestrator | governance phase orchestrator |
| governance-ssot-edit | governance ssot edit |
| harness-compliance | harness compliance |
| kos-cold-start | kos cold start |
| memory-recall | memory recall |
| multica-squad-ops | multica squad ops |
| nextgen-cognitive-mesh | nextgen cognitive mesh |
| omlxc-compute-fabric | omlxc compute fabric |
| omo-audit-baseline | omo audit baseline |
| project-governance | project governance |
| round-gate-check | round gate check |
| round-workflow | round workflow |
| scene-shadow-activate | scene shadow activate |
| spine-value-pipeline | spine value pipeline |
| swarm-escape | swarm escape |
| system-index-distill | system index distill |
| workflow-silence-detection | workflow silence detection |
| workflow:bet-execution | workflow:bet execution |
| workflow:governance-state-mutation | workflow:governance state mutation |
| workflow:mini | workflow:mini |
| workflow:project-code-change | workflow:project code change |
| workflow:project-doc-change | workflow:project doc change |
| worktree-ci-isolate | worktree ci isolate |

---

## 说明

> 工具清单由脚本自动生成，完整目录请见 `bin/README.md`
> 
> 工具使用示例请见各项目 `AGENTS.md`
> 
> 通用开发命令请见根 `AGENTS.md` §5
