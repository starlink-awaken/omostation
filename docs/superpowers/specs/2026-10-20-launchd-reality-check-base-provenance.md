---
schema_version: specification/v1
spec_version: 1.0.0
title: launchd 现实核对必须自报测量基座
bet_id: BET-Y2Q4-T10-262
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-20
---

# launchd 现实核对必须自报测量基座

> 契约对象：`bin/mof/gen-service-configs.py` 的 `--reality-check` 输出面。
> 上游：ADR-0456 风险表「漏改的 plist 永远跑旧代码 → 检测 = B3 集合相等门禁 + launchd 现实核对」；
> 判据实体 = 同一工具的 `e2_undeclared` / `owned_declared` / `owned_installed` 三键。

## 1. 缺陷形状（改前实测，2026-10-20）

同一台机器、同一个小时内的两次 `--reality-check --json` 读数不一致：

| 测量根 | `registry_declared_total` | `owned_declared` | `owned_installed` | `e2_undeclared` |
|---|---|---|---|---|
| 规范工作区检出（本地 main 落后 `origin/main` 29 个 commit） | 70 | 42 | 47 | **5** |
| `git archive origin/main` 造的对照树 | 75 | 47 | 47 | **0** |

差的 5 条 label 全部是 T10-246/253/258 三轮已合入 `origin/main` 的 observe-only 登记。
即：**这台机器上并没有 5 条漏登记的服务，是这份检出在读一份旧的注册表**。

工具本身没有错——它按 `canonical_root()` 读当前检出的 `.omo/_truth/registry/services.yaml`，
这正是 ADR-0456 的双根契约规定的读面。错的是**输出面里没有任何字段说明它读的是哪一棵树**：
22 个键（改动前）里有安装侧计数、有注册表侧计数，独独没有基座。于是两条读起来完全同形的结论——
「注册表落后于本机现实 5 条（真债，需署名准入）」与「测量装置落后于远端 29 个 commit（假债）」
——在 `--json` 输出里**不可区分**。本仓 §7 已把这类「装置面读到 host 面」列为反复致错源，
而这里更糟：塌缩的正是 B4b 分批切换唯一依赖的那张安全网。

## 2. 契约

`reality_check()` 的输出增加一个键 `measured_base`，值为一个对象，字段固定为：

| 字段 | 含义 | 取不到的时候 |
|---|---|---|
| `registry_file` | 实际读到的注册表路径，相对其所在检出根呈现（不含 host 字面量） | 不可能取不到（本函数入口即它） |
| `registry_sha256` | 该文件字节的 sha256 前 12 位 | 同上 |
| `head` | 注册表所在检出 `git rev-parse HEAD` 短 SHA | 该文件不在任何仓库里 → `null` |
| `origin_main` | 注册表所在检出 `git rev-parse origin/main` 短 SHA | 该 ref 不存在（干净 CI 检出、对照树）→ `null` |
| `base_state` | `equal` / `behind` / `diverged` / `unknown` 四值之一 | ref 不可解析一律 `unknown`，**不得**折算成 `equal` |
| `behind_count` | 该检出 `HEAD..origin/main` 的 commit 数 | 不可解析 → `null` |

**基座跟注册表走，不跟调用方给的根走**（2026-10-20 实现时自证出的缺陷）：第一次接线把 git 事实
取自 `workspace_root or workspace()`，而 worktree 里跑 CLI 时 `workspace()` 解析到 canonical 检出
—— 于是拿 canonical 的 HEAD 去标注 worktree 的注册表，自报的基座本身就是假证词。同一轮实测读数：
worktree 侧 `HEAD=69e68494e`，而那次打印的 `HEAD=fdb106c9f`（canonical main，落后 31）。
判据由此收紧为两条，且各有用例钉住：注册表在仓库内 ⇒ 报那棵树；注册表在仓库外
（`--registry /tmp/x.yaml`）⇒ `unknown`，**不退回任何猜测的根**，宁缺毋假。

三条硬约束：

1. **零判定效应**：`measured_base` 是纯观测面。`ok`、`findings`、`e1_*`…`e5_*` 的取值
   与 `measured_base` 的内容**无因果**——基座陈旧本身不是仓库缺陷，分支工作树与对照树上
   `HEAD != origin/main` 是常态。把它做成 finding 会让这张门禁在每一个合法工作树上常红，等于用噪声换掉一个信号。
2. **不扩根**：基座只描述**当前测量根**这一个事实，不引入新的根、新的 env 名、新的 profile 概念。
   ADR-0456 的定位链仍是 `OMOSTATION_ROOT → canonical 检出 → 报错` 三条。
