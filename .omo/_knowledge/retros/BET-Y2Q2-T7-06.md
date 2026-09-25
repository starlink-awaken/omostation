---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-25
type: retro
title: BET-Y2Q2-T7-06 复盘
---

# BET-Y2Q2-T7-06 复盘：门禁全景矩阵组件研发 (GatesMatrixView)

## Q1 实际耗时 vs appetite？超出比例？
约 40 分钟（vs appetite 3 小时）。得益于前序 M1 类型与 TanStack Query Hook 的完备沉淀。

## Q2 done_when 是否全部通过？哪条没过，为什么？
| done_when | 状态 | 说明 |
|---|---|---|
| 完整呈现 A1-A9 与 RF0、RC-DL；支持点击卡片展开详情与证据文件指引 | ✅ PASS | 在 `GatesMatrixView.tsx` 中完整呈现 11 大门禁，支持展开/收起查看详情、复制证据路径 |
| 包含流光骨架屏加载状态；单测全部通过 | ✅ PASS | 内置 9 个 SkeletonCard，7 个单元测试 100% 通过（耗时仅 78ms） |
| PR #33 成功 squash-merge 合入 main（提交 b91c119） | ✅ PASS | 子模块 GitHub PR 评审通过并合入主线 |

## Q3 过程中发现的与 plan 不符的事实（打假）
1. **统一导出桶文件缺失**：原本 `src/views/panorama/` 缺少 `index.ts`，导致外部引入路径容易散乱。本 BET 顺便建立了 `src/views/panorama/index.ts` 统一导出 Barrel。
2. **筛选器计数实时联动**：在筛选器中动态计算通过/异常数，并配齐空状态提示（SlidersHorizontal 图标），防止用户搜索无果时界面困惑。

## Q4 净增减：代码行 / 文件 / GaC 规则 / ADR / 脚本？
- **代码文件新增**：
  - `projects/cockpit-ui/src/views/panorama/GatesMatrixView.tsx` (+325 行)
  - `projects/cockpit-ui/src/views/panorama/__tests__/GatesMatrixView.test.tsx` (+190 行)
  - `projects/cockpit-ui/src/views/panorama/index.ts` (+3 行)
- **子模块合入 commit**：`b91c119b1664a5dbd9592153e245c97342fc8ddc` (PR #33)
- **主仓设计规约**：`docs/superpowers/specs/2026-09-24-gates-matrix-view-design.md`

## Q5 下一个认领本 track 的 agent 需要知道什么？
1. **组件引入入口**：`import { GatesMatrixView } from '@/views/panorama';` 即可直接使用。
2. **与大屏主航道整合**：在后续 `BET-Y2Q2-T10-162`（/panorama 导航装配）中，该组件将作为默认选中的 Tab「🏛️ 门禁全景」直接挂载在主全景视图内。
