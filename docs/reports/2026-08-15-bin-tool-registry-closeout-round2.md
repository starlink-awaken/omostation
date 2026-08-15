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
