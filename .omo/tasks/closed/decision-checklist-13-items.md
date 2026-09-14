---
type: ephemeral
status: archived
---

# 13 项决策一页清单 — 2026-07-28 已拍板收口

> 人类会话 2026-07-28 拍板落地（worktree `decision-inbox-land-20260728`）。
> **§F 红线已守**: agent 不代批；本文件为签核记录，非代批。

## 元决策
| 项 | 决定 |
|----|------|
| 三档重切 (A 批量 + B 单独 + C 降级) | **批准** |

## A 档 · MOF + metaos（已全部按推荐签核）

### MOF/M4 → ADR-0240
| # | 决策 | 签核 |
|---|------|------|
| M-D1 | model-driven CLI → A 删除 | ✅ 2026-07-25 拍板 · 07-28 追认 |
| M-D2 | MCP 面 → A 冻结 2 工具 | ✅ |
| M-D3 | M2 真源 → A YAML SSOT + Py 生成 | ✅ |
| M-D4 | codegen → A 降级模板投影 | ✅ |

卡: `needs-human-mof-m4-d1-d4-decisions` → **closed**

### metaos → ADR-0252
| # | 决策 | 签核 |
|---|------|------|
| O-D1 | CLI → A 正名 cockpit 契约 | ✅ 2026-07-28 |
| O-D2 | PID → A experimental 降级 | ✅ |
| O-D3 | agentkit → B 降级 reference | ✅ |
| O-D4 | admit → A blocking + 2 周观察 | ✅ |

卡: `needs-human-metaos-phase12-d1-d4` → **closed**

## B 档 · C1 五角色
| # | 决定 | 依据 |
|---|------|------|
| C1 research/delivery | **关卡（已落地）** | ADR-0235 + PR #510；非再决策 |

卡: `needs-human-batch2-role-expansion-proposal` → **closed**

## C 档 · 状态/债（移出 needs-human 决策 Inbox）
| 卡 | 处置 |
|----|------|
| p80-physical-hosts | needs-human:false · deferred · ADR-0247 |
| batch2-physical-recovery-checklist | needs-human:false · deferred |
| p80-phase45-bos-stdio | needs-human:false · engineering_debt |
| p81-batch4-proposal | **closed**（C1–C3 ADR + P84 覆盖） |

## L2 止血（执行授权，非阻塞 Inbox）
| # | 状态 |
|---|------|
| L2-D1 kairon CI path | 工程收敛，按既有主轴执行 |
| L2-D2 gbrain 红灯 | 已 closed（S4） |
| L2-D3 omo 死命令 | 已处理方向 |
| L2-D4 omo 虚假依赖 | 工程清理授权 |

## 引用
- ADR-0240 / ADR-0252
- ADR-0235 / ADR-0247
- run: `20260728T091034Z-governance-state-mutation-c8fbd835`