3. **不读运行面**：本函数照旧只读 `~/Library/LaunchAgents` 与注册表，不写、不 `launchctl`、不 `plutil -e`。

人类可读输出增加一行，把 `base_state` / `head` / `origin_main` / `registry_sha256` 打出来；
`--json` 面是权威面，那一行只是同一对象的呈现。

## 3. 非目标

- 不同步任何检出、不调用 `bin/gac/sync-main.sh`、不做 `git fetch`/`reset`。本轮修的是**报告面**，
  不是机器状态；本地 main 落后 29 个 commit 属主工作区运维，由 Principal 决定。
- 不改 `workspace_prefixes` / `exempt_labels` / E1—E5 任何判据本体，不替任何 label 决定「该不该活」。
- 不回填 E4 的 19 条未分区项与 E5 的 2 条署名项（准入清单已由 T10-259 交付，仍待 Principal）。
- 不把 `--reality-check` 接进 `ci-surfaces.yaml` / `governance-checks.yaml`（注册新门禁改变
  「门禁是否执行」，属 Principal 决策，同 T10-207 记的边界）。
- 不宣布 ADR-0456 B1/B3/B4/B5 或整个 plan 完成。

## 4. 判据（正向落点，先跑再写）

- C1 `reality_check()` 返回值含 `measured_base`，六字段齐；`base_state ∈ {equal, behind, diverged, unknown}`。
- C2 零判定效应用**同一次调用**证明：注入不同 `measured_base` 的两次调用，
  `ok` 与 `findings` 逐字相等。
- C3 假债可指认：同一份「本机现实」分别对「少了 N 条登记的旧注册表」与「完整注册表」跑一次，
  两次 `e2_undeclared` 不同，**且两次 `registry_sha256` 也不同**——即消费方仅凭输出即可判定
  这是基座差异而非机器差异。这是本 BET 的牙齿。
- C4 无 git 环境不炸：测量根不是 git 仓库时 `head/origin_main/behind_count` 为 `null`、
  `base_state=unknown`，`ok` 不受影响（复刻 `git archive` 对照树与 CI 干净检出两类装置面）。
- C5 注册表字节改动必须体现在 `registry_sha256` 上（改一行 → 摘要变），钉住「它测的是那份文件」而非别的。
- C6 `registry_file` 相对呈现，不含 `/Users/` 字面量（本仓 tests 与文档刚做完去 host 字面量两轮）。
- C7 注册表在检出 A、`workspace_root` 指向另一棵树 B ⇒ `head` 必须是 A 的，不是 B 的（假证词面）。
- C8 注册表在仓库外而 `workspace_root` 在仓库内 ⇒ `unknown` + `head/behind_count` 为 `null`
  （不许退回调用方的根凑基座）。
- 变异对照：把 C3 用例里的两次注册表内容改成一致 → 该用例必须当场红（证明断言真依赖基座差异，
  而不是恒绿）。实现轮实测九个变异体，每个都由点名它的用例杀死：
  `M1` 拆掉 return dict 接线（12 红）、`M2` 让 `behind` 产出一条 finding（C2 红）、
  `M3` 摘要改对路径而非文件字节（C3/C5 红）、
  `M4` `registry_file` 一律绝对（C6 点名用例红，另 `test_equal_when_head_is_origin_main`
  与 C7 用例同时红 —— 实测 3 failed / 29 passed，复原后逐字节相同再测 32 passed）、
  `M5` `base_state` 去掉 `not ahead`（新增的「两侧都前进」用例红 —— 原用例集杀不掉它，
  因为 `diverged` 样本 `behind=0`，落在判别式的同一侧）、`M6` ref 缺失报 `equal`（C1/C4 红）、
  `M7` 摘要给全 64 位（C5 红）、`M8/M8b` git 事实退回或改用调用方的根（C7/C8 红）。

## 5. 改前基线读数（本 BET 的对照面）

| 量 | 改前 |
|---|---|
| `--reality-check --json` 键数 | 22（无基座字段，实测 A/B：`len(r_old)==22`） |
| 规范检出（stale）`e2_undeclared` / `owned_declared` / `owned_installed` | 5 / 42 / 47 |
| `origin/main` 对照树同三键 | 0 / 47 / 47 |
| 本地 main 相对 `origin/main` | 落后 29（HEAD 龄 32.8h vs 0.2h） |
| 本机 `~/Library/LaunchAgents` plist 总数 | 77（两侧读数一致，证明机器侧零变化） |

改后期望：22 键 + `measured_base` = 23 键（实测 A/B 唯一新增键）；三键读数与 E1/E3/E4/E5 findings 逐字不变（本轮不触碰判定）。