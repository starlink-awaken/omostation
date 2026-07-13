# C1 · 治理过度工程量化审计

> 日期: 2026-07-13 · 方法: 静态解析 `.omo/_truth/registry/governance-checks.yaml`（GaC 规则 SSOT）
> 范围: 本轮聚焦**最高信号**的 GaC 规则注册表 ROI；per-gate 运行时命中率需活体证据（本沙箱无 venv，留待 Mac）。

## 头条结论：GaC 注册表已越过自己的冻结上限，且掺了一批低牙规则

治理机器确实在超配生长。硬数据：

| 指标 | 值 | 含义 |
|------|----|------|
| 总规则数 | **184** | ADR-0178 冻结 cap 是 **173** → **已超 11 条** |
| active / draft | 178 / 6 | 冻结声明未被实际执行（cap 形同虚设） |
| 弱牙规则（仅 audit/radar，无 CI/hook/local-gate 拦截） | **9** | 只审计不拦截，ROI 最低 |
| 无 ADR 溯源 | **11** | 治理注册表自己有 11 条没走 ADR（治理不治己） |
| target=None（无法机械定位） | ~100 | 半数规则无 `target` 字段，ssot_pointer 类无法机械校验 |
| 维度分布 | X4:76 X1:45 X3:32 X2:31 | X4（一致性）规则最密，易堆叠 |

**最尖锐的一点**：ADR-0178 声明"封顶 173 防膨胀"，但实际已 184——**冻结机制本身没生效**。这正是"元机器 > 产品"失衡的实锤：连防膨胀的规则都拦不住膨胀。

## 最低 ROI 的削减候选（建议冻结/合并）

### A. 9 条弱牙规则（只审计不拦截，先冻结评估）
`CR-X2-GAC-DRIFT` · `CR-X1-AGENT-AUDIT` · `CR-L2-MUTATION-BROKER` · `M4-HEALTH-SCORE` · `M4-DERIVED-PLANE-AUDIT` · `CR-META-METRIC-DEBT-FEATURE` · `CR-X-PROMOTION-LIFECYCLE` · `CR-CROSS-REPO` · `CR-PRINCIPLE-ENFORCEMENT`

这些只挂 `omo_audit`/`radar_cron`，不进 CI/hook/local-gate——即"记一笔但不拦"。若它们从未真正驱动过修复动作，就是纯维护成本。**逐条问：过去 30 天它审计出并促成过任何修复吗？答不上 → 冻结。**

### B. cross-repo 规则族（3 条重叠 → 合并为 1）
- `CR-CROSS-REPO-CONSISTENT` 和 `CR-CROSS-REPO-CHECK` **同 target** `bin/check-cross-repo-consistency.py`——明显冗余。
- 加上 draft 的 `CR-CROSS-REPO`，共 3 条管同一件事。**合并成 1 条**，净减 2。

### C. 11 条无 ADR 溯源规则（补溯源或废除）
`CR-SEC-*`（4 条安全规则，大概率该留，补 ADR 即可）+ `CR-PRINCIPLE-ENFORCEMENT` / `CR-CROSS-REPO*` / `CR-PR-DESCRIPTION-NON-EMPTY` / `CR-RUFF-SCOPE-STABLE` / `CR-WORKTREE-CLEAN-BEFORE-PR`。治理注册表要求别人走 ADR，自己却有 11 条没走——**要么补 ADR 溯源，要么废除**。

### D. 6 条 draft 规则（2026-07-08 建，7/15 将自动转 active）
`CR-CROSS-REPO` · `CR-CROSS-REPO-REGISTRY-CONSISTENT` · `CR-PR-DESCRIPTION-NON-EMPTY` · `CR-PRINCIPLE-ENFORCEMENT` · `CR-RUFF-SCOPE-STABLE` · `CR-WORKTREE-CLEAN-BEFORE-PR`
按 `draft_to_active_days:7`，若 radar 未验证就到期会**静默转正或烂尾**。7/15 前须确认每条真被 radar 验证过，否则 3 条与上面重叠的直接砍。

## 与 A4 的联动（关键决策输入）

你已批准为 A4 的两条探测真实性规则解冻（173→175）。但结合本审计：**别只是抬 cap**。184 已超 11，再 +2 = 186、超 13。更诚实的做法是**先减后加**：

> 先砍 B（cross-repo 合并 -2）+ 冻结 A 里确认无用的若干条，**腾出配额**，再把 A4 的 2 条高价值规则加进去——净规则数可能不升反降，且冻结 cap 恢复可信。

这样 A4 和 C1 一起，既补上真正该有的探测真实性规则，又实际给治理机器减负一个周期——正好落实 Track C 的纪律。

## 交付状态
- ✅ GaC 规则注册表 ROI 审计完成（本文件）——量化了超配、弱牙、无溯源、重叠四类。
- ⏳ 未覆盖（需活体证据，留 Mac）：每条规则过去 N 天的真实命中/拦截次数（`omo_audit` 日志）、其他 registry（debt/services/agent-workflows）的 ROI、pre-commit/CI workflow 的耗时占比。
- 建议：把"先减后加"作为 A4 的前置，让减负真正发生而非又一次净增长。
