---
type: ephemeral
status: completed
owner: governance-team
last-reviewed: '2026-10-28'
schema: md/v1
---

# B4b Batch 2 规模化物理切道与贾维斯桌面感知面交付收据

> **战役编号**: [BET-Y2Q4-T1-05](file:///Users/xiamingxing/Workspace/docs/plans/3y-bet-ledger.yaml) / [BET-Y2Q4-T10-244](file:///Users/xiamingxing/Workspace/docs/plans/3y-bet-ledger.yaml) / [BET-Y2Q4-T10-243](file:///Users/xiamingxing/Workspace/docs/plans/3y-bet-ledger.yaml)  
> **基线分支**: `main` (`9de3ba966`)  
> **执行日期**: 2026-10-28  
> **核心契约**: [ADR-0456](file:///Users/xiamingxing/Workspace/.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md) (双根隔离与独立安装位)、[ADR-0466](file:///Users/xiamingxing/Workspace/.omo/_knowledge/decisions/0466-system-authenticity-and-zero-mock-contract.md) (真实性与零 Mock 契约)

---

## 1. 战役执行概述

根据设计决策树与实施规划，本轮交付完成三项核心战役闭环：
1. **B4b Batch 2 物理切道**: 将 5 个受管核心后台服务从检出区改道至安装位 `~/.local/opt/omostation`，并注入独立状态根 `~/.local/state/omostation/prod`。
2. **贾维斯感知面闭环**: 修复 `observer-daily.py` 内部检测 CI 流水线的结构化解析，打通桌面 SwiftBar 菜单栏与 macOS 原生免打扰通知，生成今日晨报。
3. **4.1T 存储自动冷热分层守卫**: 研发并验证 `scripts/tools/storage-auto-tiering.py`，守卫内置 SSD 300GB+ 极速可用空间底线。

---

## 2. 物理现实测量尺读数跃迁 (Physical Reality Check Readings)

通过运行真实探测工具 [`scripts/tools/launchd-workspace-reality-check.py`](file:///Users/xiamingxing/Workspace/scripts/tools/launchd-workspace-reality-check.py)，系统实测读数实现历史性突破：

| 指标维度 | 切道前基线 (PR #4925 后) | 本轮切道后实测 (Batch 2) | 净变化 | 评价 |
| :--- | :--- | :--- | :--- | :--- |
| **指向独立安装位 (`install_count`)** | **1** | **6** | **+5 (+500%)** | 突破性跃升 |
| **指向 Workspace 存量 (`workspace_count`)** | **39** | **34** | **-5 (-12.8%)** | 稳步收敛 |
| **状态根独立分区 (`profile`)** | **1** | **6** | **+5 (+500%)** | 彻底解耦运行写面 |
| **状态根指向检出 (`checkout`)** | 8 | 8 | 0 (未恶化) | 常驻族待后续批次 |
| **总 plist 数量 (`total_plists`)** | 82 | 82 | 0 | 守恒 |

### 本轮切道的 5 个服务明细
1. `com.omostation.morning-brief` (每日业务与技术早报) -> `install` 根 + `profile` 状态根
2. `com.omostation.zhixing-projection-republisher` (投影租约续期守护) -> `install` 根 + `profile` 状态根
3. `com.l4.governance.watch` (状态治理巡检守护) -> `install` 根 + `profile` 状态根
4. `com.l4.mail.daemon` (邮件感知守护) -> `install` 根 + `profile` 状态根
5. `com.omostation.sunset-redirector` (端口导流守护) -> `install` 根 + `profile` 状态根

---

## 3. 贾维斯感知面实操证据

1. **结构化 CI 失败提醒**:
   - `observer-daily.py` 升级为 `gh run list --json status,conclusion,name,databaseId,headBranch,url`。
   - 杜绝旧版纯文本搜索 `"[FAIL]"` 的漏检假零现象。
   - 检测到新失败时触发 macOS 原生系统通知并向 `~/.local/share/menubar/reminders.json` 写入带 URL 的结构化提醒。
2. **SwiftBar 门禁核验**:
   - `bash ~/.config/menubar/bar-lint.sh` 实测 7 域全部 PASS，首屏与深度完全合规。
3. **每日晨报实测落盘**:
   - 晨报成功输出至 `.omo/_delivery/observability/daily/2026-10-28.md`（4655 字节），完整记录了五件套、本地本地大模型、治理面、双机一致性与 CI 健康度。

---

## 4. 4.1T 存储自动分层守卫实操证据

- 研发 [`scripts/tools/storage-auto-tiering.py`](file:///Users/xiamingxing/Workspace/scripts/tools/storage-auto-tiering.py)。
- 实测当前内置 SSD 空间为 **320.6GB**，高于 300GB 警戒阈值，守护判定为 `IDLE_ABOVE_THRESHOLD`。
- 通过 `--min-ssd-free-gb 350.0 --dry-run` 压力测试，验证自动扫描到 4 个大模型权重文件（共 10.53GB），并规划搬迁至 `/Volumes/Model/omostation-cold` 与软链接回指。
