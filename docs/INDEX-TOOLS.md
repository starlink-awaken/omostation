# INDEX-TOOLS.md — 治理工具统一目录

> **维护规则**
> - owner: governance-team
> - trigger: 新增 bin/ 工具 / 新增脚本 / 新增 skill
> - method: 脚本生成 (bin/ssot/gen-tools-index.py)
> - validation: 工具数与实际扫描结果一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: 2026-08-04T11:05:52.940066+00:00

---


---

## 0. Cockpit CLI 顶层命令 (L3 入口)

> 从 `projects/cockpit/src/cockpit/cli.py` 解析。人类/Agent 统一入口。
> 接入说明：`docs/operations/external-agent-attach-card.md`

| 命令 | 调用 |
|------|------|
| `research` | `uv run --project projects/cockpit cockpit research --help` |
| `import` | `uv run --project projects/cockpit cockpit import --help` |
| `status` | `uv run --project projects/cockpit cockpit status --help` |
| `readiness` | `uv run --project projects/cockpit cockpit readiness --help` |
| `omo` | `uv run --project projects/cockpit cockpit omo --help` |
| `debt` | `uv run --project projects/cockpit cockpit debt --help` |
| `score` | `uv run --project projects/cockpit cockpit score --help` |
| `list` | `uv run --project projects/cockpit cockpit list --help` |
| `summary` | `uv run --project projects/cockpit cockpit summary --help` |
| `runtime` | `uv run --project projects/cockpit cockpit runtime --help` |
| `demo` | `uv run --project projects/cockpit cockpit demo --help` |
| `gac` | `uv run --project projects/cockpit cockpit gac --help` |
| `daily` | `uv run --project projects/cockpit cockpit daily --help` |
| `data` | `uv run --project projects/cockpit cockpit data --help` |
| `index` | `uv run --project projects/cockpit cockpit index --help` |
| `types` | `uv run --project projects/cockpit cockpit types --help` |
| `gc` | `uv run --project projects/cockpit cockpit gc --help` |
| `contracts` | `uv run --project projects/cockpit cockpit contracts --help` |
| `validate` | `uv run --project projects/cockpit cockpit validate --help` |
| `export-research` | `uv run --project projects/cockpit cockpit export-research --help` |
| `export` | `uv run --project projects/cockpit cockpit export --help` |
| `identity` | `uv run --project projects/cockpit cockpit identity --help` |
| `event` | `uv run --project projects/cockpit cockpit event --help` |
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
| `get` | `uv run --project projects/cockpit cockpit get --help` |
| `search` | `uv run --project projects/cockpit cockpit search --help` |
| `serve` | `uv run --project projects/cockpit cockpit serve --help` |
| `vault` | `uv run --project projects/cockpit cockpit vault --help` |
| `domains` | `uv run --project projects/cockpit cockpit domains --help` |
| `skill` | `uv run --project projects/cockpit cockpit skill --help` |
| `health` | `uv run --project projects/cockpit cockpit health --help` |
| `brief` | `uv run --project projects/cockpit cockpit brief --help` |
| `discover` | `uv run --project projects/cockpit cockpit discover --help` |
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
| `ask` | `uv run --project projects/cockpit cockpit ask --help` |
| `remember` | `uv run --project projects/cockpit cockpit remember --help` |
| `history` | `uv run --project projects/cockpit cockpit history --help` |
| `gbrain` | `uv run --project projects/cockpit cockpit gbrain --help` |
| `kairon` | `uv run --project projects/cockpit cockpit kairon --help` |
| `bus` | `uv run --project projects/cockpit cockpit bus --help` |
| `topics` | `uv run --project projects/cockpit cockpit topics --help` |
| `metrics` | `uv run --project projects/cockpit cockpit metrics --help` |
| `publish` | `uv run --project projects/cockpit cockpit publish --help` |
| `observe` | `uv run --project projects/cockpit cockpit observe --help` |
| `up` | `uv run --project projects/cockpit cockpit up --help` |
| `down` | `uv run --project projects/cockpit cockpit down --help` |
| `logs` | `uv run --project projects/cockpit cockpit logs --help` |
| `url` | `uv run --project projects/cockpit cockpit url --help` |
| `family-hub` | `uv run --project projects/cockpit cockpit family-hub --help` |
| `api` | `uv run --project projects/cockpit cockpit api --help` |
| `mesh` | `uv run --project projects/cockpit cockpit mesh --help` |
| `nodes` | `uv run --project projects/cockpit cockpit nodes --help` |
| `route` | `uv run --project projects/cockpit cockpit route --help` |
| `bos` | `uv run --project projects/cockpit cockpit bos --help` |
| `resolve` | `uv run --project projects/cockpit cockpit resolve --help` |
| `read` | `uv run --project projects/cockpit cockpit read --help` |
| `inbox` | `uv run --project projects/cockpit cockpit inbox --help` |
| `pending` | `uv run --project projects/cockpit cockpit pending --help` |
| `watch` | `uv run --project projects/cockpit cockpit watch --help` |
| `archive` | `uv run --project projects/cockpit cockpit archive --help` |
| `capability` | `uv run --project projects/cockpit cockpit capability --help` |
| `invoke` | `uv run --project projects/cockpit cockpit invoke --help` |
| `scenario` | `uv run --project projects/cockpit cockpit scenario --help` |
| `radar` | `uv run --project projects/cockpit cockpit radar --help` |
| `assistant` | `uv run --project projects/cockpit cockpit assistant --help` |
| `workflow` | `uv run --project projects/cockpit cockpit workflow --help` |
| `agent-workflow` | `uv run --project projects/cockpit cockpit agent-workflow --help` |
| `agent` | `uv run --project projects/cockpit cockpit agent --help` |
| `agent-onboard` | `uv run --project projects/cockpit cockpit agent-onboard --help` |
| `agent-runtime` | `uv run --project projects/cockpit cockpit agent-runtime --help` |
| `iterate` | `uv run --project projects/cockpit cockpit iterate --help` |
| `compass` | `uv run --project projects/cockpit cockpit compass --help` |
| `wave2` | `uv run --project projects/cockpit cockpit wave2 --help` |
| `monitor` | `uv run --project projects/cockpit cockpit monitor --help` |
| `code` | `uv run --project projects/cockpit cockpit code --help` |
| `analyze` | `uv run --project projects/cockpit cockpit analyze --help` |
| `graph` | `uv run --project projects/cockpit cockpit graph --help` |
| `pack` | `uv run --project projects/cockpit cockpit pack --help` |
| `impact` | `uv run --project projects/cockpit cockpit impact --help` |
| `onboarding` | `uv run --project projects/cockpit cockpit onboarding --help` |
| `compute` | `uv run --project projects/cockpit cockpit compute --help` |
| `knowledge` | `uv run --project projects/cockpit cockpit knowledge --help` |
| `stats` | `uv run --project projects/cockpit cockpit stats --help` |
| `kems` | `uv run --project projects/cockpit cockpit kems --help` |
| `scan` | `uv run --project projects/cockpit cockpit scan --help` |
| `c2g` | `uv run --project projects/cockpit cockpit c2g --help` |
| `pipeline` | `uv run --project projects/cockpit cockpit pipeline --help` |

**合计**: 110 个顶层命令

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
| bdsk-virtual-board | bdsk virtual board |
| bos-contract-fix | bos contract fix |
| bos-service-discovery | bos service discovery |
| ci-red-triage | ci red triage |
| ecos-test-cycle | ecos test cycle |
| external-agent-attach | external agent attach |
| governance-phase-orchestrator | governance phase orchestrator |
| governance-ssot-edit | governance ssot edit |
| omo-audit-baseline | omo audit baseline |
| project-governance | project governance |
| system-index-distill | system index distill |
| workflow-silence-detection | workflow silence detection |
| worktree-ci-isolate | worktree ci isolate |

---

## 说明

> 工具清单由脚本自动生成，完整目录请见 `bin/README.md`
> 
> 工具使用示例请见各项目 `AGENTS.md`
> 
> 通用开发命令请见根 `AGENTS.md` §5
