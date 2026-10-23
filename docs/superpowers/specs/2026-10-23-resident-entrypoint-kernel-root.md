---
schema_version: specification/v1
spec_version: 1.0.0
title: 改道的入口脚本内核仍钉检出根 —— reality-check 需要 E6 让它可见
bet_id: BET-Y2Q4-T10-266
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-23
---

# 改道的入口脚本内核仍钉检出根 —— reality-check 需要 E6 让它可见

> 范围：`bin/mof/gen-service-configs.py` 的 `--reality-check` 增加一条 E6 观测轴。
> 不改任何 wrapper 脚本的内容、不改 plist、不改 launchd 状态、不改 `services.yaml` 里
> 任何条目的 `runtime_root` 取值、不动 E1 的判据本体。

## 1. 缺陷证据（实测，2026-10-23T03:07–03:10Z）

BET-Y2Q4-T10-265 把常驻族 6 条 plist 的**入口**改到了安装位，launchd 自己的读数是权威的：

```
com.l4.resident.{decision,execute,signals,inbox,promote}:
  /bin/bash /Users/xiamingxing/.local/opt/omostation/lib/resident-role-tick.sh <role>
com.l4.resident.event-ingest:
  /bin/bash /Users/xiamingxing/.local/opt/omostation/lib/resident-event-ingest.sh
```

六条 `last exit code = 0`，`runs` 分别为 9/9/4/4/4/2 —— 改道后确实跑过真实 tick。

但被改道的脚本**本体**仍然把项目根写成检出的字面量：

```sh
# lib/resident-role-tick.sh:24,28 与 lib/resident-event-ingest.sh:11
exec /opt/homebrew/bin/uv run --project /Users/xiamingxing/Workspace/projects/omo ...
```

且 `lib/resident-role-tick.sh` 在安装位与检出两份**逐字节相同**（`diff` 无输出），
所以这条硬编码不因改道而消失，只是被搬到了另一个 inode 上。实测 `lib/` 面共
**5 个文件、6 处** `Users/xiamingxing/Workspace` 字面量（`agora-daemon.sh`、
`bet-claim-gc.sh`、`agora-sse.sh` 以及上述两个 resident wrapper）。

**后果**：入口 argv 指向安装位、执行的 Python 码面仍是检出 —— 正是 ADR-0456 B4b
要消灭的那个谎，也是 plan §「B4b 风险」一行点名的「静默跑旧代码的 daemon」。

## 2. 为什么现有门禁看不见它

| 判据 | 实际比较的对象 | 能否命中本缺陷 |
|---|---|---|
| E1 `drift_count` | plist 文本 vs 注册表渲染结果（入口路径在 `service_root()` 下） | **否** —— 入口本来就合法地改到了安装位，E1=0 是真的，但它只证到 argv |
| E2/E5 | label 集合双向相等 | 否 —— 与码面无关 |
| E4 | plist 可解析 + 分区闭合 | 否 |
| `assert_import_root()` | `omo.__file__` 与**加载它的那棵树**的 `code_root()` | 否 —— 参照根与被检对象由同一次 `--project` 钉死决定，两边同时是检出，恒等成立 |

`assert_import_root` / `import_root_report` 在仓库里的调用点实测只有
`bin/lib/repo_root.py` 自身与 `tests/unit/test_repo_root_import_root_assertion.py`；
`git grep` 在生产路径**零命中**。plan §159 把「启动断言 `omo.__file__` 落在期望
code_root 下」当作该风险的缓解手段，这一缓解目前是可用而未接线的库函数。

⇒ 判据必须与被检对象**不共享失效模式**（AGENTS.md §7③）。能在改道之后独立证明
「码面跟着入口走了」的，只有把入口脚本的**内容**读进来比对根前缀这一条。

## 3. 契约

E6 = 对每一条声明 `runtime_root` 的 launchd 服务，沿本机 plist 的 argv 找到属于
`service_root(svc)` 的入口脚本，读该脚本内容，判断其中是否钉住了**另一个根**的字面量。

