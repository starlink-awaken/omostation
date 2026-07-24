---
id: STRAT-P81-MASTER-DECISION-INBOX
title: STRAT-P81 兑现期入场决策单（7 卡 · 人类拍板）
owner: 夏明星
created_at: 2026-07-24T08:50:00Z
status: ready_for_human
ssot_refs:
  - .omo/_knowledge/decisions/STRAT-P81-strategic-roadmap.md
  - .omo/_knowledge/audits/2026-07-24-p81-stage0-closeout.md
  - .omo/_knowledge/audits/2026-07-24-p81-s0-phase45-residuals.md
  - .omo/_knowledge/audits/2026-07-24-p81-s0-physical-probe-failclosed.md
warning: |
  本卡是 7 张 needs-human 卡的「决策汇总看板」。
  决策顺序: 共阻塞 → 自持性 → 范围扩张。
  Agent 不得在拍板前自宣进入兑现期。
---

# STRAT-P81 兑现期入场决策单

## 0. TL;DR

| # | 卡片 | 优先级 | 类型 | 今日能否自决 |
|---|------|--------|------|--------------|
| 1 | `needs-human-p80-physical-hosts` | P0 | 物理 | ❌ |
| 2 | `needs-human-p81-m1-acceptance` | P0 | 战略 | ❌ |
| 3 | `needs-human-batch2-physical-recovery-checklist` | P0 | 流程 | ❌（待 #1） |
| 4 | `needs-human-p80-phase45-bos-stdio` | P1 | 架构 | ⚠️ evidence 可备 |
| 5 | `needs-human-batch3-proposal` | P1 | 范围 | ❌ |
| 6 | `needs-human-batch2-role-expansion-proposal` | P1 | 范围 | ❌ |
| 7 | `BET-c87a` http-mcp-convergence 收尾 | P2 | 工程 | ✅ Stage 0 收尾后可启 |

**结论**: 今日 6 张卡阻塞人类决策,1 张可工程化预备证据。

## 1. 决策顺序(推荐)

```
#1 (物理) → #3 (恢复清单) → #2 (M1 验收) → #4 (bos_stdio) → #5/#6 (范围)
```

**理由**:
- #1 解锁 G-DEL.1/3 一切物理 KPI
- #3 是恢复日执行剧本,#1 不解,#3 不触发
- #2 依赖 #1+#3 物理证据
- #4 可并行(架构债)
- #5/#6 栖居于 #2 之后

## 2. 决策矩阵

### #1 物理底座 ≥4 (P0)

| 选项 | 含义 | 代价 | 收益 |
|------|------|------|------|
| A | 修 LAN/SSH 复活 macmini (192.168.31.210) | 物理手动 | 满足 4 物理机 fail-closed |
| B | macbook 走 Tailscale 接入 | 配置 tailscale | 1→2 物理,Tailscale 化加固 |
| C | 引入云节点 (VPS / Tailnet peer) | 成本 | 4 物理最快路径 |

**当前态**: `reachable_physical_hosts=1` (local-mac),`env_class=insufficient_physical`,`meets_g_del_1_unblock=false`。

### #2 M1 提前验收 (P0)

| 选项 | 含义 | 触发 |
|------|------|------|
| A | 通过 | 写 ADR + 翻 brief §1 S1 = OPEN |
| B | 拒绝 + 列缺口 | 推到 Stage 0 关闭 |
| C | 延期复评 | 14 天后再议 |

**三门禁** (ADR-0210 Confirmation):
- C1: daemon 在线率 ≥ 90% (去假阳性)
- C2: 并发 agent 主仓冲突 = 0 (gac-worktree claim 100%)
- C3: health_score 新口径 + 强相关

### #3 机器恢复日验收清单 (P0)

剧本: `bash bin/delivery/physical-recovery.sh` → `measure_physical` → G-DEL.3 → G-DEL.1 → 人类拍板

**触发条件**: #1 选项 A/B/C 任一达成。

### #4 bos_stdio 真实迁移 (P1)

| 选项 | 含义 | 风险 |
|------|------|------|
| A | internal `module_path/func_name` 移植 | 中 (跨包接口) |
| B | mcp_proxy + mcp_tool + ProxyManager dispatch proof | 中 (需新基础设施) |
| C | 接受 69.2% (修订 phase45 口径) | 低 (需 amend ADR) |

**禁止** (剧场化黑名单):
- 改 `transport: mcp_proxy` label 但不动 command/mcp_tool — rejected
- 改 gitignore 隐藏 archived — rejected
- 假装物理机在线 — rejected

**当前态**: 117/169 ≈ 0.692,目标 < 0.65。

### #5 Batch3 提案 (P1)

| 选项 | 含义 |
|------|------|
| A | 物理 KPI 冲刺 (C2 3 日 harness + 恢复日 + G-DEL.1) |
| B | 角色 4/5 实装 (research/delivery) |
| C | 收尾 http-mcp-convergence (BET-c87a) |

### #6 角色 4/5 实装 (P1)

| 选项 | 含义 |
|------|------|
| A | 装 research + delivery |
| B | 仅评估页,不实装 |
| C | 不装 |

### #7 http-mcp-convergence 收尾 (P2)

BET-c87a 已 80% (24→5 HTTP, 29/29 stdio)。剩余: 测覆 + 前端现代化。
可独立小 bet,Stage 0 收尾后启动。

## 3. Agent 自持性承诺

- 不在拍板前自宣进入兑现期
- 不搞剧场化(物理/迁移/归档三类黑名单)
- 不动 agora 业务代码直到 ARCH 立项
- 把 7 张卡的 SSOT 指针维持稳定

## 4. 工程化预备(可在人类拍板前做)

### #4 evidence 准备
- 扫描 `projects/agora/etc/bos-services.yaml` 169 服务
- 标注哪些适合 internal module_path/func_name
- 标注哪些适合 mcp_proxy + mcp_tool
- 输出 `bos-migration-candidate-map.yaml` (待人类拍板后启动)

### #7 收尾准备
- 圈出 HTTP 5 个剩余 endpoint 的测试覆盖盲区
- 圈出前端现代化 candidates

## 5. 引用

- ADR-0210 三年战略 Confirmation
- ADR-0225/0226 G-DEL fail-closed 口径
- ADR-0232 G-DEL.2b 官方通过
- STRAT-P81 路线图
- 2026-07-24 p81-stage0-closeout
