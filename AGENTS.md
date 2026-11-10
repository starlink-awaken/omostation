---
type: ssot
owner: governance-team
last_updated: 2026-11-10
last-reviewed: 2026-11-10
lifecycle: entry
status: active
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
   两份均为 `ACCEPTED`，但属于不同决定），guard: `tests/unit/test_repo_root_profile.py`.

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

- **`submit` 自 WP1 Wave B2 起是 proposal-only**：`bin/gac/gac-worktree.sh` 的 `_emit_managed_successor_proposal()`
  （定义 `:967`，打印 `MANAGED_SUCCESSOR_REQUIRED` 在 `:978`，`exit 2` 在 `:985`）在跑完门禁/子模块预检后
  只打印 `MANAGED_SUCCESSOR_REQUIRED` + `patch_digest` 然后 **`exit 2`**，**不 push、不开 PR、不调 integrate**。
  实证（2026-09-26，同一分支两次 submit）：两次都 exit 2，远端零效应。
  所以 **`exit 2` 不是拦截，是终态** —— 别把它读成"base 太旧、需要先造一个 successor"而白跑一轮 claim。
- `merge` 仍然可用，但它查的是"该分支已有 open PR"（`:1241-1244`，查不到就报 `先 submit 开 PR` 退出）。
  由于 submit 不再开 PR，**这句提示已失效**；真实前置条件是上面两行手动 push + `gh pr create`。
- `origin/main 前进 N commits` 的告警同理：它伴随 proposal 一起打印，不是要求你 rebase
  （本仓明确禁止用 rebase/merge/pull 吸收上游，见 `:966` 的 WP1 Wave B2 注释与 `:994` 的 typed 指令）。
  改动只碰文档且与上游无交集时，直接 push 即可。
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
  `governance-verify` 在 `governance-check.yml:260-261` 用 `fetch-depth: 0` + `submodules: recursive`
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

## 7. Common Pitfalls —— 索引（正文已分册至 [docs/pitfalls.md](docs/pitfalls.md)）

> 50+ 条历史实证避坑记录，**按时间追加、不重排**，跨处引用一律按**条首短语**定位（如「六类静默失效形状」「Bash 工具跑的是 zsh」），不要按序号。2026-11-03 起正文拆分至 `docs/pitfalls.md`（本节保留索引与新增规则）。新增条目**直接追加到 pitfalls.md 对应主题簇**，并在下表顺手登记条首短语。

### 主题簇速查（正文在 docs/pitfalls.md）

