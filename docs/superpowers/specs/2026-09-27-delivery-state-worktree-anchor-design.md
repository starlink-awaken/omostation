---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 交付运行态 worktree 归集 — runs/locks/events 锚定 canonical (symlink 桥)
bet_id: BET-Y2Q4-T10-209
---

# BET-Y2Q4-T10-209 — 交付运行态 worktree 归集 (delivery-state canonical anchor)

## Context

**事故实证 (#4435, 2026-09-27)**：在 worktree 内 `agent-workflow start` 写出的 run 记录
`.omo/_delivery/agent-workflows/runs/20260927T074411Z-project-doc-change-8713c068.yaml`
落在该 worktree 检出内；`.gitignore:12` 忽略 `.omo/_delivery/*`，`git worktree remove --force`
（`bin/gac/gac-worktree.sh:719` release / `:810` merge / `:1190` TTL 清理）一并抹除。
run 消失 ⇒ closeout 永久不可能、审计链断裂；拒绝伪造补录。

**根因链**：
- `projects/omo/src/omo/workflow/core.py:15` `WORKSPACE = Path(__file__).resolve().parents[5]`
  按 `__file__` 推导仓库根 ⇒ 在哪个 worktree 里跑就是哪个 worktree。
- 路径链 `core.py:428-429 run_state_dir → :421-425 _runner_path → :405-418 registry_workspace_root`
  是所有 run/lock/ledger 写读的单一咽喉点。
- `bin/lib/repo_root.py:3-6` docstring 点名的正是这个故障类；但 `state_root()` 在未声明
  env 时 `== code_root() == worktree`（`tests/unit/test_repo_root_profile.py:51-56` 钉死），
  **单纯改走 `state_root()` 修不了本 bug**。
- 现状分裂：canonical runs 目录 71 份 vs 散落在 7 个 worktree 的 run 目录（canonical 侧审计
  `closeout-audit.py:35`、`compass_radar.py:1035/1238`（"MAIN checkout runs dir"）、
  `gac-local-gate.py:817` 等 ~15 个工具全部按自己检出的字典路径读 ⇒ worktree run 对它们不可见）。

## Goal

交付运行态（`runs/`、`locks/`、`events.jsonl`，连带 `affected/`、`receipts/`）是**机器级、跨检出、
生命周期长于单个检出**的状态：物理锚定 canonical，linked worktree 以**自愈 symlink 桥**呈现，
读侧零改动。

## Design (A′ — canonical anchor + self-healing symlink bridge)

在写侧咽喉点 `core.py::_runner_path`（相对分支、仅生产布局）前挂 `ensure_delivery_anchor(ws)`：

1. **触发条件（全部满足才动作，否则 byte-identical no-op）**：
   - `ws/.git` 是文件且 `gitdir:` 解析到 `<canonical>/.git/worktrees/` 之下
     （比 `repo_root.is_worktree()` 更严——外来 clone 不归集）；
   - 检出内路径落在生产布局 `ws/.omo/_delivery/agent-workflows`（自定义相对/绝对
     runner 配置如 `test_workflow_locks.py:42`、`test_agent_workflow.py:261-280` 永不触发
     ⇒ hermetic 测试面不受影响）；
   - 能定位锚点：`OMOSTATION_STATE_ROOT`（ADR-0456 profile 优先）→ `canonical_root()`
     （`OMOSTATION_ROOT`+marker / `~/Workspace`+marker）→ 都不可得则 no-op（CI 安全）。
2. **自愈**：`<ws>/.omo/_delivery/agent-workflows` 是悬空 symlink → 重建；是真实目录 →
   **merge 迁移**（子项拷入 canonical，同名冲突 canonical 胜 + conflict log，
   追加 `events.jsonl`，verify 后 `rmtree`），再 `symlink_to(canonical)`。
3. **读写一致靠构造而非协调**：内核写路径与 `chain_bind.iter_run_records(ws)` 读路径是同一条
   字典路径，经链接解析到同一物理目录；首个触发点总在读之前（`closeout` 的 `read_run`
   `agent-workflow.py:1134`、`status` 的 `diagnostics.py:267` 均为内核操作）。
4. **锁与事件一并归集**：symlink 挂在 `agent-workflows/` 一级，`runs/`+`locks/`+`events.jsonl`
   整体重定向；全部锁包含性检查是 resolve-both-sides（`diagnostics.py:87/93`、
   `lifecycle.py:357/977/999`、`claims_authority.py:711`），相对锁引用经链接跨检出解析一致
   ⇒ 不同 worktree 的两个 agent 对同一 scope 终于互斥（现状是各持一份锁，形同虚设）。
   `display_path` 保持字典（`core.py:398-402`）⇒ 记录不泄漏绝对 canonical 路径。
5. **ADR-0456 契约**：不改 `code_root()/state_root()/canonical_root()` 解析语义
   （`test_repo_root_profile.py:51-56/:131-144` 全部保持）。新增 placement 判据写入
   `repo_root.py` docstring 第四条 + ADR-0456 addendum：**写机器级、长于单检出的交付运行态
   → 已声明 env 用之，否则 `canonical_root()`；linked worktree 内以 symlink 呈现**。

### 反对方案（已否决）

- **直接重锚 ~15 个读侧工具到 canonical**：同物理布局，但必须与内核同一大波次原子落地，
  否则 rollout 中途每个 in-session gate 读到空 worktree 本地目录。A′ 零读侧改动达成同样效果。
- **改走 `state_root()`**：未声明 env 时 == worktree，修不了；改 fallback 违反测试钉。
- **run 入仓（.gitignore re-include，rule-drafts 先例）**：`worktree remove --force` 连已提交外
  的都删 ⇒ 只留 committed = 每个 PR 带运行时 churn；rule-drafts 先例管的是"待 promote 的
  人工输入"，非机器运行态。
- **仅 archive-on-release（shell 兜底）**：修事故不修病因——worktree 存续期内对 canonical 审计
  依旧不可见、锁/事件仍分裂、崩溃/bypass 路径漏网。降级为 belt-and-suspenders。

### Belt-and-suspenders（保留）

`gac-worktree.sh` release(`:719`)/merge(`:810`)/TTL(`:1190`) 在 `git worktree remove --force`
前：若 `$wt/.omo/_delivery/agent-workflows` 是**真实目录**（`[ -e ] && [ ! -L ]`），merge-rescue
进 canonical（`cp -Rn` + 追加 `events.jsonl`，canonical 胜，幂等）并打印提示。
兜底对象是现存 7 个 legacy worktree——它们可能再也不跑内核代码就被 release。

## Non-goals

- 不改 `state_root()/canonical_root()/code_root()` 解析语义（B4b 边界）。
- 不改任何 run 读侧工具、不改 `chain_bind.py`（其 isolation 注释管辖 tracked SSOT 读，
  对 untracked 机器态的关切因单一物理存储而消解，tracked 部分逐字节不动）。
- 不碰 `branch-claims`（invocation-cwd 锚）、`.omo/_knowledge/workflow-mesh/`、
  `event_ledger_path()` 三个同类残留——各自需独立契约决策，另立 bet。
- 不把 run/lock/events 入仓。
- 不动 `affected_graph_receipt.py:93` 的防 symlink 语义（其输入 `.affected-graph.json`
  在 workspace root、不在 delivery 目录下）；**不把 receipts 迁到 agent-workflows/ 之下**。

## Edit surface

| # | 文件 | 改动 | lane |
|---|------|------|------|
| 1 | `projects/omo/src/omo/workflow/delivery_anchor.py`（新） | `locate_anchor` / `is_worktree_of` / `ensure_delivery_anchor`（幂等、迁移、自愈）~90 行 | code |
| 2 | `projects/omo/src/omo/workflow/core.py` | `_runner_path()` 相对分支挂 ensure ~5 行 | code |
| 3 | `bin/lib/repo_root.py` | 仅 docstring 第四条判据（无代码改动，YAGNI） | code |
| 4 | `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` | addendum：delivery-state 类、symlink 桥、禁 `rm -rf <link>/` 尾斜杠 | docs |
| 5 | `bin/gac/gac-worktree.sh` | `rescue_delivery_state()` + 三处调用 ~15 行 | governance_code |

明确不碰：`registry_workspace_root()`（Mesh/closeout 侧效应归 workspace，被
`test_close_run_routes_mesh_event_to_registry_workspace` 钉住）、`state_root()`、
`_root.yaml` runner 块（绝对 `workspace_root` 会机器特定化）、`chain_bind.py`、全部 ~15 读侧。

## Test strategy

1. `projects/omo/tests/test_delivery_anchor.py`（新，fake canonical+marker+fake worktree+fake
   HOME，绝不触真 `~/Workspace`）：placement（字典路径不变、resolve 到 canonical、symlink
   目标精确）/ 迁移（内容入 canonical、冲突 canonical 胜+log、二次调用幂等）/ no-op 三态
   （非 worktree、外来 worktree、无 canonical ⇒ 字节等价）/ `OMOSTATION_STATE_ROOT` 优先 /
   自定义 runner 配置不触发（hermeticity）。
2. `tests/unit/test_delivery_anchor_contract.py`（新）：跨边界契约（omo anchor ==
   `repo_root.canonical_root()`，env 名 source-string pin）/ 读写一致（worktree 内内核写
   可被 `chain_bind.iter_run_records` 找到）/ **#4435 集成回归**：真 git init+worktree add
   → ensure → 文件在 canonical → `worktree remove --force` → 文件仍在（skip if no git）。
3. 扩展：`test_workflow_workspace_isolation.py`（生产布局 in-worktree 有锚 case）、
   `tests/test_agent_workflow.py`（worktree 内 status→closeout CLI 级、钉 ensure-before-read
   顺序）、`gac-worktree.sh` rescue 的 `bash -n` + 幂等 shell dry test。
4. 既有面审计：`grep start_run(/load_registry()` in `projects/omo/tests` + `tests/`——
   任何在 worktree 里用生产布局跑 start_run 的既有测试需加 `workspace_root` override。

## Verification

- `cd projects/omo && uv run pytest tests/ -q`
- `uv run pytest tests/unit tests/test_agent_workflow.py -q`（+ `tests/test_chain_bind.py`）
- `bash -n bin/gac/gac-worktree.sh`
- `make gac-local-gate`

## Risks / rollback

- 隐藏 resolve()==workspace 断言：包含性检查已成对 resolve（见 §Design 4），全量 omo/root/cockpit 套件兜底。
- 测试 hermeticity：ensure 仅在 worktree-of-canonical + 生产布局触发；新测试全走 fake HOME/OMOSTATION_ROOT。
- 迁移撞上跨检出活动 run：copy→verify→rmtree，冲突 canonical 胜+log；遗留 straddling run 可能需一次
  `force` 重锁（ADR addendum 记录）。
- 后人 `rm -rf <link>/`：ADR addendum 明令禁止（当前无此调用，已核）。
- 回滚：revert 两个 commit + 各 `$HOME/ws-*` 内 `unlink agent-workflows`；残留 symlink 无害
  （字典读仍解析到 canonical）；无读侧改动 ⇒ 无读路径需回滚。
