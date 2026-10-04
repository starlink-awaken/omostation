---
type: ssot
owner: governance-team
last_updated: 2026-09-27
---

# AGENTS.md — Workspace Development Guide

> Root operating guide for AI coding agents. **Keep operational** — runtime facts go in SSOT files, not here.

## 0. Worktree Policy (Mandatory)

> **Main workspace is read-only. Every new change starts from an isolated worktree.**

| Action | Required |
|--------|----------|
| New feature / fix / cleanup | `bash bin/gac/gac-worktree.sh claim <session>` |
| Direct commit to main | ❌ Prohibited |

**Full policy**: [`GOVERNANCE.md`](GOVERNANCE.md) § Worktree Isolation

---

## 1. Read This First (Before Every Edit)

1. Read [`CLAUDE.md`](CLAUDE.md) for session startup context.
2. Read the target project `AGENTS.md` / `CLAUDE.md`.
3. Check `git status --short`.
4. **需求迭代强制 Workflow（ADR-0203）** — Run `bootstrap → start --profile → claim` before any requirement delivery edit. Use `bin/agent-workflow.py compliance` for compliance audit.
5. For governed state, use OMO/C2G brokers instead of direct `.omo` writes.
6. For multi-file or high-risk changes, explain the edit surface before applying patches.
7. All local/edge LLM inference MUST route through **AetherForge (`bos://compute/aetherforge/infer`)**.
8. Check the Panorama Agent Brief before choosing work: `runtime/dashboard/agent-brief.json`
   (human page: Panorama → Agent Brief). It is a read-only aggregation of authority, gates,
   unfinished work, alerts, next actions, read interfaces, and safety boundaries.
9. **Never hard-code the workspace root.** Resolve it: `bin/lib/repo_root.py` gives `code_root()`
   (the checkout — read planes, governance truth), `state_root()` (write targets — ledgers,
   `.omo/state/**` runtime, projections) and `install_root()` (where the runtime code lives,
   `None` on machines without it — a locator, it moves nothing). Ask "which root am I in?"
   with `python3 bin/lib/repo_root.py --json` or `make runtime-install-root`.
   Inside `projects/omo/` use `omo.omo_paths` instead.
   Contract: `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`（按**文件名**引用：
   `id` 字段为 ADR-0456 的文件有两份，另一份
   `.omo/_knowledge/decisions/ADR-0456-governance-downshift-closeout-grading.md` 是别的决定，
   且那份 `ACCEPTED`、这份仍 `PROPOSED`），guard: `tests/unit/test_repo_root_profile.py`.

### Key SSOT Registries

| Registry | Purpose |
|----------|---------|
| `.omo/_truth/registry/agent-workflows/` | Agent workflow facts |
| `.omo/_truth/registry/ci-surfaces.yaml` | CI 平面检查接线 |
| `.omo/_truth/registry/runtime-projections.yaml` | Runtime projections |
| `.omo/_truth/registry/governance-checks.yaml` | GaC rules |
| `docs/project-registry.yaml` | Project metadata |
| `.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` | code_root / state_root 双根契约 + profile env 面 |

### Governance Quick Reference

| Need | Command |
|------|---------|
| MOF constraint check | `ecos-constraint explain/audit/eval/drift` |
| Domain truth hygiene | `make hygiene-patrol` |
| Policy-as-code | `ecos-constraint policy audit/explain/list` |
| Intent-to-spec | `ecos-constraint intent compile` |
| Shadow challenge | `ecos-constraint challenge [--auto-patch]` |
| Sovereign compute | `omlxc fabric snapshot` |
| Cartridge factory | `ecos-constraint cartridge list/export/validate` |

**Binding architecture (DFSQ/SFOP)**: Mesh (`COMP-WS-omo`) is the only active `S` slot. Do **not** add a second dispatcher or fifth ontology.

### 能力发现

| 需求 | 入口 |
|------|------|
| 查看所有可用 skills | `cat .agents/skills/INDEX.md`（按域分组，由 generator 派生; 运行 `find .agents/skills -name SKILL.md | wc -l` 取实时计数） |
| 查看所有 workflows | `cat .omo/_truth/registry/agent-workflows/INDEX.md`（按 generator 派生; 运行 `find .omo/_truth/registry/agent-workflows -name "*.yaml" | wc -l` 取实时计数） |
| 智能推荐 workflow | `uv run python bin/agent-workflow.py suggest --from-diff --profile <agent>` |
| Cockpit CLI 命令 | `cockpit <domain> <verb>`（详见 `docs/CLI-REFERENCE.md`） |
| BOS 服务发现 | `.omo/_truth/registry/capability-providers.yaml` |
| MCP 工具清单 | `docs/generated/capability-registry.yaml` |
| MCP/BOS URI 完整性 | `python3 bin/gac/check-mcp-bos-uri-completeness.py`（`--warn` 模式审计不阻断） |

---

## 2. Documentation SSOT Contract

| Document | Owns |
|----------|------|
| `README.md` | Front door and quick orientation |
| `CLAUDE.md` | AI session startup protocol |
| `AGENTS.md` | Workspace operating rules |
| `ARCHITECTURE.md` | Stable architecture contracts |
| `docs/project-registry.yaml` | Project metadata facts |
| `.omo/_truth/registry/governance-checks.yaml` | GaC rules |

**Do not hard-code** current phase, health score, test counts, or port values in Markdown. Use pointers.

**文档归档约定**（T6-17 治理，2026-09-05）：`type: ephemeral + status: completed` 的一次性文档（总结/交接/审计报告）完成后归档到 `.omo/_knowledge/design/plans/archive/`（`.omo/_archive/` 被 .gitignore 忽略，新文件不可用），顶层不再留存；文档引用同步改为归档路径（指针化）。SSOT 判定盘点见 `docs/reports/doc-ssot-inventory-2026-09-05.md`。

Full contract: [`.omo/standards/doc-ssot-contract.md`](.omo/standards/doc-ssot-contract.md)

---

## 3. Architecture Summary

Stable architecture contracts: [`ARCHITECTURE.md`](ARCHITECTURE.md)
Project layer placement: [`docs/generated/project-layer-index.md`](docs/generated/project-layer-index.md)

**道法术器 (DFSQ/v1)**: `python3 bin/gac/check-sfop-slots.py --json`
**Execution chain**: `python3 bin/gac/check-execution-chain.py --json`

---

## 4. Governance Boundaries

| Surface | Rule |
|---------|------|
| `.omo/` | State/evidence plane. Do not add long-lived execution logic. |
| `projects/omo/` | Governance kernel: schema, audit, sync, broker, lint. |
| `projects/ecos/` | Protocol and MOF layer. |
| `bin/` | Governance tools. Do not edit runtime state manually. |
| `config/` | Machine identity. Do not edit manually. |
| `kos/` | Knowledge index. Runtime product, do not edit manually. |

---

## 5. Essential Commands

### Agent Workflow (single entry)