| 簇 | 覆盖 | 高频咬人条目（条首短语） |
|---|---|---|
| **判据/检测器自身的可靠性**（最大簇） | 扫源码的门禁必须自证 · 六类静默失效形状 · 判据报警先 print 原始行 · 解析失败退回空 · 计数含观察者（`log show` 自记 argv）· 抽样探测的覆盖面上限 · 按构造就绿 · glob 字符类陷阱 · YAML 能 parse ≠ 结构正确 · 写路径要在调用时刻解析 · 检测器的分类规则要与标记清单同源 · 仪器阴性先证其能跑（`2>/dev/null` 吞 rc=127 · 记录恒缺 ≠ 事件为零 · `os.walk` 不接 `onerror` 静默丢目录 · 双驱动污染「连续第 N 次」语义 · 未 authored 的调用按仪器故障处理 · 重复判据要过同一层 `$HOME` 展开 · `--diff` 与 `--check` 必须同口径 · cron 经 `/bin/sh -c` 展开 `$HOME` · 同一文件两套权威面要声明读数来源 · lane 范围判定排除已合并 commit · 检查的扫描面要等于被管面） · `lifecycle_state` 词汇对≠顺序对 · history 的 action 动词不是状态迁移 · 审批清单与落盘字符串出自两个函数 | 「Bash 工具跑的是 zsh」（word-splitting 塌缩 + PIPESTATUS + date %N 三连 + 别名替换 grep/find/ls/cp/ps/rm，其中 `ps -p` rc=2 与 `ps aux` 空表都能让存活判定假负）·「frontmatter UTC 时区」 ·「`2>/dev/null` 把「仪器根本没跑」洗成「零命中」」 ·「上一条「都不存在」是错诊」 ·「`git grep -E` 不认 `\b`」·「重复判据的 `$HOME` 盲区」·「`--diff` 与 `--check` 口径不一致」·「cron 经 `/bin/sh -c` 展开 `$HOME`」·「同一文件两套权威面要声明读数来源」 ·「静态分类 cron 暴露面必低报（暴露单元=导入闭包）」·「立案不进 seed_items」 ·「YAML 日期字段的装载类型才是契约」·「同口径必须单点」·「lane 范围判定排除已合并 commit」·「检查的扫描面要等于被管面」 ·「`git grep <rev>` 输出带 `rev:path` 前缀（按前缀分类会静默全 0）」 · 「往 YAML registry 插条目的脚本先 safe_load payload」 · 「panorama 镜像判据只在 CI 跑」 | · 「`lifecycle_state` 词汇对≠顺序对」 · 「history 的 action 动词不是状态迁移」 · 「审批清单与落盘字符串出自两个函数」（43 条里 33 条字面不同）· 「`rm` 别名 rc=0 而文件仍在」
| **测试与 host 状态** | hermetic 测试泄漏 host 状态 · 用例断言 host 运行态 · 判据不被任何 CI 路径跑 = 不存在 · closeout verify 断言共享主区 host 运行态 | 「memory 索引是硬容量」 | · 「closeout verify 断言共享主区 host 运行态」
| **根与 profile** | 根目录是参数 · 根有四类落点 · 运行时安装位 · XDG 状态根 · 两个根的写面收敛 · 声明 profile 后跑真实 sync · 模块级常量 import 时冻结 · 相对路径读契约必须声明根（读者按仓根读、job 按 profile 根写 ⇒ 两侧都「正确」） | 「根有四类落点」 | · 「job 全绿但读物冻 12 天」 |
| **git / 子模块 / worktree** | 并发 agent 分支隔离 · worktree 子模块与 remote 完整性 · 未初始化子模块 git -C 向上解析 · submodule-pointer 空转 · 扫描面 worktree 副本归一 · 规则接线检查对子模块检出敏感 · SKIP_SUBMODULE_INIT 仍跑 guard 全量对齐 · release 守卫在浅检出子模块假报未推 | 「未初始化子模块 `git -C` 向上解析」 · 「claim 浅 init 超时留空目录」 | · 「release 守卫在浅检出子模块假报未推」
| **交付与合并** | merge 脚本主区撞脏树 · mergeStateStatus（CLEAN/BLOCKED/DIRTY）· PR 工作流各条 · 悬空 commit 自愈判据 = 按新增行查成员 | 「mergeStateStatus」 ·「悬空 commit 自愈判据 = 按新增行查成员」 · 「script_baseline 读 committed HEAD」 |
| **工具链 / 环境** | Chrome GUI 自动化路线 · gbrain 只能用 bun run test · 生成物 CI 口径 ≠ 本地 · 本机代理造成 GitHub 读正常写失败 · macOS 27 缺 `/usr/bin/{rg,date,df,cat}` 与 `/bin/awk` · `log show` kernel 行的级别与开机会话可见性 · `du -sh` 量的是符号链接自身 · cron 的最小 PATH 不含 `/opt/homebrew/bin` | 「生成物 CI 口径 ≠ 本地」·「cron 的最小 PATH 不含 `/opt/homebrew/bin`」 |
| **跨机作用域 / 运行态平面** | `known_orphans` 是跨机并集（按本机删会回流）· registry 的主机维度（`hosts`，缺省=全部机器）· resident 两平面分裂（launchd 空转 + 双 ledger） | 「`known_orphans` 是跨机并集」·「registry 的主机维度」·「resident 两平面分裂」 |

