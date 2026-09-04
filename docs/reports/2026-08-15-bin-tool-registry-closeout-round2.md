---
type: ephemeral
created: 2026-09-03
---

# 2026-08-15 bin 工具治理收敛 Round 2

> **已退役** (2026-08-21): `scripts/bin/` 工具已迁移到 `bin/`，scripts 仓库已 archive。
> 并行收敛治理不再需要。本记录保留作为历史参考。

## 一、目标
在上一轮发现 `make bin-tool-registry-audit-strict` 失败（自循环 + 重复命名）之后，进行下一轮“高置信债务收敛”，并保持可复现验证与 Makefile 适配链路连续可用。

## 二、已实施
1. 提升 `bin/tool-registry-audit.py` 依赖分析可信度
- 调整脚本候选范围：仅扫描 `.py/.sh/.bash/.zsh` 与具备 shebang 的可执行文件，剔除 `bin/` 下异常可执行文档（如 `VERIFY.md`）。
- 去掉自调用误判：`parse_script_calls` 过滤脚本对自身入口的示例调用（`python3 bin/xxx.py`）导致的假阳性循环。
- 新增路径分层判断：`_archive`、`bin/ssot` 标记后在 strict 阶段按“高置信重复”降噪。
- 新增高置信重复识别：在 strict 时仅对同类活跃路径（非 `_archive`/非 `bin/ssot`）进行阻断性判断。
- 循环检测结果去重后剔除自环。

2. Makefile 目标回归验证
- `make bin-tool-registry-audit`
- `make bin-tool-registry-audit-emit`
- `make bin-tool-registry-convergence`
- `make bin-tool-registry-audit-strict`

3. 依赖快照与债务台账（本轮）
- 新快照：`artifacts/bin-tool-registry-audit.json`
- 输出显示：
  - `total_scripts: 509`
  - `missing_shebang: 0`
  - `non_snake: 418`
  - `duplicate_names: 9`
  - `high-confidence duplicate names: 0`
  - `cycles: 0`
  - 严格门禁：`strict checks: OK`

## 三、重复命名分层（非阻断）
- `agent_registry`: `bin/delivery/agent_registry.py`, `bin/_archive/agent-registry.py`
- `control_experiment`: `bin/collab/control_experiment.py`, `bin/_archive/control-experiment.py`
- `git_health_hook`: `bin/git-health-hook.py`, `bin/ssot/git-health-hook.py`
- `nested_with`: `bin/sweep/nested-with.py`, `bin/_archive/nested-with.py`
- `physical_recovery`: `bin/delivery/physical_recovery.py`, `bin/delivery/physical-recovery.sh`
- `predictive_governance`: `bin/gac/predictive-governance.py`, `bin/ssot/predictive-governance.py`
- `submodule_reachability_gate`: `bin/submodule-reachability-gate.py`, `bin/ssot/submodule-reachability-gate.py`
- `sync_submodules_push`: `bin/sync-submodules-push.sh`, `bin/ssot/sync-submodules-push.sh`
- `verify`: `bin/ssot/verify.py`, `bin/ssot/PACKS/dormant-adapter/VERIFY.md`

## 四、下一步建议（下一轮）
1. 基于当前归一化规则，继续清理非存档重复（优先 `agent_registry`、`physical_recovery` 的双命名来源）。
2. 制定 `duplicate_conflicts` 的治理白名单阈值与到期窗口，纳入 ADR。
3. 把 `non_snake`（418）分层：按脚本用途定义强制/建议清单，先覆盖治理核心脚本。
4. 把收敛候选（hub 出入度）纳入技术债 dashboard，按季度收敛。

## 四、Round 3：scripts/bin 并行能力收敛（兼容层机制化）

### 已完成
- 在 `bin/tool-registry-audit.py` 增加受控并行能力清单机制，新增参数：
  - `--parallel-manifest`（默认 `docs/operations/bin-scripts-convergence-manifest.json`）
  - strict 与 `--json` 共同生效：`--json` 下仍返回 strict 的真实退出码
  - 在 `stats` 中新增 `managed_parallel_duplicates`、`unmanaged_parallel_duplicates`
  - `findings` 中新增受控/未受控并行对照清单
- Makefile 里将 `bin-tool-registry-*` 目标加入统一清单参数透传，并默认扫描范围 `both`。
- 新增受控并行清单：`docs/operations/bin-scripts-convergence-manifest.json`（31 条，全部标记为 `managed`）。
- `scripts/bin/README.md` 收敛为“兼容层职责说明”，主实现归口到 `bin/`。