```bash
uv run --with "pyyaml" python "bin/agent-workflow.py" bootstrap
uv run --with "pyyaml" python "bin/agent-workflow.py" compliance
uv run --with "pyyaml" python "bin/agent-workflow.py" start <workflow-id> --profile <agent-profile> --bet <BET-ID> --objective "<summary>"
uv run --with "pyyaml" python "bin/agent-workflow.py" claim <run-id> --path <path>
uv run --with "pyyaml" python "bin/agent-workflow.py" closeout <run-id>
```

### Gates & Lint

```bash
make gac-local-gate          # Full local governance gate
make ci-local                # All local CI checks
python3 bin/gac/ci-check-runner.py --workflow governance-check.yml
```

### Testing

```bash
bash "tests/integration/run-all.sh"    # Root integration suite
cd "projects/knowledge/kairon" && make test-diff
cd "projects/knowledge/gbrain" && bun test
```

### SSOT & State

```bash
make ssot-guardian && make ssot-sync
python3 bin/gac/meta-doctor.py --workspace .
```

**Full catalog**: [`bin/README.md`](bin/README.md) | **CLI reference**: [`docs/CLI-REFERENCE.md`](docs/CLI-REFERENCE.md)

---

## 6. Git And Submodules

- Do not run `git commit`, `git push`, `git reset --hard`, or branch switching unless explicitly asked.
- **Submodule pointer update**: `bash bin/ssot/submodule-pointer-transaction.sh --message "..."`.
- **禁止 `sed -i` 做添加/删除条目操作** — use Python `read → check → modify → write`.
- **子模块 commit 三步走**: ① `cd projects/<sub> && git add && git commit` ② `git push` (子模块内) ③ `cd 主仓 && git add projects/<sub> && git commit && push`.
- **pull --rebase 风险**: 本地 commit 基于旧 main 时可能丢弃改动。rebase 后用 `git reflog` 确认。

### 高危 git 操作守门

- **`reset --hard` 前三确认**: ① 当前分支 ② reset 目标 = 该分支的 origin 状态 ③ 工作树干净。
- **改"看起来是子项目"的代码前确认仓库边界**: `ls -d <path>/.git` + `git -C <path> remote -v`.

### PR 工作流

```bash
bash bin/gac/gac-worktree.sh claim <session>    # 起隔离 worktree
git push -u origin <branch>                      # 交付：手动 push（submit 不做这件事）
gh pr create --base main --head <branch> --title ... --body-file ...
bash bin/gac/gac-worktree.sh merge <session>     # squash 合并【已存在的】open PR
bash bin/gac/gac-worktree.sh release <session>   # 释放 worktree + 清 PASW 子树
```

- **`submit` 自 WP1 Wave B2 起是 proposal-only**：`bin/gac/gac-worktree.sh:683-691` 在跑完门禁/子模块预检后
  只打印 `MANAGED_SUCCESSOR_REQUIRED` + `patch_digest` 然后 **`exit 2`**，**不 push、不开 PR、不调 integrate**。
  实证（2026-09-26，同一分支两次 submit）：两次都 exit 2，远端零效应。
  所以 **`exit 2` 不是拦截，是终态** —— 别把它读成"base 太旧、需要先造一个 successor"而白跑一轮 claim。
- `merge` 仍然可用，但它查的是"该分支已有 open PR"（`:780-783`，查不到就报 `先 submit 开 PR` 退出）。
  由于 submit 不再开 PR，**这句提示已失效**；真实前置条件是上面两行手动 push + `gh pr create`。
- `origin/main 前进 N commits` 的告警同理：它伴随 proposal 一起打印，不是要求你 rebase
  （本仓明确禁止用 rebase/merge/pull 吸收上游，见 `:507`）。改动只碰文档且与上游无交集时，
  直接 push 即可。
- **但别据此推论"CI 只评 merge tree、base 漂移无所谓"**（2026-09-27 实测，BET-Y2Q4-T10-210）。
  `.github/workflows/governance-check.yml` 四个 job 的评审对象**不同**：`meta-doctor`(`:51`)、
  `interface-check`(`:64`)、`doc-freshness`(`:146`) 用默认 checkout（PR 事件 = merge commit），
  而 `governance-verify`(`:169`) 显式 `ref: github.event.pull_request.head.sha`(`:176`) 且
  `fetch-depth: 0`(`:177`) —— 它评的是**分支自己的 head tree**。台账 `done`-transition 守卫与
  evidence/ledger 校验都在 `governance-verify` 里，所以 base 漂移**会**改变它的判定。
  该选择是刻意的（`:171-175`：GitHub 的合成 merge ref 会把冲突 gitlink 解析到 base 一侧，
  让检查看到与 PR 交付不同的子模块图）。判据：怀疑某条治理门禁看的是哪棵树时，
  `rg -n "pull_request.head.sha" .github/workflows/` 而不是引用本文件的措辞。

### Hook 机制 22c（2026-09-06, BET-Y1Q4-T6-24）

- **本仓 `core.hooksPath=.githooks`**：hooks 从 canonical 直读生效。`git rev-parse --git-path hooks` 会被重定向到 `.githooks`（不是真实 git-dir/hooks）。
- **元数据路径纪律**：installer/runner/health-check 写读 `.version`/`.content-hash` 一律用 `$(git rev-parse --git-common-dir)/hooks`（worktree 感知、不受 hooksPath 影响）；**不要用 `--git-dir`**（worktree 下返回 `.git/worktrees/<name>/`，读不到共享元数据 → 版本误报 0.0.0，2026-09-06 实证）；也不用 `--git-path hooks`（core.hooksPath 下 cp 自拷贝/检查错位，2026-09-06 实证回归）。
- **manifest 引用路径全量扫描**：改 hook 脚本路径后必须扫描 manifest 全部 hook 段（pre-commit/pre-push/post-checkout/pre-rebase/pre-merge-commit/post-merge/commit-msg），别只修一段——#3282 只改 pre-commit 段、回退 pre-merge-commit 的 conflict-marker 路径致检查静默失效。
- **同 BET 并行交付防回退**：改 canonical hooks 前先 `git fetch` 查 main 是否已含目标内容（PITFALL-GAT-006）；并行 agent 同名 BET 的 PR 可能基于旧 main、合并后回退正确值（#3282 回退 #3277 的 5 处修复实录）。

### worktree 子模块与 remote 完整性（2026-09-12, BET-Y1Q4-T10-161）

- **gitlink 新鲜度**：worktree claim **默认浅 init 子模块** —— `git submodule update --init --depth 1`
  （`bin/gac/gac-worktree.sh:504`，措辞见 `:484`）；完整 init 要 `claim --full` 或
  `GAC_FULL_SUBMODULE_INIT=1`（`:373`），`SKIP_SUBMODULE_INIT=1` 则只做 root worktree 不建子模块
  （`:473`）。`SKIP_SUBMODULE_INIT=1` 快速路径与 `git worktree add` 直创路径由 post-checkout 守卫兜底——对 pin 不一致的子模块做本地无网络 `submodule update --init --no-fetch` 对齐（只动子模块工作树，**不改根指针**）。本地缺 pin 对象时打印修复命令，不联网。
