---
schema: md/v1
status: active
lifecycle: plan
owner: governance-team
last-reviewed: 2026-09-25
type: ephemeral
---


# BET-Y2Q4-T7-02 — 公文场景第二业务驱动探索

> 目标（BET done_when）：
> 1. 产出至少一个不依赖国转中心借调的公文/决策收件箱候选业务驱动，附真实场景描述与预估请求量
> 2. 验证该候选驱动能否复用已建成的 document-review 能力（拟稿/审批/督办闭环），给出兼容度结论
> 3. 结论写入 `docs/plans/`，供后续 BET 认领决策参考

## 0. 冻结背景

| BET | 状态 | 冻结原因 |
|---|---|---|
| BET-Y3H1-T7-01 中试/政策申报升 assisted | blocked | 2026-08-19 冻结：用户不再借调国转中心，政策申报业务前提消失；**技术前置全 done** |
| BET-Y3H2-T7-01 公文场景 routine | blocked | 同上，依赖 Y3H1-T7-01 |
| BET-Y2Q4-T7-02 第二业务驱动探索 | candidate | 本文件即其交付物 |

结论前提：`scene-document-review` 的能力（拟稿 / 格式检查 / 敏感项检查 / 依据核验 / 可审计可退回旅程）已建成并通过 supervised 生命周期，**缺的不是技术，而是持续的真实业务请求流**。

---

## 1. 候选驱动 A（推荐）：本体系治理文档生产流

### 1.1 真实场景描述

本体系（织星 / OMO）的每一次实质交付都伴随结构化文档产出，且**产出者本身是 agent**：

| 文档类型 | 产生时机 | 现有模板 |
|---|---|---|
| spec（规格/设计） | BET 进入 spec 阶段 | `docs/plans` 约定 + Library `Spec与实施计划模板.md` |
| plan（实施计划） | BET 认领后 | Library `战略战役模板.md` |
| retro（复盘） | closeout 后（含 bet-retro / weekly-report） | Library `Incident-Retro-Amendment模板.md` |
| 验收/运营报告 | 阶段验收 | Library `验收运营运维模板.md` |
| handoff/control 包 | 交接 | Library `WorkPacket-Control-Handoff模板.md` |

痛点现状（可由 `document-review` 场景直接承接）：
- 格式/契约漂移：frontmatter 缺字段、`last-reviewed` 过期、链接失效 —— 已有门禁但**仅阻断式，无草稿→审查→退回的旅程**
- 依据核验缺失：结论引用无 `evidence://` 或 digest 绑定
- 敏感项外泄风险：文档中 token/凭据/私密路径（cockpit sanitizer 已识别同族模式）
- 审查滞后：由 gac 门禁在 commit 时一次性拦截，**无人类裁决环节与退回记录**

### 1.2 请求量估算（git 实证，非 mtime 估计）

| 口径 | 数量 |
|---|---|
| 近 30 天新增治理文档（spec+plan+retro） | **688 篇** |
| 近 7 天新增 | **126 篇** |
| 折算日均 | **≈ 18 篇/天** |
| 同期提交数（附文档率的分母） | 2175 |

存量面（可作为首轮回灌/回归语料）：

| 集合 | 篇数 |
|---|---|
| `docs/superpowers/specs` | 293 |
| `docs/plans` | 44 |
| `.omo/_knowledge/retros` | 468 |

**结论**：日均 18 篇新增 + 468 篇存量复盘，请求量足以支撑 `shadow → assisted` 的 30 样本门槛（≈2 天即可满样本），且**完全内生、不依赖任何外部借调**。

### 1.3 与冻结驱动的差异

| 维度 | 国转中心借调（已冻结） | 本体系治理文档流 |
|---|---|---|
| 业务前提 | 外部单位借调关系 | **无外部依赖，体系自我生产** |
| 请求连续性 | 随借调终止归零 | 持续（与交付节奏同步） |
| 数据敏感性 | 涉外部单位内部公文 | internal（本体系自有文档，可脱敏引用） |
| 失败成本 | 对外发布错误 | 体系内文档质量/返工 |
| 样本可得性 | 低（依赖外部事件） | 高（日均 18） |

---

## 2. 能力复用兼容度（逐腿核验）