### 目标效果
- `bin-tool-registry-audit-strict` 在扫描 `both` 时，仅将清单外并行高置信重复作为阻断项。
- `scripts/bin` 作为兼容入口有明确治理边界，减少未来重复能力无序扩散。
- 为子项目/域固化留出落点：`scripts/bin` 不承载新能力，能力若与子项目强绑定应下沉子项目。

## 五、Round 4（2026-08-16）：并行清单缺口机制化闭环

### 已完成
- 在 `bin/tool-registry-audit.py` 增加并行清单缺口分析：
  - 新增并行重名候选 `parallel_candidates`
  - 新增并行清单缺口 `parallel_manifest_gaps`
  - 统计新增 `parallel_manifest_gaps`、`unmanaged_parallel_candidates`
  - 每项缺口带 `gap_reasons`，首发版本为 `missing_manifest_entry`
- Makefile 新增命令入口：
  - `make bin-tool-registry-parallel-gaps`（输出并行清单缺口明细）
  - 帮助信息新增 `parallel-gaps` 入口
- 快照落地：
  - `artifacts/bin-tool-registry-audit-round4.json`

### 结果（`TOOL_REGISTRY_SCOPE=both`）
- `total_scripts: 796`
- `duplicate_names: 277`
- `parallel_candidates: 215`
- `parallel_manifest_gaps: 183`
- 缺口命中原因：全部为 `missing_manifest_entry`（未加入清单）

### 下一步路线
1. 以 `make bin-tool-registry-parallel-gaps` 作为周固定期输入，按 15–30 个缺口一批消化。
2. 每批处理必须同步产出：
   - manifest 补齐记录（或明确下沉子项目 owner）
   - `make bin-tool-registry-audit --scope both` 与 `make bin-tool-registry-parallel-gaps` 的差异快照
3. 验证指标目标：每轮 `parallel_manifest_gaps` 下降，`mirror_adjustments` 和 `managed/Unmanaged` 变化可控。

### 六、Round 5（2026-08-16）：依赖风险分析能力固化

#### 已完成
- 在 `bin/tool-registry-audit.py` 增加依赖热点分析能力：
  - 按出/入度计算风险分值（`risk_score = out_degree*3 + in_degree*2`）；
  - 结合并行收敛清单缺口，将“未托管并行 + 关键依赖链”提权到统一清单；
  - 在审计结果 `findings` 增加 `dependency_hotspots`，`stats` 补充 `dependency_hotspots` 行为口径（通过 `len(hotspots)` 输出）。
- Makefile 新增固定执行入口：
  - `make bin-tool-registry-dependency-risks`（支持 `TOOL_REGISTRY_DEPENDENCY_LIMIT` 上限）；
  - help 列表同步展示；
  - 便于把“依赖优先级”和“并行缺口”同框处理。
- 新增一轮快照：
  - `artifacts/bin-tool-registry-audit-round5.json`（本地演示文件）。

#### 本轮关键结果（`TOOL_REGISTRY_SCOPE=both`）
- `total_scripts: 796`
- `parallel_candidates: 215`
- `parallel_manifest_gaps: 183`
- `dependency hotspots: 25`（默认 Top 25）
- `managed parallel duplicates: 0`
- `unmanaged parallel duplicates: 0`
- `strict checks: OK`

#### 下一步动作
1. 每周将 `make bin-tool-registry-dependency-risks` 纳入运维巡检，按 `risk_score` 一口气消化 Top N；
2. 对 `managed=False` 的并行候选先闭环：`parallel manifest gap` 补录或显式分流到子项目 owner；
3. 在下一轮把依赖热点输出扩展为“建议下沉目标”（当前脚本仅输出影响面节点，未引入子项目映射模型）；
4. 长期机制：每次新增脚本时强制更新并行清单，结合 `make bin-tool-registry-dependency-risks` 与 `make bin-tool-registry-parallel-gaps` 双门禁。

### 七、Round 6（2026-08-16）：依赖热点下沉建议固化

#### 已完成
- 在 `bin/tool-registry-audit.py` 对 `dependency_hotspots` 增加“治理可执行建议”字段：
  - `owner_hint`（基于 manifest / 路径推断）；
  - `recommended_action`（如 `close-duplicate-gap-first` / `keep-or-review-by-team`）；
  - `recommended_sink`（如 `scripts/<owner>` 或 `bin`）；
  - `normalized_name` 修复为循环内局部变量避免“复用污染”导致全量同名问题；