- **本机是浅历史，且 worktree 子模块深浅不定 —— 可达性判据必须换地方验**（2026-09-27 实测，BET-Y2Q4-T10-210）：
  主仓 `git rev-parse --is-shallow-repository` = `true`，`.git/shallow` 只有一个边界 `6ba6bf28e`（2026-08-01），
  本地可达 commit 8,326 个（历史从这里截断，不是整仓）。子模块侧更 tricky：canonical `projects/omo` 非浅
  （767 commit），而历史 claim worktree 里的 `projects/omo` **各只有 1 个 commit**（`HEAD~1` 直接
  `unknown revision`），另一些 claim 又是深的（本次 worktree 766）——**深浅取决于 claim 路径，不能靠记忆假设**。
  后果：`git -C projects/omo merge-base --is-ancestor <child> origin/main` 这类 gitlink 可达性判据
  在 1-commit 检出里**没有意义**，跑出 false 是测量装置没历史，不是回归。而 CI 的
  `governance-verify` 在 `governance-check.yml:177-178` 用 `fetch-depth: 0` + `submodules: recursive`
  取完整历史，于是会出现"本地 false / CI 绿"的分歧 —— 别把它读成 CI 假绿。
  **判据**：可达性/祖先类检查只在 canonical 工作区或 `claim --full`（`GAC_FULL_SUBMODULE_INIT=1`）
  的 worktree 里做；动手前先测 `git -C <path> rev-parse --is-shallow-repository`。
  主仓 unshallow（`git fetch --unshallow`）是机器级对象库重写，未经确认不要做。
- **remote 污染特征**：主仓 remote URL 落入 `.gitmodules` 子仓 URL 集合即为污染（实证：origin 被并发会话改写成 cockpit-ui 仓后，一切 origin/main 验证静默失效）。**强制约束（2026-09-13 三层）**：① post-checkout hook `remote-hygiene-fix` 幂等自愈（checkout/worktree add 是污染窗口）② pre-push `remote-hygiene-check.py` 阻断（fetch+push URL 双校验）③ cron 每小时 `fix-remotes.py` 巡检自愈（`runtime/cron/remote-hygiene.log`）。push URL 可被单独改写，两层都要查。
- **污染根因（2026-09-13 实证）**：旧 `fix-remotes.sh`（bash 版）本身就是污染源——① `[ -d .git ]` 在 worktree 中恒 false → 自愈静默失效；② 对未初始化子模块（目录存在无 `.git`）执行 `git -C <sub> remote set-url` 会向上解析写进主仓共享 config（串联覆盖，最后写的赢）→ root origin 被写成最后一个子模块 URL（omostation-runtime）。已 Python 重写（`fix-remotes.py`，sh 为 shim）：worktree 兼容 + 跳过未初始化子模块 + 幂等。检查端同理：未初始化子模块不读 remote（防误报）。
- **手工核验**：`bash bin/gac/gac-worktree.sh guard-submodules [--fix]`；跳过守卫：`GAC_SKIP_POST_CHEKOUT_GUARD=1`。

### ledger BET 条目安全插入（2026-09-12, 批次 31 复盘固化）

- **禁止按行号盲插**：bets 序列被顶层键 (`campaigns/disciplines/gates/meta/milestones/objectives`) 切断，盲插会把条目塞进错误段落。用 `python3 bin/gac/ledger-safe-insert.py --file <entry.yaml>` 自动定位（yaml.compose 物理边界）+ schema/digest/id 校验 + 原子写入。
- **dry-run 先行**：`--dry-run` 校验通过后再正式写入。

### 并发 agent 分支隔离（2026-09-25 复盘固化）

- **问题**：多 agent 同时向同一分支 push/重放提交（常见于 squash-merge 后对方基于旧 tip 继续叠 commit），导致反复 non-fast-forward 被拒；若直接 merge 对方的重放提交，会回流已被清理的 junk / 覆盖自己的修复（本轮 Kilo 二次 merge 回流 5,322 文件实录）。
- **解法**：争议改动在**隔离 worktree** 完成，cherry-pick 到自己的最新 commit 上、rebase 到远端最新 tip，再 push。**不要**在原共享分支上 `merge` 对方的重放提交。
- **识别信号**：`git push` 报 "hint: use 'git pull' before pushing again" + 对方 commit message 与自己高度近似（重放迹象）→ 走干净室 cherry-pick 路径。

---

## 7. Common Pitfalls（2026-09-12 实证）

- **Bash 工具跑的是 zsh：多值列表禁止 `VAR="a b c"; for x in $VAR`（2026-10-02 固化，同日复发两次）**：zsh 对**参数展开不做 word splitting**（只有**命令替换**会）⇒ 该循环**只迭代 1 次**、`$x` 是**整串**。危险形态是「静默少迭代 + 输出看着正常」（`basename "$x"` 恰好返回整串的**最后一段**，于是单条输出看着像一条正常记录 —— 曾据此误判「worktree 被删」）；**在「批量删除前的逐项安全检查」里最致命** —— 四列全有值、格式完全正常，却在描述一个**不存在的路径** ⇒ 会得出「都干净、可删」并真去删（**安全检查的塌缩 = 安全网本身失效**，不是少查一项）。**三种正确写法**：① 字面量列表 `for d in a b c; do …; done`（首选，零心智负担）② 命令替换 `for d in $(printf '%s\n' a b c); do …; done` ③ 数组 `arr=(a b c); for d in $arr; do …; done`。**并且**：任何「批量操作前逐项校验」的脚本，收尾**必打 `echo "expect=$N got=$n"`** —— 这是当下唯一能发现塌缩的手段。⚠️ 该条只发生在 Agent 临时写的一次性 Bash 命令里（不进仓、不过 hook）⇒ **无法 harness 化**，只能靠本条协议。同源变体（同一 zsh 根因）：`${PIPESTATUS[0]}` 在 zsh **恒为空串**（zsh 用 `$pipestatus`，小写、1-based）⇒ **取退出码不要经过管道**；`date +%s%3N` 在 macOS/BSD date 无 `%N` ⇒ 毫秒计时改用 Python。
- **frontmatter UTC 时区**：`last-reviewed` 必须用 UTC 当天或更早，否则 gac-gate FAIL（PITFALL-004）
- **memory 索引（`MEMORY.md`）是硬容量，拆分文件不会腾出余量**（2026-10-04 固化）：索引
  **行数 = topic 文件个数**，每个文件**恒占 1 行**、与其多少行无关 ⇒ 把一个 571 行的文件拆成两份，
  索引反而 **+1 行**。容量 = `200 − 8 结构行 = 192 条`（200 行 / 40000 字符**双限**，
  超限部分**不会被加载**）。⇒ **新增一条索引 = 同步归档或合并一条**；动手前先查预算
  （用 Python 读 `MEMORY.md` 的行数与字符数，**别用 `wc`** —— 它给字节数，中文 3 字节/字）。
  归档落 `_archive/<类名>-<日期>/`，且**必须同步改掉指向被归档件的「另见」引用**，否则死链。
  **判「无索引指针的文件」该不该删，先看 `description` 是否含独占知识**（路径 / 协议 / 结论）
  —— 实测 16 件里 12 件不该删；只因「搜不到」就归档会净丢检索入口。**腾行数的唯一有效手段
  是合并同族条目**（压正文长度对行数零贡献）；改完必跑：死链 = 0、格式合规（`-[..](..)` 正则
  不匹配即异常）、顶层文件 100% 有链接。
