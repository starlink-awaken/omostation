---
schema: md/v1
status: PROPOSED
lifecycle: spec
owner: governance-team
last-reviewed: 2026-09-26
type: ssot
id: ADR-0456
related:
  - ./0247-strategic-pivot-collab-first-physical-deferred.md
  - ./0129-state-projection-plane-phase3.md
  - ./0414-physical-multihost-tension-resolution.md
tags: [topology, profile, code-root, state-root, launchd, ledger]
---

# ADR-0456 — 同机双安装位：code_root / state_root 分离与 profile 收敛

- **Status**: PROPOSED（方向经 2026-09-26 plan 批准，本 ADR 待 principal 批准转 ACCEPTED）
- **Date**: 2026-09-26

## Context

`/Users/xiamingxing/Workspace` 同时承担**开发区**与**运行区**两个角色，因此开发动作直接打击
在跑的系统。2026-09-26 实测的耦合面：

| 事实 | 实测值 |
|---|---|
| `~/Library/LaunchAgents` 中指向 Workspace 的 plist | 43 / 56 |
| crontab 条目（每条前缀 `cd /Users/xiamingxing/Workspace`） | ~40，真源 `crontab.new` |
| 字面量 `/Users/xiamingxing/Workspace` | 1,699 处 / 501 文件 |
| 常驻进程正跑在工作副本上 | 20+（agent-tick-daemon、signal-poller、resident daemon、omo-mcp、agora daemon、runtime mcp_server、kos、aetherforge 网关…） |
| 生产 UI 承载方式 | `vite` dev server `:5173`（`projects/cockpit-ui/dist` 已构建） |
| 运行态数据体量 | `runtime/` 51M、`.omo` 106M |

危害模式具体且重复：`git worktree` 的分支切换会把正在被 daemon import 的代码从脚下换掉；
hook 与 cron 会改写 git 跟踪文件（`.omo/state/system.yaml`、`BRIEF.md`），使文档 PR 夹带生成态
（AGENTS.md §7，#4346 / #4359 实证）。

已定的用户约束：本机第二安装位（非容器、非第二主机）、渐进双跑逐批切换、状态连续迁移
（保持同一份历史）、运行时须常开且 tailnet 可达，并且**切换后开发环境也必须随时能起**。

最后一条决定本 ADR 的主轴不是"搬家"，而是**先把根参数化**。

### 已存在的 seam（本 ADR 是收敛，不是发明）

`bin/lib/repo_root.py:canonical_root()` 已按 `$OMOSTATION_ROOT → ~/Workspace → 报错` 解析，
其 docstring 记录了 2026-08-08 两起事故的共同根因："写机器级配置的工具必须用它，
不要 `__file__` 反推"，并给出判据：只读仓内文件 → `__file__` 跟随当前检出；写仓外机器级路径
→ 必须 `canonical_root()`。

`projects/omo/src/omo/omo_paths.py` 是唯一无视该 seam 的中心模块
（`WORKSPACE_ROOT = _MODULE_DIR.parents[3]`，`OMO_ROOT` / `TRUTH_DIR` / `STATE_DIR` /
`RUNTIME_OMO_ROOT` 全部由它派生）。另有 9 处各自重复计算事件 ledger 默认路径，
以及 2 个单元测试直接断言 `/Users/xiamingxing/...` 字面量。

**但这个 seam 的实际采纳率接近零**（2026-09-26 实测）：全仓只有 **1 个** live 消费者
（`bin/gac/install-watch-agent.py:18`），而当初强制该规则的 lint
（`bin/_archive/2026-09-20-b2-archive/machine-config-write-lint.py`，提示语
"是 → 改用 `bin/lib/repo_root.canonical_root()`"）已于 2026-09-20 被归档。
这就是它没能铺开的原因。所以本轮的工作除了"收敛"，还必须**留下一道比 BET 活得更久的守卫**
（回归测试，不是新的 `bin/` 脚本），否则同样的衰减会再发生一次。

## Decision

### 1. 两个根，一个 profile

- **code_root** 由 `__file__` 推导，跟随当前检出（worktree / 第二安装位 / 未来任意位置）。
  这是"开发随时可跑"的前提。
- **state_root** 由 profile 声明，落在仓外：`~/.local/state/omostation/<profile>`。
  与仓内 `runtime/AGENTS.md`"运行态可重建、不作为源码归档区"的既有约定一致，也符合 XDG。