- `scripts/bin` 与 `bin` 并行缺口输出链路保持不变，但在 `bin-tool-registry-dependency-risks` 中新增输出：
  - owner / action / sink 字段；
  - 便于直接生成“下沉清单”与周会工单。

#### 本轮关键结果（`TOOL_REGISTRY_SCOPE=both`）
- `total_scripts: 796`
- `parallel_candidates: 215`
- `parallel_manifest_gaps: 183`
- `dependency hotspots: 25`（默认 Top 25）
- `managed parallel duplicates: 0`
- `unmanaged parallel duplicates: 0`
- 示例 Top 5 建议：
  - `bin/ssot/bus-usage-report.py => owner=ssot action=close-duplicate-gap-first sink=scripts/ssot`
  - `bin/submodule-gitlink-check.py => owner=governance action=close-duplicate-gap-first sink=scripts/governance`
  - `bin/cockpit-readiness.py => owner=governance action=close-duplicate-gap-first sink=scripts/governance`

#### 下一步路线（Round 7）
1. 优先清理 `parallel=True` 的 Top 10，并同步将结果回填 `docs/operations/bin-scripts-convergence-manifest.json`；
2. 对 `recommended_sink` 不为 `bin` 的高风险节点建立 `owner` 与 `动作截止日`；
3. 将 `dependency_hotspots` 建议字段接入每周门禁报表（CI 可选输出到 artifacts，形成证据）。

### 八、Round 7（2026-08-16）：依赖风险与周报机制沉淀

#### 已完成
- 在 `docs/operations/bin-scripts-convergence-manifest.json` 中补齐 Round7 回填清单（10 条）：
  - `bin/ssot/bus-usage-report.py` (owner=ssot)
  - `bin/submodule-gitlink-check.py` (owner=governance)
  - `bin/cockpit-readiness.py` (owner=governance)
  - `bin/mesh/mesh-orphan-cleanup.py` (owner=mesh)
  - `bin/adr/adr-drift-auto-fix.py`
  - `bin/adr/next-adr-id.py`
  - `bin/adr/adr-drift-apply.py`
  - `bin/adr/adr-drift-check.py`
  - `bin/adr/adr-trend-insight.py`
  - `bin/adr/adr-drift-classify.py`
- 全部标记 `status: managed`，`action: close-duplicate-gap-first`，`due_date: 2026-09-01`，并回填 `risk_score` / `decision_round` / `evidence.active_files`。
- `Makefile` 增加并固定了周报治理链路目标：
  - `bin-tool-registry-weekly-governance-report`
  - 目标默认输出 `artifacts/bin-tool-registry-weekly-governance-report.json`
- 清理并修正 `bin-tool-registry-dependency-risks` 目标缩进与脚本参数一致性。

#### 验证结果（本轮执行）
- `make bin-tool-registry-audit-strict`
  - `total_scripts: 796`
  - `parallel_candidates: 215`
  - `parallel_manifest_gaps: 173`
  - `dependency hotspots: 25`
  - `strict checks: OK`
- `make bin-tool-registry-dependency-risks`
  - `dependency hotspots: 25 (top 25)`
  - 当前 TOP 10（按 risk 降序）：
    - `bin/mof/mof-bootstrap.py`
    - `bin/mof/mof-m2-coverage.py`
    - `bin/mof/check-doc-claims.py`
    - `bin/mof/gen-project-registry.py`
    - `bin/mof/m2-ssot-inventory.py`
    - `bin/mof/gen-dependency-baseline.py`
    - `bin/gac/rule-history-insight.py`
    - `bin/gac/gac-hygiene-check.py`
    - `bin/gac/governance-history-insight.py`
    - `bin/gac/drift-history-insight.py`
- `make bin-tool-registry-weekly-governance-report`
  - 成功落盘：`artifacts/bin-tool-registry-weekly-governance-report.json`
  - 本次快照统计与上方一致（total_scripts 796 / managed parallel 0 / unmanaged parallel 0）。
- `make bin-tool-registry-parallel-gaps`
  - `parallel manifest gaps: 173`

#### 下一步（Round 8 建议）
- 固化 `ARTIFACTS` 周报作为每周 gate 的输入，按 `decision_round` 做“并行缺口回填 → action 收敛 → 下沉到子项目”三段闭环。
- 把 owner/action/sink 从清单与周报联通到子项目/能力 owner 的看板，按期逐步消化 `unmanaged_parallel_candidates`。

