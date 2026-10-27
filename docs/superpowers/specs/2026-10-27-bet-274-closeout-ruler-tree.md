---
schema_version: specification/v1
spec_version: 1.0.0
title: closeout 的链判据读的是「供给 kernel 的那棵树」—— 尺根必须写明并与执行检出对齐
bet_id: BET-Y2Q4-T10-274
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-10-27
---

# BET-Y2Q4-T10-274 — closeout 链判据的尺根与执行检出对齐

> 范围：协议层固化。本轮只把一次真实收口里量出来的装置塌缩写成可复用的判据，
> 不改 `bin/agent-workflow.py` 的绑定语义（那是独立工程腿，见 §5）。

## 1. 触发事实（BET-Y2Q4-T10-272 收口腿，2026-10-27）

T10-272 的工程腿与文档腿合并为 PR #4919（squash 到 `14ee5723e`）后，retro 与 receipt
**都已在 `origin/main` 上**，台账 `status: done` / `overall_state: delivery_accepted`
由校验器直接复算为 `errors=[]`，但收口步连续 4 次被拒：

```
closeout blocked by vision→retro chain (missing_retro)
```

链是实质闭合的，看不见它的是判据读的树。

## 2. 根因（逐条带测量出处）

### 2.1 同一个名字在一份脚本里被绑了两次

`bin/agent-workflow.py`（base `14ee5723e` 实测行号）：

| 行 | 内容 | 求值时刻 | WORKSPACE 含义 |
|---|---|---|---|
| `:278` | `WORKSPACE = Path(__file__).resolve().parents[1]` | import | **执行检出根** |
| `:282-287` | `from omo.workflow import (WORKSPACE, …)` | import（紧随其后） | **供给 kernel 的那棵树根** |

第二次绑定覆盖第一次。kernel 侧的值不是 profile 根解析器，而是同一形状的 `__file__` 反推：
`projects/omo/src/omo/workflow/core.py:43` `WORKSPACE = Path(__file__).resolve().parents[5]`。
所以它的含义由 **谁提供了 `omo` 包**决定，与命令行在哪个检出里执行无关。

### 2.2 两读数的分叉由探针复现（不是记忆）

在同一棵 worktree 里复刻 `:278` 与 `:282-287`，只改 kernel 供给根：

| kernel 供给根 | `:278` 读数 | `:282` 读数 | 是否分叉 |
|---|---|---|---|
| `ws-t274-closeout-ruler/projects/omo/src`（本检出） | `…/ws-t274-closeout-ruler` | `…/ws-t274-closeout-ruler` | 一致 |
| `~/Workspace/projects/omo/src`（canonical，异树） | `…/ws-t274-closeout-ruler` | `/Users/xiamingxing/Workspace` | **分叉** |

⇒ 常态下一致（子模块检出在位、kernel 从自己这棵树加载）。分叉发生在 **kernel 从别处供给**时：
worktree 的 `projects/omo` 未初始化而显式给 `PYTHONPATH`、venv 里的 omo、以及 ADR-0456 B4b
要把运行时代码搬去的 `~/.local/opt/omostation` 安装位。T10-272 正是第一种：claim 时跳过了
子模块初始化，本轮用 `PYTHONPATH=~/Workspace/projects/omo/src` 补上逐字节相同的 kernel
（gitlink 未变，已对拍），尺就跟着换到了 canonical 树。

### 2.3 换树之后，读的是「没有交付物的那棵树」

被覆盖的 WORKSPACE 喂给链判据：`bin/agent-workflow.py:1138`
`verdict = chain_bind.evaluate_closeout(payload, WORKSPACE, status=status)`；
链侧的 retro 存在性判据是 `bin/plan/chain_bind.py` 的
`retro_path_for(workspace, bet_id).is_file()`。T10-272 实测分叉面：

| 树 | `origin/main` 位置 | `.omo/_knowledge/retros/BET-Y2Q4-T10-272.md` |
|---|---|---|
| canonical 主检出 | `dc67a0f5f`（落后 2） | **ABSENT** |
| 交付所在 worktree | `14ee5723e`（= origin/main） | PRESENT |

同类分叉此前已在本仓咬过两次（AGENTS.md §7「门禁的尺本身会随 base 变」条：
`check-work-landed.py:31` 各 worktree 执行自己检出的那份脚本）。差别在于本轮多一层：
尺不是随 base 变旧，是随 **kernel 加载来源**换了树。

### 2.4 同一条链上的另外两处装置塌缩（都非数据缺陷）

| 现象 | 判据 | 真因 | 正解 |
|---|---|---|---|
| 校验器直读报 7× `COMPLETION_FILE_REF_MISSING` + `OVERALL_STATE_MISMATCH: derived='blocked'` | `validate_completion_evidence` 把 `evidence.ref` 按**磁盘树**解析 | 在落后 2 的 canonical 主检出里跑，receipt/retro 按构造不存在 | 在含交付物的检出里复算 ⇒ `derived_state=delivery_accepted errors=[]` |
| 复算首轮报 `chain_ok=False reasons=['missing_bet_binding']` | `chain_bind.iter_run_records`：`if not runs_dir.is_dir(): return []`（缺席 ≡ 空） | `/tmp` 对照树没有交付锚桥，350 条 run 记录读成 0 条 | 调 sanctioned 的 `ensure_delivery_anchor()`（`delivery_anchor.py:87`）建桥后 358 条可见 |

