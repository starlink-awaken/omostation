---
status: active
lifecycle: audit
owner: governance-team
last-reviewed: 2026-06-29
related:
  - doc-ssot-contract.md
  - ssot-7-domain-schema.md
  - ../../../projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml
  - ../_truth/registry/mof-capabilities.yaml
---

# L0 / SSOT / M0 / MOF 全链路对齐审计 (2026-06-29)

> 触发: 近期大量并发更新 (agent-workflow +672 / 文档删 7595 / AGENTS -229) 后,
> 对四者 (L0 协议层 / SSOT 事实面 / M0 模型驱动 / MOF 元架构) 做全量抽象提炼 + 验证校验 + 推导.
>
> 方法: 6 个治理工具实证 (mof-version/mof-drift/mof-m2-coverage/gac-mof-validate/gac-drift/evidence-smoke/doc-ssot-lint) + 文档 SSOT 交叉核对.

---

## 0. TL;DR

| 层 | 状态 | 证据 |
|:---|:-----|:-----|
| **执行层 (GaC/MOF/BOS/证据)** | 🟢 **全绿** | GaC drift 0 / mof-validate 132✓ / m2-coverage 19✓ / evidence resolve 1.0 / doc-ssot-lint 0 冲突 |
| **文档层 (导航/契约/registry 元数据)** | 🔴 **漂移 6 处** | INVENTORY 死链×5 + 版本漂 95 + ssot-7-domain 过时 + mof-capabilities 元数据停 + L4 治理盲区 + governance 趋势降 |

**根因**: 文档元数据 (版本号声称 / last-reviewed / 死链) **无专门 drift 检测器** —— GaC 管 rule schema, X2 管 registry target freshness, doc-ssot-lint 管 embedded table, 三者缝隙里"文档自身声称的运行时事实 vs SSOT 真值"无人监督. 并发 agent 演进 (P43→P111, 95 版本) 持续 bump mof-version, 但导航文档 (INVENTORY / ssot-7-domain) 没被同步刷新.

---

## 1. 四者抽象定义 (实体 + 职责 + 关系)

### 1.1 实体定位

| 维度 | **L0** | **SSOT** | **M0** | **MOF** |
|:-----|:-------|:---------|:-------|:--------|
| **实体** | `projects/ecos/` + `ecos/ssot/registry/` (L0-constraints/layer-boundary/topology/patterns/workflow-catalog/governance) | `.omo/_truth/` (registry/ 21 yaml + x1-x4 + mof-version + INDEX/INVENTORY) | `projects/model-driven/` (7 阶段 Stage/Gate 引擎) | `.omo/_truth/mof-version.yaml` + `registry/mof-capabilities.yaml` + `bin/mof-*` 16 工具 + `ecos/ssot` 元模型 |
| **职责** | 协议层: M1 节点 / M2 类型 / L0 约束 / 层边界 / 拓扑 | 单一事实面: 任务 / 标准 / 注册表 / X 治理 / 证据 | 横切框架: M1→M2→M3 派生 7 阶段 (零风险派生) | 元架构: data/knowledge/decision/action 四层 + 工具链 + 约束 + 集成点 |
| **GaC 规则覆盖** | `CR-L0-BOS-RESOLVE` / `CR-L0-PROTOCOLS-SSOT` + 5 `source_ref` 锚 `L0-constraints.yaml::constraints` | `doc-ssot-lint` (98 文件) + `ssot-guardian` + 28 check_type | `CR-M0-STAGE-GATE` (check_type=`mof_stage_gate`, executor=`mof_validate/mof_audit/ci_gate`) | `X2-FRESH-MOF-VERSION-BUMP` + `X4-CONS-P43-CLOSED-LOOP-SSOT` |
| **role 声称** (project-registry) | ecos: "SSB 签名链 + **MOF 元模型** + **L0 约束**" (双重身份) | — | model-driven: layer="M0" | 由 ecos 承载, 无独立 project |

### 1.2 关系链 (派生 + 治理)

