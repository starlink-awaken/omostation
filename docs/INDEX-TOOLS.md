# INDEX-TOOLS.md — 治理工具统一目录

> **维护规则**
> - owner: governance-team
> - trigger: 新增 bin/ 工具 / 新增脚本 / 新增 skill
> - method: 脚本生成 (bin/ssot/gen-tools-index.py)
> - validation: 工具数与实际扫描结果一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: 2026-07-14T07:22:23.779749

---

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
| check-cross-refs.py | 交叉引用一致性 | `python3 bin/ssot/check-cross-refs.py` |
| check_health_ssot.py | health SSOT 一致 | `python3 bin/ssot/check_health_ssot.py` |
| doc-ssot-lint.py | 文档 SSOT 门禁 (CI) | `python3 bin/ssot/doc-ssot-lint.py` |
| gen-project-registry.py | registry 派生 | `python3 bin/ssot/gen-project-registry.py` |
| project-layer-index.py | layer digest | `python3 bin/ssot/project-layer-index.py` |
| gen-projects-index.py | 项目索引生成 | `python3 bin/ssot/gen-projects-index.py` |
| gen-tools-index.py | 工具索引生成 | `python3 bin/ssot/gen-tools-index.py` |
| gen-knowledge-index.py | 知识索引生成 | `python3 bin/ssot/gen-knowledge-index.py` |
| gen-agents-index.py | Agent索引生成 | `python3 bin/ssot/gen-agents-index.py` |
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
| bos-contract-fix | bos contract fix |
| ci-red-triage | ci red triage |
| ecos-test-cycle | ecos test cycle |
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
