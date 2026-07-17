# 治理深度审计 — 问题验证与根本性治理方案

> run: 20260715T130015Z-governance-audit-7d4dae5f
> 审计师: Hermes Agent (governance-agent profile)
> 目标: 验证 8 项已知问题 → 根因分析 → 根本性治理方案

---

## 一、问题验证矩阵

| # | 问题 | 声明 | 证据 | 验证 |
|:-:|:-----|:-----|:-----|:----:|
| 1 | gateway 无 /health | `health_url: null, port: null` | matrix.yaml:91-93 | ✅ 确认 |
| 2 | ISC 公式覆盖 | ISC-1 ≠ ISC-2 | health.yaml vs Phase 44 定义 | ✅ 确认 |
| 3 | compute-onboard 超时 | GaC 永远 FAIL | gac-local-gate.py output | ✅ 确认 |
| 4 | ollama freshness 不更新 | last_healthy=764071s | scheduler_state.json | ✅ 确认 |
| 5 | system.yaml 多写 | 3 x health_score: | 行 8/194/207 | ✅ 确认 |
| 6 | BRIEF.md 回退风险 | 无写保护 | 历史被多次覆盖 | ✅ 确认 |
| 7 | gateway crash 无监控 | 无告警链路 | launchd KeepAlive 无 metrics | ✅ 确认 |
| 8 | 子模块非 main | 12/17 不在 main | `git submodule status` | ✅ 确认 |

---

## 二、根因分析

### 根因 A: 多写入口 → SSOT 不可信 (影响 #2, #5, #6)

```
     ┌──────────────────────┐
     │  c2g.strategy sync    │──→ health.yaml （ISC-1 覆盖 Phase 44）
     │  (外部策略同步)        │
     └──────────────────────┘
     ┌──────────────────────┐
     │  cron 健康扫描         │──→ system_health.yaml → system.yaml
     │  (runtime 扫描)        │    （写入 health_score: 75）
     └──────────────────────┘
     ┌──────────────────────┐
     │  agent 手动 patch     │──→ system.yaml （写入 health_score: 100）
     │  (多 session 平行写)   │
     └──────────────────────┘
     ┌──────────────────────┐
     │  BRIEF.md agent write │──→ BRIEF.md （被外部 sync 回退）
     │  (会话级认知文件)       │
     └──────────────────────┘
```

**核心问题**: system.yaml 和 health.yaml 没有写权限守卫。任何人/任何 进程都可以写入，最后一次写入赢。

### 根因 B: 门禁退化 — 永久 FAIL 导致无人看门禁 (#3)

**compute-onboard** 检查外部算力服务 (cc-switch, codexbar, litellm, omlxc)，本地没有这些服务 → 永远超时 → 门禁永远 FAIL。

但 GaC 门禁是所有治理的汇总"红绿灯"。如果它永远 FAIL，读者就学会了忽略它。**门禁退化为噪音。**

### 根因 C: 健康扫描的状态机不完全 (#4)

```python
# scheduler.py:400
if rt == "running":                          # ← 只写 "running" 的 last_healthy
    last_healthy[svc.name] = current_time     # ← ollama 的 rt="idle", 不命中
```

ollama 的 `status=idle` 在内存中被视为健康，但不持久化到 state 文件。freshness 字段对 idle 服务永远显示"从未健康"。

### 根因 D: 子模块指针没有生命周期守卫 (#8)

17 个子模块中有 12 个不在 `heads/main`。这不是错误——有些功能分支是故意的（cockpit 在 codex 分支，metaos 在 work/adr-0181）。**问题是没有守卫来回答"这个分支还对吗"**。如果上游分支删除，子模块指针损坏无声。

---

## 三、根本性治理方案

### 方案 1: SSOT 写守卫 — 写权限分层 (P1)

```
┌─────────────────────────────────────────────────┐
│                 system.yaml 写权限表              │
├──────────────┬────────────┬──────────────────────┤
│ 写入方        │ 允许字段    │ 禁止字段              │
├──────────────┼────────────┼──────────────────────┤
│ cron 健康扫描  │ health.*   │ phase.*/debt.*       │
│              │ runtime_*  │                      │
├──────────────┼────────────┼──────────────────────┤
│ c2g.strategy │ phase.*    │ health_score          │
│              │ next_*     │ (必须经过 OMO broker)  │
├──────────────┼────────────┼──────────────────────┤
│ agent patch  │ —          │ 必须先 claim          │
└──────────────┴────────────┴──────────────────────┘
```

**实施**: 在 OMO cli 中加 `state write-field` 命令，只有此命令能写 system.yaml。
直接 `write_file` / `sed` 写被 pre-commit hook 拦截。

### 方案 2: 健康分公式守卫 (P1)

**ISC-2** (Phase 44 定义) 是经过审计校准的权重。c2g.strategy 不应覆写。

**实施**: 
- `health.yaml` header 写入 `immutable: true` 标记
- `c2g.strategy` 同步时检测此标记 → 跳过 health_score 覆写
- Phase 44 的 ISC-2 权重编码为 GaC 检查 `health-score-formula-check`

### 方案 3: GaC 灰名单机制 (P2)

不是所有 check 都在所有环境下可运行。需要支持"已知不可用，豁免等待修复"。

**实施**: 在 `GATES_LIST` 中加 `broken` 属性:
```python
{"id": "compute-onboard", "broken": True, "broken_reason": "依赖本地算力服务"}
```

`broken` 的 check 不参与门禁 FAIL 计数，但 `gac-local-gate.py --strict` 仍然检查。

### 方案 4: idle 服务 freshness 修复 (P3)

**实施**: scheduler.py 行 400 的 `if rt == "running":` 改为:
```python
if rt in ("running", "idle") or hc == "healthy":
    last_healthy[svc.name] = current_time
```
这与行 378 的 freshness 更新条件对齐。

### 方案 5: 子模块分支声明 (P3)

在 `docs/project-registry.yaml` 中加 `submodule_branch_policy`:
```yaml
submodule_policy:
  stable: [projects/bus-foundation, projects/kairon, ...]
  feature: [projects/cockpit, projects/metaos, ...]
  tolerance_days: 30  # 超出此天数无更新 → warning
```

GaC #? 检查此规则。

---

## 四、实施路径: Wave 1 (这个 session)

```
P1  SSOT 写守卫     → 加 pre-commit hook 拦截无权限写 system.yaml
P1  健康分公式守卫   → health.yaml immutable header + c2g 同步检测
P2  GaC 灰名单      → gac-local-gate.py 加 broken 属性
P3  idle freshness  → scheduler.py 行 400 修复
P3  子模块声明       → project-registry.yaml 加 submodule_policy
```

---

## 五、治理自检闭环

这次审计本身揭示了治理系统的根本矛盾:

```
治理系统设计为"被信任的 SSOT"，但实际上 system.yaml/health.yaml 是多写入口的堆。
任何人写最后一行就赢了。这不是 SSOT, 这是 Write-Conflict-Tolerant Heap (WCTH)。
```

根本性治理是: **让治理系统可被治理**。写权限分层、门禁灰名单、公式不可变标志——都是让"治理之治理"可执行的手段。