- **判据报警先 print 原始行再定性（2026-10-04，同日 4 次自伤）**：「规则已生效」「条目丢失」
  「有孤儿」这类结论，报警后**先打印出问题的具体行做逐字节核实**，再下结论 ——
  实测 4 次里 **2 次报警本身是错的**（`dict` 收集让同名项互相覆盖而误报「丢 1 条」；
  孤儿判据只统计行首条目、漏算正文内嵌链接而误报「1 孤儿」）。同根因的两个判据会**一起假绿**
  ⇒ 判据须与被验对象**不共享失效模式**（死链用 `findall` 漏数，格式用「不匹配即异常」反查）。
  凡「两次探测结果不同」，**先疑基线动了**（`origin/main` 前进足以反转结论），不是先怀疑自己判错；
  写「订正」前必须先取**时间戳证据**。
- **根目录是参数，不是事实**（2026-09-26, ADR-0456 / BET-Y2Q4-T10-203）：写机器级配置、launchd plist、
  cron 或任何指向仓内路径的工具，一律经 `bin/lib/repo_root.py`（`code_root()` / `state_root()` /
  `event_ledger_path()`）取根，不要 `__file__` 反推、更不要写字面量 `/Users/…/Workspace`。
  两个根含义不同：**读**（治理 SSOT、`.omo/_truth/registry/**`）跟随当前检出；**写**（ledger、
  `.omo/state/**` 运行态、projections）跟随 profile。可用 env：`OMOSTATION_ROOT`、
  `OMOSTATION_STATE_ROOT`、`OMO_EVENT_LEDGER_DB`（优先级最高）。未声明 profile 时二者相等，
  即与历史布局逐字节一致 —— 这条不变量由 `tests/unit/test_repo_root_profile.py` 钉住。
- **运行时安装位已存在，但它不是第三个可写的根**（2026-09-27, ADR-0456 B4a / BET-Y2Q4-T10-207）：
  `~/.local/opt/omostation` 是运行时代码的**独立 clone**（自有 `.git`，**不是 git worktree**，
  detached 在记录在案的 `origin/main` SHA —— 本仓没有可用的 release-tag 序列）。
  `repo_root.install_root()` 只负责定位它；`canonical_root()` 仍解析到 `~/Workspace`，43 个 plist
  也仍指向 Workspace —— **改道是 B4b，不属于这一轮**。两条纪律：别按 plan 时代的旧路径找运行时
  （`~/Runtime/omostation` 已作废，那个 inode 是 `projects/runtime` 的数据域），也别把它当清理残留
  扫掉（`worktree-hygiene-audit` 的候选面只有 `$HOME/ws-*` / `$HOME/workspace-*`，扫不到它，
  边界由测试钉住）。问根：`python3 bin/lib/repo_root.py --json` 或 `make runtime-install-root`。
- **XDG 状态根上已有两份 ledger 产物，都不是权威**（2026-09-27, ADR-0456 B4b 批次 1 / BET-Y2Q4-T10-208）：
  `~/.local/state/omostation/prod/` 是生产库的**在线备份快照**（`Connection.backup()`，WAL 安全，
  非 `cp`），`~/.local/state/omostation/dev/` 是 dev profile 的**自有空库**。权威仍是
  `$(state_root())/runtime/omo/event-ledger.sqlite3`，launchd plist 与 crontab 一行未改。
  辨认依据不是"像不像一个 ledger"，而是同目录 `*.provenance.json` 里的 `authoritative: false`
  —— 别把它当已改道，也别复制一份出来冒充历史。机制：`omo ledger snapshot --source … --dest …`
  / `--bootstrap`，入口 `make runtime-state-snapshot`（`--dest` 已存在即拒绝，不静默覆盖）；
  契约 `docs/superpowers/specs/2026-09-27-event-ledger-state-snapshot.md`。
  把权威真正翻过去属 B4b 批次 2+，需逐批授权。
- **两个根的写面收敛，靠的是一条没人复述的沉默契约**（2026-09-30, ADR-0456 F1 / BET-Y2Q4-T10-215）：
  声明 `OMOSTATION_STATE_ROOT` 后，四件投影与 `runtime/omo/**` 镜像根确实落在 state 根 ——
  但链节能闭合的前提是 `bin/compass_radar.py:482` 的 `subprocess.run` **不传 `env=`**
  （`:482-492` 实测参数只有 `cwd` / `capture_output` / `text` / `timeout` / `check`），
  子进程 `bin/gac/evidence-smoke.py` 因此靠**继承**拿到 profile。谁给它加一个 env 白名单，
  写面就断在子进程边界、投影回写检出，而且**没有任何测试会红**。改这行前先跑正向落点判据。
- **声明 profile 后跑真实 sync，检出照旧脏两个文件 —— 那不是回归**（同上，实测读数）：
  脏的是 tasks 面时间戳（`.omo/state/system.yaml` 的 `updated_at` 与
  `.omo/tasks/registry/INDEX.md` 的 `Updated:`），投影面与 evidence 面字段零脏。判别量不是
  「检出里没有」，而是**同一字段的值只在 state 根滚动**（检出的 `health_score_evidence` 三行逐字未变，
  新时刻只出现在 state 根）。据此两条纪律：别把这两处脏读成写面回归而白跑一轮；别用「脏检出」
  这一个否定式当验收 —— 每条"移走某个写目标"的契约都要配一条正向落点断言，**且先跑一次再写进契约**
  （本轮就有一句「检出不含这三行」被自己的 receipt 否证）。
- **治理协调面是全机共享面，`gitignore` 不等于本地化**（2026-09-30, ADR-0456 F1 / BET-Y2Q4-T10-215 实证）：
  `.gitignore:12` 忽略 `.omo/_delivery/*`，说的是这一面**不进 git**，不是说每个检出各一份 ——
  `ensure_delivery_anchor()`（`projects/omo/src/omo/workflow/delivery_anchor.py:87`）把每个 worktree 的
  `.omo/_delivery/agent-workflows/` 做成指向 canonical 检出的 **symlink**（实测 worktree 与主区的 `locks/`
  同一 inode），所以并发会话的 run / scope 锁**互相可见**。两个后果：① `closeout --status ok` 的前置
  `heartbeat_run()`（`projects/omo/src/omo/workflow/lifecycle.py:1592` → 逐锁校验 `:1017`）会在锁被
  并发 run 接管时**直接拒绝整条 closeout**，此时用 `close --status ok --evidence <note>`
  （`release_locks()` 只 unlink `run_id` 等于自己的锁）；② **别用 `prune-locks` 绕** —— 阈值
  `_HEARTBEAT_STALE_SECONDS = 3600`（`projects/omo/src/omo/workflow/lifecycle_locks.py:27`）只看心跳时间，
  实测一次 `--scan-only` 把共享面 29 条锁里的 22 条判成 zombie，而这三个 run 的
  `status` **全是 active**（只是会话闲置过一小时），prune 会当场拆掉别人的活锁。
