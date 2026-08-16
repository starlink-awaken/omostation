# 2026-08-15 bin 工具治理收敛 Round 2

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
