---
status: active
lifecycle: ssot
owner: governance-team
last-reviewed: 2026-06-28
---

# Omostation 债务状态追踪 — 审计后续 & 当前断裂清单

**生成日期**：2026-06-28T12:30+08:00
**基线文档**：`.omo/_knowledge/audits/2026-06-28-debt-realness-audit.md`
**基线提交**：`57f9cf46`（债务 drift 修复）
**后续修复**：`4a2203c1`（X-Plane Audit Agent：registry SSOT 对齐 + health 门禁恢复）
**子模块 bump**：`dc3f9843`（ecos/kairon/omo 指针对齐）

---

## 1. 已关闭项（基线中 9 个问题，已解决 5 个）

| # | 问题 | 审计级 | 修复内容 | 修复者 |
|:-:|:-----|:------:|:---------|:------:|
| 1 | debt-items 目录缺失 | 🔴 P0 | 创建 `.omo/debt/items/`（含 .gitkeep），registry 路径回归顶层目录 | X-Plane Audit Agent |
| 5 | pre-commit 钩子全部失效 | 🔴 P0 | `pre-commit 4.6.0` 已安装，26 个 hooks 注册生效，`pre-commit run` 可达 | 自动确认 |
| 6 | ecos 子模块指针漂移 | 🔴 P0 | 子模块已 bump 对齐：ecos→0a13cf7, kairon→f83462a, omo→118cfd8 | X-Plane Audit Agent |
| 7 | health.yaml 过期（4 天） | 🟡 P1 | `bin/compass_radar.py` 已刷新，health_score=70 | X-Plane Audit Agent |
| 9 | commit 门禁断裂（check_health_ssot） | 🟡 P1 | 脚本路径修正 + health 恢复，`--no-verify` 不再必须 | X-Plane Audit Agent |

### 1.1 重要纠偏记录

基线初版将 debt 路径误指向 `.omo/_control/debt-items/`（假设遵从 4-plane 分层）。X-Plane Audit Agent 验证后发现 `DEBT_DIR` 在代码中是顶级运行时目录（与 `GOALS_DIR`/`TASKS_DIR` 平级），非 `_control` 子目录。路径已回归 `.omo/debt/items/`。

> **教训**：架构原则不能靠猜测应用——必须先查代码中 `omo_paths.py` 等实际路径定义，再判断归属。

---

## 2. 当前剩余断裂点（4 个开放）

### 🔴 P0 — 运行时 & CI

#### #2 — 5/9 运行时服务离线

**基线状态**：system.yaml `online_services: 4`, `offline_services: 5`
**当前状态**：**未变**

| 指标 | 值 |
|:-----|:---:|
| 总服务 | 9 |
| 在线 | 4 |
| 离线 | **5** |
| 健康 | 8（含离线的仅看健康探针） |
| 上次扫描 | `1782286194`（6月23日前后） |
| 陈旧服务 | 0 |

**证据**：`system.yaml` L189-L197 未更新，`last_scan` 仍在 6月23日。

---

#### #3 — gbrain-index launchd 僵尸

**基线状态**：`unhealthy_services: [gbrain-index]`，exit 0 但未卸载
**当前状态**：**未变**

仍然在 system.yaml 不健康列表，无人处理。

---

#### #4 — D2_CI_E2E CI pipeline 全部禁用

**基线状态**：4 处 `if: false`，workflow 标记废弃（P41-W1）
**当前状态**：**未变**

| Job | 行号 | 状态 |
|:----|:----:|:----:|
| kairon 安装 | L62 | `if: false` |
| docker-build | L82 | `if: false` |
| integration-test | L99 | `if: false` |
| kairon-e2e-test | L154 | `if: false` |

**根因**：SharedBrain 已归档 + kairon 被 `.gitignore` 排除导致 workflow 事实上不可运行。容器化基础设施（Dockerfile/docker-compose/entrypoint）已完成，但 CI 通道被架构决策截断。

**恢复前提**：需重新评估 kairon 的 CI 策略（可能迁移到子模块独立 CI）。

---

### 🟡 P1 — 数据过时