| # | `scene-document-review` 能力腿 | 现有可复用资产（实证） | 兼容度 |
|---|---|---|---|
| 1 | 公文**草稿生成** | 5 类模板（战略战役 / Spec与实施计划 / Incident-Retro / 验收运营 / WorkPacket-Handoff）；runtime 已声明 `bos://capability/compute/generate` | **高**（模板即 schema，直接填充） |
| 2 | **格式检查** | `bin/gac/fix-frontmatter.py`、`check-doc-freshness-gate.py`、`doc-link-check.py`、`docs/templates/{ssot,derived,ephemeral}-template.md` 契约 | **高**（检查器已存在，仅需包成 journey state） |
| 3 | **敏感项检查** | cockpit `query_engine._sanitize` / `ASSIGNMENT_SECRET` / `SECRET` 模式族；`codex-worker-adapter` SECRET_ENV_PARTS | **高**（正则族可平移） |
| 4 | **依据核验** | `evidence://` 引用约定 + sha256 digest 绑定（cockpit `proof_reference` 已实现判定）；scene-outcome/四桥的 digest 机制 | **高**（判定逻辑已在 observation 面验证过） |
| 5 | **可审计、可退回旅程** | `journey-engine` inbox-to-decision + human_gate 置信度分支（2026-09-16 已实现自动完成/升级）+ `scene-outcome-recorder` 退回记录 + `human-adjudication-canary` | **高**（旅程与退回记录已落地） |

**综合结论：5/5 能力腿可直接复用，无需新建基础设施。**

差异仅在**输入契约**：冻结驱动要求「公文任务引用（evidence:// 或 vault://redacted/）」，治理文档流可直接以
`docs/**/*.md` + frontmatter 作为输入契约，**更易获得且无需脱敏外部内容**。

### 2.1 建议的最小落地形态

```
scene-document-review（已存在，复用）
  trigger: 新增/变更 docs/**/*.md 且 frontmatter.type ∈ {ssot,design,ephemeral}
  journey: journey-document-review（已存在，10 states / 1 human_gate）
  input:  文档路径 + frontmatter + 正文摘要
  legs:   格式检查(gac) → 敏感项(cockpit regex) → 依据核验(evidence/digest) → human_gate
  outcome: scene-outcome → 四桥（MOS/value-evidence/North-Star/personal_episode）
```

预估请求量：**≈ 18 scene runs/天**（新增文档），另可加存量回灌批次。

---

## 3. 候选驱动 B（备选）：职业日常公文（低优先）

- 场景：个人职业场景下的总结/请示/报告类文书
- 优势：与 work 域语义最近
- 劣势：**请求量不可估**（无留痕数据可估）、无模板、涉个人信息需脱敏
- 判定：**暂不推荐**，留作驱动 A 跑通后的观察项

## 4. 候选驱动 C（备选）：健康域文书（不推荐）

`scene-health-*` 均为 draft + 人工触发，卡面明确「敏感域约束」。健康域文书**不应**接入自动审查流，除非先具备本地脱敏与最小暴露边界。

---

## 5. 结论与建议

1. **推荐驱动 A：本体系治理文档生产流** —— 内生、高量（≈18/天）、零外部依赖、5/5 能力腿可复用
2. **兼容度结论：高**，无需新建能力，仅需给 `scene-document-review` 增加 `docs/**/*.md` 信号触发并复用既有 journey
3. 建议后续 BET 认领路径：
   - 步骤一：为 `scene-document-review` 接线 docs 变更触发（poller 需支持非 iris 的本地文件信号源，或复用 `lifecycle: work` 的 documents 通道）
   - 步骤二：以 468 篇 retro 存量做 shadow 回灌，快速跨过 30 样本门槛
   - 步骤三：calibration ≥ 0.6 后按 Y3H1-T7-01 的既有路径升 assisted
4. **本文件不改变任何 BET 状态** —— 仅提供认领决策依据

## 6. 风险与边界

| 风险 | 缓解 |
|---|---|
| 文档流由 agent 触发、agent 审查（自证风险） | human_gate 保留人类裁决；校准看 precision/false_positive_rate 而非数量 |
| 治理文档含内部路径/凭据 | 复用 cockpit sanitizer；输入以脱敏摘要为主，正文不落 ledger |
| 存量回灌噪声（既有格式不合规文档） | 回灌批次与新增批次分开统计 calibration |
| 与 gac 门禁职责重叠 | 场景负责**旅程化审查与退回记录**，门禁仍是最终阻断（不替代） |

---

## 7. 证据索引（可复核）

| 断言 | 复核命令 |
|---|---|
| 近 30 天新增 688 篇 | `git log --since="30 days ago" --diff-filter=A --name-only --pretty=format: -- docs/superpowers/specs docs/plans .omo/_knowledge/retros \| grep -c '\.md$'` |
| 近 7 天 126 篇 | 同上，`--since="7 days ago"` |
| 存量 293/44/468 | `ls docs/superpowers/specs/*.md \| wc -l` 等 |
| 能力腿 2 资产 | `ls bin/gac/fix-frontmatter.py bin/gac/check-doc-freshness-gate.py` |
| 能力腿 5 资产 | `bin/ssot/journey-engine.py`（human_gate 置信度分支）、`bin/ssot/scene-outcome-recorder.py` |
