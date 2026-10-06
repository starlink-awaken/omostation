---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-10-06
type: retro
bet_id: BET-Y2Q4-T3-04
title: BET-Y2Q4-T3-04 复盘（closeout）
created: 2026-10-06
---


# BET-Y2Q4-T3-04 复盘（closeout）

> 2026-10-06 closeout 补全。本文件是 T3-04 的 per-BET 记录，承载 D3 纪律偏差存档
> 与 gitlink-hazard 新教训。

## Q1 实际耗时 vs appetite？

- appetite = 2 days；实际跨 4 轮（实施 → adversarial review 修复 → 递归 CTE →
  交付/合并），单轮实耗约 <1 天/轮，总实耗 ≤ appetite，未触发 circuit breaker。

## Q2 done_when 是否全部通过？

- item 1: `SELECT created_at FROM documents` 不被拒；INSERT/UPDATE/DELETE/DDL 由
  default-deny authorizer 阻断（writable-handle 测试证明，非 mode=ro）。✅
- item 2: 六条中文意图对完整问句分类正确；ASCII 形式与 eval_harness 零漂移；
  `test_routing_matrix.py` 转为 failing-then-passing 守卫并落入版本库（D0）。✅
- item 3: 默认（无 live env）`data_mode=fixture` + notice；live 仅 flag+available+
  no-last_error；`memory-os.yaml` 声明一致；`test_data_mode.py` 覆盖 5 场景。✅
- item 4: `documents.body` 原文 + `documents_fts.body=fts_text(body)`；
  jieba 缺失可观测；`test_fts_body_tokenization.py` 钉住。✅
- 干净环境全量：MOS 93 passed；KOS 574 passed / 3 预存无关失败。✅

## Q3 过程中发现的与 plan 不符的事实（打假）？

1. **`engine.py:714` 的「body 未分词」前提在 915fc76 上不成立**：`_process_file:818`
   已在上游分词；真正缺陷是同一份分词文本同时写进 `documents.body`。修复改为
   `documents.body` 保留原文 + `documents_fts` 显式 `fts_text(body)`。
2. **default-deny 起初把 `SQLITE_RECURSIVE(33)` 也拒掉**，human 判定过度收紧
   （递归 CTE 是知识库图查询的合法读），已加回（Task A）。
3. **D3 越权偏差（human-approved）**：`bin/ssot/test-mcp-kos.py` 的 M1 修复不在
   本 BET write_surfaces 内（claim 拒：`WORK_PACKET_SCOPE_MISMATCH`），但 gate 会红、
   review 判 blocker；处置 = 本复盘记录偏差 + 另开 `BET-Y2Q4-T10-231` 对账，正式收口
   见 T10-231 closeout。未使用 gate waiver。
4. **GITLINK HAZARD（新仓库级教训）**：GitHub squash/rebase 会重写子模块 commit
   SHA；父仓 gitlink 若钉住合并前的 SHA 即悬空。`bin/ssot/submodule-reachability-gate.py`
   只认 `refs/remotes/origin/main` 祖先。实测：kairon #97 squash 后
   `merge-base --is-ancestor 86c485c9 origin/main` exit=1；修复 = 提交 re-point 根
   gitlink 到 `35f2ab77`（`bf2fbdac1`）后 root CI 全绿。预留：以后子模块 PR 只要
   合并方法会重写 SHA，就必须在父 PR 里重新指向新的子模块 main tip。

## Q4 净增减？

- kairon 子模块：5 个源文件修改 + 3 个新测试文件（`test_routing_matrix.py` 自
  untracked 落库，1008 行）+ ~1288 行净增（含测试矩阵，属保护量，非削减）。
- 父仓：`bin/gac/mcp-server-kos.py`（authorizer 重写，净减黑名单）、
  `bin/ssot/test-mcp-kos.py`（+断言与子测试）、`memory-os.yaml`（+note）、台账
  （+2 bet 条目 + completion_evidence）、2 个 spec、1 个 retro、1 个 closeout receipt。
- 门禁：lint OK（527 bets）；`gac-local-gate` PASS。测试行增量为主（保护量上升，
  非表面积扩张）。

## Q5 下一个认领本 track 的 agent 需要知道什么？

- `bin/ssot/test-mcp-kos.py` 的改动已由 `BET-Y2Q4-T10-231` 认领并 closeout
  （run `20261006T040738Z-bet-execution-ab85640c`，见
  `.omo/_knowledge/retros/BET-Y2Q4-T10-231.md`）；本 BET 的 D3 偏差已正式收口。
- gate 的 test-mcp-kos 已拆分：default-deny authorizer 子测试不依赖 `data/kos/` 恒跑；
  DB 协议检查无 runtime DB 时 exit 78 软跳过。
- **子模块合并 → 父 gitlink re-point 流程**：合并前先确认子模块 main 的最终 SHA；
  合并后必须 `merge-base --is-ancestor <old-pin> origin/main` 验真；exit=1 就 re-point
  父 gitlink 到一个新 commit 再合并父 PR（见 Q3-4）。
- kairon 子模块在浅/单分支 refspec 下 `@{u}` 不可解析会卡 pre-push
  submodule-reachability；交付前把 `remote.origin.fetch` 恢复为 glob refspec。