#### #8 — debt dashboard 过期

**基线**：`current.yaml` + `health-trend.md` 最后更新 2026-06-11
**当前**：**未变** — 已 **17 天**未刷新

dashboard 显示 6月11日的债务快照（当时 9 项债务全标记为 done），但由于 `debt/` 目录已重建后，dashboard 未重新生成，内容仍反映 17 天前的状态。

---

## 3. 新发现信号（基线之后产生的）

### 3.1 health_score 骤降 18 点

| 指标 | 审计时（system.yaml） | 当前（health.yaml） | 变化 |
|:-----|:--------------------:|:-------------------:|:----:|
| health_score | 100 | **70** | ↓ 30 |
| health_score_raw | 88 | —（不再暴露 raw） | — |
| debt_adjusted | 88.0 | — | — |
| 异常数 | 0 | **2** | ↑ 2 |

下降原因不是系统变差了，而是旧健康分使用了有 bug 的公式（100 分是自评漂移值），`compass_radar` 给出了更真实的评分。

### 3.2 两个健康异常

```
[WARN]  L3 高风险任务 1 个, 需重点 review
[WARN]  Owner 集中度: unassigned 持有 54% 任务 (单点故障风险)
```

- L3 高风险任务：需定位具体是哪一个 planned task
- 任务无主率 54%：29 个 planned tasks 中约 16 个无 assigned_to

### 3.3 任务管线微涨

| 指标 | 审计时 | 当前 |
|:-----|:------:|:----:|
| 总任务 | 157 | **158** |
| 已完成 | 128 | 128 |
| 已规划 | 29 | **30** |

多出来 1 个 planned task（可能来自当天的 OPC 自演化产出）。

---

## 4. 当前断裂图谱

```
                   影响范围
                  窄 ←───→ 广
严  高  ┌──────────────────┐
重       │ #2 服务离线(5/9) │ ← 不变
度       │ #3 gbrain 僵尸   │
    ↑    │ #4 CI 禁用(4×)   │
         │                  │
  中     ├──────────────────┤
         │ #8 debt dashboard│
         │ 过期 17 天       │
         │                  │
  低     └──────────────────┘
         (P0 项从 6 → 3 个)
```

---

## 5. 推荐修复路径（更新版）

| 优先级 | 行动 | 预估 | 依赖 | 说明 |
|:------:|:-----|:----:|:-----|:-----|
| 🥇 | 排查 5 个离线服务根因 | 2h | 无 | 先区分是部署漂移还是服务真挂；gbrain-index 优先 |
| 🥇 | 清理 gbrain-index 僵尸 | 0.3h | 上述 | `launchctl` 卸载 + 重启或清理 |
| 🥇 | 刷新 debt dashboard | 0.2h | #1 已修 | 重新生成 `current.yaml` + `health-trend.md` |
| 🥈 | CI 策略评估（kairon） | 1h | 架构决定 | 是否需要复活 workflow，或迁到子模块独立 CI |
| 🥉 | 审查 L3 高风险任务 + 分配 owner | 1h | 无 | 降低 unassigned 54% |
| 🥉 | 认领 3 个 P0 planned tasks | 各 1-4d | — | 待战略排期 |

---

## 6. 修复时间线

```
57f9cf46   [Hermes Agent] 债务 drift 修复（system.yaml 同步、debt_weight=0、公式修正）
     │
     ├─ dc3f9843   [X-Plane Agent] 子模块 bump（ecos/kairon/omo）
     │
     └─ 4a2203c1   [X-Plane Agent] P0 治本
            ├─ #1 debt-items 目录重建（纠偏 _control 路径误判）
            ├─ #7 health.yaml 刷新（compass_radar → health=70）
            ├─ #9 commit 门禁恢复
            └─ 测试验证：27 governance+debt 测试 pass
                    │
                    └─ ⬅ 当前位置
                       4 个坑开放（#2 #3 #4 #8）
```

---

*跟踪人：Hermes Agent · 2026-06-28T12:30+08:00*
*基线：`.omo/_knowledge/audits/2026-06-28-debt-realness-audit.md`*
