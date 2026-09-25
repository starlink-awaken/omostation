---
name: dashboard-governance-patrol
description: 全景驾驶舱与治理大屏日常巡检、端口导流守护、数据新鲜度与门禁探针自愈技能包。
version: 1.0.0
owner: governance-team
last-reviewed: 2026-09-25
---

# Dashboard Governance Patrol Skill

> **单一人类总控入口巡检守则**：负责全景驾驶舱（Panorama & Cockpit-UI）的运行态巡检、端口导流守护（Sunset Redirector）、底层数据链路新鲜度校验与 11 大门禁矩阵探针核验。

---

## 1. 触发场景 (When to Use)

- 当需要确认治理驾驶舱 `:5173/panorama` 是否正常运行时；
- 当排查原 `:43191`（知行底座）或 `:43910`（Panorama 静态看板）端口被占或无法导流时；
- 当 Agent 启动会话需获取权威边界与任务建议时（检查 `agent-brief.json` 是否新鲜）；
- 每次日常 `make hygiene-patrol` 或提交重大架构变更前的前置健康巡查。

---

## 2. 核心巡检项与操作命令

### 巡检项 1: 原生驾驶舱与大屏路由可用性
- **目标**: 确保前端 `:5173` 正常服务，且 `/panorama` 5 大 Tab 原生可用。
- **命令**:
  ```bash
  # 检查 5173 端口响应
  curl -sI http://127.0.0.1:5173/panorama | grep -E "HTTP/|200"
  
  # 通过 Cockpit CLI 原生唤起全景控制舱
  cockpit panorama --web
  
  # 以沉浸大屏壁挂模式唤起
  cockpit panorama --wallboard
  ```

### 巡检项 2: 端口导流守护器 (Sunset Redirector) 存活态
- **目标**: 确保原 43191 与 43910 端口已全面关闭独立服务，统一由 `bin/panorama/sunset-redirector.py` 承载 302 导流与遥测镜像。
- **验证命令**:
  ```bash
  # 查看导流守护进程健康状态
  cockpit panorama --sunset
  
  # 验证 43191 导流响应 (期望 302 -> http://localhost:5173/panorama?tab=hero)
  curl -sI http://127.0.0.1:43191/ | grep -E "302|Location"
  
  # 验证 43910 导流响应 (期望 302 -> http://localhost:5173/panorama?tab=gates)
  curl -sI http://127.0.0.1:43910/ | grep -E "302|Location"
  ```
- **异常恢复**:
  ```bash
  # 若守护进程掉线，一键自愈拉起
  python3 bin/panorama/sunset-redirector.py --daemon
  ```

### 巡检项 3: 底层 SSOT 聚合产物新鲜度
- **目标**: 验证 `runtime/dashboard/` 下只读聚合产物是否在 74s 哨兵周期内保持新鲜。
- **核验路径**:
  - `runtime/dashboard/data.json`（全量 70 项采集键值）
  - `runtime/dashboard/agent-brief.json`（Agent 首读权威信封）
- **核验脚本**:
  ```bash
  python3 -c '
  import json, time, os
  p = "runtime/dashboard/agent-brief.json"
  if os.path.exists(p):
      age = time.time() - os.path.getmtime(p)
      print(f"agent-brief.json 年龄: {round(age, 1)}s (期望 <= 74s)")
  else:
      print("❌ agent-brief.json 缺失，需执行 bin/panorama/panorama-collect.py")
  '
  ```

### 巡检项 4: 11 大宪法级系统门禁 (A1-A9, RF0, RC-DL)
- **命令**:
  ```bash
  python3 bin/panorama/panorama-collect.py --gates
  ```

---

## 3. 避坑指南 (Pitfalls)

1. **禁止直接重启旧版 `live_server.py`**：原 43191 已正式 sunset 并入 `:5173/panorama`，切勿手动运行历史单体服务，否则会与 `sunset-redirector` 发生端口冲突。
2. **严禁破坏只读 SSOT 约定**：`bin/panorama/panorama-collect.py` 必须遵守 `--check-side-effects`，产物仅允许写入 `runtime/dashboard/`（gitignored），绝不能在仓库中留下未跟踪脏文件。
