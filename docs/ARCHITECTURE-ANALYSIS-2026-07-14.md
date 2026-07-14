# eCOS v6 系统性架构分析 (2026-07-14)

> 基于架构 SSOT (`ARCHITECTURE.md` / `BRIEF.md` / `.omo/state/system.yaml`) +
> 2026-07-14 全盘 submodule 巡检实战数据 + memory 沉淀的 7 次踩坑。
> 不是穷尽清单, 是**痛点驱动的洞察 + 治本路线**。

---

## 一、成熟度悖论: 声明面满分 vs 执行面有 gap

| 指标 | 声明值 (`system.yaml`) | 实际观察 |
|------|---------------------|---------|
| `ecosystem_maturity_score` | **100** | — |
| `metacognition_safety_score` | **100** | — |
| `governance_loop_safety_score` | **100** | — |
| `debt_health` | **100** | resolved 多, 确实改善 |
| **`health_score`** | **84** → `debt_adjusted` **61.6** | 警戒 |
| **daemon 在线率** | **60%** (8 服务 3 在线, ollama stale) | ⚠️ runtime 层弱 |
| `active_agents` | 0 (idle 4) | 实战并发 agent 疯狂跑 |

**核心洞察**: 这是 `decl-exec-gap-meta-pattern` (memory, 11+ 实例) 的持续体现 —
maturity/safety 全 100 (声明面 SSOT 漂亮), 但 health 84 / daemon 60% / 并发 agent
实际造成 main 混乱 (执行面). **架构的"图纸"质量远超"实物"运行质量**.

---

## 二、分层健康度矩阵

```
L4 文档层     A   doc-ssot-contract 严格, 19 类 SSOT 各有权威源
L3 入口层     A   agora MCP gateway 统一 (14 mcp-server) + cockpit
L2 内核层     A-  kairon God Module 5/5 全拆, 16 包 ~155K LOC 稳
I0 织层       A   agora hub 单点接入, 命名空间内置
X1-X4 治理    B+  GaC 强, 但 worktree 假阳性 + agent 协调弱
L1 运行时     C+  ⚠️ daemon 60%, ollama stale, 探测假阳性 (已治本 4 层)
L0 协议层     A   ecos MOF M1-M3 + L0 constraints 稳
```

**最弱环节 = L1 运行时** (daemon 在线率 60%). 见 `runtime-probe-false-positive-treatment`
(memory): launchd 保活导致 "PID 在但服务死" 的假绿灯.

---

## 三、三大架构支柱状态

### ✅ 支柱 1: MCP Gateway (2026-07-14 正面突破)
- agora I0 hub + **14 mcp-server** 声明式注册 (kairon 9 + omostation 6, 含
  `bin/mcp-server-kos.py` 0-dep 双入口)
- FastMCP 统一 (kairon/eidos/kos 全迁) + `service.tool` 命名空间内置
- **评价**: AI agent 单点接入闭环, eCOS 最完整的架构成果之一

### ⚠️ 支柱 2: Submodule 治理 (脆弱 → 已补巡检)
- 17 submodule, 有 reachability gate (防悬空) + `sync-submodules-push`
- **痛点**: 2026-07-14 实战 **3 次 gitlink 全盘分叉** (agora/ecos/metaos/
  aetherforge/cockpit/bus-foundation 本地 vs origin 全不一致), 靠人工
  `submodule update ×9` 清零
- **本次治本**: `bin/submodule-gitlink-check.py` (PR#351) — 自动检测 `+/-/U`
  前缀, `--json` CI/cron 友好, 漂移 exit 1

### 🔴 支柱 3: 多 Agent 协调 (最大未解痛点)
- 声明面: AdvisoryLock (跨 session lockfile) + agent-workflow contract + P74
- **执行面**: worktree isolation 「终态治本就绪**未启用**」
  (`agent-isolation-rollout` memory)
- 2026-07-14 并发 agent (`claude --allowed-tools`) 直接抢主仓 main, 老王 4 次
  查 reflog 都在秒级动, **完全无法介入**
- **矛盾**: `governance_loop_safety` 100, 但 agent 协调实际靠 "人工等/停"

---

## 四、风险分级 + 治本路线

### 🔴 P0: 启用 agent isolation (战略级, 需拍板)
- **风险**: 不启用 = 每次多 agent 必互相破坏 (2026-07-14 实测).
  `governance_loop_safety` 100 是虚的.
- **治本**: `docs/AGENT-ISOLATION-ROLLOUT.md` 的 worktree + branch protection
  启用, 强制每 agent 走 `gac-worktree.sh claim`, 不碰主仓 main.
- **落地**: 写 ADR + 分阶段 (先新 agent 强制, 存量 agent 迁移).

### 🟡 P1a: submodule gitlink 巡检 — ✅ 已落地 (PR#351)
`bin/submodule-gitlink-check.py`, 建议挂 foundry 6h cron.

### 🟡 P1b: 补 L1 runtime 健康度 (daemon 60%)
- **风险**: daemon 在线率 60% × 探测假绿灯 = 服务实际死但报活.
- **治本**: ollama 等 stale 服务要么真启要么从 registry 摘; daemon 健康分
  纳入 `health_score` 主权重.

### 🟢 P2: 收敛声明/执行鸿沟 (meta)
- **风险**: maturity 100 vs health 84 的 gap 持续误导决策.
- **治本**: `health_score` 公式纳入 "执行面实证" (daemon 在线率权重↑ +
  声明面 maturity 权重↓), 让分数反映实物而非图纸.

### 🔵 P3 收尾 (2026-07-14 进度)
- ✅ `bin/git-health-hook.py` 移植 (core.bare 检测, PR#351, 源 r79-bump 已删)
- ✅ GitHub auto-delete head branch 启用 (`delete_branch_on_merge=true`)
- ⏳ bus-foundation pre-push format gate (和 cockpit 统一, 需改子仓 hook)

---

## 五、2026-07-14 落地进度

| 项 | 状态 | PR/动作 |
|----|------|---------|
| git-health-hook 移植主仓 | ✅ | PR#351 |
| submodule-gitlink-check 巡检脚本 | ✅ | PR#351 |
| r79-bump 孤儿分支删除 | ✅ | hook 移植后删 |
| auto-delete head branch | ✅ | repo 设置 |
| agent isolation 启用 | 📋 待拍板 | 需 ADR + 分阶段 |
| health_score 公式调整 | 📋 待拍板 | 需调权重 |
| bus-foundation pre-push gate | 📋 待拍板 | 改子仓 hook |

---

## 六、一句话总结

> **eCOS 的架构"设计"是 A 级 (分层清晰 / SSOT 严格 / MCP gateway 闭环 / 治理即代码),
> 但"运行"是 B- 级 (runtime 60% / agent 协调靠人工 / submodule 飘忽 / 声明执行鸿沟持续).
> 最大的杠杆点不是再加架构, 是把已有的治本机制启用起来 (agent isolation rollout) +
> 让健康分反映执行面 (maturity 权重降).**

---

**关联 memory**: `decl-exec-gap-meta-pattern` · `concurrent-agent-contention` ·
`runtime-probe-false-positive-treatment` · `agent-isolation-rollout` ·
`core-bare-anomaly` · `agora-mcp-gateway-p0` · `merge-conflict-verify-all-markers`
