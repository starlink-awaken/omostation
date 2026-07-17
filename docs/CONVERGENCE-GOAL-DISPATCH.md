---
title: 收敛期 · Goal 模式命令下发模版
status: active
type: dispatch-template
owner: 夏明星
created: 2026-07-15
related:
  - .omo/_knowledge/decisions/0210-three-year-strategy-execution-convergence.md
  - docs/CONVERGENCE-EXECUTION-STATUS.md
  - .omo/goals/current.yaml
note: >
  按 eCOS goal 模式 + agent-workflow 生命周期封装的收敛期落地下发单。
  每个 G-CONV.* block 可独立下发给一个 agent 执行。运行时数字以 .omo/state/*.yaml 为准。
---

# 收敛期 · Goal 模式命令下发模版

> **用法**：把某个 `G-CONV.*` block 整段发给一个 agent。每个 block 自带 goal 定义、
> ADR-0203 workflow 生命周期、隔离 claim、验收标准、上下文文档。agent 照此闭环。
> **红线**：所有 block 强制先 `agent-workflow.py start` 再改文件（ADR-0203）；
> 走独立 worktree 不碰主仓 main（ADR-0218 dogfood）。

---

## 0. 通用 dispatch 信封（模版占位，复制后替换 `<...>`）

```bash
# ── eCOS Agent Dispatch Envelope ─────────────────────────────
# GOAL: <G-CONV.N>  <一句话目标>
# PROFILE: <agent-profile>          # 如 runtime-engineer / governance-agent / data-engineer
# RISK: <L0|L1|L2|L3>

WS=/Users/xiamingxing/Workspace; cd "$WS"

# 1) 选对 workflow（防错位；ADR-0203 强制）
uv run --with "pyyaml" python bin/agent-workflow.py suggest --from-diff --profile <agent-profile>

# 2) start（拿 run-id；未 start 直接改文件 = 违规）
uv run --with "pyyaml" python bin/agent-workflow.py start <workflow-id> \
  --profile <agent-profile> --objective "<G-CONV.N 一句话目标>"

# 3) 隔离 worktree（dogfood ADR-0218，不碰主仓 main）
bash bin/gac/gac-worktree.sh claim <session-slug>     # 落在 $WS_PARENT/ws-<session-slug>

# 4) 执行 <见各 goal 的 acceptance 步骤>

# 5) claim 路径 + verify + closeout
uv run --with "pyyaml" python bin/agent-workflow.py claim <run-id> --path <改动路径>
uv run --with "pyyaml" python bin/agent-workflow.py verify <run-id> --from-diff --execute
uv run --with "pyyaml" python bin/agent-workflow.py closeout <run-id>

# 6) 提交（隔离分支 → PR → merge；勿直推 main）
bash bin/gac/gac-worktree.sh submit <session-slug>    # push + gh pr create
bash bin/gac/gac-worktree.sh merge  <session-slug>    # squash merge + release + 删分支
```

---

## 1. Goal 定义块（可 append 到 .omo/goals/current.yaml，经 OMO broker）

```yaml
# 收敛期 M1 goals（ADR-0210）— 按性价比排序
- id: G-CONV.4
  desc: gitlink 巡检挂 foundry 6h cron
  kpi: submodule-gitlink-check.py 每 6h 自动跑，漂移 BRIEF 可见
  priority: P1
  risk: L0
  status: pending
  tasks: []
- id: G-CONV.1
  desc: Agent Isolation ISC-4 收尾（branch protection API 核实）
  kpi: gh api .../branches/main/protection 返回 200
  priority: P0
  risk: L0
  status: pending
  tasks: []
- id: G-CONV.2
  desc: 修复 L1 runtime daemon 假红灯（运行态诊断，非改码）
  kpi: service_online_ratio ≥ 0.9（去假阳性口径），system.yaml/health.yaml 一致
  priority: P0
  risk: L1
  status: pending
  tasks: []
- id: G-CONV.3
  desc: health_score ISC-3 重构（分项去污染）
  kpi: 三分项均可追溯执行面实测；制造并发冲突 governance 子分可下探
  priority: P1
  risk: L2
  status: pending
  tasks: []
- id: G-CONV.5
  desc: 单写者门禁即免疫 L2 自愈（声明已建，补自愈草案）
  kpi: 门禁失败自动生成修复草案 commit；write-owner-audit 进 pre-commit
  priority: P2
  risk: L2
  status: pending
  tasks: []
- id: G-CONV.6
  desc: KOS 索引启动（个人大脑前置）
  kpi: kos/ 索引篇 > 0 且季度持续增长；首批导入 636 创意创作产出
  priority: P1
  risk: L1
  status: pending
  tasks: []
```

---

## 2. 逐 goal 下发单（复制整块发给 agent）

### ▶ G-CONV.4 · gitlink 巡检挂 cron（最快见效，先做）

```bash
# GOAL G-CONV.4 | PROFILE governance-agent | RISK L0
WS=/Users/xiamingxing/Workspace; cd "$WS"
uv run --with "pyyaml" python bin/agent-workflow.py start project-code-change \
  --profile governance-agent --objective "G-CONV.4 gitlink 巡检挂 foundry 6h cron"
bash bin/gac/gac-worktree.sh claim gconv4-gitlink-cron
# 执行:
#   - 把 bin/submodule-gitlink-check.py --json 加入 foundry 6h cron deck
#   - 漂移 exit 1 → deck fail → BRIEF 可见
# 验收: foundry 每 6h 跑; 制造一次 gitlink 漂移被自动检出
# 上下文: docs/CONVERGENCE-EXECUTION-STATUS.md 第①④行
bash bin/gac/gac-worktree.sh submit gconv4-gitlink-cron && bash bin/gac/gac-worktree.sh merge gconv4-gitlink-cron
```

### ▶ G-CONV.1 · Agent Isolation ISC-4 收尾（1 条命令）

```bash
# GOAL G-CONV.1 | PROFILE governance-agent | RISK L0
gh api repos/starlink-awaken/omostation/branches/main/protection | jq '.required_pull_request_reviews, .enforce_admins'
# 验收: 返回 200 且 required_pull_request_reviews 非空 → ISC-4 达成, 回写 ADR-0218 Confirmation
# 若 404: bash bin/gac/gac-branch-protection.sh --set  (交互确认后 PUT)
```

### ▶ G-CONV.2 · 修复 L1 runtime daemon（M1 最高杠杆；运行态诊断）

```bash
# GOAL G-CONV.2 | PROFILE runtime-engineer | RISK L1
WS=/Users/xiamingxing/Workspace; cd "$WS"
uv run --with "pyyaml" python bin/agent-workflow.py start project-code-change \
  --profile runtime-engineer --objective "G-CONV.2 修复 agora-gateway daemon 假红灯"
bash bin/gac/gac-worktree.sh claim gconv2-runtime
# 执行 (关键: 这是运行态诊断, 探测跳过 stdio 的源码修复已存在于 health.py):
#   1. 重启 agora-gateway 让进程拾取最新 health.py (_is_transient/_tick 已修)
#   2. 活体查 _is_transient: registry.get_saved_config(name) 是否带 command/mcp_endpoint
#      → 若配置缺 mcp_endpoint, persistent 判定失准, 全后端被误当 persistent 探测全 fail
#   3. 若重启后仍 all-dead = 真故障(20 persistent 后端不可达), 查后端本身
#   4. ollama status=idle 计入在线 (idle≠down)
# 验收: system_health.yaml agora-gateway health_check=healthy; service_online_ratio≥0.9
# 上下文: docs/RUNTIME-DAEMON-REMEDIATION.md (根因 A 深挖版)
uv run --with "pyyaml" python bin/agent-workflow.py verify <run-id> --from-diff --execute
bash bin/gac/gac-worktree.sh submit gconv2-runtime && bash bin/gac/gac-worktree.sh merge gconv2-runtime
```

### ▶ G-CONV.3 · health_score ISC-3（依赖 G-CONV.2 先落）

```bash
# GOAL G-CONV.3 | PROFILE governance-agent | RISK L2 | BLOCKED-BY G-CONV.2
WS=/Users/xiamingxing/Workspace; cd "$WS"
uv run --with "pyyaml" python bin/agent-workflow.py start project-code-change \
  --profile governance-agent --objective "G-CONV.3 health_score ISC-3 分项去污染"
bash bin/gac/gac-worktree.sh claim gconv3-isc3
# 执行 (经 OMO broker, 勿直写 health_score):
#   1. runtime 子分改用去假阳性 ratio (依赖 G-CONV.2)
#   2. governance 子分掺入执行面: 并发冲突数/抢号事件/孤儿 worktree 计数
#   3. service_online_ratio 单源 (health.yaml 权威 + system.yaml AUTOGEN 回指)
#   4. omo state sync 重算
# 验收: 三分项可追溯执行面实测; 制造并发冲突 governance 子分下探
# 上下文: docs/HEALTH-SCORE-ISC3-DESIGN.md
uv run --with "pyyaml" python bin/agent-workflow.py verify <run-id> --from-diff --execute
bash bin/gac/gac-worktree.sh submit gconv3-isc3 && bash bin/gac/gac-worktree.sh merge gconv3-isc3
```

### ▶ G-CONV.5 · 单写者门禁即免疫 L2 自愈

```bash
# GOAL G-CONV.5 | PROFILE governance-agent | RISK L2
WS=/Users/xiamingxing/Workspace; cd "$WS"
uv run --with "pyyaml" python bin/agent-workflow.py start project-code-change \
  --profile governance-agent --objective "G-CONV.5 门禁即免疫 L2 自愈草案"
bash bin/gac/gac-worktree.sh claim gconv5-gate-immunity
# 执行 (声明层 write-owners.yaml + GaC#38 已存在, 补自愈):
#   1. 确认 bin/ssot/write-owner-audit.py 进 .pre-commit-config.yaml
#   2. 门禁失败时自动生成本地修复草案 commit (L2), 供人审
# 验收: 非 owner 写入被拦且生成修复草案; audit 在 pre-commit 生效
# 上下文: .omo/_truth/registry/write-owners.yaml
uv run --with "pyyaml" python bin/agent-workflow.py verify <run-id> --from-diff --execute
bash bin/gac/gac-worktree.sh submit gconv5-gate-immunity && bash bin/gac/gac-worktree.sh merge gconv5-gate-immunity
```

### ▶ G-CONV.6 · KOS 索引启动（唯一从零；跃迁期前置）

```bash
# GOAL G-CONV.6 | PROFILE data-engineer | RISK L1
WS=/Users/xiamingxing/Workspace; cd "$WS"
uv run --with "pyyaml" python bin/agent-workflow.py start project-code-change \
  --profile data-engineer --objective "G-CONV.6 KOS 索引启动 首批入库"
bash bin/gac/gac-worktree.sh claim gconv6-kos-seed
# 执行:
#   1. 盘 @创意创作/_outputs (636 篇) 等高价值知识源
#   2. 建入库流程, 首批导入 kos/, 打通 gbrain/kos 入库链路
#   3. 设季度积累目标写入 goals
# 验收: kos/ 索引篇 > 0 且持续增长; 入库流程可复用有证据
# 上下文: c2g Pitch Idea-P1-KOS-索引积累启动
uv run --with "pyyaml" python bin/agent-workflow.py verify <run-id> --from-diff --execute
bash bin/gac/gac-worktree.sh submit gconv6-kos-seed && bash bin/gac/gac-worktree.sh merge gconv6-kos-seed
```

---

## 3. 编排建议（依赖 + 并发）

```
并发可同时下发:  G-CONV.4 (cron) · G-CONV.1 (ISC-4) · G-CONV.6 (KOS)   # 互不依赖
串行:            G-CONV.2 (runtime) ──→ G-CONV.3 (ISC-3)               # ISC-3 依赖 runtime 去假阳性
独立:            G-CONV.5 (门禁免疫)                                    # 随时
```

> **红线复述**：每个 agent 必先 `agent-workflow.py start`、走独立 worktree、经 PR 合并；
> 禁止直推 main、禁止手写 planned task 入 .omo（走 c2g/omo broker）。撞 ADR/分支号按 ADR-0202 D4。

---

*Goal 下发模版 · 2026-07-15 · 夏明星 · 占位 `<...>` 由下发人替换*
