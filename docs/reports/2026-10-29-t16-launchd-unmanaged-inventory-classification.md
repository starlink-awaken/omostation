---
schema: md/v1
status: completed
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-29
type: ssot
title: T16-01 launchd 平面未登记存量分类盘点与处置报告
bet_id: BET-Y2Q4-T16-01
created: 2026-10-29
---

# T16-01 launchd 平面未登记存量分类盘点与处置报告

> **BET 依据**：`BET-Y2Q4-T16-01` · ADR-0457 · `Track: T16-DRIFT-GUARD`
> **准入条件**：27 条 W 组存量完成 owner 分类并各有处置结论，方可达成 shadow 阶段验收与申请转 warning 段。

---

## 1. 存量全局盘点概况

截至 2026-10-29 实测，宿主已安装 LaunchAgents plist 共计 82 项，比对 `.omo/cron/registry.yaml` 登记源，总体分布如下：

| 分组类别 | 数量 | 状态 / 判定 | 治理口径与处置策略 |
|---|---:|---|---|
| **R 组（已登记 active）** | 15 | 正常受控 | 在 `.omo/cron/registry.yaml` 显式登记且 100% 匹配 |
| **W 组（仓内脚本·未登记）** | 31 | 存量核心 | 本报告重点分析对象（原 27 条基线，演进为 31 条） |
| **E 组（用户/外部独立工具）** | 36 | 外部自治免除 | CleanMyMac、Steam、FleetOps、LifeOS、Magpie 等 |
| **D 组（死链/目标缺失）** | 0 | 健康通过 | 82 个 plist 执行目标 100% 存在，无任何死链 |

---

## 2. W 组（仓内脚本·未登记）31 项分类与处置矩阵

所有 31 条 W 组存量均已定位其物理脚本、业务职能与归属团队，并给出明确处置结论：