- 契约只走环境变量：`OMOSTATION_ROOT`（已有）、`OMOSTATION_STATE_ROOT`、`OMOSTATION_PROFILE`。
  （`OMOSTATION_PROFILE` 是目标契约面，不是 B1 交付物：在出现第一个消费者（B3 服务注册 /
  B4 安装位）之前引入它，等于埋下第二个分叉。）
  已有的 `OMO_EVENT_LEDGER_DB`（canonical 名在
  `projects/omo/src/omo/sovereignty/enforcement.py`）、`OMO_STATE_FILE`、`.env.example` 的
  `VAULT_PATHS_*` 一律折进同一 profile，不并行第二套机制。

`canonical_root()` 升级为 code/state 双根解析。**只搬写侧**：`omo_paths` 的 `STATE_DIR` 与
`RUNTIME_OMO_ROOT`（以及事件 ledger）改挂 state_root，而 `OMO_ROOT` / `TRUTH_DIR` /
`CONTROL_DIR` 等 `_truth/registry/**` **读侧**继续挂 code_root —— 按 `repo_root.py` 自己的判据，
读仓内文件必须跟随当前检出；把读侧也移过去会让 worktree 从主仓解析治理真相，
那是没人要求的行为变更。未设置 profile 环境变量时，所有派生路径必须与改动前逐字节相同。

### 2. 运行时装在哪

代码安装位 **`~/Runtime/omostation`**：`git clone --local`（hardlink 对象）、
**独立 clone 而非 git worktree**、detached 在 release tag。

不做成 worktree 是硬约束：本仓每日自动清理例程 `make worktree-hygiene`（04:00，
`worktree-hygiene-audit.py --auto-clean --fail-on-unsafe`）与 `make worktree-prune`（04:30）
会波及登记进共享 `.git` 的 worktree。

裸放 `$HOME` 被否：`$HOME` 已是 agent 工作树倾倒场（`~/ws-sh53-exec`、`~/ws-t1069`，
其中一条 cron 直接 `cd ~/ws-t1069`），运行时与临时工作树平级混居迟早被"清理残留"扫掉；
macOS 默认卷大小写不敏感，不能指望 `~/runtime` 与 `~/Runtime` 区分，且
`projects/runtime/scripts/service-ctl.sh` 已把 `$HOME/runtime` 当旧约定引用。

### 3. dev 可随时跑且不双写

dev profile 默认起自己的空 store；生产 ledger 只有 prod 一个写者。需要真实数据时显式取
只读快照（`sqlite3 ".backup"` → `~/.local/state/omostation/dev/ledger-snapshot.sqlite3`，
非权威、名字带来源 seq）。**不共享文件** —— `fcntl` 锁按路径生效，同机两实例若指向同一文件
会互相争用，指向不同文件则完全没有互斥。

跨实例并发保护三层（按可靠性排序）：launchd label 命名空间（`services.yaml` 每条已有显式
`label:`）→ 端口段（`protocols/port-registry.yaml` 已有 `types: {…, …: env-only}` 先例）→
ledger 内的 single-writer 声明行。

**git 写权限只给 prod**：dev 侧 `OMO_ALLOW_GIT_WRITE=0`。两个会自动 commit 的 cron
（capability-registry 04:05、`check-mcptool-impl-drift.py --report` 05:45）在 dev 下退化为
只写 state root。否则双实例会在生成文件上互相回滚 —— 这不是用 flock 能解的问题。

### 4. 生成态出库（收尾 ADR-0129）

`.omo/state/system.yaml`、`health.yaml`、`BRIEF.md`、`.omo/_knowledge/retros/resident/*.md`
当前既是跟踪文件又被 cron 改写。修法沿用已批准机制：
`.omo/_truth/registry/runtime-projections.yaml` 已把它们登记为 canonical `.omo/state/runtime/*`，
且 `.gitignore` 已忽略该目录；`omo_paths.projection_path()` 就是规定入口。本 ADR 只要求
"把剩余消费者接进去 + 从跟踪中摘除"，配套读取方（`meta-doctor.py`、`evidence-smoke.py`、
`compass_radar.py`、`generate-brief.py`、`doc-ssot-lint`）改用 `projection_path()`
并在 dev 侧回退到最后一次提交的快照。

`.omo/_truth/registry/**` 保持跟踪 —— 那是权限声明，不是运行态。

### 5. 安装位防呆

搬迁落位后必须同步：把安装位写进 `bin/lib/repo_root.py` 的解析序，并加入
`worktree-hygiene-audit.py` / `gac-branch-prune.sh` 的排除清单。

### 6. 三个离群项直接定性

- **`~/.local/share/zhixing-dashboard`（142M，自带 `.git`）**：声明为**外部依赖**并给契约，
  不并入主仓（实测已有 16 个子模块，并入 = 白多第 17 个）。契约 = registry 条目锁 repo+SHA、
  `ZHIXING_DASHBOARD_ROOT` 环境变量、`check-signals` 里加 `/health` 探针。
