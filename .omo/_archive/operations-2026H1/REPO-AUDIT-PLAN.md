---
lifecycle: contract
owner: governance-team
last_updated: 2026-08-18
title: 全面审计方案：omostation 多仓库治理健康度（REPO-AUDIT-PLAN）
type: doc
---
# 全面审计方案：omostation 多仓库治理健康度（REPO-AUDIT-PLAN）

> 由 2026-08-08/09 会话 grill-me 产出。14 个决策点全部确认。
> 执行请另开会话，按本文档蓝图推进。

## 一、审计边界（决策 1）

**范围**：全仓库（omostation 主仓库 + 17 个子模块） × 治理机制 × 分层递进

| 维度 | 范围 | 说明 |
|---|---|---|
| 仓库 | 主仓库 + 17 子模块（git submodule status 自动枚举） | 三层分级：深度 2（omostation/agora）+ 中度 3（kairon/ecos/bus-foundation）+ 浅度其余 |
| 主题 | 治理机制（CI 健康度/submodule 漂移/hook 一致性） | 不审代码质量/安全（另议） |
| 深度 | 分层递进 | 先全量浅扫出风险地图 → 按红点密度深挖 top 3-5 |

## 二、产出物（决策 2 + 8）

**三件套**（报告 + 台账 + 看板三联动）：
1. **审计报告**：`docs/operations/REPO-AUDIT-2026-08-09.md`（风险地图 + 红点清单 + 根因 + 修复建议）
2. **台账条目**：`debt.yaml` 追加 `capability_gap`（`.omo/_truth/registry/debt.yaml`，gap_items_dir + gap_registry 机制已存在），命名 `repo-audit-2026-08-09/<red-item>`，每条含 `status: open` + `verification` + `owner`
3. **看板**：`.github/workflows/repo-health-daily.yml`

## 三、检查项清单（决策 3）

| 组 | 检查项 | 工具 |
|---|---|---|
| A. CI 健康度 | workflow 最近 N 次 runs 结论；连续全红识别；死配置（未触发 workflow） | gh run list / gh api workflows |
| B. Submodule 治理 | gitlink 领先/落后/不可达；指针单调性；autobump 运转 | 调 check-submodule-pointer-drift.py + reachability gate |
| C. Hook 一致性 | canonical `.githooks/` vs 执行位置分叉；worktree hook 同源；remote-hygiene 期望值单一源 | diff + 配置比对 |
| D. 卫生（简化） | 已合并未删分支；孤儿 worktree；未推送 commit | git 命令，只记不深挖 |

## 四、数据获取（决策 4）

**纯 gh CLI**：
- `gh run list --workflow X --limit N`（每 workflow runs 结论）
- `gh api repos/{owner}/{repo}/actions/workflows`（枚举）
- `gh --repo <repo> pr list`（分支保护/活跃）
- 18 仓库 × ~5 workflow × 10 runs ≈ 900 调用，2-3 分钟可接受
- 私有仓库 404 容错（跳过 + 报告标注）

## 五、脚本设计（决策 9）

**编排器模式** `bin/ssot/audit-repo-health.sh`（薄脚本，调用既有治理脚本，不重复造轮子）：

```bash
bin/ssot/audit-repo-health.sh
├── enumerate_repos()      # git submodule status → 仓库清单
├── audit_ci()             # gh run list per repo workflow
├── audit_submodule()      # 调 check-submodule-pointer-drift + reachability gate
├── audit_hook()           # canonical vs 执行位置 diff
├── audit_hygiene()        # 分支/worktree 卫生 (简化)
└── render_report()        # JSON + Markdown 双格式输出
```

依赖既有脚本接口（已确认 argparse 参数）：`check-submodule-pointer-drift.py --range <base> HEAD --submodules`、`submodule-reachability-gate.py --source head --fetch --changed-from <base>`。

## 六、执行策略（决策 5 + 10）

**风险热力排序**：
- Phase 1：全量浅扫 → `REPO-AUDIT-MAP`（每仓库：CI 状态/漂移数/hook 一致性/风险分）
- Phase 2：按地图红点密度深挖 top 3-5 仓库根因 → 补进报告
- 只读操作，与并行 agent 零冲突；深挖遇"并行 agent 活跃区"（如 #1262 评测集）跳过标注

## 七、修复与闭环（决策 6）

**三件套闭环**：
```
审计脚本跑 → 报告(红点+根因+建议)
    ↓
修复清单排期(P0机制/P1体系/P2结构)
    ↓
机制类红点直修(授权) → 看板确认变绿 → 台账转 verified
    ↓
repo-health-daily.yml 每日跑 → 新红点自动告警(防回归)
```

- **机制类红点**（hook 分叉/期望值波动/CI 噪音）：授权直接修，走 PR 提交
- **结构性红点**（agora 依赖耦合）：进台账 + P2 排期
- **并行活跃区**：标注跳过

## 八、看板规格（决策 11 + 12）

`.github/workflows/repo-health-daily.yml`：

```yaml
on:
  workflow_run:            # 关键 gate 失败事件触发
    workflows: [phase-gate, evidence-gate, gac-gate, agora-ci, kairon-ci, ecos-ci]
    types: [completed]
  schedule:                # 每日基准
    - cron: '0 8 * * *'
```

- **仓库范围**（首期 5 核心，事件触发）：omostation/agora/ecos/kairon/bus-foundation
- **其余 12+ 子模块**：每日浅扫兜底（不挂事件）
- **告警通道**：自动开 GitHub issue（`repo-health-alert` 标签），可追踪可留痕
- **后续扩展**：看板跑稳后按需加仓库/邮件/Slack 通道

## 九、验收标准（决策 13）

**分级验收**：

本期完成（本次审计会话）：
```
□ audit-repo-health.sh 可运行（编排器，调用既有脚本）
□ REPO-AUDIT-MAP 产出（18 仓库风险地图）
□ 深挖 top 3-5 仓库根因
□ 机制类红点修复 + 台账转 verified
□ 结构性红点进台账 + P2 排期
□ repo-health-daily.yml（每日 cron + 关键 gate 事件 + issue 告警）
□ 看板首跑确认绿
```

完全完成（数月）：结构性红点清零（agora 依赖 PyPI 发布等）。

## 十、执行入口（决策 14）

**本方案文档即执行蓝图**。执行另开会话：
1. 读本文档（决策全在此）
2. 建 worktree `work/repo-audit`，写 `bin/ssot/audit-repo-health.sh`
3. 手动跑 Phase 1 浅扫 → 出地图 → Phase 2 深挖
4. 产出三件套（报告 + 台账 + 看板）
5. 按分级验收清单闭环
