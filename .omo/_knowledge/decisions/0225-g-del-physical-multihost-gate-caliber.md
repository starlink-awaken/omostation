---
status: ACCEPTED
lifecycle: decision
owner: 架构师
last-reviewed: 2026-07-19
related:
  - 0210-three-year-strategy-execution-convergence.md
  - 0221-g-del-5a-emergence-collective-decision-risk-review.md
  - 0223-phase-gate-ci-enforcement.md
  - 0224-m1-conflict-count-rootcause-before-adversarial-pass.md
supersedes: []
amends: [0210]
---

# ADR-0225: G-DEL 兑现期门禁维持物理多机口径（方案 A）

> **编号**: D1 claim `next-adr-id.py --session g-del-caliber --claim` → **0225**。  
> **修正**: ADR-0210 兑现期执行面门禁的**测量口径**——in-process 模拟不得冒充物理多机达标。

## Context and Problem Statement

ADR-0210 兑现期门禁原文要求：

- 4 机调度成功率 > 99%（G-DEL.1）
- 同步延迟等跨机指标（G-DEL.3：p99 < 100ms）

`docs/G-DEL-EXECUTION-METRICS.md` 已诚实声明当前 harness 为 **in-process 4 逻辑节点模拟**。  
若用模拟数字宣布 G-DEL.1/3「达标」，则门禁失真。

同时，2026-07-19 物理节点盘点（见审计包）显示：

| id | 注册状态 | 可达（测量向） | 证据 |
|----|----------|----------------|------|
| local-mac | active | **是** | 当前会话主机 |
| macmini | active | **是** | `192.168.31.210` ping+SSH BatchMode；hostname=`Mac-mini` |
| y7000p | active | 否 | ping 通，SSH:22 超时 |
| cloud | active | 否 | 注册表无 endpoint，fail-closed |

**`reachable_physical_hosts = 2` ≥ 2** → 选定 **方案 A（真机口径）**，不采用 B（两级 M2a/M2b 降级）。

## Decision Drivers

- **D1 · 观测诚实**：模拟跑通 ≠ 物理门禁达标。  
- **D2 · 有机则不降级**：≥2 台 SSH 可达物理节点，门禁保持物理多机。  
- **D3 · CI 可执行**：口径进 `phase-scope.yaml`，phase-gate 拒绝 sim 填真机字段。

## Considered Options

- **A · 真机口径（选定）**：门禁维持物理多机；产出接入方案；达标须真机实测。  
- **B · 两级里程碑**：暂无多机时 M2a 模拟 + M2b 真机；当前仅标 M2a。  
  *未选：盘点已确认 2 台可达。*

## Decision Outcome

### 1. 门禁口径（amends ADR-0210 兑现期）

| Goal | 官方门禁 KPI | 允许环境 `env_class` | 模拟 harness |
|------|--------------|----------------------|--------------|
| G-DEL.1 | schedule success > 99% | **`physical_multi_host`** | 仅 `meets_sim_harness`，**不得** `meets_physical_gate` / 官方 `meets_gate` |
| G-DEL.3 | sync p99 < 100ms | **`physical_multi_host`** | 同上 |
| G-DEL.2b | collab complete > 95% | process-local 协议可验收 | 允许 `meets_gate`（非跨机网络 KPI） |
| G-DEL.5b | accuracy > 80% + kill-switch | 启发式+安全闸 | 允许 `meets_gate`（非跨机网络 KPI） |

理想节点数仍为 **4**（ADR-0210 原文）；当前底座 **2** 台可启动真机接入，4 机达标前不得宣称「4 机门禁完成」。

### 2. 字段约定（metrics JSON）

- `env_class`: `in-process_simulation` | `physical_multi_host`
- `meets_sim_harness`: 模拟 KPI 是否过线（开发用）
- `meets_physical_gate`: 仅物理多机测量可 true
- **`meets_gate`（G-DEL.1/3）= `meets_physical_gate`**（官方口径，不再等于模拟过线）

### 3. 接入方案（2 机起步 → 4 机理想）

1. **节点**: `local-mac`（本机）+ `macmini`（`192.168.31.210` / `mac-mini.local`，SSH 用户同局域网账号）。  
2. **预备**: 两端同 commit 工作树；Python ≥3.9；SSH 互信（BatchMode）。  
3. **测量**: 后续物理 harness（非本 ADR 实现范围）在 ≥2 主机上跑 schedule 批与 sync RTT，写 `env_class=physical_multi_host` 与 `physical_hosts≥2`。  
4. **扩展**: y7000p 打开 SSH:22；cloud 补注册 endpoint 后可扩到 4。  
5. **禁止**: 把 `measure_all.py` 默认 in-process 输出直接写入真机门禁「达标」声明。

### 4. CI / phase-scope

`phase-scope.yaml::metrics_caliber` 声明物理门禁集合；`phase-gate-check` 校验：  
若 `env_class=in-process_simulation`（或 env 文案标明 sim）却 `meets_physical_gate=true` 或（G-DEL.1/3）`meets_gate=true` → **fail**。

## Consequences

- 正面：ADR-0210 兑现期不被模拟假绿；有 2 机底座可推进真机接入。  
- 代价：当前 `measure_all` 对 G-DEL.1/3 官方 `meets_gate=false`；进度不得标「G-DEL.1/3 达标」。  
- 不采用 B：避免在已有 2 机时把物理门槛降级为 M2a 叙事。

## Confirmation

- 盘点包：`.omo/_knowledge/audits/2026-07-19-physical-node-inventory.json`  
- `phase-scope.yaml` 含 `metrics_caliber`  
- pytest：sim 声明物理 pass → fail；诚实 sim → pass  
- `measure_all` 输出 `env_class=in-process_simulation` 且 G-DEL.1/3 `meets_physical_gate=false`

## References

- ADR-0210 兑现期门禁原文  
- `docs/G-DEL-EXECUTION-METRICS.md`  
- inventory 2026-07-19  
