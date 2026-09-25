---
type: ssot
owner: governance-team
last-reviewed: 2026-09-25
---

# 驾驶舱面（Dashboards）职责边界

> 本文件是「哪个驾驶舱负责什么」的 SSOT。双核彻底归一后，全景与控制台已合一（BET-Y2Q2-T10-166）。

## 1. 架构主控入口（单一人类总控）

| 入口 | 名称 | 代码位置 | 版本控制 | 定位 |
|---|---|---|---|---|
| `:5173` / `:8090` (`/panorama`) | **Cockpit-UI 全景控制舱** | `projects/cockpit-ui/`（子仓） | ✅ **完全受控** | **唯一人类主入口**：全景驾驶舱、门禁矩阵、74s 哨兵大屏、道法术器 DFSQ 拓扑、BCOS 进化链与夏明星签署通道 |
| `:43191` | 织星底座（Sunset 导流态） | `bin/panorama/sunset_redirector.py` | ✅ 仓库内守护 | **已收敛下线**：HTTP 302 自动重定向至 Cockpit-UI `/panorama` |
| `:43910` | Panorama 静态页（Sunset 导流态） | `bin/panorama/sunset_redirector.py` | ✅ 仓库内守护 | **已收敛下线**：HTTP 302 自动重定向至 Cockpit-UI `/panorama` |

## 2. 职责划分（双核彻底归一后）

- **`Cockpit-UI (/panorama)` = 体系全景主控（唯一人类主入口）**
  - 数据源：`useGovernancePanorama` 双模态供给（优先实时 REST API，离线降级为静态快照），永不白屏。
  - 承载：
    1. **门禁全景矩阵**（A1-A9、RF0、RC-DL 11 大门禁裁决与证据抽屉）；
    2. **74s 哨兵大屏**（健康度评分环、脉冲倒计时、四维子系统健康度与自愈流水线）；
    3. **道法术器架构拓扑**（DFSQ/v1 4 阶图谱与 COMP-WS-omo 唯一 S 槽位）；
    4. **BCOS 认知进化链**（世代仪表盘、自蒸馏知识提炼与历代进化轨迹）；
    5. **执掌者总控与在位签署通道**（夏明星在位签署抽屉与宏观驾驶舱）。
  - 微交互：按 `F` 沉浸大屏全屏模式，按 `A` 开启 25s 自动巡航轮播（交互感知防抖暂停），数字键 `1-5` 快速直达。

- **`:43191` & `:43910` = 下线导流守护**
  - 由 `bin/panorama/sunset_redirector.py` 提供轻量常驻守护；
  - 浏览器访问自动 302 导流至 `http://localhost:5173/panorama`；
  - 存量脚本访问 `/api/panorama/overview` 等接口时返回遥测快照 JSON，确保零中断。

## 3. 历史问题彻底根治记录

### 3.1 历史 `:43191` 部署目录不受版本控制风险（已彻底根除）
- **历史痛点**：原 `~/.local/share/zhixing-dashboard/` 不在任何 git 仓库中，多 agent 并发直接编辑会导致代码覆盖、丢失与语法错误。
- **终极根治**：通过全景重构大 Goal，所有大屏模板与前端交互逻辑已 100% 迁移至受严格 Git 审查保护的 `projects/cockpit-ui` 仓库，通过独立的特性分支、GitHub PR、Squash-Merge 与 94 个单元测试（815 个用例）全流程严守质量与版本追踪。

## 4. 关联 SSOT
- 端口注册表：`protocols/port-registry.yaml`
- 全景控制舱规范：`docs/superpowers/specs/2026-09-24-panorama-master-route-and-navigation-design.md`
- 导流守护脚本：`bin/panorama/sunset-redirector.py`