1. **入口脚本的识别**：argv 中形如 `<root>/<...>.sh|<...>.py` 且解析后位于
   `service_root(svc)` 之下的那一项。识别不出（脚本不存在、argv 里没有脚本项）
   记为 `undetermined`，不得记为通过（§7⑨：解析失败不得折叠成空）。
2. **另一个根**：`checkout` 与 `install` 两个根路径字符串。声明 `install` 却出现检出根
   字面量、或声明 `checkout` 却出现安装根字面量，都算 `pinned_other_root`。
3. **缺省 = 今日行为**：E6 只进返回值与打印行，**不进 `findings`**，因此不影响
   `ok` 与 rc —— 今天 6 条服务全部命中，直接计入会让 CI 与本地门禁当场翻红，
   而翻红本身不构成任何修复。
4. **升级为硬判据由注册表内容决定**：条目声明 `require_kernel_root_match: true` 时，
   该条的 **`state != "ok"`**（即 `pinned_other_root` **与** `undetermined`）都进
   `findings`。缺省 `false`。把 `undetermined` 也算进阻塞是 §3.1 的另一半：若开关只
   管字面量命中，那么把入口改成认不出的形状就等于关掉这道闸 —— 「认不出」必须与
   「不合规」在阻塞面同形，在观测面异名。这样「把某族的内核也改道」与「声明它已经
   改道」是同一次注册表编辑里的两件事，可逐批、可回退。
   `require_kernel_root_match` 只适用于 `scheduler=launchd` 且声明了 `runtime_root`
   的条目，否则是 schema 违规（与 `runtime_root` 同一族校验位）；取值只接受 `true`，
   写 `false` 就是给「缺省即不声明」造第二个真值来源。
5. 本 BET **不**把 `runtime_root: install` 赋给任何新条目，也**不**把
   `require_kernel_root_match` 置真 —— 那需要先把安装位追平（§4）。

## 4. 为什么修复半不在本轮

安装位此刻不具备承接码面的条件，实测三条：

- 根 clone 冻结在 B4a 的 landing commit（`1b5f02cb3`），落后 `origin/main` **438** 个
  commit；本仓没有任何 cron / launchd 条目会推进它（`crontab -l` 全量里没有
  `~/.local/opt/omostation`）。
- 其 `projects/omo` 在 `a9d0165`，检出侧在 `980b9cb`。
- `projects/omo/.venv` 不存在，root 侧 `.venv` 存在但那是 B4a clone 时的产物。

⇒ 让 wrapper 改成自解析（`BASH_SOURCE` 推根），当刻的效果是把这 6 条常驻服务从
「检出的最新码」切到「安装位 438 个 commit 之前的码」。那是生产行为变更，且推进
安装位属机器级写面，逐批授权归 principal（AGENTS.md §7「运行根选择器」条与
BET-Y2Q4-T10-265 授权范围都不含「追平安装位」）。本轮交付的是**可见性**：改道的
第二半从此有一个读数，而不是靠 E1=0 的措辞暗示它已经完成。

## 5. done_when

1. `--reality-check --json` 返回值含 `e6_kernel_pin` 面，且**逐条**列出
   `label / declared_root / script / state(ok|pinned_other_root|undetermined)`。
2. 在真实机器上跑出非零命中：6 条声明 `runtime_root: install` 的服务全部
   `pinned_other_root`（这就是本轮的 receipt，命中为零即说明检测器没接上）。
3. `ok` 与 rc 在本轮**不变**（缺省 observe-only）；`require_kernel_root_match: true`
   的合成条目下 `pinned_other_root` 与 `undetermined` 各进 `findings` 一条且 rc=1
   —— 正反两面都由用例钉住。
4. 检测器自证：注入一条命中的合成 wrapper 必须点名它；一条合法的（只含声明根）
   必须不命中。空绿不被接受（AGENTS.md §7③）。
5. E1 保持 0：`--check --json` 逐字节不改行为，`drift_count=0` 复跑前后各一次。