### 当场会咬人的三条（进任何编辑会话前扫一眼）

1. **zsh word-splitting**：多值列表禁止 `VAR="a b c"; for x in $VAR` —— 只迭代 1 次；批量校验脚本收尾必打 `echo "expect=$N got=$n"`
2. **frontmatter UTC**：`last-reviewed` 不得晚于 UTC 当天，否则 gac-gate FAIL
3. **声明 ≠ 执行**：任何判据先问「锚定实现在哪」（详见 `.omo/_knowledge/patterns/p73-truth-driven-engineering-pattern.md`）

## 8. Testing Guidance

| Change Surface | Minimum Verification |
|----------------|----------------------|
| Documentation only | `make gac-local-gate` and diff review |
| Python code | Targeted `uv run pytest` |
| kairon | `make test-diff` from `projects/knowledge/kairon` |
| gbrain | `bun run test` from `projects/knowledge/gbrain`（分片并行 runner） |
| Cross-project | Targeted tests on every touched consumer |

If a test cannot run, report why and what risk remains.

---

## 9. Closeout Checklist

1. Review `git diff --stat`.
2. Run the verification appropriate for the change.
3. Prefer `make agent-workflow-closeout RUN_ID=<run-id>` for governed runs.
4. Mention files changed and checks run.
5. Do not create commits unless explicitly requested and confirmed.
6. **大任务后复盘+固化**: 教训写 memory + AGENTS.md (协议层) + hook (harness 层).

---

## 10. Architecture Standards (Agent 必读)

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

## 11. Harness 集成 (Phase 8)

- **Cockpit CLI**: `cockpit harness <command>` (12 子命令)
- **8 阶段 DAG**: `admission → spec → grill → dispatch → execute → verify → audit → accept`
- **Hook 层**: 6 个 exit 1 拦截点 (pre-commit)
- **GaC 规则**: 32 个强制/高优先级规则

```bash
python3 bin/gac/harness-compliance-check.py --report
cockpit harness compliance|full|status
```

---

## 12. Key Patterns & References

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
- **并发 agent 的 submodule update 周期会清空 worktree 内手动布置的检出（2026-10-14, BET-Y2Q4-T10-252 实证）**：post-checkout 守卫 `guard-submodules --fix` 对 pin 不一致的子模块执行 `submodule update --init --no-fetch`，该命令把「已存在但 gitdir 布局非标准」的检出当无效目录**先删后建**；网络受限时重克隆必失败留空目录，而并发 agent 的 claim/release 周期在每次 worktree add/checkout 都触发守卫 → 手动布置的检出被周期性清空（ptr-bump/ptr-bump2 两轮交付实证：`.git` 条目被删、空目录残留、remote-hygiene 报 origin 指向本地路径）。**判据**：worktree 内子模块检出目录被反复清空、且 `git submodule status` 对该路径报 `+` 或 fatal，先怀疑并发守卫而非自己的布置错。**纪律**：① 守卫只对**无 `.git` 条目**的路径执行破坏性 update --init，已存在且可解析的检出改非破坏性 `checkout <pin>`（本地有对象）或跳过 advisory（缺对象），任何情况不删除既有 `.git` 条目（INV-1/2/3/4，`tests/unit/test_gac_guard_submodules.py`）；② 门禁脚本按 `__file__` 解析仓库根，子模块解析走主工作区检出（稳定），gitlink 读 worktree index —— 交付不依赖 worktree 内物理检出；③ 滞留 gitdir 的 origin URL 要改回远端，否则 pre-push remote-hygiene 报「origin 指向本地路径」。

## 13. 归档/收敛项目说明

- agora-dashboard 独立入口已收敛 (能力并入 cockpit/agora)
- (归档) hermes-console 与 dashboard_server 作为子应用挂载 (L3 入口能力收敛到 cockpit/agora)

---

## 14. 自动化设计纪律（2026-10-25 固化）

