---
status: needs-human
lifecycle: history
owner: governance-team
last-reviewed: "2026-07-29"
type: ephemeral
status: archived
---
# Y1-Y4: main 绿确认 + 场景库降级 + W 波观察 + 产能去污

## Y1 · main 绿 ✅ (pointer 修 + CI 跑通)

- PR #604 MERGED (2026-07-29T06:18:13Z, gac-gate + phase-gate pass)
- origin/main = 69bc1b344c04, runtime pointer = **f3db619** (修, 非 0d48a55 损坏)
- main gac-gate **completed success** (55s) —— CI 红根因 (pointer 损坏) 彻底修复
- SSOT: system.yaml sync 后 (X5), M (dirty 待 commit)

**#604 兼两件事**: pointer 修复 (0d48a55→f3db619) + #592 实质回滚 (f3db619 不含 Agent Registry).

## Y2 · 场景库降级为本地工作数据 (二选一决策)

**决策**: `.omo/_delivery/collab-scenarios/` **gitignored = 本地工作数据, 不可汇报产能轨**.

**理由** (二选一):
- 纳入版本控制: ADV 场景进 git, CI 扫, 但构造场景污染 git 历史 + 产能轨
- ✅ **降级本地工作数据**: ADV 场景本地 only (不污染 git), **不可汇报产能** (P84 §0 构造场景不计产能轨)

**门的影响**:
- check-scenario-growth 扫 .omo/_delivery (gitignored) → CI 扫空 (ADV 场景门 CI 无效)
- **detector 门 (scenario_lib tracked) CI 有效** (拦新 _synthesize_*)
- 结论: detector 门是 CI 主门 (拦源头), ADV 场景本地验证 (不可汇报)

**注意 (Y1 发现的矛盾)**: detector 70 > baseline 49, 但 #604 gac-gate pass (detector 门没拦).
→ check-scenario-growth detector 门可能在 CI 没真跑, 或 baseline 在 CI 不同. **待查** (门有效性后续验).

## Y3 · W 波观察 (一周实证, 不猜)

**现状 (2026-07-29)**:
- W17-W24 (#596-#606) 已 merge 进 main (在 required check 设之前 / 不匹配时)
- #604 被 required 拦过 (后 merge) = **required 现在工作**
- main pointer 修 (f3db619) + CI 绿

**一周观察 (2026-07-29 ~ 08-05)**:
- required check (gac-gate + phase-gate) 现拦 PR merge (FAIL 不能合)
- 若一周内无新 W 波 merge → 传送带真停
- 若仍有 W 波 → 还有没找到的路径 (direct push? admin? 别的), **如实报告不猜**

**当前判断 (待实证)**: required 工作 + pointer 修 → 未来 W 波应被拦. 但 W17-W24 已在 main (存量).

## Y4 · 产能轨去污 (月 15 目标)

**最新去污 (92 done)**:
- 🔴 自产 (W 波/能力轨): **62 (67% 污染)** —— W17-W24 加 33 自产 (传送带污染持续)
- 🟡 真实无 PR (疑似): 21
- ✅ 真实有 PR: **9**

**月 15 目标**:
- 保守 (9 有 PR): **9 < 15 不达标**
- 宽松 (30 含疑似): 30 ≥ 15 达标 (但疑似未验证)
- 完成率: 保守 9.8% / 宽松 32.6%

**🔴 产能轨 SSOT 不可信** (export-dualtrack 报 103/98.1%, 真实 9-30). 需 export 加自产过滤 (T1 去污标准).

## 🔴 红线 + 待人类
- Y1 main 绿 ✅
- Y2 场景库降级本地 (不可汇报产能) — 落档
- Y3 一周观察 W 波 (不猜, 实证)
- Y4 产能 67% 污染 (月 15 保守不达标), export 需去污过滤
- check-scenario-growth detector 门矛盾 (70>49 但 pass) 待查

## References
- X1-X5 (pointer 修 + CI 跑通) · T1 (去污标准) · R1 (协作收窄)
- #604 (pointer 修 merge) · W17-W24 (传送带存量)
