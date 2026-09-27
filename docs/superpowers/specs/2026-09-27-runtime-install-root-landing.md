---
schema_version: specification/v1
spec_version: 1.0.1
title: ADR-0456 B4a — 运行时代码安装位落位（零运行时效应）
bet_id: BET-Y2Q4-T10-207
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-27
---

# ADR-0456 B4a — 运行时代码安装位落位（零运行时效应）

> 上游契约：`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`（code_root / state_root 双根）。
> 分期来源：plan `nimble-bay-asp.md` B4，本轮由 principal 拆为 B4a（本文件）与 B4b（状态搬迁 + 切换）。

## 1. 问题与本轮边界

ADR-0456 B1 把"根"参数化了，但没有第二个根可指：开发、运行、写机器级配置三件事仍然只有
`~/Workspace` 一个落点。B4 的目标是造出运行时安装位。plan 原文把 B4 当一步做，实测把它拆成两半：

| | 效应面 | 本 bet |
|---|---|---|
| **B4a 落位** | 新建一个目录 + 只增不改的解析 API | ✅ |
| **B4b 切换** | 43 个 plist、~40 条 cron、ledger 物理搬迁 | ❌ 另立，逐批确认 |

**B4a 的判据是"零运行时效应"**：不启停任何服务、不写 `~/Library/LaunchAgents/**`、不改 crontab、
不搬 ledger、**并且不改 `canonical_root()` 的解析结果**。最后一条是关键：那 43 个 plist 指向
Workspace 且正在跑，此刻把 canonical 解析器指向新位置，等于让所有"写机器级配置"的工具在一次
commit 之后静默改道 —— 那是 B4b 的动作，不是 B4a 的。

所以 B4a 交付的是**定位器（locator）**，不是**开关（switch）**。

## 2. 实测：三条前提被证伪，按实测改

写 spec 前逐条量过，plan 里三处假设不成立，全部按现实修正而非按 plan 执行：

1. **"detached 在 release tag" 无 tag 可用。** 本仓 481 个 tag，`v*` 系列最后一个是
   `v2026-06-15-r1`（三个月前），其余是 `bet/BET-*`、`zombie-archive/*` 一次性 tag。
   不存在干净的 release-tag 序列 → 改为 **detached 在 `origin/main` 的具体 SHA** 并把 SHA 记进
   receipt。发明一个 tag 来凑 plan 的字面要求，是给未来的更新路径埋第二个死约定。
2. **"`git clone --local`（hardlink 对象，成本≈0）不成立。** 主仓是 **shallow** 仓
   （`git -C ~/Workspace rev-parse --is-shallow-repository` → `true`，`.git/shallow` 41 B）。
   实测 git 自己报 `warning: source repository is shallow, ignoring --local`，于是对象是**复制**
   而非硬链接：安装位 `.git` = **183 MB**（跟踪文件 9,885 个 / 70.9 MiB）。
   plan 的磁盘前置检查据此从"可忽略"改为"约 250 MB，仍可接受"。主仓 shallow 本身是**上报项**，
   不在本 bet 处置（`git fetch --unshallow` 是对共享仓的大规模网络写操作）。
3. **"加入 `worktree-hygiene-audit.py` / `gac-branch-prune.sh` 的排除清单" 是空操作。**
   读代码即知二者扫不到这个路径：`worktree-hygiene-audit.py:160-165 _candidate_dirs()` 只 glob
   `$HOME/ws-*` 与 `$HOME/workspace-*`（外加 `git worktree list` 的登记路径），
   `gac-branch-prune.sh` 只做 `git fetch --prune` + 删除已合并的 `work/*` 分支，不处理任何目录。
   加排除清单 = 给一条不存在的边加守卫。**替换做法**：写成守卫测试，钉住"安装位对这两个清扫
   例程不可见"这个事实本身 —— 一旦将来有人扩大清扫候选面（例如 glob 改成 `$HOME/*`），测试变红。
   排除清单是"事后打补丁"，守卫测试是"把边界钉住"，后者才是本轮要的。