- **新跟踪文档的 frontmatter 必填 `owner`**（同上）：`doc-governance-check.py --no-new-warnings
  --scope tracked` 里 `accepted-specifications` 桶的**未基线告警等于 error**，而 `bet-closeout-chain`
  的"七件套"没列 `owner` —— 照清单抄就会红一轮。判据：新文档 frontmatter 抄同批已绿的邻居，不抄 checklist。
- **WorkPacket 只 gate claim，不 gate 状态翻转**（2026-09-30, BET-Y2Q4-T10-216 本轮实测）：
  `verify` / `done_when` / `scope` 这些字段进了 packet 投影，所以 `start` 之后再改台账条体会让后续
  `claim` 报 `WORK_PACKET_SOURCE_DRIFT`（`bin/plan/bet-ledger.py:2336`）；而 `refresh-packet`
  （`bin/agent-workflow.py:1031`）要求 ledger+spec **已在 `origin/main`**（`:770` 逐源比对字节），
  新建 BET 的首轮用不了它。顺序纪律：**台账定稿 → `start` → claim 完 → 才改非投影字段**
  （`status` / `done_at` / `completion_evidence` 不在投影里，所以 `complete` 照常能跑；
  packet 校验的调用点只有 claim 与子 run 继承 `projects/omo/src/omo/workflow/lifecycle.py:1307`）。
- **ci-surfaces 不加自引用路径**：严格匹配 workflow `on.paths`
- **生成态会被交付动作扫进 commit**（2026-09-26 实证）：commit / claim 期间 hook 会重写
  `.omo/state/system.yaml` 的 `health_score_evidence_generated_at`（纯时间戳），一次文档 PR
  因此多带一个 `wip:` commit。判据：交付前跑 `git diff --name-status origin/main..HEAD`，
  把 `.omo/state/**` / `BRIEF.md` 这类生成态与你的真实改动分开数 —— 出现 `M .omo/state/...`
  而你没碰过它 = hook 产物，剔除（#4346 / #4359 均剔除，生成态不随文档 PR 走）。
  同一命令还能一眼看出 base 漂移带来的反向条目（主仓已改的文件会显示为 `D`/`M`，非你所为）。
