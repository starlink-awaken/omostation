---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-team
last-reviewed: 2026-10-27
bet_id: BET-Y2Q4-T10-269
---

# BET-Y2Q4-T10-269 收口 receipt —— 统一 scheduler 检查的检出

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-269`  
规格：`docs/superpowers/specs/2026-10-26-scheduler-checkout-root-unification.md`  
复盘：`.omo/_knowledge/retros/BET-Y2Q4-T10-269.md`  
工程腿：PR #4901 (`2521b3b0868c4ff708760898100c95a161b475d9`) 与 PR #4896 (`958ec2d88`)  
收口腿：分支 `agent/governance-agent/scene-parser`，run `20261027T031507Z-bet-execution-bdbf1c81`

## 1 交付范围

1. **统一 registry 根解析**：`bin/panorama/assets/host/scheduler_collector.py.asset` 增加 `registry_root()` 解析逻辑：优先取 `PANORAMA_CODE_ROOT`（publisher 检出），缺省回退 `DEFAULT_WORKSPACE_ROOT`，使调度器检查与 A4 门禁读取同一棵 registry，消除由于工作区滞后导致的虚假降级。
2. **运行时环境与脚本路径分离**：`collect()` 运行时 (`argv[0]`) 取自工作区的 `managed-python`（保证解析到 `.venv` 解释器），被检查的脚本来自解析出的 registry 根（保证由脚本所在目录导出正确的 registry 文件）。
3. **陈旧度可见（observe-only）**：`scheduler` 源状态增加 `registry_root` / `registry_root_oid` / `registry_root_stale` 三键，仅作可观测记录，不影响判定结果。
4. **单测覆盖与断言自证**：`tests/unit/test_scheduler_collector_registry_root.py` 包含 5 项聚焦测试，含合成检出注入与正向落点自证。

## 2 验收读数

实测于工作区（2026-10-27）：

```text
1. python3 -c "import yaml,pathlib; d=yaml.safe_load(pathlib.Path('.omo/cron/registry.yaml').read_text()); print('known_orphans', len(d.get('known_orphans') or []), 'has_test_all', any('test-all' in str(k) for k in (d.get('known_orphans') or [])))"
→ known_orphans 22 has_test_all True

2. python3 bin/scheduler-compile.py --check --json
→ {"ok": true, "drift_count": 0, "orphan_count": 0, "known_orphan_count": 11, ...}

3. uv run pytest -o addopts="" tests/unit/test_scheduler_collector_registry_root.py
→ 5 passed in 0.03s
```

## 3 运行时观测

| 观测面 | 读数 | 判读 |
|---|---|---|
| A4 调度门禁 | `ok: true`, `drift_count: 0`, `orphan_count: 0` | 调度声明与安装态一致性通过 |
| cockpit `scheduler` 采集器 | `ok: true`, `state: OBSERVED` | 根解析正确识别 `registry_root`，与 A4 读数一致 |
| A9 可观测性影响 | 消除因为主工作区滞后而把 A4 读数报成 `DEGRADED` 的假阳性 | A9 维持原有可观测判据，不再受视差干扰 |

## 4 完成证据矩阵

- **Engineering**: `VERIFIED`。代码与测试已由 PR #4901 合入 `origin/main`（可达提交 `2521b3b08`），单测 5 项全绿。
- **Operational**: `PROVEN`。本地 `scheduler-compile.py --check --json` 实测 `ok: true`, `drift_count: 0`, `orphan_count: 0`。
- **Value**: `NOT_PROVEN`。台账 `value_indicator_policy=false`，不主张用户业务价值。