## 3. 决策

### 3.1 路径：`~/.local/opt/omostation`（principal 2026-09-27 选定）

plan 原写 `~/Runtime/omostation`，实测与一个活的 Tier-1 数据域同 inode（macOS 大小写不敏感卷：
`~/Runtime` 与 `~/runtime` 同一 inode 146632641，那里是 `projects/runtime` 的
`matrix.yaml` / `scheduler_state.json` 家，其自带 `CLAUDE.md` 明写"写需确认"，且
`projects/runtime/scripts/service-ctl.sh:10` 把 `$HOME/runtime` 当 `RUNTIME_HOME` 缺省值）。
这正是 plan 决策 1 理由 3 自己警告、结论却没吸收的碰撞。`~/.local/opt/` 此前不存在（本轮创建），
且不在任何清扫例程的候选面内。

### 3.2 独立 clone，不是 worktree（硬约束，维持）

worktree 会登记进共享 `.git`，被 claim / release / `gac-worktree.sh` 与每日 04:00 的
`make worktree-hygiene` 波及。实测：新安装位的 `git rev-parse --git-dir` 返回 `.git`（自有 git 目录），
`git worktree list`（主仓侧）不含该路径。

### 3.3 API：只增不改

`bin/lib/repo_root.py` 新增：

- `INSTALL_ROOT_ENV = "OMOSTATION_INSTALL_ROOT"`、`install_root() -> Path | None`
  —— env 优先，缺省 `~/.local/opt/omostation`，**MARKER 不在则返回 None，绝不抛异常**
  （定位器的失败模式不能是崩掉调用方）。
- `roots_report() -> dict` 与 `--json` CLI —— 回答"我现在在哪个根"。此前 `repo_root.py`
  完全没有 CLI（实测 origin/main 无 `__main__` / argparse），而 plan 的 B4a 判据
  `python3 bin/lib/repo_root.py --json` 需要它。
- `canonical_root()` / `code_root()` / `state_root()` / `event_ledger_path()` **一字不改**。

### 3.4 刻意不发：`omostation.profile.toml`

plan 决策 2 说每个安装位一份 gitignored profile 文件。本轮**不发**，理由与
`.omo/_knowledge/retros/BET-Y2Q4-T10-203.md:44` 记录的同一判据一致：**零消费者的机制不发**。
B4a 之后没有任何 plist / cron / 服务读这个文件；真正需要它的是 B4b 的切换（届时它承载
`OMOSTATION_STATE_ROOT` 与 profile 名，并成为 canonical 根从"猜"变成"声明"的地方）。
现在写一个空壳只会让"profile 已就位"成为一句无法证伪的话。

## 4. done_when

1. `~/.local/opt/omostation` 存在，是**自有 `.git` 的独立 clone**（非 worktree、非 submodule），
   detached 在 `origin/main` 的某个**记录在案的 SHA**。
2. `python3 bin/lib/repo_root.py --json` 在该目录内运行，报出
   `code_root == install_root == ~/.local/opt/omostation`，同时 `canonical_root == ~/Workspace`
   —— **两条同时成立**才是 B4a 的正确形状：安装位可定位，且解析结果未被搬走。
   时序注意：这条**只能在合并后**验证。安装位 clone 早于本轮代码（实测该 clone HEAD
   `2306f94d…`，其 `repo_root.py` 里 `install_root` 出现 0 次），所以合并后必须把 clone
   重新 detach 到含本轮代码的 main SHA 再跑；`make runtime-install-root` 在未重新 detach 前
   会显式打印「安装位落后于本轮」，不会把空输出伪装成通过。
