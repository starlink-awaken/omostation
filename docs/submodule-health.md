---
status: active
lifecycle: entry
owner: auto-fix-loop
last-reviewed: 2026-09-11
---
# 子模块健康度报告

> 生成时间: 2026-09-06 23:47 UTC
> 自动生成: `bin/gac/generate-submodule-health-report.py`

## 概览

| 指标 | 数值 |
|------|------:|
| 子模块总数 | 16 |
| 远程分支总数 | 38 |
| Tags 总数 | 207 |
| 指针漂移 | 0 |
| 未初始化 | 0 |

## 子模块详情

| 子模块 | 远程分支 | Tags | 指针状态 | 最后同步 |
|--------|----------|------|----------|----------|
| runtime | 1 | 1 | ✅ 对齐 | 2026-09-06 |
| metaos | 1 | 0 | ✅ 对齐 | 2026-09-06 |
| l4-kernel | 1 | 2 | ✅ 对齐 | 2026-09-06 |
| ecos | 4 | 21 | ⬇️ -1 | 2026-09-06 |
| agora | 4 | 14 | ⬇️ -1 | 2026-09-06 |
| cockpit | 5 | 32 | ✅ 对齐 | 2026-09-06 |
| family-hub | 1 | 20 | ✅ 对齐 | 2026-09-06 |
| model-driven | 1 | 0 | ✅ 对齐 | 2026-09-06 |
| gbrain | 2 | 0 | ✅ 对齐 | 2026-09-06 |
| omo | 4 | 22 | ✅ 对齐 | 2026-09-07 |
| aetherforge | 1 | 16 | ✅ 对齐 | 2026-09-06 |
| bus-foundation | 2 | 0 | ✅ 对齐 | 2026-09-06 |
| observability | 1 | 0 | ✅ 对齐 | 2026-09-06 |
| omlxc | 4 | 79 | ✅ 对齐 | 2026-09-06 |
| cockpit-ui | 1 | 0 | ✅ 对齐 | 2026-09-06 |
| kairon | 5 | 0 | ✅ 对齐 | 2026-09-06 |

## 建议

- 定期清理已合入 main 的远程分支
- 清理过期 tags，保留最近 20 个
- 同步子模块指针到最新 origin/main
- 清理悬空 tracking 分支

---

*本报告由 `bin/gac/generate-submodule-health-report.py` 自动生成.*