- **`vite` dev server 当生产 UI（`:5173`）**：就地消灭，不是搬迁。`package.json` 已有
  `build: tsc --noEmit && vite build` 且 `dist/` 已构建 —— 生产走静态构建，vite 降级为
  dev-profile 专用进程。这是全部清单里最站不住脚的一条。
- **`.omo/cron/registry.yaml` 的 24 处主机字面量**（以及断言它们的
  `tests/unit/test_agent_cell_scheduler.py` 5 处、`tests/unit/test_panorama_runtime_scheduler.py`
  8 处）：该 registry 是**已安装 launchd job 内容的真源**，改它属于 B3 服务注册面（有集合
  相等门禁），不属于 B1 根解析面。B1 只把它们记为已测量的危害证据。

### 7. B1 执行期实测出的两个例外（决定后续分期归属，写在这里以免重新考古）

- **`bin/panorama/panorama-collect.py` 不能接 seam** —— 三条实测理由：① 它的根由
  `PANORAMA_ROOT` 决定，两个已安装 plist 都会注入该变量，与 `code_root()` 的 `__file__`
  推导不是同一个根；② 它按**单文件**部署在检出之外（`~/.local/share/…`），在那里
  `from repo_root import …` 会在启动即失败；③ `docs/plans/3y-bet-ledger.yaml` 有一条
  `cmp` 逐字节比对把它与 `bin/panorama/assets/host/panorama-collect-main.py.asset` 绑死，
  改它必须同步改 `.asset`，那已不是根解析面。它本身已经优先读 `OMO_EVENT_LEDGER_DB`，
  所以这是"不接 seam 但契约成立"的唯一合法形状。B1 交付 **8/9**。
- **治理内核自己有 31 处主机字面量根解析（17 文件）**：`projects/omo/src/omo/**` 用
  `os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))` 自己算根，其中
  `event_ledger/surface.py` 与 `sovereignty/enforcement.py` 两处是 ledger 默认路径。
  而生产 ledger 写者 `bin/ssot/scene-outcome-recorder.py`（SH-5 证据桥）**只**经
  `omo.event_ledger.surface._resolve_db_path()` 到达 ledger —— 转换它等于改变受治理证据
  的落盘位置（worktree 驱动的 closeout 会写去别处），属人类拍板范围，B1 不动。
  推荐替代：由**生产者**显式声明 `OMO_EVENT_LEDGER_DB`（launchd/cron env 注入），把
  内核 fork 留给 B3 服务注册面收口。

## 明确否掉的方案

| 方案 | 否掉的理由 |
|---|---|
| 容器化 | 根 `docker-compose.yml` 是 `services: {}` 空壳，只有零散单服务镜像；20+ 常驻 daemon 与 launchd 生命周期不匹配 |
| 第二台主机 | ADR-0247 ACCEPTED 将物理多机达标 DEFERRED（不设时间表、不占预算）；ADR-0418 对外扩展默认不做 |
| `/opt/omostation` | 这些是**用户域** launchd job，root 拥有的代码由用户 daemon 执行，每次更新都要 sudo → 必然被绕过 |
| 独立 macOS 用户 | 隔离最彻底，但现在做会打断 `~/.claude/LIFEOS`、`config/security/vault.yaml`、`~/.hermes` 与"单主机 flock"全部前提。列为日后选项，不进本轮 |
| 新造 profile 机制 | `repo_root.py` 的 seam 已存在且已确立正确判据（code/state 之分），工作是采用并加固它，不是发明第二套 |

## 与 ADR-0247 的正交性

ADR-0247 DEFERRED 的对象是**物理多机达标**（跨主机部署、主机可达性测量、物理底座周提醒）。
本 ADR 是**同一台主机上的第二个检出**，不新增主机、不宣称物理多机达标、不改 D4 四项的
"须人类逐项拍板"状态。ADR-0414 对 0225/0226 的 G-DEL.1 口径（`reachable_physical_hosts`
实测 2 < min 4，deferred 期间语义降级为 parked）不受影响 —— 本 ADR 不改变主机计数，
也不把 parked 读成 unblocked。

## 与 BET-Y1Q3-T1-08 先例的冲突与消解

本仓有一条 **done** 的 BET 与"独立 clone 部署"方向相反：
`BET-Y1Q3-T1-08`（"退役 coordination-daemon 独立 clone 部署并迁移备份到 Workspace"，
goal 明写"消除旧代码版本污染运行时 truth 的风险"）。必须先回答它，否则本 ADR 是在重犯
一个已经拍过的错。