| Label | 目标程序 / 脚本 | 业务领域 | Owner | 处置结论 |
|---|---|---|---|---|
| `com.agora.daemon` | `lib/agora-daemon.sh` | A2A 协议总线 | platform-team | 保持 launchd 守护，后续由 services.yaml 统一纳管 |
| `com.kos.web` | `projects/knowledge` | 知识服务 Web 界面 | knowledge-team | 运行态服务，保留独立配置 |
| `com.l4.bet-claim-gc` | `lib/bet-claim-gc.sh` | 治理台账垃圾回收 | governance-team | 治理清理任务，建议合并进日常巡检 |
| `com.l4.governance.watch` | `bin/gac/governance-watch.py` | 治理看门狗 | governance-team | 核心守护，保持运行 |
| `com.l4.mail.daemon` | `bin/mail-daemon.py` | Agently 邮件网关 | platform-team | 保持 launchd 驱动 |
| `com.omlxc.watchdog` | `projects/omlxc/scripts/watchdog.sh` | 本地算力守护 | omlxc-team | 算力织网看门狗，保持常驻 |
| `com.omostation.agent-brief-materialize` | `bin/panorama/materialize-agent-brief.py` | Brief 真实物化 | governance-team | 核心物化定时任务，保持 2min 驱动 |
| `com.omostation.agent-tick-daemon` | `bin/agent-tick-daemon.py` | Agent 轮询驱动 | platform-team | 核心守护，保持运行 |
| `com.omostation.autoloop-daily` | `bin/gac/autoloop-daily.py` | 自动循环日巡 | governance-team | 日常巡检，已由 launchd 排程 |
| `com.omostation.claims-observation-r0` | `zhixing-dashboard/claims-obs.py` | 状态声明观测 | governance-team | 观测平面任务，保持当前配置 |
| `com.omostation.deadline-tracker` | `bin/deadline-tracker.py` | 交付倒计时雷达 | governance-team | 保持运行 |
| `com.omostation.eg2-embeddings` | `eg2-runtime/venv/bin/python` | 嵌入向量计算 | omlxc-team | 本地嵌入服务，按需常驻 |
| `com.omostation.evolution-agent` | `bin/evolution-agent.py` | 自进化决策引擎 | governance-team | 保持常驻 |
| `com.omostation.expiry-radar` | `bin/gac/check-expiry-radar.py` | 证书/凭证到期雷达 | governance-team | 治理周期任务，保持 24h 排程 |
| `com.omostation.mbp-night-patrol` | `bin/night-patrol.py` | 夜间系统巡更 | governance-team | 夜间排程，保持运行 |
| `com.omostation.morning-brief` | `bin/morning-brief.py` | 早晨简报生成 | governance-team | 日常生成任务，保持运行 |
| `com.omostation.omo-debt-refresh` | `projects/omo/bin/debt-refresh.py` | 治理债务刷新 | governance-team | 债务治理任务，保持排程 |
| `com.omostation.panorama-compact-observation` | `bin/panorama/compact-obs.py` | 驾驶舱观测压缩 | governance-team | 驾驶舱辅助，保持运行 |
| `com.omostation.problem-detector` | `bin/gac/problem-detector.py` | 系统故障自诊断 | governance-team | 诊断探针，保持常驻 |
| `com.omostation.resident-agent` | `projects/omo/.venv/bin/resident-agent` | Resident Agent 主服务 | resident-team | ADR-0456 B4b 重点服务，保持 install 运行 |
| `com.omostation.resident-daemon` | `projects/omo/.venv/bin/resident-daemon` | 全 topic 事件守护 | resident-team | ADR-0456 B4b 重点服务，保持 install 运行 |
| `com.omostation.resident-web` | `bin/resident-web.py` | Resident Web 宿主 | resident-team | 界面服务，保持运行 |
| `com.omostation.signal-poller` | `bin/signal-poller.py` | 外部信号长轮询 | platform-team | 保持常驻 |
| `com.omostation.spine-daily-ingress` | `scripts/tools/spine-daily-ingress.py` | 北极星主干真值流摄入 | spine-team | B4b 新增主干任务，每日 09:15 排程 |
| `com.omostation.sunset-redirector` | `bin/sunset-redirector.py` | 下线导流守卫 | governance-team | 路由守卫，保持常驻 |
| `com.omostation.tailscale-heartbeat` | `bin/health/tailscale-heartbeat.sh` | 组网心跳探针 | platform-team | 网络守护，保持运行 |
| `com.omostation.zhixing-brief-watchdog` | `bin/zhixing-brief-watchdog.sh` | 简报守护看门狗 | governance-team | 保持运行 |
| `com.omostation.zhixing-dashboard-watchdog` | `zhixing-dashboard/liveness-watch.sh` | 驾驶舱存活守护 | governance-team | 保持运行 |
| `com.omostation.zhixing-dashboard` | `zhixing-dashboard/serve.py` | 织星驾驶舱服务 | governance-team | 驾驶舱主程序，保持常驻 |
| `com.omostation.zhixing-projection-fullrefresh` | `bin/panorama/projection-full-refresh.py` | 投影全量刷新 | governance-team | 投影核心守护，保持 2h 排程 |
| `com.omostation.zhixing-projection-republisher` | `bin/republish-projections.py` | 投影重发布器 | governance-team | 保持运行 |

---

## 3. E 组（用户/外部工具）与免除范畴

共计 36 项 plist 属于外部系统、独立产品或用户桌面级应用，不在 omostation 仓库调度编译器管理范畴内，明确作为**已知免除项**：
- **系统/商业软件**：CleanMyMac (`com.macpaw.*`)、Steam 清理 (`com.valvesoftware.steamclean`)、LMStudio (`com.lmstudio.server`)。
- **独立多仓协同产品**：FleetOps 运维组网 (`com.fleetops.*`)、WorkAgent 运维引擎 (`com.localbrain.*`)、LifeOS 个人脉冲 (`com.lifeos.pulse`)。
- **本机本地工具**：`com.local.*`（如 clash-dist-serve、magpie、zg-server、route-pilot 等）。
- **异构大模型引擎**：`com.omlxc.daemon`（独立二进制 omlxcd）与 `com.omlxc.ollama-env`。

---

## 4. 阶段门（Stage Gate）评估结论

依据 ADR-0457 规定的三段式落地纪律：
1. **Shadow 阶段跑满 1 周**：✅ **已达成**（2026-09-29 上线至今已满 30 天，无阻断主干提交事故）。
2. **27 条 W 组存量完成 owner 分类与处置结论**：✅ **已达成**（本报告完整梳理并固化 31 条 W 组存量）。
3. **双向差集完整可复算**：✅ **已达成**（`missing_installed` 与 `undeclared_installed` 均已在 `check_drift()["launchd"]` 中落地并通过单元测试）。

**结论**：`BET-Y2Q4-T16-01` 的全部验收标准（Acceptance Criteria）已 100% 达成，具备完整闭环结项条件。后续如需转入 Warning 段（开始报警提示清理期限），可凭本报告及 owner 映射方案提起专项 Principal 审批。
