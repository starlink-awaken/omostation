# 2026-08-15 Bin 工具治理盘点报告（全局实施第一轮）

## 1. 本次执行摘要

在 `Makefile` 与 `bin/tool-registry-audit.py` 落地后，对 `bin/` 进行全量扫描，形成第一版治理基线。

- 入口总数：`453`
- 域数量：`14`
- 同名命令重复：`5`
- `legacy snake_case`：`37`
- 缺少 shebang：`0`
- 厚脚本（>= 220 行）：`140`
- 依赖闭环节点：`156`

执行命令：

```bash
python3 bin/tool-registry-audit.py --json
python3 bin/tool-registry-audit.py --scope gac --json
python3 bin/tool-registry-audit.py --emit docs/generated/bin-tool-registry.json
make bin-tool-registry-audit
make bin-tool-registry-audit-emit SNAPSHOT=docs/generated/bin-tool-registry.json
```

> 说明：`make bin-tool-registry-audit-strict` 会返回非 0（当前历史遗留 `5` 个重复命令 + 依赖闭环），用于 PR 前置门禁。

## 2. 依赖分析结论（全量：all）

### 2.1 入口耦合图关键指标

- 出度 Top（调用方）
  - `gac/gac-local-gate.py`：59
  - `ssot/gen-tools-index.py`：54
  - `change-lane-check.py`：23
  - `gac/governance-dashboard.py`：21
  - `gac/gac-healthcheck.py`：19

- 入度 Top（被依赖方）
  - `agent-workflow.py`：11
  - `gac/gac-drift.py`：6
  - `gac/gac-validate.py`：5
  - `mof/mof-drift`：4
  - `mof/mof-bootstrap.py`：4

- 闭环规模：`156`（高耦合热点在 ADR、gac、ssot、mof 与治理链路）

### 2.2 下沉价值高的候选路径

1. **同名冲突（先切）**
   - `git-health-hook`：`git-health-hook.py` / `ssot/git-health-hook.py`
   - `nested-with`：`_archive/nested-with.py` / `sweep/nested-with.py`
   - `predictive-governance`：`gac/predictive-governance.py` / `ssot/predictive-governance.py`
   - `submodule-reachability-gate`：`ssot/submodule-reachability-gate.py` / `submodule-reachability-gate.py`
   - `sync-submodules-push`：`ssot/sync-submodules-push.sh` / `sync-submodules-push.sh`

2. **高厚度脚本（可拆分为 wrapper + domain 模块）**
   - `collab/scenario_lib.py`（4835）
   - `gac/orca-codex-supervisor.py`（1465）
   - `gac/agent-clone.py`（1178）
   - `gac/swarm_discipline.py`（1042，且命名含 snake_case）
   - `gac/gac-local-gate.py`（919）

3. **命名债务（snake_case）**
   - 目前发现 37 项，包含 `gac/coordination_store.py`、`gac/swarm_discipline.py`、`gac/test_coordination_layer.py` 等。

## 3. 与治理机制对齐

- `bin/README.md` 已补充该机制与执行节奏。
- `Makefile` 已新增目标：
  - `bin-tool-registry-audit`
  - `bin-tool-registry-audit-strict`
  - `bin-tool-registry-audit-emit SNAPSHOT=...`
- `bin/gac/gac-local-gate.py` 已包含 `tool-registry-audit` 检查项（当前非阻断）。

## 4. 落地机制（长期迭代）

### 周度（固定）
- 跑全量快照：
  `make bin-tool-registry-audit-emit SNAPSHOT=docs/generated/bin-tool-registry-$(date +%F).json`
- 与上期 diff：看 `duplicate_count/legacy_snake_case/cycle_nodes/thick_entries` 的增长率

### 月度（稳定化）
- 处理完 1 个重复域后移入“收敛清单”
- 每次 PR 输出包含：
  - 迁移前后命令映射（新入口 + shim）
  - 依赖图收敛说明（出度/入度变化）

### 季度（能力下沉）
- 在 `gac/ssot` 交叉依赖链中优先识别高入度 / 高出度节点，提炼为 domain module。
- 保留 wrapper 的同时把厚脚本逻辑下沉为可测模块。

## 5. 验证与执行结果

已执行：
- `python3 bin/tool-registry-audit.py --json`
- `python3 bin/tool-registry-audit.py --emit docs/generated/bin-tool-registry.json`
- `python3 bin/tool-registry-audit.py --scope gac --json`
- `make bin-tool-registry-audit`
- `make bin-tool-registry-audit-emit SNAPSHOT=docs/generated/bin-tool-registry-from-make.json`
- `make bin-tool-registry-audit-strict`（**返回非 0，符合预期**）

## 6. 风险与下一步（本次未闭环）

1. `--strict` 目前会被现有历史债务阻断，必须走“两阶段并行”模式：
   - 阶段 A：先补齐 duplicates 与关键闭环治理清单（非阻断）
   - 阶段 B：再开启 `--strict` 进入 PR gate
2. 自动提取依赖仍有文本式边界限制：脚本注释/动态拼接命令可能漏检，后续可补充基于 ast/shlex 的更强解析。

## 7. 产物清单

- 规则脚本：`bin/tool-registry-audit.py`
- 计划执行入口：`Makefile` 新增 3 个目标
- 固化文档：`bin/README.md`
- 快照：`docs/generated/bin-tool-registry.json`
- 本次复盘：`docs/reports/2026-08-15-bin-tool-registry-audit-report.md`
