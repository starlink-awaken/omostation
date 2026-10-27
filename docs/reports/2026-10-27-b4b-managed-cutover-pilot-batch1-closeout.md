---
type: ephemeral
status: completed
owner: governance-team
last-reviewed: 2026-10-27
---

# B4b 真实物理切道试点（Pilot Batch 1）验收收据与证据链

> **战役来源**: [BET-Y2Q4-T1-05](file:///Users/xiamingxing/Workspace/docs/plans/3y-bet-ledger.yaml) / [BET-Y2Q4-T10-272](file:///Users/xiamingxing/Workspace/docs/plans/3y-bet-ledger.yaml)  
> **服务对象**: `com.omostation.agent-brief-materialize`  
> **规范依据**: [ADR-0456](file:///Users/xiamingxing/Workspace/.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md) (双根隔离与独立运行时安装位契约)  
> **执行日期**: 2026-10-27

---

## 1. 交付目标与实测结果

本单完成了 ADR-0456 B4b 真实物理切道的首个服务试点（Pilot Batch 1），在零故障、零业务中断的前提下，将 `com.omostation.agent-brief-materialize` 从主工作区 `~/Workspace` 完全切入独立运行时安装位 `~/.local/opt/omostation` 并对齐 XDG 状态根：

| 维度 | 切道前状态 | 切道后状态 | 验证判据与工具 |
| :--- | :--- | :--- | :--- |
| **代码执行根 (`code_root`)** | `/Users/xiamingxing/Workspace` | `/Users/xiamingxing/.local/opt/omostation` | `launchd-workspace-reality-check.py` |
| **数据状态根 (`state_root`)** | `undeclared` (检出根默认) | `/Users/xiamingxing/.local/state/omostation/prod` | `gen-service-configs.py --reality-check` (E7) |
| **日志落点** | `~/.local/log/agent-brief-materialize.log` | `~/.local/log/agent-brief-materialize.log` | 实测 tail 日志验证成功物化 |
| **Workspace 存量计数** | 40 | **39** (成功减少 1 条) | `launchd-workspace-reality-check.py` |
| **Install 位存量计数** | 0 | **1** (实现 0 的突破) | `launchd-workspace-reality-check.py` |
| **E7 写根分区分类** | `{'checkout': 6}` | `{'checkout': 6, 'profile': 1}` | `gen-service-configs.py --reality-check` |
| **E1 服务漂移门** | `0 drift` | `0 drift` | `gen-service-configs.py --check` |

---

## 2. 真实运行时证据 (Runtime Evidence)

### 2.1 Launchctl 运行态读数
```text
$ launchctl list | grep "agent-brief-materialize"
26787   0   com.omostation.agent-brief-materialize
```
- 进程退出码为 `0`（正常调度运行）。

### 2.2 日志实际产出读数
```text
$ tail -n 1 ~/.local/log/agent-brief-materialize.log
[agent-brief-materialize] 已物化: revision=72f4b7cdc2e3 data_generated_at=2026-10-27T09:07:07Z copied_at=2026-10-27T09:07:07.884233Z target=/Users/xiamingxing/.local/state/omostation/prod/runtime/dashboard/agent-brief.json
```
- 产物直接写入 `/Users/xiamingxing/.local/state/omostation/prod/runtime/dashboard/agent-brief.json`。

### 2.3 现实核对尺 (launchd-workspace-reality-check) 读数
```json
{
  "total_plists": 82,
  "pointing_to_workspace_count": 39,
  "pointing_to_install_count": 1,
  "state_root_distribution": {
    "checkout": 8,
    "profile": 1,
    "install": 0,
    "undeclared": 73
  }
}
```

---

## 3. 备份与安全防护

原始 plist 文件已完整备份于：
- `~/.omo/_delivery/plist-backups/b4b-pilot-20261027/com.omostation.agent-brief-materialize.plist`
- `~/.omo/_delivery/plist-backups/b4b-pilot-20261027/com.l4.bet-claim-gc.plist`