- **mergeStateStatus**：值是 CLEAN/BLOCKED/DIRTY（非 MERGEABLE）
- **worktree 创建后立即** `git submodule update --init`：防指针回退
- **`gac-worktree.sh merge` / `release` 的「worktree 有未提交改动」五种脏项全部可自清（2026-09-30 固化）**：守卫判据是 `git diff --quiet`（**不含 untracked**），但**子模块状态会让它报非 0**。四类：① `uv run` 改写**被跟踪的**子模块 `uv.lock`（注意各子模块跟踪状态不一致：cockpit 未跟踪、agora/runtime 已跟踪）→ `git -C <sub> checkout -- uv.lock` ② bump gitlink 后**未同步子模块检出** → `git submodule update --init <path>` ③ 子模块内**生成物**（如 `projects/cockpit` 的 `CAPABILITY-MAP.md`，pre-commit `sync-check` 写出）→ `git -C <sub> checkout -- <file>` ④ **主仓生成态被本地门禁/测试刷新**（如 `.omo/state/system.yaml` 的 `health_score_evidence_generated_at` 时间戳，跑 `make gac-local-gate` 即触发）→ `git checkout -- <file>`，⚠️**勿提交**（生成态走专门 `chore(state)` 通道，搭进功能 PR 会让 CI 干净检出报 mismatch） ⑤ claim 半途失败留下的**成批 `D ` 坏 index**（须先确认无非 `D` 项：`git status --porcelain | awk '$1!="D"'` 为空）→ `git submodule foreach --quiet 'git reset --hard -q'`。**只有「真有在制工作」才该走 submit / stash**。守卫现已自己打印这份明细（带子模块名）+ 自清命令，报错即解法；手工排查用 `git submodule foreach --quiet 'p=$(git status --porcelain); [ -n "$p" ] && printf "%s\n" "$p" | sed "s|^|   $displaypath: |"'`（⚠️ `--quiet` 会把 `Entering '<name>'` 一并压掉，不加 `$displaypath` 就只能报「某处脏」不能定位）。
- **并发 agent 争用**：stash+checkout main 恢复；不替并发 agent 写 retro
- **主工作区共享改动丢失（2026-09-17 实证）**：`/Users/xiamingxing/Workspace` 被多 agent 共享——他人分支切换/`reset --hard` 会静默丢掉你未提交的改动，反之你提交时也会裹入他人暂存内容（本人两件都经历过）。git 无 pre-checkout/pre-reset 钩子，无法在破坏性操作前拦截，故采用**快照兜底 + 脏态告警**：① post-checkout 钩子自动快照（仅主工作区）② cron 每小时快照（`omostation-wip-guard`）③ `python3 bin/gac/workspace-wip-guard.py status|check`。**纪律：主工作区只读，凡改动必 worktree**；若不得不在主工作区留改动，先 `make wip-snapshot`。恢复：`python3 bin/gac/workspace-wip-guard.py restore <snapshot> --force`（默认 dry-run）。
- **Diff 工具 ref 解析**：已加 `_resolve_ref` fallback 到 origin/<ref>
- **gitlink-only push 不触发 Dependabot 复评（2026-09-25 实证）**：Dependabot 只在「manifest 变化的 push / 新 advisory」时扫描，无 schedule；子模块 gitlink bump 不改父仓 manifest → 陈旧告警 `updated_at == created_at` 永不复评（GitHub 机制，非 bug）。强制重扫唯一入口是 UI 齿轮 "Refresh Dependabot alerts"（1 次/小时，无 API 等价物），且实测**只加新告警、不关陈旧告警**。兜底：`PATCH /repos/{o}/{r}/dependabot/alerts/{n}`，字段 **`dismissed_reason`**（enum `fix_started|inaccurate|no_bandwidth|not_used|tolerable_risk`，非 `dismissal_reason`/`state_reason`）+ `dismissed_comment` ≤280；PATCH 计 5 点/次，批量限速；dismiss 前必须按 gitlink 解析子模块 lock 实际版本逐条匹配全部 `vulnerable_version_range`。
- **Chrome GUI 自动化路线（2026-09-25 实证）**：AX tree 被 AXMenuBar 噪声占满且 2000 节点截断，`query` 对页面内容零命中 → 控件用截图+像素定位（或 grep AX 树找 `AXPopUpButton` 后 `AXPress`，`AXShowMenu` 弹的是右键菜单）；omnibox 用 `set_value`+`return`（`type_text` 是追加、`cmd+a` 无效）；视觉分析降级链 @observer（模型缺失时不可用）→ zai analyze_image（易超时）→ `read` 直读 PNG 最可靠；不传 `session`（idle TTL 快）。
- **gac-worktree.sh claim 可能超时但实际已建成（2026-09-25 实证）**：claim 被 timeout 杀死后 worktree 可能停在子模块半初始化态——先 `git worktree list` 确认存在，再 `git submodule update --init --recursive` 对齐（防指针回退），勿重复 claim。
- **生成物 CI 口径 ≠ 本地（2026-09-25 实证）**：`gen-*.py --check` / drift / ledger 等生成物依赖子模块检出完整度。本地 worktree 常只 init 部分子模块，CI 递归检出全部，导致 registry tools 计数等偏差（本轮 capability-registry 本地 566、CI 643）。**解法**：生成物验证前用 `git clone --recurse-submodule` 做 fresh 复刻，双环境逐字节 diff 一致后再 push。
- **hermetic 测试泄漏 host 状态（2026-09-25 实证）**：fixture/集成测试不得依赖 host 运行时状态（authority broker / shared store / 网络 / 本机端口）。开发机 broker 状态变化会让测试从绿变红，CI 无此状态则绿，形成环境类假绿。**解法**：通过 env seam 切断（如 `CLAIMS_AUTHORITY_HERMETIC_UNACTIVATED=1`），生产路径零变更；测真实状态的用例显式自行 patch。
- **僵尸 `.git/index.lock` 静默中断 `gac-worktree.sh merge` 清理段（2026-09-27, #4419 实证）**：0 字节 + 旧 mtime 的 stale lock 会让**合并成功后**的 checkout/pull 段失败退出（脚本 `set -e`，且 `cmd | tail` 吞 exit code，末行没有显式报错 ≠ 跑完），worktree/分支/claim 全部残留。判据：`ls -l .git/index.lock`（0 字节即可疑）+ `lsof .git/index.lock`（**无输出 = 无持有者** → 可 `rm -f`；有输出则先查持有进程，禁删）。**合并本身发生在锁之前**：先 `gh pr view <n> --json state,mergedAt` 确认 MERGED 再清理，别把清理失败误读成合并失败而重跑一轮。
- **merge 脚本主区 `checkout`/`pull` 撞脏树中止，清理段需补跑（2026-09-27, #4420 实证）**：脚本在 `gh` squash 合并成功后才在主区 `git checkout main` + `git pull --ff-only`；共享主区有未提交改动时 git 打印 `Aborting` 拒绝推进（**只保护不丢弃，不会丢改动**），脚本随即中止 → worktree/分支/claim 残留。补跑：`bash bin/gac/gac-worktree.sh release <session>`（清 worktree + claim，**不删本地分支**）→ `git branch -D agent/governance-agent/<session>`。三查判据应全空：`git worktree list | grep ws-<session>`、`git branch --list agent/governance-agent/<session>`、`ls .omo/_delivery/branch-claims/<session>.json`。
- **「已提交的 legacy 兜底」不是这份仓库的性质（2026-10-02, BET-Y2Q4-T10-221 实测）**：`.omo/_truth/registry/runtime-projections.yaml` 声明的 **17 条投影路径里只有 1 条在 `origin/main` 上被跟踪**，而那条是 `.omo/_truth/registry/memory-os.yaml`（权限面，不是生成态）；其余 8 条 canonical + 8 条 legacy 生成态**全部既未跟踪又被 gitignore** —— 包括测试断言要兜回去的 `.omo/state/health.yaml`（`.gitignore:411`）和被忽略的 canonical 面（`.gitignore:281`）。`bin/lib/repo_root.py:182` 的 `projection_read()` 只返回**路径**、不判存在性（`bin/lib/repo_root.py:199` 有则读 canonical，`:201` 否则给 legacy），所以**兜底只在「这个检出曾经跑过写者」时才存在**：fresh clone 与 CI 干净检出两面皆无。后果与纪律三条：① 别把「读者有兜底」当仓库保证，需要旧值就显式跑一次生成或取快照；② **测兜底必须先物化** —— `tests/unit/test_projection_reader_resolution.py::test_projection_read_prefers_canonical_then_legacy_and_reports_absent` （`:52` 起）之所以绿，是它的 fixture 自己 `write_text` 出 legacy 文件（`:61`）；而 `tests/unit/test_repo_root_profile.py::test_projection_falls_back_to_committed_legacy_path`（`:174`）断言「退回仓内已提交的 legacy」在 T10-221 基线上按构造不可满足（实测 1 failed / 1 passed，判据见该 BET）—— T10-222 让该用例转绿的方式正是**由 fixture 自己物化 legacy**，所以今天的绿是构造出来的绿，不是仓库保证，**别把它的红读成写面回归，也别顺手把用例改窄**；③ 检出里 `.omo/state/system.yaml` 仍被跟踪是 `.gitignore:294` 那条 `!.omo/state/system.yaml` **显式反选**的结果，不是疏漏 —— 自 #4606 起它是**设计上的陈旧快照**，读者不得当现值（现值在 state 根那份，经 `bin/lib/repo_root.py:204` 的 `state_file_read()` 取，且它只在 `OMOSTATION_STATE_ROOT` 已声明时才探 state 根：`bin/lib/repo_root.py:217`）。
- **写路径要在调用时刻解析；缝的另一半是「不许写半份镜像」（2026-10-02, #4606 固化）**：模块级常量在 **import 时**求值，profile 晚声明就被冻结在旧根上，且**没有任何测试会红**（与 `bin/compass_radar.py:482` 不传 `env=` 那条沉默契约同族）。四个 system.yaml 写者因此一律走缝：`bin/compass_radar.py:1138`、`bin/gac/harness-omo-bridge.py:39`、`bin/gac/self-evolution-loop.py:35`、`bin/gac/evidence-smoke.py:212` —— 新写者把路径写成模块级常量就是这个错误形状。第二半更容易被忽略：`bin/gac/harness-omo-bridge.py:193` 在 state 根那份**不存在时跳过**而不是凭空建 —— 写出一份只含自己那几个键的镜像，会让 `state_file_read()` 的读者读到「新但缺字段」的状态。**判据**：整文件偏向 state 根的正确性依赖这条不变式，加写者时先问「缺副本时我写不写」，再问「写到哪」。
- **扫源码的门禁必须自证，且允许清单要钉成集合相等（2026-10-02, #4606 实证）**：① `/`-链要**按源码顺序递归展平**（`tests/unit/test_system_yaml_write_plane.py:254` 的 `_path_segments`），用栈弹出序拼接会漏掉同一种字面量的别的写法；② 任何这类检测器都要拿**合成违规样本自证**（`projects/omo/tests/test_omo_system_yaml_state_root.py:99`），否则「绿」可能只是**检测器压根没命中** —— 空绿的代价是一条判据在写者没改完时就变绿；③ 残留豁免是显式集合且被测试钉死（`tests/unit/test_system_yaml_write_plane.py:240` 清单本体、`:293` 断言实测集合与之相等、`:296` 断言每条理由指向真实文件），**判据**：加豁免前先跑那两条断言，别在检测器里加临时 `if` 跳过。
- **三个治理门禁的真实语义，都会以「判据自否证」的方式咬人（2026-10-02, T10-219 / T10-220 实测）**：① `bin/ssot/script-registry.py` 的 `validate()` 把 id 收进 **set**（`bin/ssot/script-registry.py:119` + `:124`）⇒ 重复 id **静默折叠**，且 `missing = git ls-tree HEAD 的 bin 全部脚本 − registered`（`:133` + `:147`）⇒ 「把一个 id 改指到活副本」会让旧脚本从 registered 消失、当场 `Missing registrations: 1`，所以登记面只能加不能挪；它也不校验 schema。② `bin/gac/omo-state-write-guard.py` 的归属检查是 `present == declared` **双向**（`bin/gac/omo-state-write-guard.py:156`，两类违规 `:181` undeclared-key / `:189` ghost-declaration，计数 `:256`）⇒ **只声明已经存在的键**，声明一个当前不写的键会当场造幽灵、把上一轮的绿判据变红。③ `R-GOV-2` 结构上只能 WARN：`bin/gac/governance-convergence-lint.py:159` 的 `check_score_convergence()` 在 `:161` 初始化 `errors`、`:176` 原样返回，中间只 append warnings ⇒ 把「自己复制自己的分当真值」这类同义反复删掉**不需要先登记 known-debt**。另附一条可见性边界：`.github/workflows/governance-check.yml:118` 起是**显式 pytest 文件白名单**（到 `:127`），**不含 `tests/unit/**`** ⇒ 那批用例本地跑得到、CI 永远看不见，「CI 绿」不构成它们的证据。
- **BET 闭环交付机制三条读数（2026-10-02, T10-220 两轮 PR 实证）**：① `python3 bin/plan/bet-ledger.py complete <BET>` 要求 `engineering.merged_reachable_commit` **在本地对象库里可达**（`bin/plan/bet-ledger.py:1682`）⇒ squash-merge 之后**先 `git fetch origin main`** 再 complete，否则它会连带报 `OVERALL_STATE_MISMATCH: derived='blocked'`，看着像 evidence 写错、其实是没取对象。② `WORK_PACKET_SOURCE_DRIFT`（`bin/plan/bet-ledger.py:2336`）与 packet 校验**只 gate `claim`**，`status` / `done_at` / `completion_evidence` 不在投影里，retro 与 receipt 路径实测可未 claim 提交；`refresh-packet`（`bin/agent-workflow.py:1031` → `:814` → `:738`，字节比对失败报 `:772`）要求检出的 ledger/spec **已等于 `origin/main`**，所以**新建 BET 的首轮用不上它** —— 顺序纪律仍是「台账定稿 → `start` → claim 完 → 才改非投影字段」。③ GitHub 对 squash-merge **自动删除 head 分支**；往同名分支再 push 会把**整条旧 stack** 复活成 PR 内容 ⇒ 二次交付必须从当前 `origin/main` 起新分支 + `cherry-pick` 那一个 commit，并用 `git diff --name-status origin/main..HEAD` 查有没有 `D` 行（PITFALL-COO-005 同族）。④ `claim` 还有一道前置：必须先产 affected-graph receipt（缺失时 `projects/omo/src/omo/workflow/lifecycle.py:1313` 直接拒），而 receipt 的**输出父目录不允许含 symlink**（`bin/gac/affected-graph.py:121`，同文件 `:125` 再查 resolve 一致）—— 协调面 `.omo/_delivery/agent-workflows/` 本身就是 symlink 桥，所以它**不能落在那里**，只能落真实目录且路径须 workspace-relative（如 `runtime/affected/`，用完即删、不进 commit）。
- **六类会让判定静默失效的形状（2026-10-04, BET-Y2Q4-T10-225 固化；准入沿用 T10-221）**：以下每条都满足「当场让安全网或验收判据失效」且「有不依赖本机状态的指认方式」，措辞含 证据→判据→纪律。
  - **① YAML 重复键是静默的 last-wins，不是报错**：`yaml.safe_load` 对重复键**不抛异常**，构造 mapping 时保留最后一个。实证 `.omo/cron/registry.yaml` 两条 panorama 记录各带**两个** `reality` 键（`declared_only`+`pending`、`installed`+`pending`），文件同时印着「已装机」与「待装」，而**所有读者只看到 `pending`**；全文件 dup-aware 扫描恰好 2 处、其余 68 条干净（PR #4623 → `d8ab0aa58`）。**纪律**：这类文件**只改其中一行无效，另一行仍会赢** —— 删被遮蔽的键、留唯一真值。**判据**：`safe_load` 结构上看不见重复，所以任何查这类违规的检测器必须自带 dup-aware `MappingNode` constructor，并按 #4606 的纪律**自证** —— 标准形状是 `tests/unit/test_cron_registry_reality_invariants.py` 的 `test_duplicate_key_detector_is_not_a_no_op`（向真实文本注入重复行、断言点名它）+ `test_safe_load_alone_would_have_missed_that_violation`（断言 `safe_load` 折叠成一条、看不见违规）。
  - **② 时钟炸弹 = fixture 写绝对时间戳 × 断言用相对窗口**：`tests/unit/test_projection_reader_resolution.py` 三处 fixture 硬写 `generated_at: 2026-…`，而判据是「新鲜度 ≤ N 分钟」，于是用例**跑得越晚越红** —— 2026-10-02 起必红，与代码零关系，且形状与真回归**无法用眼景区分**（T10-222 / PR #4617 把这类从 3 处降到 0 处）。**纪律**：fixture 时间一律**相对 now 派生**（`_fresh_ts()`，该文件 `:21`）。**指认命令**：`grep -rn "write_text.*generated_at:[ ]20" tests/unit --include="*.py"` 必须 CLEAN。
  - **③ 「按构造就绿」—— 断言的前提由 fixture 自己写出**：`tests/unit/test_projection_reader_resolution.py` 的 `test_projection_read_prefers_canonical_then_legacy_and_reports_absent`（`:52` 起，`:61` 处 `legacy.write_text("legacy")`）之所以绿，是它自己写出了 legacy 侧文件；对面的 `tests/unit/test_repo_root_profile.py::test_projection_falls_back_to_committed_legacy_path`（`:174`）断言「退回仓内已提交的 legacy」则**按构造不可满足**（17 条投影只 1 条被跟踪，见「已提交的 legacy 兜底」条）。**纪律**：这类断言必须配**变异对照或合成违规自证**，否则「绿」只是装置没命中 —— T10-222 verify-3 把 `legacy.write_text(` 换成 `pass` 后单跑该用例得 `MUTATION_EXIT 1`，才证明断言真依赖该前提。**同一条错误的另一端**：用例/检查器里**被检对象的根不得由 `__file__` 反推**，要走 `bin/lib/repo_root.py` 显式 resolver（写侧版本见「写路径要在调用时刻解析」）。
  - **④ GitHub「no checks reported」的第一因是 CONFLICTING，不是 `on.paths` 过滤**：`gh pr checks` 零输出时先跑 `gh pr view --json mergeable,mergeStateStatus` —— PR #4623 实测是 `CONFLICTING` / `DIRTY`，**冲突未解的 PR 根本不排队**。**判据搞混双向有代价**：把「冲突未解」读成「CI 放过我了」，或反过来把 `on.paths` 当万能解释 —— 注意 `.github/workflows/governance-check.yml` 的 `on.pull_request.paths` **不含 `tests/unit/**`**，那批文件**本地 pytest 是唯一证据**（与 §7「三个治理门禁」条里 `:118-127` 的显式白名单是同一事实的两个面），这是独立于冲突的第二件事。
  - **⑤ Bash 工具的 shell 是 zsh + 别名，Python 子进程拿的是另一套二进制**：实测 `type` 读数 `grep → rg`、`find → fd`、`ls → eza`、`cp → cp -iv`；而 `subprocess.run(..., shell=True)` 里是 `/usr/bin/grep`、`/bin/cp`（**别名不继承**）。四个已踩形状：`grep -iE "a|b"` 报 `unknown encoding`（rg 的 `-E` 是编码、`-r` 是 replace，都不是你以为是的那个）、`find … -name` 报 fd 用法错、`ls -lat` 报 `--time` 非法值、`cp` 对已存在文件打印 `overwrite …? not overwritten` 后 **rc=1 且目标逐字节未变**（不是静默成功，但那行消息看着像提示，容易被当成跑过了）。**纪律**：脚本化文件操作一律走 Python 或绝对路径二进制；**「脚本里跑得通」不等于「一行命令里等价」**；凡改动后断言没变，先用 sha 逐字节复核，再怀疑逻辑。零匹配计数断链另见 §11「管道计数命令零匹配断链」。
  - **⑥ 行号指针会随上一轮交付漂移，固化感知前先重跑解析**：本文件此前有两条指针写在 T10-221 基线上 —— `tests/unit/test_projection_reader_resolution.py:42` 与 `tests/unit/test_repo_root_profile.py:146`；T10-222 重写这两个文件后，`:42` 变成一行 `registry = next(...)`、`:146` 变成一段 TRUTH_DIR 注释，**断言本体分别移到 `:61` 与 `:174`**，而文档逐字未变、读起来依然权威。**纪律**：**优先写符号名（测试函数名 / YAML 键名 / 函数名），行号只作辅助**；引用行号前用 `git show origin/main:<path>` 取该行内容核一遍再落笔；交付时顺手修正发现的陈旧指针（本轮修正上述两条）。

