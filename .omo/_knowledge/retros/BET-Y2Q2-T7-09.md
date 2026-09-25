---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: retro
title: BET-Y2Q2-T7-09 复盘
---

# BET-Y2Q2-T7-09 复盘：BCOS 主权进化链与学习图谱组件研发 (BcosEvolutionChainView)

## Q1 实际耗时 vs appetite？超出比例？
约 30 分钟（vs appetite 2 小时）。得益于前序 M1 类型与数据供给架构的打通。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 | 说明 |
|---|---|---|
| 进化记录时间轴与自愈指标可视化展示正常 | ✅ PASS | 在 `BcosEvolutionChainView.tsx` 中完整呈现当前 Epoch、自蒸馏知识条目数、认知自愈指数与历史进化里程碑时间轴 |
| 包含流光骨架屏加载状态；单测全部通过 | ✅ PASS | 内置 3 个 SkeletonCard，单元测试全部通过（耗时 45ms） |
| PR #36 成功 squash-merge 合入 main（提交 84a1b67） | ✅ PASS | 子模块 GitHub PR 评审通过并合入主线 |

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **测试断言多重匹配**：在单测中因顶部卡片与时间轴第一行均出现 `Epoch 24`，导致测试库 `getByText` 报歧义。规范修复为 `getAllByText`，提高了单测健壮性。
2. **时间轴响应式设计**：时间轴卡片在移动端垂直排列，桌面端左右两翼展开，保证不同分辨率下的清晰可读。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
- **代码文件新增**：
  - `projects/cockpit-ui/src/views/panorama/BcosEvolutionChainView.tsx` (+191 行)
  - `projects/cockpit-ui/src/views/panorama/__tests__/BcosEvolutionChainView.test.tsx` (+88 行)
  - `projects/cockpit-ui/src/views/panorama/index.ts` 导出更新 (+1 行)
- **子模块合入 commit**：`84a1b6704736308592e188c7880eea9ed57bdbfb` (PR #36)
- **主仓设计规约**：`docs/superpowers/specs/2026-09-24-bcos-evolution-chain-view-design.md`

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **组件引入入口**：`import { BcosEvolutionChainView } from '@/views/panorama';` 即可直接使用。
2. **大屏装配**：至此，M2 里程碑的 4 大核心大屏组件全部研发完成（门禁、哨兵、架构拓扑、BCOS 进化链）。下一个里程碑 M3 将把它们组合装配进顶层 `/panorama` 体系全景主航道！