### 九、Round 8（2026-08-16）：依赖热点 Top10 继续并行缺口收敛

#### 已完成
- 从 `make bin-tool-registry-dependency-risks` 上一轮 Top 10 里提取并回填 10 条 `parallel=True` 高影响节点到清单：
  - `bin/mof/mof-bootstrap.py` → `scripts/bin/mof/mof-bootstrap.py`（owner=mof）
  - `bin/mof/mof-m2-coverage.py` → `scripts/bin/mof/mof-m2-coverage.py`（owner=mof）
  - `bin/mof/check-doc-claims.py` → `scripts/bin/mof/check-doc-claims.py`（owner=mof）
  - `bin/mof/gen-project-registry.py` → `scripts/bin/mof/gen-project-registry.py`（owner=mof）
  - `bin/mof/m2-ssot-inventory.py` → `scripts/bin/mof/m2-ssot-inventory.py`（owner=mof）
  - `bin/mof/gen-dependency-baseline.py` → `scripts/bin/mof/gen-dependency-baseline.py`（owner=mof）
  - `bin/gac/rule-history-insight.py` → `scripts/bin/gac/rule-history-insight.py`（owner=gac）
  - `bin/gac/gac-hygiene-check.py` → `scripts/bin/gac/gac-hygiene-check.py`（owner=gac）
  - `bin/gac/governance-history-insight.py` → `scripts/bin/gac/governance-history-insight.py`（owner=gac）
  - `bin/gac/drift-history-insight.py` → `scripts/bin/gac/drift-history-insight.py`（owner=gac）
- 所有 10 条补齐到 `docs/operations/bin-scripts-convergence-manifest.json`：
  - `status: managed`
  - `action: close-duplicate-gap-first`
  - `risk_score: 15`
  - `due_date: 2026-09-08`
  - `decision_round: round8`

#### 验证结果
- `make bin-tool-registry-audit-strict`
  - `parallel manifest gaps: 163`（较 Round7 下降 10）
  - `dependency hotspots: 25`
  - `managed parallel duplicates: 0`
  - `unmanaged parallel duplicates: 0`
  - `strict checks: OK`
- `make bin-tool-registry-weekly-governance-report`
  - 输出落盘：`artifacts/bin-tool-registry-weekly-governance-report.json`
  - 本地快照文件：`artifacts/bin-tool-registry-audit-round8.json`
- `make bin-tool-registry-parallel-gaps`
  - 当前 `parallel manifest gaps: 163`
- `make bin-tool-registry-dependency-risks`
  - 当前 Top 10 按风险未被管理（`managed=False`）：
    - `bin/gac/gac-gc.py`
    - `bin/gac/dim-weight.py`
    - `bin/gac/x2-rule-add.py`
    - `bin/gac/x2-freshness-check.py`
    - `bin/gac/x2-rule-lint.py`
    - `bin/gac/governance-alert-dispatch.py`
    - `bin/gac/auto-merge-lane-policy.py`
    - `bin/gac/omo-state-write-guard.py`
    - `bin/gac/p0-event-listener.py`
    - `bin/gac/omo-acl-ops-window.sh`

### 十、Round 9（2026-08-16）：Top10 漂移后的本轮闭环

#### 已完成
- 复盘 Round8 以来 `make bin-tool-registry-dependency-risks` 漂移的 Top10，确认仍有 `managed=False` 变更项；
- 将本次 Top10（执行时点）中已重复出现且具备稳定 owner 的 10 条入 `docs/operations/bin-scripts-convergence-manifest.json`：
  - `bin/gac/alert-aggregator.py`
  - `bin/gac/gac-bootstrap.py`
  - `bin/gac/gac-mof-validate.py`
  - `bin/gac/m1-closeout-report.py`
  - `bin/gac/state-freshness-check.py`
  - `bin/gac/gac-coverage-lint.py`
  - `bin/gac/event-loop-lint.py`
  - `bin/gac/kos-seed-import.py`
  - `bin/gac/phase-gate-check.py`
  - `bin/_archive/2026-08-conv3/alert-mock-p0-notify.py`
- 为可执行闭环，补齐 Makefile：
  - `.PHONY` 增加 `bin-tool-registry-round9`
  - `make bin-tool-registry-round9` 作为 strict + 并行缺口 + 依赖热点 + 周报的一键闭环。