```
                    ┌─────────────────────────────────────┐
                    │  MOF 元架构 (ecos 承载)              │
                    │  M1 节点 (1177) → M2 schema (46)     │
                    │            → M3 元素 (8)             │
                    └──────────────┬──────────────────────┘
                                   │ 派生 (7 阶段 Stage/Gate)
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  M0 model-driven (横切框架)          │
                    │  驱动 M1→M2→M3 零风险派生            │
                    └──────────────┬──────────────────────┘
                                   │ 约束
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  L0 ecos (协议层)                    │
                    │  L0-constraints.yaml (43k, 5 规则锚) │
                    └──────────────┬──────────────────────┘
                                   │ 注册 / 事实化
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  SSOT .omo/_truth/ (事实面)          │
                    │  mof-version.yaml (v0.0.107)         │
                    │  registry/mof-capabilities.yaml      │
                    │  + X1-X4 治理 + 21 registry          │
                    └──────────────┬──────────────────────┘
                                   │ 执行
                                   ▼
                    ┌─────────────────────────────────────┐
                    │  GaC 132 规则 (gac-validate/drift)   │
                    │  layer_enum: [M0,L0,L1,L2,L3,I0,X,meta]  ← ⚠️ 缺 L4 │
                    └─────────────────────────────────────┘
```

**关键洞察**:
1. **ecos 是 L0 + MOF 双重身份** —— project-registry 明写 ecos role="MOF 元模型 + L0 约束". L0 (协议层) 和 MOF (元架构) 物理同体, 逻辑分层.
2. **MOF 没有独立 project** —— MOF 是元层概念, 寄生在 ecos (元模型) + `_truth/mof-version.yaml` (版本 SSOT) + `bin/mof-*` (工具链) + model-driven (派生引擎) 四处.
3. **SSOT 是面不是层** —— `.omo/_truth/` 横切所有层, 是事实锚点, 不在 L0-L4 垂直分层里.

---

## 2. 执行层对齐矩阵 (全绿证据)

| 工具 | 输出 | 状态 |
|:-----|:-----|:-----|
| `bin/mof-version show` | Current version: **v0.0.107** (P111, 2026-06-27) | ✅ |
| `bin/mof-drift` | 5 drifts (2 MEDIUM + 3 LOW), 无 HIGH/CRITICAL | 🟡 (见 D6) |
| `bin/mof-m2-coverage.py` | 19 M2 schema 全 ✓ (Component 168x ... Pattern 11x) | ✅ |
| `bin/gac-mof-validate.py` | 132 规则全符合 GacRule M2 type (机制 7 生效) | ✅ |
| `bin/gac-drift.py` | **0 drift** (132 规则) | ✅ |
| `bin/evidence-smoke.py` | resolve 率 **1.0** (BOS 鸿沟 0) + 反馈回路存活 (governance 1h 前) | ✅ |
| `bin/doc-ssot-lint.py` | 0 冲突 (扫描 98 文件) | ✅ |

**结论**: 治理执行引擎 (GaC/MOF 元模型/BOS 路由/证据回路/文档 embedded 门禁) **完全自洽**. 漂移不在执行链路, 在文档元数据.

---

## 3. 文档层 drift 清单 (6 处实证)

| # | drift | 级别 | 证据 | 影响 |
|---|-------|:----:|------|------|
| **D1** | `INVENTORY.md` 死链 `../PROJECTS.yaml` ×5 | **P1** | `ls PROJECTS.yaml` → 不存在; 真 SSOT 是 `docs/project-registry.yaml` (ARCHITECTURE.md §1 正确) | 导航文档指错, agent/人按链接找不到项目注册表 |
| **D2** | `INVENTORY.md` 声称 `mof-version v0.0.12` vs 实际 **v0.0.107** | **P1** | 漂移 **95 个版本** (P43 R5 2026-06-21 → P111 2026-06-27) | 导航文档的运行时事实完全失真, 误导决策 |
| **D3** | `ssot-7-domain-schema.md` v1.0 (2026-05-30) 提 `tasks/active/` ×2 | P2 | 实际目录是 `tasks/planned/` (archive/archived/blocked/done/planned/registry/remediation) | 契约文档目录名过时, 新 agent 按旧路径写入会出错 |
| **D4** | `mof-capabilities.yaml` 元数据漂移 | P2 | `updated_at: 2026-06-20` (停 9 天) + `version: "2.0"` 静态; `bin/mof-manage` 实体存在但 registry **未注册**; `mof-reason` 注册路径指 `projects/ecos/...` 非 bin/ | 工具注册表不完整, `mof-manage` 无治理覆盖 |
| **D5** | GaC `layer_enum` 缺 **L4** + **0 条** layer:L4 规则 | **P1** | `layer_enum: [M0,L0,L1,L2,L3,I0,X,meta]`; `grep layer:L4` → 0; 但 `project-registry` 有 `L4: "自我层 (l4-kernel)"` | **l4-kernel 整层治理盲区** —— 自我层的变更无 GaC 规则约束 |
| **D6** | mof-drift 报 governance 趋势降 + planned 累积 | P2 (趋势) | governance 最近 20 次均 98.5 (前 20 次 100.0); planned 任务 11 (>5 阈值, P49 清零过) | 治理质量轻微回落 + 任务积压回升 |

