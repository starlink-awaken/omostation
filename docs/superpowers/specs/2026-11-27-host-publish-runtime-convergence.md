---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-366
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-27
accepted: "2026-11-27 governance-agent 会话延续轮 —— BET-Y2Q4-T10-365 复盘 §4「同一半边契约可能在别处重演」"
title: 宿主发布运行期一致性 —— 切换 current 后必须让运行中的 live server 重新绑定并验收收敛
created: 2026-11-27
---

# BET-Y2Q4-T10-366: 宿主发布运行期一致性

## 背景与问题

`BET-Y2Q4-T10-365` 把「采集器字节 == 生产者代码根 HEAD 字节」这条前置条件补进了发布器,
但复盘 §4 留了一条尾巴: **「同一半边契约可能在别处重演」**。本轮把它落到运行期的另一半 ——
**live server 自己的身份自校验**。

### 事实链（源码 + 线上读数）

**1. live server 的身份绑定在「进程启动那一刻解析的 release 目录」上。**

- `bin/panorama/assets/host/runtime_paths.py.asset:17`:
  `CODE_ROOT = Path(__file__).resolve().parent` —— import 时求值, `resolve()` 跟随
  `current` 软链 ⇒ **进程一旦启动, 就钉死在当时的 release 目录上**。
- `bin/panorama/assets/host/live_server.py.asset:223-233`: `SERVER_CODE_SHA256` /
  `QUERY_CODE_SHA256` / `RUNTIME_PATHS_CODE_SHA256` / `CODE_BUNDLE_SHA256` 全部在
  import 时从 `Path(__file__)` 与其同级文件算出来 ⇒ **冻结值**。
- `live_server.py.asset:1730-1747`（`projection_revision()`）把四者与投影 revision 比对:
  `code_oid` / `tree_sha256` / `code_bundle_sha256` 任一不等, 或冻结的
  `CODE_BUNDLE_SHA256 != revision.dashboard_code_bundle_sha256` ⇒ 抛
  `CODE_DRIFT` ⇒ 全部路由（含静态资源）返回 503 `projection_code_drift`。

**2. revision 侧的绑定来自「采集器当时看到的 `current`」。**

- `bin/panorama/panorama-collect.py:552-612`（`resolve_projection_dashboard_code_root()`
  → `collect_projection_dashboard_identity()`）: `ZHIXING_DASHBOARD_CODE_ROOT` 下的
  `current` 软链 → `releases/<oid>`; 该 release 有 `.zhixing-host-release.json` ⇒ 走
  manifest 分支 ⇒ `managed_release_identity()` 返回该 release 的
  `code_oid` / `tree_sha256` / `code_bundle_sha256`。
- manifest 的 `commit_oid` = **发布时的 omostation 提交 oid**（线上实测:
  `current` → `releases/8f43efedc4e04e80e7612a68c6be046f4950c6cb`, 其
  `commit_oid` = omostation 提交 `8f43efed`「T10-355 done-transition」）。
  ⇒ **每次发布换一个 oid, 绑定必然移动。**

**3. 于是「发布成功」与「宿主可用」之间没有任何机器校验。**

`bin/gac/zhixing-host-sync.py` 的 `publish()` 只做四件事: 准备版本目录 → 原子切换
`current` → 资产 SHA 校验 → 返回 `ok: true`。它**从不读运行态**。切换之后:

| 时刻 | 现象 |
|------|------|
| t0 切换 | 运行中 server 的 `__file__` 指向 `current/…` ⇒ 磁盘字节已变 ⇒ `/health` 的 `code_drift` 立刻转 `true`（`live_server.py.asset:2268-2280` 比对磁盘字节与冻结字节） |
| t1 采集器刷新（≤240 s, `com.omostation.panorama-dashboard-refresh`） | revision 绑定移到新 release ⇒ server 钉死的旧身份 ≠ revision 的新身份 ⇒ 全部路由 503 `projection_code_drift` |
| t2 人工重启 live server | server 重新 `resolve()` ⇒ 钉到新 release ⇒ 恢复 |

