# BET-Y1Q4-T8-24B Retro — 六面正交 Store 底座与 ⌘K 命令面板

> 日期: 2026-09-12 | 状态: engineering VERIFIED (operational/value 待 24C/D/E 前端消费后单独证明)

## 交付

cockpit-ui#9 (squash 9877645) + 主仓 #3615 (gitlink b1d3ce0 → 9877645)。

## 交付内容

1. 六面正交 Zustand Store (src/stores/):
   control / knowledge / business / evolution / collaboration / delivery
   - 每面独立 store, 互相零 import; 跨面组合只在组件层
   - 旧 src/store.ts useCockpitStore 保持兼容 (渐进迁移, 不破坏)
2. ⌘K 全局命令面板:
   - commandPaletteCore.ts 纯逻辑 (store + buildCommandItems + fuzzyFilter)
   - commandPalette.tsx 组件层 (react-refresh/only-export-components 合规)
   - 模糊检索: 前缀 100 > 子串 80 > 副本 60 > 关键词 40 > 分词 20, 上限 50
   - 数据源: cockpitPageRegistry (54 路由) + observatory 快照注入 (302 BOS / 1248 能力)

## 验收实测

| done_when | 结果 |
|---|---|
| #1 6 大 Zustand Store 建立且解耦 | ✅ 6 store + 互不污染断言 (planes.test.ts 正交性测试) |
| #2 ⌘K 50ms 模糊检索 1248 能力/302 服务 | ✅ 内存索引 + 稳定排序实测 (bun test 内联) |
| #3 Causal Inspector 侧抽屉 | ⏳ 抽屉 UI 属 24C Studio 交付; 数据源 (SHA-256 展示用 entity/query) 已由 24A/B 数据面就绪 |

## 测试

- bun test src/stores/: 11 passed
- typecheck: 0 错; build ✓ (1.08s)
- 全套 bun test 699: 1 error 为既有 EnhancedDataTable 债务 (stash 对照确认)
- eslint src/stores/: 0 问题 (react-refresh 合规: 逻辑/组件拆分)

## 剩余 (非本 BET)

- Causal Inspector 侧抽屉 UI → T8-24C (Studio) / 24D (Operations)
- Store 实际接线到视图 → 24C/D 逐面落地
