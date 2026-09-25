---
type: ssot
owner: governance-team
last-reviewed: 2026-09-25
---

# 织星全景控制舱（Panorama Dashboard & Master View）

> 体系全景运行指挥台 —— 已全面归一至 Cockpit-UI 原生 `/panorama` 航道（BET-Y2Q2-T10-166）。
> 运行事实以 `runtime/dashboard/data.json` 与 REST API 为准，不硬编码。

## 1. 唯一访问主入口

```bash
# 1. 启动 Cockpit 控制台
bun run dev --cwd projects/cockpit-ui          # 前台开发服务 → http://localhost:5173/panorama
open http://localhost:5173/panorama           # 浏览器查看治理全景大屏
```

> **提示**: 原 `:43191` 与 `:43910` 端口已转入下线导流守护状态，浏览器访问会自动 302 重定向至 `http://localhost:5173/panorama`。

## 2. 五大原生重塑板块

| 板块 | 内容 | 特性 |
|---|---|---|
| **门禁全景矩阵** | A1–A9、RF0、RC-DL 11 大门禁裁决与状态过滤 | 折叠抽屉、退出码审计、证据链溯源 |
| **74s 哨兵大屏** | 持续心跳巡航、四维健康雷达与自愈工作流 | 74s 脉冲倒计时环、红黄绿状态流、健康评分 |
| **道法术器架构拓扑** | 道/法/术/器 4 阶图谱与唯一 Active S 槽位 | 节点脉冲连接、COMP-WS-omo 单主控映射 |
| **BCOS 认知进化链** | 世代仪表盘、自蒸馏知识提炼与历代进化轨迹 | Epoch 刻度、自蒸馏总数与历史 Timeline |
| **执掌者总控视界** | 夏明星在位签署抽屉与宏观驾驶舱视界 | 审批队列联动、主权在位印章与批次核准 |

## 3. 人机微交互与大屏挂机

- **沉浸全屏模式**: 键盘按键 `F` 一键切换。
- **自动巡航轮播**: 键盘按键 `A` 开启/暂停 25 秒自动轮播，内置鼠标/键盘交互智能感知暂停（12 秒防抖恢复）。
- **数字键直达**: 按键 `1` ~ `5` 毫秒级直达指定板块。
- **全局命令面板**: 随时按 `⌘K` 或 `Ctrl+P` 秒级唤起全景子视图。

## 4. 关联 SSOT

- 职责边界：`docs/DASHBOARDS.md`
- 端口注册表：`protocols/port-registry.yaml`
- 架构规范：`ARCHITECTURE.md`
- 导流守护：`bin/panorama/sunset-redirector.py`
