---
title: G-DEL 执行面门禁 · 实测说明
status: active
type: metrics
related: [BET-7e074, BET-664e3, BET-3e602, BET-8c7c, ADR-0221, ADR-0225]
---

# G-DEL 执行面门禁

| Goal | KPI | 官方口径 | 状态 | Harness |
|------|-----|----------|------|---------|
| G-DEL.1 | schedule success > 99% | **physical multi-host ≥4** | **BLOCKED** (ADR-0226) | `measure_physical` (需 4 机) |
| G-DEL.2b | collab complete > 95% | process-local | OPEN | `collab_cli` + `measure_all` |
| G-DEL.3 | sync p99 < 100ms | **physical multi-host ≥2** | OPEN | `measure_physical` |
| G-DEL.4 | 角色记忆共享 | single_repo gbrain | OPEN | `shared-context-cli` + `role_memory` + gbrain |
| G-DEL.5b | accuracy > 80% + kill-switch | process-local | OPEN | `emergence_cli` + `measure_all` |

**G-DEL.1 解除条件**: `reachable_physical_hosts ≥ 4` 且物理测量 `meets_physical_gate=true`。  
当前盘点 = 2 → 任何 sim / 2 机数据标 G-DEL.1 达标均被 phase-gate 拒绝。

## 环境声明（诚实）

默认 `python3 bin/delivery/measure_all.py` 为 **in-process multi-node simulation**
（4 逻辑节点，非物理多主机）。字段约定：

| 字段 | 含义 |
|------|------|
| `env_class` | `in-process_simulation` \| `physical_multi_host` |
| `meets_sim_harness` | 模拟 KPI 是否过线（开发用） |
| `meets_physical_gate` | 仅物理多机测量可 true |
| `meets_gate`（G-DEL.1/3） | **= `meets_physical_gate`**（官方 ADR-0210/0225） |

**禁止**用模拟数字宣布 G-DEL.1 / G-DEL.3 官方达标。  
CI：`phase-gate-check --metrics <json>` 拒绝 sim 填真机门禁字段。

## 物理底座（2026-07-19 盘点）

| 节点 | 可达 | 备注 |
|------|------|------|
| local-mac | 是 | 当前开发机 |
| macmini | 是 | `192.168.31.210` SSH |
| y7000p | 否 | ping 通，SSH:22 超时 |
| cloud | 否 | 无 endpoint |

方案 **A**：门禁维持物理多机；接入见 ADR-0225。当前 `all_physical_gates_pass=false`。

```bash
python3 -m pytest tests/test_delivery_g_del.py tests/test_phase_gate_check.py tests/test_physical_mesh.py -q
python3 bin/delivery/measure_all.py
python3 bin/gac/phase-gate-check.py --files README.md --check-caliber --json
```

## 物理多机实测（ADR-0225 接入）

默认 LAN 对：`local-mac`（本机）+ `macmini`（`192.168.31.210`）。

```bash
# 默认 n_ops=10000；p99 仅当 n≥1000 可信，否则 insufficient_samples
python3 bin/delivery/measure_physical.py --auto-default-lan --start \
  --remote-root ~/Workspace --n-ops 10000 \
  --out .omo/_knowledge/audits/g-del-physical-latest.json
```

字段：`env_class=physical_multi_host`；分位见 `latency_summary`（p50/p90/p95/p99/p999/max + histogram）。

### 真机快照（large-N n=10000）

| 跑次 | mode | n | p50 | p90 | p95 | p99 | p999 | max | 判定 |
|------|------|---|-----|-----|-----|-----|------|-----|------|
| fan-out | parallel_fanout_put | 10000 | 10.1 | 15.3 | 19.3 | **101.0** | 111.0 | 177.9 | fail（真实尾） |
| protocol | cross_host_put | 10000 | 11.5 | 18.8 | 24.8 | **105.1** | 122.5 | 233.6 | fail |

- n≈100 时 p99≈157ms≈max → **小样本假象**；large-N 证明主体健康但 **p99 仍 ≥100ms**（WiFi 尾）。
- 有线：macmini en0 Ethernet **inactive**，无法隔离 WiFi。
- G-DEL.1 在 2 机下 **BLOCKED**（min=4）。
证据：`.omo/_knowledge/audits/2026-07-19-g-del3-*-large-n.json`。

有线复测清单：[`docs/G-DEL-3-WIRED-REMEASURE.md`](G-DEL-3-WIRED-REMEASURE.md)  
链路探测：`python3 bin/delivery/network_path.py 192.168.31.210`（写入 measure_physical env_evidence）。

看板：[`docs/G-DEL-PHASE2-BOARD.md`](G-DEL-PHASE2-BOARD.md) · 2b/5b 运维：[`docs/G-DEL-2b5b-OPS.md`](G-DEL-2b5b-OPS.md)
