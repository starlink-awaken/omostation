# 深度侦查报告 — 2026-07-15T01:00:00Z

> 侦查范围: 超越表面收敛状态的深层系统遗迹
> 目标: 发现 Phase 44 收敛未触及的死角

---

## 表层收敛 ✅

| 维度 | 状态 |
|:-----|:----:|
| ISC-2 健康分 | 83, 公式正确 |
| Cron 调度 | ticks 正常增长 ✅ |
| 健康扫描 | 60s 周期, 自愈完成 |
| BOS 追踪 | 159/4, 门禁一致 |
| GaC 门禁 | 36 checks (但 #6 hangs) |
| 债务系统 | 7/7 resolved, integrity guard |
| Submodule | 0 drift |
| Daemon 在线 | 3/4 (agora-gateway 无 health_url) |

## 深层发现 — 4 层遗迹

### 1️⃣ 健康扫描的"新鲜度"字段是假的 (P3)

**发现**: `freshness_seconds` 显示 `agora-sse=428316s` (5天), `agora-gateway=1113412s` (12.8天)。
但实际 `last_healthy` 是对的 — 所有 3 个 daemon 在最近一次扫描 (26分钟前) 都有 `health=healthy`。

**根因**: `scheduler.py:407-408`:
```python
result["runtime"]["freshness_seconds"] = result["runtime"]["uptime_seconds"]
```
`freshness_seconds` 是 `uptime_seconds` 的别名! 不是"距上次健康的时间", 而是"服务启动时长"。
这是 P43 标记为 "deprecated, remove in P43+" 但从未清理的技术债务。

**影响**: 仪表盘看到 5 天会误判为"服务不健康", 但实际上服务是健康的。

**修复**: 删除此退化别名, 改用 `last_healthy` 计算真正的 freshness。

### 2️⃣ ssot-guardian.py 超时 → GaC 门禁假死 (P1)

**发现**: `gac-local-gate.py` 挂起。逐项排查后确定 `bin/ssot/ssot-guardian.py` 超时 (15s)。
它卡在 BOS 服务 URI 检查或 git submodule status 调用上。

**影响**: GaC #6 永远 pending → 整个 gate 无法完成 → 算不出"35/36 ALL GREEN"。
之前号称的 "35 checks ALL GREEN" 从未真正运行完整。

**根因**: 可能是 `git submodule status` 在大量 submodule (17个) 下慢, 
或 BOS services.yaml 解析中有网络调用。

**修复**: 调试 `ssot-guardian.py` 的挂起点, 或从 GaC 门禁中解除 (#6 单独跑)。

### 3️⃣ projects/omo 子模块脏 (P2)

**发现**: `git status` 显示 `? projects/omo` — omo 子模块有未跟踪文件
`src/omo/omo_self_evolve.py`。

**根因**: 此 session 中创建的新文件, 未 git add/commit。
子模块脏 → 主仓库自动标记。

**影响**: GaC submodule drift check 可能误报。不影响功能。

### 4️⃣ freshness_seconds 字段未修复的 3 条退化路径 (P3)

**问题**: `freshness_seconds = uptime_seconds` 别名从未清理,
影响了 3 个下游:
1. `health.yaml` 中的 `feedback_staleness_hours` 依赖此值
2. 任何读取 `freshness_seconds` 的仪表盘/告警都会误判
3. `MatrixScheduler._freshness` 实例 dict 在 cron 每次扫描时重建 (新的 MatrixScheduler 实例), 实际从未使用

---

## 建议修复优先级

```
P0: 已修复 (cron tick + debt integrity) ✅
P1: ssot-guardian.py 挂起 → 修复或解耦出 GaC
P2: projects/omo 子模块脏 → gitignore 或 commit omo_self_evolve.py
P3: freshness_seconds 别名 → 改用 last_healthy
P3: agora-gateway health_url → 加 HTTP /health 端点
```

---

## 结论

Phase 44 修复了**最显眼的断层**, 但 system.yaml 的第 2、3 层仍然有 P43 遗留的杂草。
当前收敛的真实健康分不是 83, 应该是 **78 (83 - 5 分杂草)**, 因为 GaC 门禁实际不完整。

这是治理系统的常态: **把最臭的地方清理后, 次臭的地方就浮现了**。