---

## 8. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Python code | Targeted `uv run pytest` |
| kairon | `make test-diff` from `projects/knowledge/kairon` |
| gbrain | `bun test` |
| Cross-project | Targeted tests on every touched consumer |

If a test cannot run, report why and what risk remains.

---

## 8. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Prefer `make agent-workflow-closeout RUN_ID=<run-id>` for governed runs.
4. Mention files changed and checks run.
5. Do not create commits unless explicitly requested and confirmed.
6. **大任务后复盘+固化**: 教训写 memory + AGENTS.md (协议层) + hook (harness 层).

---

## 9. Architecture Standards (Agent 必读)

**场景卡生命周期** (5 级): `draft → shadow → assisted → supervised → routine`
- 标准: `.omo/standards/scene-card-lifecycle.yaml`
- 升级必须按顺序，shadow 需 3-sample，assisted 需 30-sample + calibration ≥ 0.6

**业务域** (5 域): `work` / `health` / `research` / `knowledge` / `governance`
- 标准: `.omo/standards/business-domains.yaml`

**维度系统** (12 维度): 治理维 4 + 业务维 7 + 新增维 1
- 标准: `.omo/standards/dimension-system.yaml`

**价值循环** (5 阶段): 信号感知 → 信号分类 → 旅程执行 → 价值记录 → 进化反馈
- 标准: `.omo/standards/value-loop-standard.yaml`