那次问题的性质是**无版本锚点、无人管理的陈旧 clone**：clone 静默跑旧代码，运行时 truth
被旧版本污染，且没有任何机制发现。ADR-0419 记录的"独立 clone 拓扑"本身是被当作
已就绪基建承认的 —— 被否的是失控的 clone，不是 clone 这个形态。

因此本 ADR 把消解条件写成硬要求，而不是留作实施细节：

1. **版本锚点**：安装位 detached 在 release tag，dev 与 prod 钉同一 tag；
   `git describe` 不一致即告警（进 CI，不靠人记得）。
2. **集合相等门禁**：`services.yaml` registry 集合 == 已安装 launchd label 集合
   （`gen-service-configs.py --check` exit 0），配合 `meta-doctor` launchd 现实核对。
   这是发现"静默跑旧代码"的唯一可靠机制。
3. **中止判据**：做不到第 2 条就不做搬迁（B4 停在 B3 之后）。带 20 个无人管理的 plist
   做半程切换，严格比现状更糟。

## Consequences

**得到**

- 开发动作（checkout / worktree claim / hook 重写）不再打击在跑的系统。
- `git worktree` 的分支切换从"运行时事故"降级为"仅影响 dev"。
- AGENTS.md §7 的"生成态随文档 PR 漂移"老坑变成**结构上不可能**。
- 自算 ledger 路径从 9 处重复定义收敛到 1 个解析入口（8 处接 seam + 1 处单文件宿主例外，
  见 §7），并留下回归守卫防止再次衰减。

**代价与风险**

- 双实例可能抢写 ledger → 靠 seq 连续性检查 + 既有 `REASON_LEDGER_UNAVAILABLE` fail-closed。
- "dev 能跑"可能退化成 dev/prod 漂移 → verify 在两个 profile 上各跑一遍进 CI；
  dev 钉在同一 release tag，`git describe` 不一致即告警。
- 漏改的 plist 会永远跑旧代码 → 服务 registry 与已安装 label **集合相等**门禁 +
  `meta-doctor` launchd 现实核对。
- agent 误写 prod 状态 → 进程启动时 `state_root != profile 声明` 直接硬退出。
- 跨安装位 import 错包（venv `.pth` 装的 workspace 副本会赢过 worktree）→
  启动断言 `omo.__file__` 落在期望 code_root 下。
- **内核侧根解析仍是分叉的**（§7 第二条，31 处 / 17 文件）：B1 之后 `bin/` 读 profile，
  `projects/omo` 内核仍读 `WORKSPACE_ROOT` 字面量默认值。收口路径二选一 —— 要么转换内核
  （改变受治理证据落盘位置，须人类拍板），要么由生产者在 launchd/cron env 里显式声明
  `OMO_EVENT_LEDGER_DB`（B3）。在此之前"dev profile 完全隔离"只对 `bin/` 消费者成立。

**分期（每步独立有价值、可各自回滚）**

| BET | 交付 | 完成判据 |
|---|---|---|
| B1 | profile 收敛（双根 + 8/9 处 ledger 常量 + 回归守卫；第 9 处 panorama 单文件宿主按 §7 例外） | dev profile 运行只写 dev state root；未设 profile 时逐字节同今天；`bin/` 内自算 ledger 默认路径归零（守卫测试拦截回归） |
| B2 | dev 端口段注册；UI 改走 `dist` | prod 全量在跑时本地 gate 绿，未注册端口 0 |
| B3 | 未登记 label 回填 `services.yaml`；label 加 profile 前缀；`.omo/cron/registry.yaml` 去主机字面量化 | `gen-service-configs.py --check` exit 0 且 registry == 已安装集合 |
| B4 | 安装位落地 + `.backup` 状态迁移 + 分批切 cron/plist | `PRAGMA integrity_check` ok；ledger 哈希链迁移边界无缺口；指向 Workspace 的 plist 归零 |
| B5 | 生成态摘库（走 ADR-0129 canonical 路径） | 一次 dev 运行后 `git status --short .omo/state` 为空 |

**中止判据**：B3 若做不到 registry == 已安装集合，**停在 B4 之前** —— 带着 20 个无人管理的
plist 做半程切换，严格比现状更糟。

搬迁成本在代码与 per-submodule venv，不在数据（`runtime/` 仅 51M）。
B1→B2→B3 完成后，B4 本质是 `launchctl bootstrap` 换路径：
`bin/ssot/install-resident-cron.sh` 已用 `BASH_SOURCE` 自推 WORKSPACE，从安装位跑它
就得到安装位的路径，不需要重写 40 条 cron。
