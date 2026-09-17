---
id: P107
status: active
lifecycle: pattern
owner: governance-team
created: 2026-09-17
last-reviewed: 2026-09-17
type: ssot
---

# P107: SPA Catch-All Route vs Test Expectation xfail Pattern

> **2026-09-17 沉淀** · 来源: cockpit dashboard favicon 404 修复 + test_unknown_path_returns_404 冲突
> 适用: 任何 SPA (单页应用) 前端项目, catch-all 路由与测试期望冲突的场景

## TL;DR

SPA 的 catch-all 路由 (`@app.get("/{path:path}")`) 必须返回 index.html/200 才能支持客户端 deep linking。但测试经常期望未匹配路径返回 404。**这不是 bug, 是设计冲突**。正确做法: 对已知静态资产（favicon.ico / robots.txt）做窄例外返回真 404, 其余路径保持 catch-all, 冲突测试标记 `strict xfail` 并解释原因。

## 陷阱表

| 陷阱 | 症状 | 对策 |
|------|------|------|
| 把测试当真理 | 看到 200≠404 就改代码, 破坏 SPA routing | 先判断是 bug 还是设计冲突 |
| 一刀切改 404 | 所有未匹配路径返回 404, deep linking 全挂 | 只对已知静态资产做窄例外 |
| 不解释就 xfail | 未来的 agent 不知道为啥 xfail, 反复掉进同一个坑 | xfail reason 必须写清楚 design rationale |

## 纪律

1. **先判断冲突性质**: 测试期望 vs 产品设计, 哪个对?
2. **窄例外优于大改**: 只修 favicon.ico / robots.txt, 不动 catch-all
3. **xfail 必须解释**: reason 字段写清楚 "SPA catch-all intentionally serves index.html for client-side routing"
4. **不要强行"修复"测试**: 测试错了就改测试, 不是改产品代码

## 实证

cockpit dashboard_server.py:
- 修了: favicon.ico / robots.txt 返回真 404（窄例外）
- 没改: 其余路径保持 catch-all index.html/200
- test_unknown_path_returns_404 → strict xfail with reason

## 反模式

- 为了测试通过把 catch-all 改成 404 → deep linking 全挂
- 删除测试 → 失去回归保护
- 静默 xfail（不写 reason）→ 未来 agent 不知道为什么