3. 守卫测试 `tests/unit/test_repo_root_profile.py` 新增用例覆盖：安装位缺席→None、
   安装位存在→`canonical_root()` 不变、`install_root()` 不污染 `state_root()`/ledger 路径、
   CLI `--json` 的键与 hermetic env 下的取值。测试不得读 host 真实 `~`（AGENTS.md §7
   hermetic 纪律：用 monkeypatch HOME + subprocess env 显式注入）。
4. 清扫不可见性被钉住：断言 `~/.local/opt/omostation` 不在 `worktree-hygiene-audit.py`
   的 `_candidate_dirs()` 语义面（`ws-*` / `workspace-*` glob）内。
5. `make runtime-install-root` 存在且无需第二处入口（`bin/` 有净新增脚本配额）。
   名字与邻居 `service-registry-reality` 同族（`runtime-*` = 运行时事实查询）。
6. AGENTS.md / ARCHITECTURE.md 侧的 agent 感知更新：第三个根的名字、路径、"它不是 worktree"、
   "canonical 仍指向 Workspace 直到 B4b"。principal standing 指令："完成之后记得更新运维和基建
   以及 agent 的感知，否则其他 agent 不知道。"
   同一轮改正脚本登记表 `bin/_registry/scripts/governance/repo_root.yaml`：它写明
   "库模块（非可执行入口）"，本轮之后不成立（新增 `--json` 入口）。留着一条假描述，
   比多改一个文件更贵。
7. ADR-0456 同步修正：§2 路径、"release tag"→"记录 SHA"、§5 防呆改判为守卫测试；
   并记录**标识冲突**（见 §6）。

## 5. verify（可复跑）

| 命令 | 期望 |
|---|---|
| `git -C ~/Workspace worktree list \| grep -c '\.local/opt/omostation'` | `0` |
| `python3 bin/lib/repo_root.py --json`（在安装位内） | `code_root` 与 `install_root` 均为安装位，`canonical_root` 为 `~/Workspace` |
| `python3 bin/gac/worktree-hygiene-audit.py --json`（**不带 `--execute`**，即 dry-run） | 报告中不含安装位路径 |
| `python3 -m pytest tests/unit/test_repo_root_profile.py -q` | exit 0 |
| `python3 bin/plan/bet-ledger.py lint`（或既有 ledger 门禁） | 新条目 schema 通过、`meta.total_bets` 与条目数一致 |

**不跑** `make worktree-prune`：`gac-branch-prune.sh` 会删除已合并的本地 `work/*` 分支，
在并发多 agent 的共享仓里跑它 = 可能删掉别人的分支，属计划外副作用。它扫不到安装位这件事由
读代码 + 守卫测试证明，不用一次有破坏性的运行来证明。

## 6. 上报，不处置（principal 范围）

- **ADR 标识冲突**：`.omo/_knowledge/decisions/` 下有两个文件同时声明 `id: ADR-0456`
  （本契约 `0456-dev-runtime-profile-root.md` 与 `ADR-0456-governance-downshift-closeout-grading.md`），
  ADR-0401 同样重号。后果已经发生过一次：T10-205 的 receipt 记"ADR-0456 经 `72c93f896` / #4413
  升级为 ACCEPTED"，而 `git show --stat 72c93f896` 只碰了**另一个**文件 —— 本契约在 origin/main
  上仍是 `status: PROPOSED`。本 bet **不**替 principal 翻这个状态（那会把一次已经发生过的误归因
  固化成第二条记录），只在 ADR 里加标识冲突提醒并要求引用写文件名。
- 主仓 shallow（§2.2）；清扫例程的候选面是否应扩到 `$HOME/.local/**`（本轮用测试钉住现状，不改行为）。

## 7. 回滚

安装位是无引用物：`rm -rf ~/.local/opt/omostation`（同时释放 183 MB）。代码侧
`install_root()` 只增不改，回滚 = revert 本 PR，`canonical_root()` 与全部消费者不受影响。
本轮不产生任何需要撤销的运行态变更。