⇒ **t1 之后、t2 之前, 驾驶舱整站只读。** 而 t2 没有任何机器触发。

**4. 自动恢复链看不见这个故障形态。**

宿主看门狗 `~/.local/share/zhixing-dashboard/liveness-watchdog.sh`（launchd
`com.omostation.zhixing-dashboard-watchdog`, 每 120 s）的探针是
`curl -s -o /dev/null --max-time 5 "$URL"` —— **不带 `--fail`** ⇒ HTTP 503 的退出码仍是 0
⇒ 只读态被判定为「活着」⇒ tier1/tier2 恢复链**从不触发**。这份脚本在宿主仓
（`zhixing-dashboard`）里, 不在本仓写面内（见「非目标」与「残留登记」）。

### 问题定性

半边契约的第二种形态: **采集器的自校验是「正在执行的字节 == 生产者 HEAD 的字节」**,
发布器补了那一半（T10-365）; **live server 的自校验是「正在执行的 release == 投影
绑定的 release」**, 发布器这一半仍然空着 —— 缺的不是检查, 是**发布事务的收敛**。

## 契约

> **发布切换 `current` 之后, 投影绑定的新 release 与运行中 live server 实际执行的
> release 必须一致; 否则 server 的身份证明失效 ⇒ `code_drift` ⇒ 静态资源 503。**

发布器作为唯一的指针写入方, 对这条契约负责: 它要么**让宿主收敛到该状态**, 要么
**拒绝这次发布** —— 不能在明知会破坏绑定的情况下返回 `ok: true`。

## 方案

### 1. 切换前取两侧身份（只读）

| 侧 | 取法 |
|----|------|
| 运行中 server 的绑定身份 | 只读 `GET http://127.0.0.1:43191/health` ⇒ `dashboard_code_oid` / `dashboard_tree_sha256` / `dashboard_code_sha256`（`live_server.py.asset:2286-2290`） |
| 候选 release 的身份 | 用候选 release 自己的 `release_identity.py` 跑 `managed_release_identity(root)` ⇒ `code_oid` / `tree_sha256` / `code_bundle_sha256` |

**探针必须证明「这个 server 就是本发布器管的那个」**: `/health` 的 `pid` 必须等于
`_running_registered_runtime()` 取到的 launchd 注册进程 pid。取不到 pid 或 pid 不符 ⇒
不可观测 ⇒ 跳过（不阻断）。

### 2. 三态判定（`check_runtime_binding()`）

| 态 | 条件 | 动作 |
|----|------|------|
| 不可观测 | 无 server / 探针失败 / pid 不符 / 任一侧身份三元组不完整 | **跳过**（`checked=false`）—— 无法自证时不反手阻断发布（与 T10-365 同源纪律） |
| 绑定保持 | 两侧 `code_oid` + `tree_sha256` + `code_bundle_sha256` 全等 | 放行, 无需协调 |
| **绑定将被破坏** | 任一不等 | **必须协调**（见 3）; 协调不可用 ⇒ **拒绝发布**（`ok=false`, `reason=runtime_coordination_unavailable`） |

> 为什么几乎必然落入第三态: release 的 `commit_oid` 就是发布时的 omostation 提交,
> 而 `tree_sha256` 覆盖 release 全树 ⇒ 任何一次发布都会改 oid 或改树 ⇒ 绑定必移动。
> 这是设计使然, 不是配置漂移。

### 3. 收敛（`coordinate_runtime()`）—— 发布事务的后半段

切换 `current` 之后, 发布器自己完成重绑定并**验收**:

1. `launchctl kickstart gui/<uid>/com.omostation.panorama-dashboard-refresh`
   —— 让采集器立刻跑一轮, 把 revision 绑到新 release（已启动时视为「本来就会跑」, 非致命）;
2. `launchctl kickstart -k gui/<uid>/com.omostation.zhixing-dashboard`
   —— 重启 live server, 使其重新 `resolve()` 到新 release;