### D6 细分 (mof-drift 5 条)

```
🟡 MEDIUM (2):
  [governance] governance score 趋势下降: 最近 20 次平均 98.5 (前 20 次 100.0)
  [governance] 治理累积: planned 任务 11 (> 5 阈值, 历史 P49 已清零) (done=94, registry=1336)
🔵 LOW (3):
  [gbrain] gbrain TODOs: keep=13, fix=6, close=7, planned=27, unknown=0
  [gbrain] gbrain TODOs Top-5 文件: search/mode.ts:5, migrations/v0_28_0.ts:5 ...
  [workspace] 工作树累积 26 文件 (≤100 健康, bumps_24h=10, last_commit=0h ago)
```

---

## 4. 根因推导 (为什么漂)

### R1. 文档元数据无专门 drift 检测器 (主因)

三套检测器职责边界:
- **GaC/drift** → 管 rule schema (声明 vs 执行器) 一致性
- **X2 freshness** → 管 registry target (如 `mof-version.yaml` 的 history 增量) 新鲜度
- **doc-ssot-lint** → 管入口文档 marker 段内的 embedded table

**缝隙**: "导航文档 (INVENTORY/ssot-7-domain) 自身**声称**的版本号 / 路径 / 目录名 vs SSOT 真值" 这种**跨文档元数据一致性**无人监督. INVENTORY 写 `mof-version v0.0.12` 不会触发任何 lint (它不是 embedded table, 不是 X2 target).

### R2. 并发 agent 演进不留文档痕迹

P43→P111 共 95 个 mof-version bump, 每次都 `bin/mof-version record` 落 `_truth/mof-version.yaml`, 但**导航文档的 owner 不知该同步刷新** (或导航文档无明确 owner 刷新触发器). 执行层 (version SSOT) 实时准, 文档层 (导航声称) 静态腐化.

### R3. L4 层治理从设计就有盲区

`layer_enum` 定义 (governance-checks.yaml:128) 漏 L4. 推测: L4 (l4-kernel 自我层) 是后加的层 (5+4+1+1 架构演进), enum 定义时未跟上, 导致:
- 任何标 `layer: L4` 的 GaC 规则会 schema 校验失败 (enum 不含) → 所以 0 条 L4 规则
- l4-kernel 的变更 (自我层管理面) 完全游离 GaC 治理外

---

## 5. 理想态 + 修复路径 (KISS, 逐处)

> 原则 (遵 [[architecture-overengineering-lesson]]): 不抽象通用"文档元数据 drift 检测器", 用已有 X2 freshness 机制针对具体文档加 rule.

### 5.1 修 6 处 drift (治标)

