---
schema_version: specification/v1
spec_version: 1.0.0
title: E7 —— 服务注册表现实核对补上「写根」轴（observe-only）
bet_id: BET-Y2Q4-T10-272
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-26
---

# E7 —— 服务注册表现实核对补上「写根」轴

> ADR-0456 B4b 的验收条款「指向 `Workspace` 的 plist 由 43 → 0」在仓库里**没有尺**。
> 本轮补一把只读的尺，不改任何 plist。

## 1. 证据：六桶里没有「写到哪」这件事

`bin/mof/gen-service-configs.py` 的 `--reality-check` 现有六个桶：E1 argv 漂移、E2 装了未声明、
E3 lint 债、E4 分区不闭合、E5 声明未装、E6 入口脚本**内核**钉的根。其中唯一与「根」有关的是
E1 与 E6，二者比较的都是**码面**（argv 与 wrapper 里的 `--project`），没有一个桶读
`EnvironmentVariables`。

2026-10-26 本机实测（`~/Library/LaunchAgents`，81 份 plist）：

| 读数 | 条数 |
|---|---|
| 执行根 = 检出（argv 或 WorkingDirectory 含 `/Users/xiamingxing/Workspace`） | **30** |
| 执行根 = 安装位（含 `.local/opt/omostation`） | **8** |
| 执行根 = 其他（外部程序、纯脚本包装） | 43 |
| 上述 8 条里，`EnvironmentVariables` 仍把根钉回检出的 | **8** |

最后一行是本轮的动机：`com.l4.resident.execute.plist` 的 argv 已改到
`~/.local/opt/omostation/lib/resident-role-tick.sh`，而它的 env 是
`{'OMOSTATION_STATE_ROOT': '/Users/xiamingxing/Workspace'}` —— 码在安装位、**写在检出**。
按 `bin/lib/repo_root.py` 的解析序，这 8 条中的常驻族 6 条把运行态写回开发工作副本，
正是 ADR-0456 §Context 要切断的那条耦合。

**覆盖面边界（2026-10-26 实跑读数，不是上表的 8）**：E7 的枚举对象是**注册表里声明了
`runtime_root` 的 launchd 条目**，今日 6 条（常驻族，BET-Y2Q4-T10-265 声明）。上表那 8 条里的
`com.cockpit.dashboard` 与 `com.omostation.zhixing-projection-fullrefresh` 虽然执行根也在
`~/.local/opt/…` 之下，却在注册表里**没有** `runtime_root: install` 声明（cockpit 走
`generate: false` + 自己的 release-worktree 机制），所以 E7 不点名它们。这不是漏判：
判据一律来自注册表内容，不来自机器扫描 —— 否则就又回到手工数 plist。差额 2 条的处置属于
B4b 批次 2+ 的注册表回填，不在本轮。

而 E1 对此**结构性失明**：`runtime_root` 字段的语义覆盖 entrypoint / watch_paths / outputs
三类相对路径，env 面不在其中（`gen-service-configs.py:183`）。所以「E1 保持 0」这句话
对写根轴没有任何含义 —— B4b 批次 2+ 的验收至今靠人手工数 plist。

## 2. 约束（照 E6 定过的三条，不新造机制）

1. **纯观测缺省**：E7 的 findings 只在服务条目显式声明准入键时产生。缺省读数为
   「报了分类、不报警」，与 E6 的 `require_kernel_root_match` 同形（`:187-195`）。
   今日 6 条命中项一条都不升级 —— 改道是 principal 的逐批授权面（AGENTS.md §7
   「运行根选择器必须是注册表内容」条），本轮没有授权碰 plist。
2. **准入键只接受 `true`**：`require_state_root_partitioned` 挂在 `runtime_root` 已声明的条目上，
   写 `false` 是给「缺省即不声明」造第二个真值来源（`gen-service-configs.py:88` 的原话）。