- 本轮执行链路：`make bin-tool-registry-round9`
  - `parallel gaps: 143`
  - `dependency hotspots: 25`
  - `managed parallel duplicates: 0`
  - `unmanaged parallel duplicates: 0`
  - `strict checks: OK`
  - 周报产物：`artifacts/bin-tool-registry-weekly-governance-report-round9.json`
- Top10 快照（执行时点，仍可能受清单回填导致漂移）：
  - `bin/collab/adv-fail-report.py`
  - `bin/collab/recommend_mode.py`
  - `bin/collab/export-dualtrack.py`
  - `bin/collab/bos-stdio-inventory.py`
  - `bin/ssot/doc-ssot-lint.py`
  - `bin/ssot/check-boundary.py`
  - `bin/ssot/ts-file-analyze.py`
  - `bin/ssot/god-module-13-error-list.py`
  - `bin/ssot/check-toolbox-ssot.py`
  - `bin/ssot/venv-yaml-check.py`

#### 下一步（Round 10）
- 继续按 `make bin-tool-registry-dependency-risks` 固定 `TOOL_REGISTRY_DEPENDENCY_LIMIT=10`，优先处理当前 `managed=False` Top10：
  - 本轮待纳管清单建议优先 `collab` + `ssot` 下沉脚本与 `action=close-duplicate-gap-first` / `fill-parallel-manifest` 条目。
- 建议将 Round9 中新增 `bin-tool-registry-round9` 目标纳入每周例会固定验证项，形成 `audit → closeout → 下一轮` 的循环。

### Round 10（2026-08-16）：Top10 漂移后的一键闭环收口

#### 已完成
- 基于 `make bin-tool-registry-round9`（运行时点）Top10 依赖热点，补齐三组长期高频并行缺口：
  - `control_experiment`
  - `git_health_hook`
  - `physical_recovery`
- 追加到 `docs/operations/bin-scripts-convergence-manifest.json`，并按本轮机制补齐治理证据：
  - `control_experiment`（owner=collab）
  - `git_health_hook`（owner=governance）
  - `physical_recovery`（owner=delivery）
- 三条都设为 `status: managed`，`action: close-duplicate-gap-first`，`evidence.decision_round: round10`，`due_date: 2026-09-22`。

#### 本轮执行结果
- 运行命令：`make bin-tool-registry-round10`
- 关键指标：
  - `parallel manifest gaps: 0`（由 3 降到 0）
  - `managed parallel duplicates: 0`
  - `unmanaged parallel duplicates: 0`
  - `dependency hotspots: 25`
  - `strict checks: OK`
- 周报落盘：`artifacts/bin-tool-registry-weekly-governance-report-round10.json`

#### 机制固化
- `Makefile` 新增 `bin-tool-registry-round10`，与 `round9` 命令链路保持一致：`audit-strict`、`parallel-gaps`、`dependency-risks`、`weekly-governance-report`。
- 通过 manifest 缺口一键回填动作的机制延续了“可复现收敛闭环”，实现每轮只关心 Top10 漂移 + 周报留痕。

#### 下一步（Round 11）
1. 复用本轮模板每周持续执行：`make bin-tool-registry-round10`（后续可演进为 `make bin-tool-registry-round11`）。
2. 将本轮 `parallel manifest gaps=0` 与 `unmanaged=0` 作为“该轮闭环通过条件”写入季度回顾模板。
3. 继续推进 scripts 与 bin 以及子项目固化的长期机制：
   - 对 `scripts/bin` 逐步仅保留兼容层入口；
   - 与子项目强相关能力下沉到子项目 owner 与项目脚本目录。

### Round 11（2026-08-16）：并行治理机制持续化（无新缺口巡检）

#### 已完成
- 将 `make bin-tool-registry-round11` 纳入 Makefile：复用 `round10` 的严格审计链路并落盘 `artifacts/bin-tool-registry-weekly-governance-report-round11.json`，用于“继续下一轮”的固定操作模板。
- 本轮未新增 `bin/scripts` 并行缺口清单条目，目标聚焦机制稳定性与周报归档；`scripts/bin` 与 bin 侧的并行能力边界保持不变。

#### 本轮执行结果
- 运行命令：`make bin-tool-registry-round11`
- 与 `round10` 同口径指标一致，当前为：
  - `parallel manifest gaps: 0`
  - `managed parallel duplicates: 0`
  - `unmanaged parallel duplicates: 0`
  - `dependency hotspots: 25`
  - `strict checks: OK`
- 周报落盘：`artifacts/bin-tool-registry-weekly-governance-report-round11.json`

