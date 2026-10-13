---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 §风险与检测 —— B1–B5 的 verify 在两个 profile 上各跑一遍进 CI（STATE_ROOT 双根 + install_root 落后即告警）
bet_id: BET-Y2Q4-T10-248
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-13
---

# 双 profile verify 腿 —— 让「dev 能跑」不再退化成 dev/prod 漂移

## 0 需求出处与本轮实测到的三条前提修正

`docs/plans/3y-bet-ledger.yaml` 所属方案 `§风险与检测` 有一行检测：

> 「dev 能跑」退化成 dev/prod 漂移 → B1–B5 的 verify 在**两个 profile 上各跑一遍**进 CI；
> dev 钉在同一 release tag，`git describe` 不一致即告警

本轮（2026-10-13，全部为实测读数，非回忆）把这句话拆成「可实现的一半」与「按字面不可实现的一半」：

| 前提 | 实测读数 | 后果 |
|---|---|---|
| `OMOSTATION_PROFILE` 是 profile 开关 | **零消费者**。`bin/lib/repo_root.py` 只读 `OMOSTATION_STATE_ROOT`（`:48`）/ `OMOSTATION_ROOT` / `OMO_EVENT_LEDGER_DB` / `OMOSTATION_INSTALL_ROOT`；该 env 在 `bin/` 里唯一出现处 `bin/ssot/check-hardcoded-ports.py:239` **刻意不读它**（注释写明首个消费者本应是 B3） | 以它建 CI 腿 = 造一个按构造就绿、不改变任何解析结果的假门禁 |
| B3 已消费 `OMOSTATION_PROFILE` | 未消费。`.omo/_truth/registry/services.yaml` 的 8 处 `profile` 全是 `bos://persona/health-profile/*` URI，与运行 profile 无关 | 同上；`--profile dev|prod` 至今只是 `check-hardcoded-ports.py` 的 CLI flag，不是 env 面 |
| 本仓有 release tag 序列，可用 `git describe` 比对 | 有 487 个 tag，但**没有 release 序列**（`BET-Y1Q3-T1-13`、`_probe_rootstart`、`a2-resident-status-purity-child-*` 混在一起）。`git describe --tags` 在 code root 给 `bet/Y2Q2-T5-01-…-596-gdf9457d1d`，在 install root 给 `…-284-g1b5f02cb3` —— **今天就不一致**，且原因与 profile 漂移无关 | 「describe 不一致即告警」按字面接上线就是永久噪声；须换成同义的仪表 |
| 运行时安装位不落后 | `~/.local/opt/omostation` 在 `1b5f02cb3`，是 `origin/main` 的**祖先**（`merge-base --is-ancestor` rc=0），落后 **312** 个 commit | 这正是 `§风险与检测` 另一行「漏改的 plist 永远跑旧代码」的现实实例，可测 |

据此，按主用户裁定（2026-10-13）落 **STATE_ROOT 双根 + 落后即告警**：忠于该检测的意图（抓 dev/prod 漂移与陈旧运行时），
仪表换成实际被消费的旋钮与被 git 证明的祖先关系。**不改发布基建、不打 tag、不动 launchd。**

## 1 交付面

`bin/gac/dual-profile-verify.py`（新增）—— 一次调用把「声明的写面生成器」在**两个不同 state 根**下各跑一遍，
并对每一条腿做**正向落点断言**：

```
env -u OMOSTATION_ROOT -u OMO_EVENT_LEDGER_DB \
    python3 bin/gac/dual-profile-verify.py --profiles prod,dev --json
```

`prod`/`dev` 是**标签**，不是新的 env 面。每条腿的 root 按此顺序解析：`--root <label>=<绝对路径>` 显式覆盖 →
否则取 `OMOSTATION_STATE_ROOT/<label>` 子目录（已声明时）→ 否则 `tempfile.mkdtemp(prefix="dual-profile-<label>-")`。
**默认必须是每次新建的 scratch root**：`~/.local/state/omostation/{prod,dev}` 已住着 B4b 批次 1 的在线备份快照与
`*.provenance.json`（AGENTS.md 记为「都不是权威」），把生成态写进那两个真目录会污染机器级状态面；
scratch 默认同时让本腿在无 XDG 的 CI 干净检出上可跑。脚本对每条腿**自己注入** `OMOSTATION_STATE_ROOT`，
并剥掉 `OMOSTATION_ROOT` / `OMO_EVENT_LEDGER_DB`（否则父 env 优先级更高，腿就测不到 profile）。