3. **装置复用既有计算点**：`enumerate_launchd_plists()` 已把整份 plist 序列化进
   `row["blob"]`（`:443`），env 从 blob 解析即可，不改枚举器、不新开一次 `plutil` 调用。

## 3. 分类判据

对每条 `scheduler: launchd` 且声明 `runtime_root` 的服务，读本机那份 plist 的
`EnvironmentVariables`，按 `repo_root.py` 的实际解析序归入五态：

| state | 条件 | 含义 |
|---|---|---|
| `profile` | `OMOSTATION_STATE_ROOT` 落在 `~/.local/state/omostation/<profile>` 之下 | 写面已进 XDG profile 根 |
| `checkout` | `OMOSTATION_STATE_ROOT` 等于检出根 | 码已改道、写未改道（本轮实测的形状） |
| `install` | `OMOSTATION_STATE_ROOT` 等于安装位根 | 写面落在安装位（不是 XDG，也不是检出） |
| `undeclared` | 无 `OMOSTATION_STATE_ROOT` 键 | 写根由 `code_root()` 兜底决定，即跟随该进程实际加载的检出 |
| `undetermined` | 本机没有该 label 的 plist（未安装） | 不可判定；与「装了但没写根键」不得同形（AGENTS.md §7「目录缺席与目录为空同形」同族） |

`undeclared` 不算违规：它是未声明 profile 的合法历史形状（`state_root == code_root`
的不变量由 `tests/unit/test_repo_root_profile.py` 钉住）。`undetermined` 计入未分区一侧
（未安装就无法证明写面已分区），但安装缺口本身由 E5 点名，E7 不重复报。E7 只把「声明了
`runtime_root: install` 却把写根钉回检出」这一条形状视为需要准入才报警的形状。

## 4. 不在本轮

- **不改 plist、不 bootout/bootstrap、不动 crontab** —— 机器级写面，B4b 批次 2+ 逐批授权。
- **不引入 `OMO_ALLOW_GIT_WRITE`**（决策 3，同一授权面，7 份 spec 一致记为逐批授权）。
- **不动 E1–E6 的判据本体**，只新增桶与返回值字段。
- 不把 6 条命中项登记成 known-debt：它们是 B4b 待执行的工作项，不是门禁债。

## 5. 验收

- V1 正向落点：合成一份「argv 指安装位 + env 钉检出」的 plist，E7 必须点名它且分类为 `checkout`。
  （AGENTS.md §7「每条『移走某个写目标』的契约都要配一条正向落点断言，且先跑一次再写进契约」）
- V2 反证：删掉分类段 ⇒ V1 用例红。
- V3 空转自证：注入一条 `require_state_root_partitioned: true` 的合成条目 + 钉检出的 plist ⇒
  findings 点名 E7；不加准入 ⇒ findings 不含 E7（今日真机读数）。
- V4 真机读数随交付走：`--reality-check --json` 在 `runtime_root` 声明面给出
  `e7_checkout = 6 / e7_profile = 0 / e7_blocking = 0`（6 = §1 覆盖面边界那条的注册表读数，
  不是 host 扫描的 8）。`ok` 不因 E7 变 false：`ok=false` 由 E4 的未分区 label 与 E5 的安装缺口
  决定（E7 前后同值），findings 里不含 E7 前缀。2026-10-27 在 base `616c07338` 上的读数是
  E4 19 条、E5 声明未装 2 条 + 禁用仍装 1 条 —— 这两个桶的条数随注册表与本机现实而变，
  不是 E7 的契约内容。
- V5 分类可穷尽：返回值 `e7_states` 按实测 state 聚合，且
  `sum(e7_states.values()) == len(e7_state_root)`。只列三个命名项的人读行会把 `undetermined`
  算进「未分区」却不在分类里出现 —— 与 AGENTS.md §7「目录缺席与目录为空同形」同族。
- V6 schema 准入：`require_state_root_partitioned` 未声明 `runtime_root` 时报违规；写 `false` 时报违规。