3. 轮询 `/health`（有界预算, 默认 180 s / 每 5 s 一次）直到
   `code_drift == false` **且** `dashboard_code_oid == 候选 release 的 code_oid`
   ⇒ 收敛成立。

**不收敛 ⇒ 回滚**: `current` 切回上一版 + 再跑一次同样的协调（让 server 钉回旧
release、采集器把 revision 绑回旧 release）⇒ 返回
`ok=false` / `reason=runtime_convergence_failed`, 并附最后读数与每一步动作结果。

`restore()`（人工回滚）同样翻转指针 ⇒ 同样要走收敛, 否则回滚本身会把宿主留在只读态。

### 4. 返回值诚实化

`publish()` / `restore()` 的返回体新增 `runtime` 段: 判定态、两侧身份、协调动作、
收敛读数。**没协调就不假装协调**（`coordinated: false` + 原因）。

## 验收

| 项 | 判据 |
|----|------|
| 绑定保持时不协调 | 单测: 两侧身份全等 ⇒ 不触发任何 kickstart |
| 绑定将被破坏时协调并验收 | 单测: 身份不等 ⇒ 触发 refresh + dashboard 两次动作, 并轮询到收敛 |
| 不收敛即回滚 | 单测: 探针持续报 `code_drift=true` ⇒ `ok=false` / `reason=runtime_convergence_failed`, 且 `current` 切回上一版 |
| 不可观测时不阻断 | 单测: 探针不可达 / pid 不符 ⇒ `checked=false`, 跳过, 不报错 |
| 接线钉在真实入口 | 单测走 `publish()` / `restore()` 真实入口（沿用 T10-365「测试绕过接线就钉不住接线」的纪律） |
| 发布面不回归 | `tests/unit/test_zhixing_release_identity.py` + `tests/unit/test_zhixing_publish_producer_binding.py` 全绿 |

## 非目标

- 不改 live server 的身份自校验语义（它是正确的; 缺的是发布侧那一半）。
- 不改宿主仓 `zhixing-dashboard` 的任何文件（含看门狗探针的 `--fail` 缺失）——
  那是跨仓写面, 见「残留登记」。
- 不动 `code-main` 重锚（`bin/ssot/anchor-install-root.sh` 属机器级运行时变更, 属 principal 窗口）。
- 不改采集器的身份自校验语义, 不改驾驶舱契约守卫的告警语义。
- 不改治理占比判据面（`GOVERNANCE_CEILING` / `_classify`）。
- 不改 `migrate()`（一次性迁移路径, 见「残留登记」第 2 行）。
- 本轮**不在本机执行任何一次真实发布**（机器级变更, 属 principal 窗口）; 只交付
  发布器侧代码与判据。

## 残留登记

| 残留 | 位置 | 判据 |
|------|------|------|
| 看门狗探针把 503 当活着 | `~/.local/share/zhixing-dashboard/liveness-watchdog.sh` 的 `curl -s -o /dev/null` 缺 `--fail` | HTTP 层失败 ⇒ 只读故障永不自动恢复; 应改为 `curl --fail` 或校验状态码; 跨仓, 留宿主仓裁决 |
| `migrate()` 同样切 `current` 但不收敛运行期 | `bin/gac/zhixing-host-sync.py::migrate()` | 迁移会切 baseline release 且只改 plist、不 reload launchd ⇒ 运行中 server 仍钉旧 release ⇒ 同族漂移; 但迁移是一次性动作且迁移后本就要重新加载 launchd 才生效 ⇒ 本轮不改, 留作同族残留 |

## 影响面

- `bin/gac/zhixing-host-sync.py` (+ 身份快照 / 绑定判定 / 协调 / 回滚收敛)
- `tests/unit/test_zhixing_publish_runtime_convergence.py` (新)
- `docs/plans/3y-bet-ledger.yaml` (台账条目)
- `docs/superpowers/specs/2026-11-27-host-publish-runtime-convergence.md` (本规格)
- `.omo/_knowledge/retros/BET-Y2Q4-T10-366.md` (复盘)
- `docs/reports/2026-11-27-t10-366-publish-runtime-convergence-closeout.md` (收口回执)
