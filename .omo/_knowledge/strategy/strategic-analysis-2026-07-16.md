# 系统性战略分析 — omostation 项目

> 生成时间: 2026-07-16
> 基于当前 main (53ae8b482) 的全维度扫描

---

## 一、战略全景图

### 1.1 项目结构

```
5+4+1+1 架构
17 子模块 / 17 项目 / 1 非子模块 (cockpit-ui)
68 个 GaC 工具 / 51 个 SSOT 工具

L0 ecos          协议层 — MOF / SSOT 注册表 / 约束
L1 runtime       运行时 — 调度 / 健康扫描 / MCP / KEI
L2 kairon/gbrain/omo/metaos  引擎 — 推理/知识/治理/元OS
L3 cockpit      入口 — 控制面 + 表现面
L4 l4-kernel    自我 — 自我改进
I0 agora        织层 — MCP-SSE 网关 + gateway
X  aetherforge/c2g/bus-foundation/omo-debt/observability/family-hub
```

### 1.2 运行时

| 服务 | 状态 | 端口 | 最后健康 | 运行时长 |
|:-----|:----:|:----:|:--------:|:--------:|
| **cron-service** | ✅ | 7450 | <60s | ~22h |
| **agora-sse** | ✅ | 7431 | <60s | ~22h |
| **agora-gateway** | ✅ | UDP 42024 | <60s | ~26h |
| **ollama** | ⏹️ idle | 11434 | <60s | — |

cron 线程调度器稳定, 健康扫描 60s, 自愈正常。**idle freshness 修复生效** — ollama 从 8.8 天未更新恢复到 <60s。

### 1.3 治理

| 维度 | 值 | 状态 |
|:-----|:---|:----:|
| **Phase** | 44 active | 目标: 治理可观测性 |
| **BOS** | 159/4 | 稳定 |
| **GaC 门禁** | 34 checks | ⚠️ FAIL (1 governance-semantic WARN, 非阻断) |
| **Debt** | 7 items, 全部 resolved | ✅ 刚刚从 git 恢复 |
| **健康分** | 83/75/83 (3 个值并存) | ⚠️ 多写冲突 (已知) |
| **Daemon 在线** | 3 running + 1 idle = 4/4 | ✅ |

---

## 二、关键矛盾

### 矛盾 1: 外部 Sync 覆盖治理工作

```
模式识别:
  main 上 ~70% 提交来自外部 sync (author: starlink-awaken)
  sync 内容: cockpit 功能提交 / submodule 指针更新 / 状态写入
  
  外部 sync 的行为:
  - 不加 warning 覆盖 .omo/state/system.yaml
  - 不加 warning 覆盖 .omo/state/health.yaml (ISC-1 冲掉 ISC-2)
  - 不加 warning 删除 .omo/debt/items/ 目录
  - 不加 warning 覆盖 BRIEF.md
  
  结果: 治理团队修的, sync 覆盖的。治理团队再修, sync 再覆盖。
```

**根因**: 外部 sync 进程无写权限意识，认为"写最后一行的赢"。治理团队无防御设施。

### 矛盾 2: GaC 门禁永不绿

```
34 checks 中 33 个 PASS, 但 governance-semantic 报 WARN (非阻断)
→ 结果: FAIL
→ 门禁输出被忽略 (狼来了效应)
```

### 矛盾 3: 健康分无事实标准

```
同一个 system.yaml 里有 3 个 health_score:
  83   ← ISC-2 推算 (gov=0.3/runtime=0.5)
  75   ← runtime 健康扫描 (3/4)
  83.0 ← debt_adjusted (Phase 44 定义)

health.yaml 里还有一个:
  100  ← ISC-1 (gov=0.5/runtime=0.3, 被外部 sync 覆盖)
```

**没有 SSOT** — 4 个值, 4 个含义, 谁信谁的?

### 矛盾 4: agora-gateway 是架构盲区

```
matrix.yaml → health_url: null → 健康扫描只能查 PID
gateway 进程活着, 但无法验证是否正常服务
无 HTTP /health 端点
无 crash 监控 (launchd 5s 自动重启, 无人知道重启了多少次)
```

---

## 三、结构化建议: 分层行动

### Layer 1 — 防御 (P0, 周内)

| # | 行动 | 价值 |
|:-:|:-----|:-----|
| 1 | **GaC #38 写守卫** — 已创建, 需验证在 CI 中触发 | 检测 system.yaml 多写 |
| 2 | **Debt 目录写保护** — `.omo/debt/` 加 `.gitignore` pista? 或 pre-commit 检测 | 防止外部 sync 再次删除 |
| 3 | **健康分对齐** — 选定一个公式, 删除其他值 | 停止"4 个健康分"混乱 |

### Layer 2 — 修复 (P1, 月内)

| # | 行动 | 价值 |
|:-:|:-----|:-----|
| 4 | **agora-gateway HTTP /health** — 加一个简单的 `GET /health` 端点 | 解决架构盲区 |
| 5 | **GaC 门禁信号重置** — governance-semantic WARN 改为非阻断或修复 | 门禁回到 GREEN |
| 6 | **GaC compute-onboard** — 从 broken 改为正式修复或彻底移除 | 减少噪音 |

### Layer 3 — 架构 (P2, 季度)

| # | 行动 | 价值 |
|:-:|:-----|:-----|
| 7 | **外部 sync 治理化** — sync 进程改为写 OMO broker 而非直接写文件 | 根治覆盖问题 |
| 8 | **子模块策略执行** — GaC #39 从文档变为可执行 | 防止子模块衰减 |
| 9 | **BRIEF.md 自动化** — 由 agent 启动时从 SSOT 自动合成 | 消除手动维护 |

---

## 四、风险矩阵

| 风险 | 概率 | 影响 | 缓解 |
|:-----|:----:|:----:|:-----|
| 外部 sync 再次删除 debt 目录 | 高 | 中 | GaC #37 + `.omo/debt/` git restore |
| health_score 分歧导致误判 | 高 | 高 | 选一个公式, 删除其他 |
| agora-gateway 崩溃无声 | 中 | 高 | 加 /health 端点 |
| 外部 sync push 覆盖 main | 中 | 高 | 分支保护 + push hook |
| ollama idle 被误判为故障 | 低 | 低 | 已修复 (idle freshness) |

---

## 五、一句话总结

```
项目有 17 个子模块, 68 个门禁, 159 个 BOS 服务, 4 个运行时 daemon,
但真正决定系统健康的关键信号(健康分/GaC 状态/gateway 服务性)都是模糊的。
系统不缺代码, 缺一个"到底什么是好的"的定义一致性。
```

**当前最高价值行动**: 让 system.yaml 只有一个 health_score, 让 GaC 门禁回到 GREEN, 保护 debt 目录不被再次删除。