> 来源：2026-10-24 对外部平台评估的结论——**只借纪律，不引产品**。以下三条在本仓规模内可执行；文末四项判定为过度设计，不进本仓。

### 14.1 纪律一：自动化拆成四类步骤，审批是阻塞步

每条自动化（workflow、定时任务、Agent 编排）都必须能标出下表四类步骤；确实不存在的类别要显式写「无」，不允许隐含。

| 步骤类型 | 职责 | 判据 |
|----------|------|------|
| 参照 (reference) | 取哪些输入、从哪个 SSOT/台账读 | 引用的路径或 registry 键可解析 |
| 判断 (judge) | 按什么口径得出结论 | 口径有出处（ADR/registry/文档），不写在 prompt 里 |
| 执行 (act) | 落盘、提交、发消息、改状态 | 副作用可回滚或可幂等重放 |
| 人工审批 (approve) | 人在执行前承认 | **阻塞步**：未承认则流程停在待确认，不得降级为事后通知 |

**反模式**：把审批做成「执行完再通知」或「PR 事后 review」——那是事后审计，不是审批步。

### 14.2 纪律二：一次运行落一条结构化记录

每次自动化运行产出一条记录，字段固定六个，缺值写 `null`，不省略键：

| 字段 | 内容 |
|------|------|
| `inputs` | 引用了哪些输入（文件路径、registry 条目、外部查询参数） |
| `basis` | 判断依据（口径与规则出处，如 ADR 编号、registry 键） |
| `approver` | 谁批准（人工审批步的执行者；无审批步写 `none`） |
| `result` | 执行结果（成功/失败、产物路径、变更摘要） |
| `duration_ms` | 耗时 |
| `model_usage` | 模型 id 与 token 用量（无模型调用写 `none`） |

**最小实现口径**：单条 JSON 落盘 + 一个查询命令即可（按日期分片，落在既有 state 面下），**不引入审计系统、不做导出**。合规签核类字段依赖机构内控，本仓不设。
**反模式**：留痕散在 git 历史、服务日志、投影产物与对话里，回溯每次都要人拼——那叫留痕，不叫可回放。

### 14.3 纪律三：领域实体与判准抽成独立文档，作为跨 Agent 共享语义层

- 领域实体（项目、厂商、指标口径）与判准抽成**独立文档**，多个 skill / workflow 引用同一份，**不写进各自的 prompt**。
- 首期只覆盖工作侧三类：**项目**、**厂商**、**指标口径**；不扩到个人域与知识演化域。
- 已有唯一 SSOT 的（如 `docs/project-registry.yaml`、`.omo/_truth/registry/**`）直接引用，不建平行副本；确需新建前先查是否已有等价 registry。

### 14.4 明确不做（四项）

| 不做 | 理由 |
|------|------|
| 把治理层单独做成产品层 | 治理已由 GaC / OMO / ECOS 承载，再加一层只增组织税 |
| 多级或按额度分级审批 | 服务于机构内控的分层授权；本仓单一 owner 决策，无分层对象 |
| 审计记录导出到合规系统 | 无监管报送义务，导出链路是纯负担 |
| FDE 式驻场交付 | 无外部客户交付场景 |

四项被提出时引用本节即拒；确需推翻走 ADR。

<!-- GaC-RULES-START -->
<!-- AUTO-GENERATED by bin/gac/gac-export-agents.py — do not edit manually -->

### GaC Rules Pointer

> SSOT: `.omo/_truth/registry/governance-checks.yaml::gac.rules`
> Full generated digest: `docs/generated/agent-gac-rules.md`
> Validate: `python3 bin/gac/gac-validate.py --gate` | Drift: `python3 bin/gac/gac-drift.py`
> Regenerate: `python3 bin/gac/gac-export-agents.py`

Do not paste the full rule inventory into `AGENTS.md`; keep this file as an operational pointer.

<!-- GaC-RULES-END -->