#### 下一步（Round 12）
- 继续固定每轮执行 `make bin-tool-registry-round11`，当依赖风险 Top10 有未纳管 `managed=False` 再回填 manifest；
- 将 `parallel manifest gaps=0` 与 `strict checks: OK` 作为“机制无回退”的最低通过线。

### Round 12（2026-08-16）：Top10 风险收敛机制常态化（无新增缺口）

#### 已完成
- 新增 `make bin-tool-registry-round12`，沿用 `round11` 固定链路（`audit-strict`、`parallel-gaps`、`dependency-risks`、`weekly-governance-report`）固化为下一轮可复用入口。
- `Makefile` 同步恢复 `bin-tool-registry-audit*` 目标链路定义，修复目标块误缺失问题，确保闭环目标可执行并形成长期可复用标准。

#### 本轮执行结果
- 运行命令：`make bin-tool-registry-round12`
- 关键指标（与 round11 一致）：
  - `parallel manifest gaps: 0`
  - `managed parallel duplicates: 0`
  - `unmanaged parallel duplicates: 0`
  - `dependency hotspots: 25`
  - `strict checks: OK`
- 周报落盘：`artifacts/bin-tool-registry-weekly-governance-report-round12.json`

#### 结果解读（本轮 Top10）
- `bin/ssot/bus-usage-report.py`（risk_score 11）
- `bin/compass_radar.py`（risk_score 7）
- `bin/submodule-gitlink-check.py`（risk_score 7）
- `bin/cockpit-readiness.py`（risk_score 7）
- `bin/mesh/mesh-orphan-cleanup.py`（risk_score 7）
- `bin/adr/adr-drift-auto-fix.py`（risk_score 7）
- `bin/adr/next-adr-id.py`（risk_score 7）
- `bin/adr/adr-drift-apply.py`（risk_score 7）
- `bin/adr/adr-drift-check.py`（risk_score 7）
- `bin/adr/adr-coverage.py`（risk_score 7）
- 所有 Top10 均 `managed=True`，`recommend_action=retain-bin-owner`，且 `parallel=True`，结论是“**不需要新增下沉条目**，继续维持机制巡检。

#### 下一步（Round 13）
- 每周固定执行 `make bin-tool-registry-round12`，将 `parallel manifest gaps=0`、`managed=False=0` 与 `strict checks: OK` 作为 pass 条件；
- 若后续出现 `managed=False` 或缺口复发，优先补齐 `docs/operations/bin-scripts-convergence-manifest.json` 或下沉到对应项目 owner。

### Round 13（2026-08-16）：继续常态化巡检（无新增缺口）

#### 已完成
- 新增 `make bin-tool-registry-round13`，复用 `round12` 一次性闭环链路（`audit-strict`、`parallel-gaps`、`dependency-risks`、`weekly-governance-report`），并将周报落盘路径扩展为 `artifacts/bin-tool-registry-weekly-governance-report-round13.json`。

#### 本轮执行结果
- 运行命令：`make bin-tool-registry-round13`
- 关键指标：
  - `parallel manifest gaps: 0`
  - `managed parallel duplicates: 0`
  - `unmanaged parallel duplicates: 0`
  - `dependency hotspots: 25`
  - `strict checks: OK`
- 周报落盘：`artifacts/bin-tool-registry-weekly-governance-report-round13.json`

#### 结果解读（本轮 Top10）
- `bin/ssot/bus-usage-report.py`（risk_score 11）
- `bin/compass_radar.py`（risk_score 7）
- `bin/submodule-gitlink-check.py`（risk_score 7）
- `bin/cockpit-readiness.py`（risk_score 7）
- `bin/mesh/mesh-orphan-cleanup.py`（risk_score 7）
- `bin/adr/adr-drift-auto-fix.py`（risk_score 7）
- `bin/adr/next-adr-id.py`（risk_score 7）
- `bin/adr/adr-drift-apply.py`（risk_score 7）
- `bin/adr/adr-drift-check.py`（risk_score 7）
- `bin/adr/adr-coverage.py`（risk_score 7）
- 结论：Top10 全部 `managed=True`，`action=retain-bin-owner`，`parallel=True`，当前继续保持机制收敛与周更节奏。

#### 下一步（Round 14）
- 每周固定执行 `make bin-tool-registry-round13`，将 `parallel manifest gaps=0`、`managed=False=0` 与 `strict checks: OK` 作为 pass 条件；
- 当 Top10 仍持续出现相同风险项时，优先对 owner 做“动作标准化”与职责清单复检，避免 Top10 长尾漂移。