**架构校验**: `make architecture-check`

---

## 10. Harness 集成 (Phase 8)

- **Cockpit CLI**: `cockpit harness <command>` (12 子命令)
- **8 阶段 DAG**: `admission → spec → grill → dispatch → execute → verify → audit → accept`
- **Hook 层**: 6 个 exit 1 拦截点 (pre-commit)
- **GaC 规则**: 32 个强制/高优先级规则

```bash
python3 bin/gac/harness-compliance-check.py --report
cockpit harness compliance|full|status
```

---

## 11. Key Patterns & References

- **Historical patterns**: `.omo/_knowledge/patterns/` (P75, P91, P43, P71, P72, P78, etc.)
- **分支等价性判据**: 只用 **内容 diff** (`git diff origin/main...<branch>`)
- **动手前先查 main 是否已自愈 (PITFALL-GAT-006)**: claim/start 前先 `git fetch origin main` 并做内容等价检查 — 被改文件在最新 main 是否已含目标内容 (`git diff origin/main...<branch>` 是否为空/仅剩预期增量), `git log --oneline origin/main -N` 是否已有同类 PR. 多 agent 并发下修复目标可能已被其他 PR 达成 (total_bets #3099 / scene-cards #3097 两次复发); 已合入则放弃分支, 勿开 PR — 否则 PR 合并会回退 main 正确值.
- **PR CI lint fail 不一定是本 PR 引入 (PITFALL-COO-004)**: 子模块 pre-existing violation 同样会让主仓 PR fail. 验证: 1) PR diff 文件清单排除 gitlink 后是否触发 lint; 2) 近 5-10 个 PR 同 lint 都 fail = pre-existing; 3) rebase 到含子模块 bump 的 main.
- **cherry-pick 跨 base 重放带 parent reverse (PITFALL-COO-005)**: cherry-pick commit 到新 base 会反向删除 main 已合入内容. 跨 base 重放: `git show <old>:<path>` 拿文件 + 在新 base 重做, 不用 cherry-pick 当 commit. 跑后立即 `git diff origin/<base>..HEAD --name-status`, 出现 "D" 行立即 abort.
- **本地工作树 ≠ origin/main 状态 (PITFALL-COO-006)**: fetch 后没 reset, 工作树停留 fetch 前快照. "main 是不是这样" 判断, 先 `git fetch origin main && git reset --hard origin/main`; 或 `git show origin/main:<path>` / curl raw github, 不信本地工作树.
- **Resident Agent**: `make resident-status` | BOS: `bos://resident/*`
- **BCOS**: `make bcos-evolve` | `python3 bin/bc-os/evolution_engine.py --json`
- **ADR index**: `.omo/_knowledge/decisions/`

---

- **管道计数命令零匹配断链（2026-09-27 会话实证 ×3）**：`cmd | grep -c pattern && next` 在零匹配时 grep exit 1 直接断链（最重一次：两个债务登记文件从未提交、worktree 释放即丢失，#4498 重铸恢复）。纪律：`grep -c` 后接 `|| true`，或用 python 计数断言；**worktree 释放前必查 `git status --short` 确认交付物全部已提交**。
- **幽灵判定双检（2026-09-27, T10-01/T10-08 实证）**：声明契约的 source_ref 指向不存在脚本 ≠ 脚本不存在——commit-assist 在 `bin/` 根（声明写 `bin/gac/`）、SEC×2 被 `omo.cli lint` 覆盖。纪律：全库 `find bin -name "$(basename <声明脚本>)"` + `omo.cli lint --help` 双检后再定"幻影"，否则误删活测试/漏接线。
- **验收条款先实证通道行为（2026-09-27 实证）**：done_when 写"doc 指向 X"前先跑一次真实通道——ingest 的 canonical_path 是 `kos::default::<文件名>` 不保目录、gh pr list 分页会静默触顶。想象中的通道行为写进验收 = 埋假红/假绿。

## 12. 归档/收敛项目说明

- agora-dashboard 独立入口已收敛 (能力并入 cockpit/agora)
- (归档) hermes-console 与 dashboard_server 作为子应用挂载 (L3 入口能力收敛到 cockpit/agora)
