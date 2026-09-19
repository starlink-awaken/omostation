# 治理迭代战役收官复盘 (T10-139 → T10-140 → 三轮迭代)

- date: 2026-09-08
- scope: 同号竞速根治 → 清理器防护 → 判定内核三轮精化
- prs: #3405 #3408 #3409 #3411 (T10-139) · #3416 #3418 #3419 #3420 (T10-140 + 生成器)
  · #3430 #3433 #3435 #3438 (三轮迭代) · #3422 #3423 #3426 (对齐/盘点)
- 全部 merged, 零回滚

## 战役主线 (问题 → 根治链)

```
同号竞速 4 轮 PR 浪费 (T10-135~138)
  └→ T10-139 认领广播 (claim-bet/start 拦截/gc/自动释放)
       └→ 共享锚点洞察: .omo/ gitignored → worktree 互盲 (用户提问触发)
并行 reset 吃未推 commit ×7 (含刀落 commit 后)
  └→ T10-140 清理器引用保护 (三维 guard + 三工具接入)
       └→ 迭代①: patch 等效豁免 (squash 残留误保护)
       └→ 迭代②: claim-gc 调度补全 (launchd 每日)
       └→ 迭代③: prune-zombie 僵尸语义 (git 认=活现场)
       └→ 迭代④: 子模块扫描 guard 标注 (omo 3 过期分支全放行)
```

## 模式级沉淀 (可复用判例)

### M1 — 防御层失败语义分层
写入侧 fail closed (claim-bet 异 actor 拒), 读取侧宽容 (guard 故障放行+警告)。
防御层自身**不许成为新单点** — T10-139 guard 与 T10-140 guard 同哲学。

### M2 — 判定内核单点共享 (DRY)
三清理器共用 lib/cleanup-guard.py 一份判定; 盘点审计 (T6-16 报告) 复用同内核。
语义升级 (patch 等效豁免) 一次改动全链生效。

### M3 — 保护判定的语义边界靠实测暴露
- 空 cherry 输出 (tip 已在 main 内) 初版被当"不可判"保守保护 — E2E 实测分支形态
  暴露单测盲区。**空集是"全吸收"不是"不可判"**。
- merged-clean 判定把活 worktree 标可删 — dry-run 实测暴露, enforce 前拦截。
  **判定器的语义边界必须在真实数据上 dry-run, 单测的合成形态永远不全**。

### M4 — 共享工作面纪律 (多 agent 混战生存术)
- 未提交改动活不过 reset 窗口 (观测 5 次 reset 吞实施中代码) → 做完一块立即
  commit + push (远端 refs 是唯一物理锁)
- 并行 commit 叠老王分支 → reflog 锚点重开干净分支 (两次实战: fix/resident-jobs-clean,
  guard-equivalence-clean)
- 树上 stash/autostash 活动频繁 → 改动前先看清本地领先面再动作

### M5 — SSOT 变更走生成器正路 (ADR-0435 模式三连实证)
launchd 修复 = 注册表 (services.yaml) + tracked wrapper + 生成器 --write。
本轮三证: 角色 jobs (#3416), StartInterval 映射 (#3420), claim-gc (#3435)。
**手改 plist/机器级配置必被生成器覆盖回坏状态**。

### M6 — 结构化判定优先于文本匹配
rg 'status: active' 误报 71 run (嵌套 step 字段) 差点批量误清 — yaml 顶层字段
结构化判定是唯一可靠口径 (PITFALL-MEA-004)。

## 判定内核终态 (cleanup-guard)

| 维度 | 保护 | 豁免 | 失败语义 |
|---|---|---|---|
| unpushed | 远端有未推 / patch 未吸收 (+) | 空 cherry (全吸收) / 全 '-' (等效吸收) | cherry 不可判 → 保守保护 |
| open-pr | gh 有 open PR | — | 查询失败 → 放行 (宽容) |
| bet-claimed | 分支名含活跃认领 bet_id (全 id / 边界短 id) | — | 读取失败 → 跳过该维度 |

配套调度: claim-gc 每日 launchd; prune-zombie 注册中 worktree 跳过;
branch-ttl-gate 子模块扫描带 ⛔ 保护标注 (omo 3 过期分支全放行 = 可清面)。

## 尾款 (诚实记录)

- fix/resident-jobs-adr0435 分支 5 个未吸收 patch 仍受保护 — 混战期并行方工作,
  等其 owner 处置
- #3406 (kos bump) 与已合 #3422 内容交叠 — 需 review 确认 stale
- cockpit detached HEAD — 并行方确认意图
- 6 个等效吸收 DELETABLE 分支 — 删除决定权在并行方
