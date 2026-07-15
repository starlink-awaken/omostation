---
status: ACCEPTED
lifecycle: decision
owner: 夏明星
last-reviewed: 2026-07-15
related:
  - 0202-fake-green-prevention.md
  - 0179-runtime-probe-false-positive-treatment.md
  - 0195-architecture-convergence-isc2.md
  - ../patterns/p73-truth-driven-engineering-pattern.md
  - ../patterns/p74-workflow-solidification-pattern.md
  - ../../../docs/STRATEGY-3YEAR-PANORAMA.md
  - ../../../docs/VISION-ROADMAP.md
  - ../../../docs/ARCHITECTURE-ANALYSIS-2026-07-14.md
supersedes: []
---

# ADR-0210: 三年综合战略方向 — 从"扩图纸"转向"收敛执行面"

> **注**: 编号 0210 取自 INDEX 最大号 + 1（0209）。多 Agent 高频环境下编号为共享可变资源，
> 若落地时发现撞号，按 ADR-0202 D4 处理（占号即推送 / 接受重号成本）。战略决策已 `ACCEPTED`（2026-07-15 用户授权「继续推进」定档）。

## Context and Problem Statement

eCOS v6 经过 44 个 Phase、W1–W4 多轮治理升级，已建成完整的 `5+4+1+1` 架构、17 子项目、
agora I0 单点 MCP 网关、SSOT 严格的 GaC 体系。**架构"图纸"质量是 A 级、是稀缺资产。**

但 2026-07-14 全盘 submodule 巡检暴露了系统的结构性张力——`decl-exec-gap-meta-pattern`
（memory 已沉淀 11+ 实例）：声明面满分（`ecosystem_maturity_score` / `metacognition_safety_score`
/ `governance_loop_safety_score` 全 100），执行面却持续警戒——复合 `health_score` 83（截至
2026-07-15 快照，权威源 `.omo/state/system.yaml`），L1 runtime daemon 在线率约 60%（ollama
等 stale + 探测假绿灯），多 Agent 协调"就绪未启用"、实战靠人工等/停抢主仓 main。

问题陈述：**未来三年，织星的战略重心应放在"继续扩张架构图纸"，还是"收敛已暴露的声明-执行鸿沟"？**
这决定资源投向与阶段门禁，是架构方向级决策，需 ADR 定档。

## Decision Drivers

- **D1 · 鸿沟是最大杠杆**：2026-07-14 六字总结——"设计 A 级，运行 B- 级"。再加架构会扩大领先图纸、
  加深鸿沟；启用已有治本机制（如 agent isolation rollout）是低成本高回报。
- **D2 · 度量诚实度**：`health_score` 现口径受声明面 maturity 主导，掩盖了 runtime 60% 的实况，
  持续误导决策（见 ARCHITECTURE-ANALYSIS §2 成熟度悖论）。
- **D3 · 愿景兑现前置条件**：蜂群/多机/个人大脑愿景，必须建在稳的执行面地基上；地基漏水时盖楼 = 返工。
- **D4 · 已有资产未变现**：GaC + SSOT + MCP 网关 + MOF 是可复制的治理方法论，应外溢为护城河。
- **D5 · KOS 空积累信号**：X3 知识复用维度"KOS 索引篇 = 0"，个人大脑愿景缺前置数据积累。

## Considered Options

- **选项 A · 愿景优先（图纸驱动）**：直接按 VISION-ROADMAP Phase 2–5 推进多机/蜂群/个人大脑，
  执行面问题边走边修。
  - 优点：愿景推进快，叙事漂亮。
  - 缺点：在 daemon 60% / agent 抢 main 的地基上叠分布式，几乎必然返工；扩大声明-执行鸿沟。
- **选项 B · 收敛优先（执行面驱动，本 ADR 选定）**：先设"收敛期"只治本不加功能，M1 执行面达标后再进
  愿景阶段，愿景每步以执行面门禁验收。
  - 优点：地基稳，度量诚实，愿景落地不返工；杠杆最大。
  - 缺点：短期愿景叙事"看起来慢"，需要战略纪律顶住"多加功能"的诱惑。
- **选项 C · 双线并行**：治本与愿景同时推进。
  - 优点：表面兼顾。
  - 缺点：有限人力被摊薄，治本项（需硬性纪律）最易被愿景挤占，历史上正是这样形成鸿沟。

## Decision Outcome

**选定选项 B — 收敛优先，三阶段推进**：

1. **收敛期（2026H2–2027Q1）· 只治本**：
   - 🔴 **P0 · 启用 Agent Isolation**：worktree + branch protection，强制每 agent 走
     `gac-worktree.sh claim`，不碰主仓 main（分阶段：新 agent 强制、存量迁移）。
   - 🔴 **P0 · 修复 L1 runtime**：stale daemon 真启或摘除，daemon 在线率纳入 `health_score` 主权重。
   - 🟡 **P1 · 重构 health_score 公式**：执行面实证权重↑、声明面 maturity 权重↓（衔接 ADR-0202 反假绿灯）。
   - 🟡 **P1 · submodule gitlink 巡检挂 foundry 6h cron**。
   - **门禁**：里程碑 M1（2027Q1）不达标（daemon ≥ 90% / 并发 agent 零主仓冲突），不进阶段二。
2. **兑现期（2027Q1–2028）· 蜂群落地**：Agent 注册中心、分布式调度、角色框架、涌现检测；
   每步以执行面门禁验收（4 机成功率 > 99% / 3 角色完成率 > 95% / 涌现准确率 > 80%）。
3. **跃迁期（2028–2029）· 个人大脑 + 护城河外溢**：个人知识图谱 / 偏好学习 / 数字孪生；
   治理方法论产品化，完成一次对外复用验证。KOS 索引篇从 0 起，收敛期即设季度积累目标。

**后果 (Consequences)**：
- 正面：地基先稳，度量反映实物，愿景落地不返工；已有治本资产被启用而非闲置。
- 代价：收敛期愿景叙事看似放缓；`health_score` 口径切换会使分数短期下探（这是诚实化的预期结果，非退化）。
- 影响面：本 ADR 是方向决策，不新增 GaC 规则；具体 P0 落地（agent isolation / health 权重）
  各自另立子 ADR 承载执行细节（衔接 ADR-0171 哲学：教训须落为 red 执行点，文档化教训是墓志铭）。

## Confirmation

- **战略层**：`docs/STRATEGY-3YEAR-PANORAMA.md` 作为叙事 SSOT，三阶段门禁写入其路线图章节。
- **收敛期验收（M1, 2027Q1）**：
  - `.omo/state/system.yaml` 中 daemon 在线率 ≥ 90%（去假阳性后口径）。
  - 并发 agent 主仓冲突 = 0（`gac-worktree.sh` claim 覆盖率 100%）。
  - `health_score` 新口径落地且与 daemon 实测强相关（非声明面主导）。
- **决策生效追踪**：P0/P1 各子举措落地时补对应子 ADR，并回填本 ADR `related`。
- **工具校验**：`uv run --with "pyyaml" python bin/adr/adr-coverage.py` 通过 frontmatter 完整性；
  `adr-drift-check.py` 通过引用路径校验。

---

*ADR-0210 · PROPOSED · 2026-07-15 · 夏明星 · 待拍板转 ACCEPTED*