⇒ 「缺席折叠成空」在这两处同形：目录缺席与目录为空在判据里读不出区别（AGENTS.md §7
「目录缺席与目录为空在 glob 兜底下同形」条的链判据面）。

### 2.5 `bet-ledger.py complete` 在 done 之后是 no-op，不能当校验器用

`bin/plan/bet-ledger.py:3259 cmd_complete` 在 `:3275-3277` 早退：

```python
if b.get("status") == "done":
    print(f"[complete] {b['id']} 已是 done, 无需操作")
    return 0
```

台账已 `done` 时 rc=0 只证明「早退分支命中」，**不证明** evidence 面完好。若把它当完成证据，
就把 D0 入库检查、`validate_completion_evidence`、`chain_bind.evaluate_complete` 全当成跑过了。
判据：状态已是 `done` 时须直接调校验函数取证，不得读 `complete` 的 rc。

## 3. 要固化的判据（本轮交付内容）

1. **写明尺读哪棵树**：任何 `closeout`/链判据的读数，必须标注「产出该读数的那份 kernel
   由哪棵树供给」。凡「本地 FAIL / 别处 PASS」的链分歧，第一步是问
   `omo.workflow.core.__file__` 落在哪，而不是先改台账或补文件。
2. **取证要在含交付物的树上复算**：判 `missing_retro` / `COMPLETION_FILE_REF_MISSING`
   之前，先在**含本次 receipt 与 retro 的检出**里直接调 `chain_bind.evaluate_closeout`
   与 `validate_completion_evidence` 复算；两份读数不一致 ⇒ 是尺换了树，不是数据坏。
   「目录缺席 ≡ 空」这一折叠须由交付锚桥（`ensure_delivery_anchor()`）消除，
   不要手工 `ln -s` 造桥。
3. **实质闭合时走原生记录面，不伪造 closeout**：链在事实上闭合、装置看不见时，
   用 `bin/agent-workflow.py close <run> --status ok --evidence "<含装置原因的证据>"`
   ——把「为什么不是 closeout」写进 evidence 本身，而不是给 `evaluate_closeout`
   塞豁免、加 flag，或改窄判据。
4. **陈旧树不用破坏性同步治**：`bin/gac/sync-main.sh` 默认执行 `git reset --hard origin/main`，
   在主区被并发 agent/cron 持有未提交工作时不是「快进」而是销毁。判据：需要新鲜基线就
   **另起 worktree 到 `origin/main`**，不动共享主区；`--allow-dirty`（内部 stash）同样不擅自用。

## 4. 反证（判据承重）

| 若把 §3 的哪一条反过来做 | 会得到的错误结论 | 本轮实测证据 |
|---|---|---|
| 不在含交付物的树上复算，直接信 canonical 读数 | 「receipt/retro 没入库、evidence 写坏了」 | 7× `COMPLETION_FILE_REF_MISSING` 全部指向**已跟踪且已在 `origin/main`** 的两个 blob |
| 信 `complete` 的 rc=0 当完成证据 | 「台账校验过了，链也该算闭合」 | `:3275` 早退，校验函数一次没跑 |
| 不给 kernel 换根、直接 `PYTHONPATH` 兜过 `ModuleNotFoundError` | 「omo 缺失是回归」 | 两棵树 `omo` 逐字节相同（gitlink 未变），缺的是子模块初始化 |
| 用 `sync-main.sh` 快进主区 | 「基线新了，绿灯是真的」 | 主区当时脏于并发 agent 的未提交工作，默认 `reset --hard` 会丢它们 |

## 5. 本轮不做的事

- 不改 `bin/agent-workflow.py:278/:282-287` 的双重绑定，也不给 `evaluate_closeout` 加
  `--workspace`/env 开关：绑定语义变更会同时影响 `REGISTRY_PATH`、`RUNS_DIR`、`cwd=` 传参
  （`:407`）等 8 个消费点（`:364/:383/:511/:818` 等默认参数），属独立工程腿且需测试面。
- 不宣布 ADR-0456 B1/B3/B4/B4b/B5 或整个 plan 完成；B4b 批次 2+ 与 E4/E5 仍待署名授权。
- 不动运行面：不写 `~/Library/LaunchAgents`、不 `bootout`/`bootstrap`/`kickstart`、
  不改 `services.yaml`、不翻权威 ledger。
- 不登记「AGENTS.md 幽灵路径 `bin/gac/doc-governance-check.py`」——该候选项已被否证
  （`git grep -c` = 0，AGENTS.md 引的是裸文件名 `doc-governance-check.py`，真实脚本在
  `bin/ssot/`）。把自己的笔误登记成仓库缺陷即伪造溯源。
- 不 `--no-verify`、不 admin merge、不 rebase/merge/pull 吸收上游、不 `prune-locks`。