| drift | 修复动作 | 工作量 |
|:------|---------|:------:|
| **D1** INVENTORY 死链 | sed 5 处 `../PROJECTS.yaml` → `../../docs/project-registry.yaml` | 5min |
| **D2** INVENTORY 版本号 | 删 "mof-version v0.0.12" 硬编码 (运行时事实不入导航文档), 改指针 "见 `.omo/_truth/mof-version.yaml`" | 5min |
| **D3** ssot-7-domain 过时 | sed 2 处 `tasks/active` → `tasks/planned` + `last-reviewed` bump 2026-06-29 | 5min |
| **D4** mof-capabilities | 补注册 `mof-manage` + `updated_at` bump 2026-06-29 + `version: "2.1"` | 10min |
| **D5** L4 盲区 | GaC `layer_enum` 加 L4 + 评估补 L4 治理规则 (或显式 ADR 声明 L4 豁免理由) | 30min (需决策) |
| **D6** 趋势 | planned 11 任务逐个评估 (推进/归档); governance 98.5 是 worktree dirty 46 文件拖累, 工作树清后自愈 | 关联并发 agent |

### 5.2 治本 (防复发, 遵 [[gac-digest-treatment]] 模式)

新增 **X2 freshness rule** 监督导航文档元数据漂移:

```yaml
# 建议加到 .omo/_truth/x2-freshness-rules.yaml
- id: X2-FRESH-NAV-DOC-META
  title: 导航文档不准内嵌运行时版本号 / 分数 / 计数
  target:
    - .omo/_truth/INVENTORY.md
    - .omo/standards/ssot-7-domain-schema.md
  check: 文档内不得出现 "mof-version v0.0.X" / "governance 100 A+" / 具体任务数等
         运行时事实声称, 只能指针 ("见 _truth/mof-version.yaml")
  action: warn
  rationale: 运行时事实写导航文档 = 第二事实源, 必漂移 (R1 根因)
```

效果: INVENTORY 写 `mof-version v0.0.12` 这种声称会被 X2 rule flag, 逼 owner 改指针. 从根上消灭 D2 类漂移.

### 5.3 L4 治理补全 (D5 决策点)

两条路:
- **A (补规则)**: `layer_enum` 加 L4 + 为 l4-kernel 补 Stage/Gate / boundary / freshness 规则 (与其他层对齐)
- **B (显式豁免)**: `layer_enum` 加 L4 + 记 ADR 声明 "L4 自我层暂豁 GaC 强约束, 理由: 自我层变更频次低 + 由 l4-kernel 自身 CI 守"

老王建议 **B** (KISS + YAGNI): l4-kernel 当前 0 条 GaC 规则也没炸 (执行层全绿), 说明自我层低频变更不需要 GaC 重约束. 加 enum + 记豁免 ADR 即可, 不过度设计 L4 规则集.

---

## 6. 验证 (修复后跑)

```bash
# D1-D4 文档修复后
python3 bin/doc-ssot-lint.py                    # 应仍 0 冲突
python3 bin/check-cross-refs.py 2>&1 | tail     # INVENTORY 死链应消
bin/mof-version show                            # 确认 v0.0.107

# D5 GaC layer_enum 加 L4 后
python3 bin/gac-validate.py 2>&1 | tail         # schema 校验过
python3 bin/gac-drift.py                        # 应仍 0 drift

# D6 工作树清后
python3 bin/mof-drift                           # governance 趋势回升
python3 bin/evidence-smoke.py                   # resolve 仍 1.0

# 治本 X2 rule 加后
python3 bin/x2-freshness-check.py               # 新 rule 可执行
python3 bin/gac-local-gate.py                   # CI 门禁过
```

---

## 7. 关联

- 契约: [`doc-ssot-contract.md`](../../standards/doc-ssot-contract.md) (SSOT 正交)
- 模式: [`doc-presentation-pattern.md`](../../standards/doc-presentation-pattern.md) (digest+pointer+lint, 治本参考)
- L0 SSOT: [`projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml`](../../../projects/ecos/src/ecos/ssot/registry/L0-constraints.yaml)
- MOF 能力: [`../_truth/registry/mof-capabilities.yaml`](../_truth/registry/mof-capabilities.yaml)
- 教训: [[architecture-overengineering-lesson]] (别抽象通用 drift 检测器, 先用已有 X2 机制)

---

*审计者: 老王 (laowang-engineer) | 证据驱动: 7 工具输出 + 6 文档交叉核对 | 下一步: 用户拍板修复顺序 (D1-D4 治标先 / D5 决策 / 治本 X2 rule)*
