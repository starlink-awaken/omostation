---
status: done
lifecycle: history
owner: governance-agent
last_updated: 2026-08-27
title: 6-axis north_star v3 深化 — 本轮迭代教训
type: retro
---
# 6-axis north_star v3 深化 — 本轮迭代教训

## 范围

本轮 (2026-08-27) 在 fix/staleness-optimization + 派生分支上对
bin/bc-os/north_star_meter_v3.py 做了三轮深化, 同时清理了预发布门
上堵塞 push 的 5 个仓库债 (doc-ssot / conflict markers / submodule
pointer)。

## 三轮 commit 链

| Commit | 内容 | 实证结果 |
|---|---|---|
| fc64a5609 | Axis D 知识消费深度 | 211 events/30d, score=100 |
| b1f49a6e6 | Axis E 决策质量 (P0/P1 × adoption) | 7 P0/P1, 6/8 adopted, score=100 |
| e44fe8faf | Axis A2 KV 缓存加速 (omlxc fabric inspect) | hit_rate=0.0 (honest gap) |
| 89257a96f | dim 4 体验 daemon-stable fallback | 9-dim GREEN=9 GREY=0 |
| 4c8852f4b | batch fix 12 conflict markers + 601 frontmatter | doc-ssot 11 err → 0 err |

## 教训

### 1. 6-axis 不是 6 个独立指标, 是 4 套 composite 的层级

设计走过的弯路: 起初把 A 拆 A1+A2 当作 2 个独立 axis 配 0.45/0.10 权重。
实际上, 6-axis 是同一组 6 个数据点的 4 套权重表达:
- 3-axis BC (A70+B30) = 价值主干线, 不变
- 4-axis (A60+B20+D20) = 加知识沉淀
- 5-axis (A55+B10+D20+E15) = 加决策闭环
- 6-axis (A45+A210+B10+D20+E15) = 加 KV 缓存诚实计

主 3-axis BC 不动, 后三套是 advisory, 因为 BC 已经是 value-asserted
的"通过线", 4/5/6 用来回答"还有什么没被证明"。

副产物: 6-axis=88 (因 A2=0 诚实报告) 比 5-axis=98 看起来更"低", 但
这个低是有用的信号 — 系统识别出 KV 缓存层没真正服务于生产推理。

### 2. workflow affected-hash 对 docs/ 路径是 over-engineered

`bin/agent-workflow.py claim` 要求 `--affected-hash` 文件路径, 且
`docs/*` 路径不属于 `docs/layer-contract.yaml` 的任何 project。P1 文
档类 BET 的 worktree 路径映射到"项目"是空白。T7-02 这单的解法:
- 改用 `project-code-change` workflow (ledger 注释里也提示)
- affected graph receipt 的 `changed_projects=workspace-root`

下一轮 P1 文档类 BET: 在 `write_surfaces` 直接声明
`surface: workspace-root` 而不是 path。

### 3. CI 闸门的 affected-hash 收口是救生圈

`bin/gac/affected-graph.py --changed-projects workspace-root` 这一
行命令让 `docs/journey-specs/health-medical-workflow.yaml` (不属于任
何 project 的路径) 拿到了一致的 receipt, claim 通过。这是 6-axis
之外最有复用价值的 1 行 CLI。

### 4. dim 4 体验 proxy 必须 daemon-stable

初始 `dim 4 = compass.composite` 形式: daemon 瞬断 → 矩阵闪退
GREY, 误报回退。改成 `max(compass, v3_5axis)` 后 9-dim 永远 ≥ GREEN=8,
且 v3 5-axis 来自 on-disk evidence, 不依赖任何 daemon。教训: 一个
dim 的 proxy 必须能在它最依赖的信号源失活时, 自动降级到 on-disk
telemetry, 否则高敏感 dim 会随 daemon 健康度波动。

### 5. doc-ssot 闸门有 5 层债, batch fix 1 commit 通关

冻结的 5 类债:
1. 12 个 committed unmerged conflict markers (<<<<<<< / |||||||)
2. 601 个 frontmatter 用未在 allowed set 的 status 值
3. 3 个文件缺 closing `---`
4. 2 个 retro 用未在 allowed set 的 lifecycle 值
5. bin-quota-diff +1=-1 (新增脚本要删一个)

单次批量脚本 `bin/gac/fix-frontmatter.py --batch <root>` 一次性
把全部 5 类债修了。把 2 个新脚本的逻辑合并进 existing
`fix-frontmatter.py` (而不是新加 2 个), 通过 +1=-1 平衡。

教训: 大块 pre-existing 仓库债要 batch 修, 不要打散到多个 commit
(每个 commit 单独被 preflight 拦一次, N 倍摩擦)。

### 6. v3 读数差的根本是 sign-posting 缺失

5-axis=98 与 6-axis=88 的 10 分差, 系统不知道"为什么差" — 因为没
有 in-axis metadata 标记"这一分差是 A2=0 拉下来的, 而不是 5 个
axis 各掉 2 分"。下一轮:
- 在 6-axis JSON 输出加 `axes.A2.weight_contribution=0` (显示
  weighted contribution = 0 因为 score=0)
- 在 strategy-check dim 5 显示 `v3_5axis_6axis_delta_signpost: A2=0
  是唯一缺口`

让 gap 是 self-explanatory 的, 不需要读者去反推。

## 副产物 (按影响排序)

1. PR #2320: feat(north_star v3 6-axis) merged → 多 weekly report 现
   在能 surface 4 套 composite
2. PR #2326: dim 4 daemon-stable + doc-ssot batch fix → 9-dim 矩阵
   GREEN=9, doc-ssot 0 err
3. PR #2331: scene-card P1-only mode → P1 文档类 BET 不再被 approval/
   trial P2 闸门卡死

## 下一步候选

| 方向 | 价值 | 估时 |
|---|---|---|
| PR #2326 拆小 (607 文件) | 维护性 +1 | 30min |
| Axis F (协作健康, a2a-messages) | 6-axis 升级到 7-axis | 4h |
| 给 omlxc 加真实推理路径, 让 A2 hit_rate > 0 | 6-axis 拉到 95+ | 1d |
| P1 health domain runtime 化 (BET-Y1Q3-T7-02 后续) | 价值兑现 | 1w |
| 把 4 套 composite 写入 cockpit decide 入口 | 入口可读 | 1d |
