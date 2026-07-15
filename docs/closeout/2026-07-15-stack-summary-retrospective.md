# Closeout — 2026-07-15 全栈总结与复盘

> **范围**: Scheme C 5b → 5c L2 ACE apply → ops（doctor/cron/status API）+ Wave2 A/B/C 全链路  
> **主干 tip（feature 收口）**: `128bb661a` — PR [#369](https://github.com/starlink-awaken/omostation/pull/369)  
> **前置基线**: 2026-07-14 tech-debt/CI landing（PR #352 及前序）  
> **本文件性质**: 总结 + 复盘（无新代码）；各阶段 closeout / ADR 为 SSOT 细节源

---

## 1. 一句话结论

一天内按 **方案先行 → 小 PR 串行落地 → worktree+PR 合入 main** 的节奏，关闭了 Scheme C **5b 容器执行面** 与 **5c OS 写面 ACL（L1 巡检 → L2 chmod → named ACE apply）**，并完整交付 Wave2 **预测/热力图/治理提案/仪表盘/演示种子/TaskCenter 交接** 与 **doctor→cron→API 告警** 运营闭环；刻意 **不** 做自动改 GaC 规则、不在 UI 一键 apply 任务、不在 CI 强制 host ACL。

---

## 2. 交付地图（两条主线）

```
                    ┌─────────────────────────────────────────┐
  Scheme C 证据面   │ 5b container executor (agora spawn)     │
  (隔离 + 写面)     │ 5c L1 path-acl doctor                    │
                    │ 5c L2 acl plan|apply (chmod)             │
                    │ 5c named ACE plan → apply (setfacl/+)    │
                    │ doctor rhythm → cron → streak API        │
                    └─────────────────────────────────────────┘
                    ┌─────────────────────────────────────────┐
  Wave2 决策面      │ A backtest (前置 #352/ADR-0183)          │
  (C2G→OMO 提案)    │ B EMA+heatmap + dashboard JSON           │
                    │ C proposals (proposal-only)              │
                    │ cockpit UI + TaskCenter handoff          │
                    │ demo-seed CLI/API/UI                     │
                    └─────────────────────────────────────────┘
```

两条线在 **cockpit L3** 汇合：`GET /api/wave2/*` 与 `GET /api/omo/doctor` 同面板可见。

---

## 3. 时间线与 PR / ADR 对照

| 顺序 | PR | 主题 | ADR | 要点 |
|------|-----|------|-----|------|
| 1 | [#355](https://github.com/starlink-awaken/omostation/pull/355) | Scheme C 5b container executor | 0184 | agora spawn 统一门面；默认 local；docker 可选 |
| 2 | [#356](https://github.com/starlink-awaken/omostation/pull/356) | Wave2 B + 5c design | 0185, 0186 | EMA+heatmap；OS ACL **设计冻结**（无 host 变更） |
| 3 | [#357](https://github.com/starlink-awaken/omostation/pull/357) | Wave2 C + 5c L1 | 0187, 0188 | `omo lint path-acl`；proposals **不**自动改规则 |
| 4 | [#358](https://github.com/starlink-awaken/omostation/pull/358) | 5c L2 + dashboard 契约 | 0189, 0190 | `omo acl plan|apply`（`OMO_OS_ACL=1`+`--yes`）；`c2g.wave2.dashboard.v1` |
| 5 | [#359](https://github.com/starlink-awaken/omostation/pull/359) | Wave2 cockpit UI | 0191 | `GET /api/wave2/dashboard` + Wave2 面板 |
| 6 | [#361](https://github.com/starlink-awaken/omostation/pull/361) | proposal→TaskCenter | 0192 | dry-run plan；UI 跳转任务中心；真创建仍 CLI |
| 7 | [#362](https://github.com/starlink-awaken/omostation/pull/362) | demo seed + setfacl 设计 | 0193, 0194 | 确定性 OutcomeTracker fixture；ACE 设计 |
| — | [#360](https://github.com/starlink-awaken/omostation/pull/360) | main 分叉调和 | — | 并发 PR 后本地/远端分叉收敛 |
| — | (fix) | ADR 编号撞车 | 0195 保留 ISC-2 | architecture-convergence 让号；功能 ADR 重编号 |
| 8 | [#365](https://github.com/starlink-awaken/omostation/pull/365) | plan --acl + demo-seed UI | 0196, 0197 | named ACE **干跑**；`POST /api/wave2/demo-seed` |
| — | [#363](https://github.com/starlink-awaken/omostation/pull/363) | agora-gateway probe | — | 心跳 dead/total，修假绿灯（旁路硬化） |
| 9 | [#366](https://github.com/starlink-awaken/omostation/pull/366) | apply --acl | 0198 | 双闸门执行 named ACE；缺 setfacl soft-skip |
| 10 | [#367](https://github.com/starlink-awaken/omostation/pull/367) | doctor + runbook | 0199 | doctor 纳 path-acl warn；运维手册 |
| 11 | [#368](https://github.com/starlink-awaken/omostation/pull/368) | doctor-cron + bootstrap | 0200 | 09:20 rhythm；bootstrap checklist |
| 12 | [#369](https://github.com/starlink-awaken/omostation/pull/369) | status API + streak | 0201 | streak≥3 ALERT；`GET /api/omo/doctor` |

**ADR 编号备注**: **0195** = architecture-convergence ISC-2（非 ACL）；ACL 相关为 **0196–0198**。撞车经 #360 调和 + INDEX 修正。

### 分阶段 closeout 索引

| 文件 | 覆盖 |
|------|------|
| `docs/closeout/2026-07-15-scheme-c-5b-container-executor.md` | 5b |
| `docs/closeout/2026-07-15-wave2-b-5c-design.md` | Wave2 B + 5c design |
| `docs/closeout/2026-07-15-wave2c-5c-l1.md` | Wave2 C + L1 |
| `docs/closeout/2026-07-15-5c-l2-wave2-dashboard.md` | L2 + dashboard contract |
| `docs/closeout/2026-07-15-wave2-ui-dashboard.md` | UI |
| `docs/closeout/2026-07-15-wave2-proposal-handoff.md` | TaskCenter handoff |
| `docs/closeout/2026-07-15-wave2-demo-seed-setfacl.md` | seed + setfacl design |
| `docs/closeout/2026-07-15-acl-plan-demo-seed-ui.md` | plan --acl + seed UI |
| `docs/closeout/2026-07-15-omo-acl-apply-named.md` | apply --acl |
| `docs/closeout/2026-07-15-doctor-path-acl-runbook.md` | doctor + runbook |
| `docs/closeout/2026-07-15-doctor-cron-bootstrap.md` | cron + bootstrap |
| `docs/closeout/2026-07-15-doctor-status-api.md` | API + streak |
| **本文** | 全栈总结 + 复盘 |

---

## 4. 架构结果（做完之后系统长什么样）

### 4.1 Scheme C 执行/写面硬化

| 层 | 能力 | 默认安全姿态 |
|----|------|----------------|
| 5b | `agora.execution.container_executor` | `AGORA_SPAWN_BACKEND=local`；docker 需显式开 |
| 5c L1 | `omo lint path-acl` / doctor 检查 | 只读；warn 不 fail CI |
| 5c L2 chmod | `omo acl plan` / `apply --yes` | 无 `OMO_OS_ACL=1` 不写 host |
| 5c ACE | `plan --acl` / `apply --yes --acl` | 双闸门 + argv-only；无 setfacl 则 skip |
| ops | doctor-cron + streak≥3 ALERT | 不自动 apply；提示 `omo acl plan` |

### 4.2 Wave2 决策闭环（proposal-only）

| 阶段 | 产物 | 禁止项 |
|------|------|--------|
| A | OutcomeTracker backtest | 自动改策略 |
| B | EMA 预测 + heatmap export | 重型 Prophet/ARIMA 强依赖 |
| C | governance_feedback proposals | 自动改 `.omo/_truth` / GaC |
| UI | dashboard + proposals plan dry-run | UI 一键 `--apply-tasks` |
| seed | demo_seed → `runtime/c2g/outcomes` | 写 `.omo/` |

契约不变式：**`auto_mutate_rules: false`** 写在 dashboard JSON 里，UI/API 一致。

### 4.3 运维可观测

```
omo doctor (含 path-acl)
    → bin/gac/omo-doctor-cron.py (09:20)
    → runtime/cron/omo-doctor-latest.json + history.jsonl
    → path_acl_warn_streak / path_acl_alert
    → GET /api/omo/doctor → Wave2 面板 banner
```

手册: `docs/operations/omo-path-acl-runbook.md`  
引导: `docs/operations/omo-bootstrap-checklist.md`  
路线图状态: `docs/METAOS-ECOS-SCHEME-C.md`

---

## 5. 刻意非目标（仍成立）

| 非目标 | 原因 |
|--------|------|
| UI 自动 apply-tasks / 写 GaC | 政策抖动 + 审计缺口；保持 human-in-loop |
| CI 强制 `OMO_OS_ACL=1` | 多 agent / 临时 runner 会砖；L1 默认 advisory |
| Docker-as-MCP-tool / 强制 docker CI | 5b 先统一门面；daemon 依赖与 CI 绿冲突 |
| 全仓 recursive ACL / 自动建组 | 运维 blast radius 过大 |
| Windows ACL | 当前主体为 macOS/Linux 工作站 |

---

## 6. 复盘：做得对的

1. **双闸门成为默认语法** — `OMO_OS_ACL=1` + `--yes`；plan 永远可 dry-run；doctor/cron **永不** mutation。把「能写 host」与「默认可跑」拆开，是 5c 能合入而不炸多 agent 的前提。
2. **contract-first 再 UI** — ADR-0190 JSON 契约先于 0191 面板；B 阶段用 stdlib EMA 而非先上重模型，避免 c2g 依赖膨胀与半成品 UI。
3. **proposal-only 闭环** — Wave2 C 用「提案 + dry-run plan + TaskCenter 跳转」替代「自动改规则」，风险可控且可演示。
4. **小 PR + 单 deliverable** — 12+ feature PR 串行，冲突面可控；每步有 ADR + closeout，上下文丢失后可恢复。
5. **worktree 隔离** — 符合 AGENTS.md §6.1；主仓 main 不 direct push；子模块仍 direct push 约定清晰。
6. **旁路硬化顺手做** — #363 agora-gateway 心跳 dead/total，避免「主线绿、探针假绿」。

---

## 7. 复盘：踩坑与修复

| 坑 | 症状 | 根因 | 修复/教训 |
|----|------|------|-----------|
| **ADR 编号撞车** | 0193/0195 双线占用；INDEX/adr-coverage 红 | 并发 agent 各自占号 | 让号：ISC-2 固定 **0195**；功能顺延 **0196+**；合入前 `ls decisions/01*` + INDEX |
| **main 分叉** | local/origin 分叉、gitlink 不一致 | 多 PR 并行 + 子模块指针 | #360 reconcile；子模块先推 tip 再 bump 主仓 |
| **PR 冲突 / rebase** | #366 等需 rebase | 串行栈上叠提交快 | 合入前 rebase origin/main；force-push 仅 lease 分支 |
| **cron 无 omo 子模块** | doctor-cron 空/炸 | worktree 部分 init | cron 对 missing/error 软处理；claim 时 init 关键子模块 |
| **apply 测试脆弱** | setfacl/权限环境不一 | 真 host 依赖 | `force=True` 单测路径；缺 setfacl soft-skip |
| **hermes-console / UI 路径** | 面板不进仓或进错 | gitignore / 子模块边界 | 改 UI 前确认 submodule 与 ignore；面板落 hermes-console 时同步 tip |
| **假绿灯** | 探针 total 绿但 backend 死 | 只看进程存活 | probe 用 heartbeat dead/total（#363） |

### 可固化机制（建议，非本 PR 范围）

1. **ADR 占号脚本**: claim worktree 时预占 `next-adr-id` 或短锁，避免 019x 撞车。  
2. **worktree claim 默认 init 集合**: omo + cockpit + agora（至少）列入 claim 文档/脚本。  
3. **CI 不设 `OMO_OS_ACL`** 写进 GaC/redline 指针，防「好心严格」砖 runner。

---

## 8. 验证清单（收口后回归）

```bash
# 5b
cd projects/agora && PYTHONPATH=src pytest tests/test_container_executor.py -q

# 5c L1/L2/ACE（只读 + 单测 force 路径）
uv run --project projects/omo omo lint path-acl --json
uv run --project projects/omo omo acl plan --acl --json
# 切勿在 CI: OMO_OS_ACL=1 omo acl apply --yes --acl

# Wave2
uv run --directory projects/c2g python -m c2g.dashboard_export --json | head
uv run --directory projects/c2g python -m c2g.demo_seed --data-dir /tmp/c2g-demo --reset --json

# ops
uv run --with pyyaml python bin/gac/omo-doctor-cron.py --json | head
# cockpit 起服务后: curl -s localhost:8090/api/omo/doctor | jq .highlights

# 门
make gac-local-gate   # 或 scoped 文件门
```

---

## 9. 残留与下一棒（显式）

| 项 | 优先级 | 说明 |
|----|--------|------|
| 生产 docker image digest pin | P1 | 5b 已可 docker；digest 未锁 |
| macOS `chmod +a` 实机验收 | P1 | 设计+代码有；多 agent 主机需 ops 窗口验证 |
| GaC lint 禁 agora 旁路 raw Popen | P2 | 5b follow-up |
| Wave2 真图表库 / 生产 outcome 源 | P2 | 现为 table + demo seed |
| UI `--apply-tasks`（若要） | P3 | 需单独 ADR：权限、审计、二次确认 |
| Prophet/ARIMA 可选后端 | P3 | 保持 c2g 默认轻量 |
| Windows ACL | — | out of scope |

---

## 10. 操作员一页纸

```bash
git checkout main && git pull --ff-only

# 演示 Wave2
uv run --directory projects/c2g python -m c2g.demo_seed --reset
# 或 cockpit UI「加载演示数据」

# 看治理提案 / 仪表盘
uv run --directory projects/c2g python -m c2g.dashboard_export --json | head
# cockpit: 系统治理 → Wave2

# ACL 只读诊断
omo doctor --json
omo acl plan --acl --json
# 仅当明确要改 host 权限:
#   export OMO_OS_ACL=1
#   omo acl apply --yes          # chmod
#   omo acl apply --yes --acl    # + named ACE

# 日常: operating-rhythm 09:20 写 runtime/cron/omo-doctor-*
# streak≥3 → API highlights.path_acl_alert + UI banner
```

---

## 11. 本复盘的交付定义

- [x] 功能 PR #355–#369（及必要 fix/reconcile）已在 main  
- [x] ADR 0184–0201（含 0195 ISC-2 让号说明）已入册  
- [x] 分阶段 closeout 齐全  
- [x] **本文**: 全栈总结 + 复盘 + 残留清单  
- [ ] 本文经 PR 合入 main（本 PR 职责）

---

## 12. 引用

- 方案 C 路线图: [`docs/METAOS-ECOS-SCHEME-C.md`](../METAOS-ECOS-SCHEME-C.md)  
- ACL 运维: [`docs/operations/omo-path-acl-runbook.md`](../operations/omo-path-acl-runbook.md)  
- Bootstrap: [`docs/operations/omo-bootstrap-checklist.md`](../operations/omo-bootstrap-checklist.md)  
- ADR INDEX: [`.omo/_knowledge/decisions/INDEX.md`](../../.omo/_knowledge/decisions/INDEX.md)  
- 前日基线: [`docs/closeout/2026-07-14-tech-debt-ci-landing.md`](2026-07-14-tech-debt-ci-landing.md)
