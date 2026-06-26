# GaC Roadmap v1 — 治理即代码落地路线 (ADR-0106)

> **北极星**: [NORTH-STAR.md](./NORTH-STAR.md) | **注册表**: `.omo/_truth/registry/governance-checks.yaml::gac`
> **状态**: 阶段 0 ✅ done | 阶段 2 部分 ✅ (gac-validate) | 阶段 1/3/4/5 待推

---

## 阶段 0: 激活 + 锚定 ✅ done (2026-06-26, commit 00c324ed)

- [x] T0.1 `NORTH-STAR.md` 北极星 (目标/不变量/反模式/7 机制/元治理递归/不走偏红线)
- [x] T0.2 `governance-checks.yaml::gac` schema (7 必填字段 + enum) + drift/lifecycle 配置
- [x] T0.3 登记 6 条代表规则 (X4 SSOT / M0 Stage-Gate / L0 BOS / L2 task / X2 drift / X1 audit)
- [x] T0.4 `ADR-0106` GaC 架构决策
- [x] 附: 修原文件 `^>` block scalar 误用 (为阶段 2 schema 校验铺路)

---

## 阶段 1: 执行绑定 (W2-W3)

把注册表规则接到执行通道 (AGENTS.md / hook / MCP / CI).

- [ ] T1.1 **AGENTS.md 从注册表导出 GaC 段** — agent 读到规则 (根仓, 安全)
- [ ] T1.2 **泛化 PreToolUse hook** — 读注册表按 check_type 执行 (机制 3; 需 .claude/hooks/)
- [ ] T1.3 **MCP 工具内置注册表检查** — omo MCP 扩展 (workspace_edit 等; ⚠️ omo 并发阻塞)
- [ ] T1.4 **CI gate 挂 gac-validate --gate** — `.github/workflows/gac-validate.yml`

---

## 阶段 2: 动态一致性 (W3-W4) — 🔥 核心

| 任务 | 状态 | 交付 |
|------|:---:|------|
| T2.1 schema 校验 (机制 2) | ✅ done | `bin/gac-validate.py` |
| T2.3 矛盾检测 (机制 5) | ✅ done | 合 `gac-validate.py` |
| T2.2 drift 检测 (机制 4, radar) | ⏳ | `bin/gac-drift.py` (静态版先, 动态版阶段 1 后) |
| T2.4 lifecycle 状态机 (机制 6) | ⏳ | draft→active→deprecated→removed |
| T2.5 补全规则覆盖 | ⏳ | X3 价值 / L1/L3 层 (当前 X4×3/X1×2/X2×1, 缺 X3) |

---

## 阶段 3: 元模型派生 (W5)

规则上 MOF, 元模型约束派生 (机制 7, omostation 独有).

- [ ] T3.1 规则 M1 元模型 (`RuleDefinition` 注册到 MOF)
- [ ] T3.2 派生链 M1→M2→M3 (mof-derive)
- [ ] T3.3 mof-validate 集成规则校验

⚠️ 需 ecos/model-driven (待查并发状态)

---

## 阶段 4: 度量 + 自愈 (W6)

- [ ] T4.1 治理仪表盘 (X1-X4 + GaC 强制度量: 规则触发率/违规率/drift 率)
- [ ] T4.2 drift 自愈 (漏执行规则自动绑定 executor; `drift.auto_heal: true`)

⚠️ 需 cockpit/dashboard (待查并发状态)

---

## 阶段 5: 常态化 (持续)

- [ ] T5.1 radar 每日 cron (GaC drift 检测, `.omo/cron/`)
- [ ] T5.2 gc 每周 cron (过时规则清理, lifecycle deprecate)
- [ ] T5.3 规则变更 ADR 流程 (brainstorm→draft→bet→ADR)

---

## c2g 落地映射

```
brainstorm  →  GaC 新规则提案 ( Pitch: dimension/layer/check_type/ROI )
   ↓
draft       →  规则 Pitch 结构化
   ↓
bet         →  governance-checks.yaml::gac.rules 条目 + OMO Task
   ↓
radar       →  bin/gac-drift.py (机制 4, drift 检测)
   ↓
gc          →  lifecycle deprecated → removed (机制 6, 28 天清理)
```

---

## 当前阻塞 & 推进策略

| 阻塞 | 影响 | 策略 |
|------|------|------|
| **omo 并发 agent** (governance_surfaces/omo_lint 拆分) | T1.3 MCP / 阶段 3 部分需 omo | 根仓 bin/ 先做 (gac-validate/drift), omo 部分等并发停 |
| **ecos/cockpit 并发状态未知** | 阶段 3/4 | 待查, 安全则推 |
| **阶段 1 hook 绑定** | 机制 3 (泛化执行器) | 需 .claude/hooks/ 改动, 评估影响 |

**安全可立即推** (根仓, 不碰并发):
- T2.2 `bin/gac-drift.py` (静态 drift)
- T1.1 AGENTS.md GaC 段 (手动导出)
- T1.4 CI gate (gac-validate --gate)
- T5.1/T5.2 cron 配置

---

## 版本

- v1.0 (2026-06-26): 阶段 0 done + 阶段 2 部分 (gac-validate) done, 路线细化