本轮实测已确认通道行为（不是想象中的）：`repo_root.py --json` 在 `OMOSTATION_STATE_ROOT=/tmp/t248/{prod,dev}state` 下
分别报出该 root（`code_root` 保持检出不变）；`bin/gac/materialize-system-state.py --json` 在两侧各写出
`<root>/.omo/state/system.yaml`（`status: materialized, bytes: 638`），而检出的 `git status --short .omo/state` 全程为空。

## 1b 陷阱：为什么「检出没写」不足以当验收

`§7` 已固化「每条"移走某个写目标"的契约都要配一条正向落点断言」。本腿把这条写成结构判据而非口头要求：
每条腿必须报告它**实际落在哪个绝对路径**，落在声明 root 之外（含检出、含另一 profile 的 root）即 FAIL；
「检出不脏」只作为**隔离**副判据，绝不可单独构成通过证据 —— 否则「writer 根本没跑」与「writer 正确改道」两者同绿。

## 2 完成判据（逐条可反证）

- **I1 双根各跑一遍**：脚本对 `--profiles` 声明的每个 profile 解析出**互不相同**的 state 根并各跑一遍声明腿；
  两个 root 相同 → exit≠0（防「一个 root 假装两个 profile」）。
- **I2 正向落点**：每条腿的 `landing` 字段是该腿实际写出文件的绝对路径，且必须在**本 profile 声明的 root 下**；
  文件不存在于该 root → 该腿 FAIL。判据不得写成「检出里没有」。
- **I3 假门禁防护**：脚本一律不读 `OMOSTATION_PROFILE`；测试断言「设/不设该 env 时 `repo_root` 的解析逐字节相同」，
  把「以未消费 env 为开关」这条路钉死。
- **I4 隔离**：双腿跑完后，检出的声明写目标保持未跟踪/未出现（`git status --short` 对相关路径为空），
  且 dev root 的文件不在 prod root 内（反向亦然）。另须钉住**不落任何真权威面**：默认解析出的 leg root 必须是
  脚本自建的 scratch 目录，断言它既不在检出根之下，也不在 `~/.local/state/omostation/**` 之下（后者住着 B4b 批次 1
  的备份快照，写进去就是污染机器级状态面）。
- **I5 install_root 落后即告警**：探到 `install_root()` 时报告 `head`、`is_ancestor`、`behind`；
  `behind > 0` 或非祖先 → `warn`（exit 0，检测语义是「告警」不是「中止」）；
  探不到 install root（CI 干净检出）→ `deferred`，**不得记为 pass**。
- **I6 host-only 腿一律 DEFER**：需要 launchd / 真实服务 / 本机端口的判据（如 `--reality-check` E2、
  `make gac-local-gate` 的宿主面）在无该面的环境记 `deferred` + 原因，不计入通过数。
- **I7 CI 接线**：workflow 内新增一步调用本脚本（两 profile），CI 日志即该腿证据；
  同时把 `tests/unit/test_dual_profile_verify.py` 加进 `governance-check.yml` 的显式 pytest 白名单 ——
  该白名单（`:118-127`）不含 `tests/unit/**`，不加进去则「CI 绿」不构成这些用例的证据。
- **I8 牙齿（变异对照）**：把 I2 的落点断言替换为 `pass` 后，测试必须当场变红；
  把 profile 名单收成单元素时，I1 必须变红。变异未致死 = 断言没牙齿，本轮不允许交付这种绿。
- **I9 注册面**：新脚本登记进 script registry，`check-index-drift` / `bin-scripts-convergence-audit` 保持绿
  （登记面只能加不能挪，见 `§7` 三个治理门禁条）。

## 3 不在本轮范围（写出来防越界）

- 不改 `~/.local/opt/omostation` 的代码、不推进它的 checkout、不动 43 个 plist 与 crontab（B4b 批次 2+，逐批授权）。
- 不 mint release tag、不建版本序列（前提修正已由主用户裁定绕开，不是推迟）。
- 不把 `OMOSTATION_PROFILE` 变成真 env（那是另一个 BET 的决定，涉及 B3/端口的首个消费者归属）。
- 不新增第五个 dispatcher 或第四层本体（`AGENTS.md` 绑定架构约束）。
