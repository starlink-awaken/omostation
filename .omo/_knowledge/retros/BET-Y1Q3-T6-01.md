---
title: BET-Y1Q3-T6-01 retro — gbrain+kairon 归并 knowledge (L3 停审)
type: retro
owner: engineering-agent
created: 2026-08-16
bet: BET-Y1Q3-T6-01
related:
  - docs/plans/2026-08-16-t6-01-knowledge-merge-spec.md
  - docs/plans/2026-08-16-t6-01-dedup-ledger.md
lifecycle: history
last_updated: 2026-08-18
---

# BET-Y1Q3-T6-01 复盘（五问）— 停审版

## Q1 做了什么（事实）

**治理层归一 + 异构栈目录内包**：`projects/knowledge/{gbrain,kairon}` 单一 L2 项目，
`.gitmodules` 双条目删除，gitlink 移除。

- gbrain：1770/1770 文件 git archive 搬运，**git 索引完整**（经历 gitignore 吞文件事故后补齐）
- kairon：1328 tracked（1454 tree − 129 运行时目录按根仓 ignore 语义正确排除）
- 全仓引用重写：~140 活文件 sed + registry/layer-contract/Makefile/BOS（yaml 64 处 +
  agora services.py 45 处双声明源）+ CI workflows path filter
- 子仓适配：cockpit/agora path 依赖深度（两轮修正 ../../knowledge → ../knowledge）、
  agora BOS c2g 改道 omo._vendored、kairon-pipeline bus-foundation 深度 +1
- 去重清单终版：治理面 ~9,433 行（kairon .omo 残留 9,410 为主）

## Q2 证据

| 验证 | 结果 |
|------|------|
| gbrain bun test | 内包 7377P/388F vs 原仓基线 7388P/389F — **fail 持平零新增** |
| kairon 16 包 pytest | **FAIL=0**（修复 kos import os 10F→0、mos alias 1E→0、iris 断言、minerva 3F→0）|
| evidence-smoke | **100/100 鸿沟 0**（修复前 85.1/48 鸿沟）|
| gac-local-gate | 44 checks PASS |
| doctor | ok=True（path 深度修正后）|
| 台账 lint | 112 bet 零错 |
| CI (#1600) | Actions 平台事件延迟（当日 3 次），最后一 head 待消化 |

## Q3 决策点

1. **形态：目录内包而非代码互融** — 异构栈（bun/ts vs python/uv）物理不可互融，
   MOS→gbrain 本就是 subprocess 边界。重写业务逻辑是 non_goal。
2. **kairon .omo/ 删除（-9,410 行）** — 独立仓时代治理残留，归并后治理面收敛根仓；
   minerva 路径测试暴露 walk-up 就近命中问题，实证此残留有害。
3. **子仓走 main 直推 + PR #27（squash）** — pointer-drift gate 只认 origin/main，
   side-branch 指针被拦是设计盲区；用子仓 main 合流让指针天然 aligned。
4. **断测顺手清偿 8 项** — kos import os（原仓同挂实证）/ mos alias / iris 断言集 /
   minerva 降级断言 + 路径语义化 / agora a2a importorskip / c2g 死路径 / conflict-marker
   Setext 误报 / capability 产物 regenerate。

## Q4 教训（新坑入册）

1. **gitignore 泛目录规则是内包黑洞**：`kos/`、`skills/` 任意深度匹配把 342 个源码文件
   吞出索引，tree-vs-disk 磁盘对比全绿掩盖 git 索引缺失——**大规模内包必须 git ls-files vs
   git ls-tree 对比，磁盘对比不算数**。CI capability drift 是唯一暴露口。
2. **`git add -A` 会吸收 submodule checkout 旧 HEAD**：checkout 未对齐时指针 staged 错值，
   submodule-guard 拦截正确——被拦时先查三方状态（index/staged/checkout）别急着绕。
3. **GitHub Actions 事件延迟当日 3 次**：push 后 runs=0 持续 10-25 分钟，空 commit
   retrigger 有效但需 debounce 窗口意识；本地验证链完备时不必空等平台。
4. **sed 批量重写会误伤自指文本**：spec 文档、pre-commit hook 的 PASW_ISOLATED 路径、
   .gitmodules 条目全被改——批量 sed 后必须 review 自指文件。

## Q5 停审理由（human_gate 项）

**L3 不可逆归并，红线要求人类批准**：

1. 单一 knowledge 项目、双子模块条目移除 — done_when ✅（本地证据齐，CI 待平台恢复）
2. 去重清单 + src 下降量 — ✅ 治理面 ~9,433 行（dedup-ledger 逐项可复核）
3. **test_loc ≥ 350,854 — ⏳ 需 merge 后主仓 surface 实测**（worktree 数字失真不可用）
4. 回滚 tag — 本地已打 `pre-knowledge-merge-20260816`（远端推送被 lane 白名单拦，
   需人工 `git push origin pre-knowledge-merge-20260816`）
5. 全量测试 — gbrain/kairon 双侧实证通过；`tests/integration/run-all.sh` 待 merge 后主仓跑

**待用户裁决**：① 批准归并（merge #1600 后跑 PR-4 收口三件：surface 对比 + 集成套件 +
tag 远端推送）② 或回滚 tag 重来。
