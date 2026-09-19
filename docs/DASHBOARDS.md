---
type: ssot
owner: governance-team
last-reviewed: 2026-09-17
---

# 驾驶舱面（Dashboards）职责边界

> 本文件是「哪个驾驶舱负责什么」的 SSOT。改动职责边界时同步更新本文件与各自页脚。

## 1. 三套入口

| 入口 | 名称 | 代码位置 | 版本控制 | 定位 |
|---|---|---|---|---|
| `:43191` | **织星主权控制面**（Zhixing Dashboard） | `~/.local/share/zhixing-dashboard/`（**部署目录**） | ❌ **不在仓库** | **主入口**：战略/治理/知识/场景运行态 |
| `:43910` | Panorama 全景驾驶舱 | `bin/panorama/panorama-collect.py`（生成 `runtime/dashboard/`，gitignored） | ✅ 采集器在仓库 | 运行指挥台：门禁/BET/Agent/运行态聚合 |
| `:8090` | Cockpit Dashboard | `projects/cockpit/`（子模块） | ✅ | 工程面：observatory API + 工作台 |

## 2. 职责划分（收敛后）

- **`:43191` = 主权视窗（唯一人类主入口）**
  - 数据源：`refresh.py` 每 5 分钟采集 + **复用 panorama `build_payload()`**
  - 承载：核心决策 / 门禁 / BET / 运行态 / 知识记忆 / 技能清单 / **场景系统运行态**
  - 边界：只读视窗；不做执行、不派工

- **`:43910` = 运行指挥台（Panorama）**
  - 数据源：`panorama-collect.py`（约 20+ 采集器）→ `runtime/dashboard/data.json`
  - 承载：体系运行聚合 + 面板（与 `:43191` 数据同源，展示面更工程化）

- **`:8090` = 工程工作台（Cockpit）**
  - 数据源：`projects/cockpit` observatory（只读投影）+ 工作台 API
  - 承载：Agent 用的结构化查询面（`scene_status` / `scene_graph` 等）

**关系**：`panorama-collect.py` 是 `:43191` 与 `:43910` 的**共同数据源**；`:43191` 是给人看的主入口，`:8090` 是给 agent 查的工程面。

## 3. 已知问题与缓解

### 3.1 `:43191` 部署目录不受版本控制（**高风险**）

`~/.local/share/zhixing-dashboard/` 不在任何 git 仓库中，多 agent 并发编辑同一
`template.html` 会**互相覆盖**。

**实证（2026-09-17）**：
- 场景系统面板被另一 agent 的「metrics redesign」覆盖丢失（且所有备份均无该代码）
- 该次覆盖同时回退了已修好的 `ens[n.type]` bug
- 另发现一处语法错误（`` `...'—'%}` ``）直接使整个第二脚本失效 → `D is not defined` → 页面主功能损坏

**缓解措施**：
1. 面板代码**版本化为仓库资产** `bin/panorama/assets/scene-panel.html`
2. `bin/gac/zhixing-panel-sync.py ensure` **幂等自愈注入**（cron 每小时巡检，`omostation-zhixing-panel`）
3. `make zhixing-panel-check` 漂移检测（缺失退出非零）
4. **宿主文件纳管**（2026-09-18 补）—— 上面 1~3 只覆盖 **panels**，而实测被覆盖的
   是**宿主文件本身**（`template.html` 324KB / `refresh.py` 97KB，原先完全未纳管）。
   现版本化为 `bin/panorama/assets/host/`，由 `bin/gac/zhixing-host-sync.py` 管理：

   | 命令 | 作用 |
   |---|---|
   | `make zhixing-host` | 漂移检测（部署被直接编辑 → exit 1） |
   | `make zhixing-host-status` | 仓库 vs 部署 逐文件 sha 摘要 |
   | `make zhixing-host-capture` | 部署 → 仓库（有意变更后版本化） |
   | `python3 bin/gac/zhixing-host-sync.py restore --force` | 意外覆盖 → 从仓库回滚（留 `.before-restore`） |

   捕获的是**注入后稳定态**（panels/补丁幂等，故不产生伪漂移）。cron 每小时
   随 `omostation-zhixing-panel` 一并巡检。

   > **承载方式（2026-09-19）**：crontab **写入在系统层已坏**（连原样重写都返回
   > `Interrupted system call`；`/var/at/tabs` 为 `root:wheel drwx------`）。
   > 本机 dashboard 周期任务本就跑 launchd，故改用
   > `bin/ops/launchd/com.omostation.zhixing-host-drift.plist`（每小时 :23，
   > 与 `workspace-wip-guard.py protect` 合并为一个 job）。日志
   > `runtime/cron/zhixing-host-drift.log`。crontab 里的对应条目在写入恢复前
   > 不会生效。

   > `refresh.py` 在仓库中存为 **`refresh.py.asset`**：`script-registry` 与
   > `bin-quota` 两个门禁把 `bin/**/*.py` 一律当作**脚本**（排除规则只认
   > `bin/_*` 目录），而这是部署文件的版本化副本 —— 是资产不是脚本。用 `.asset`
   > 后缀既保持与同行 panels 资产相邻，又不误纳入脚本治理面。

**残余风险**：纳管的是"快照 + 漂移检测"，不是"禁止直改"—— 部署目录仍可被写，
但现在**覆盖会被检出**（原先静默丢失）。根本解法（迁入子仓库、以 PR 流程替代
直改部署目录）仍未做，建议单列 BET。

### 3.2 面板/入口重叠

`:43191` 与 `:43910` 数据同源、展示重叠。**收敛方向**：保留 `:43191` 为主入口，
`:43910` 作为其工程化补充视图（或后续并入），避免第三份维护成本。

## 4. 关联

- 场景系统：`docs/scene-system-v3.md`
- Panorama 入口：`docs/PANORAMA-DASHBOARD.md`
- 面板自愈工具：`bin/gac/zhixing-panel-sync.py`
