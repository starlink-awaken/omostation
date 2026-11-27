---
schema: md/v1
schema_version: specification/v1
bet_id: BET-Y2Q4-T10-367
spec_version: 1.0.0
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-27
accepted: "2026-11-27 governance-agent 会话延续轮 —— BET-Y2Q4-T10-366 复盘 §4 同族残留「migrate() 同样切 current 但不收敛运行期」"
title: 宿主迁移路径一致性 —— 迁移基线必须可被运行期绑定, 且切换后必须收敛运行期
created: 2026-11-27
---

# BET-Y2Q4-T10-367: 宿主迁移路径一致性

## 背景与问题

`BET-Y2Q4-T10-366` 把「切换 `current` 之后必须让运行中 live server 重新绑定并验收收敛」
补进了 `publish()` 与 `restore()`, 复盘 §4 留了一条同族残留:

> **同族残留**: `migrate()` 同样切 `current` 但不收敛运行期（一次性迁移路径）。

本轮把这条残留连同它下面的第二层空洞一起收掉: **迁移激活的基线 release, 运行期
根本绑不了** —— 也就是说即便补上收敛, 收敛的目标态本身也是不可达/不可验证的。

### 事实链（源码 + 线上读数）

**1. `migrate()` 是第三个会切 `current` 的入口, 但它没有 T10-366 的任何一半契约。**

`bin/gac/zhixing-host-sync.py::migrate()`（`:1105-1220`）的动作是: 捕获部署态 →
`_prepare_version()` 建基线 release → `_switch_current()`（`:1182`）→ 改写 plist
entrypoint 为 `current/live_server.py` → `_registered_runtime()` 复核。

对照同文件的 `publish()`（`:931-1067`）与 `restore()`（`:1071-1104`）:

| 契约段 | `publish()` | `restore()` | `migrate()` |
|--------|-------------|-------------|-------------|
| 运行期身份快照 `runtime_binding_snapshot()` | 有 | 有 | **无** |
| 切换前比两侧身份 `check_runtime_binding()` | 有 | 有 | **无** |
| 协调不可用 ⇒ 拒绝切换 | 有 | 有 | **无** |
| 切换后收敛 `coordinate_runtime()` + `/health` 验收 | 有 | 有 | **无** |
| 收敛失败 ⇒ 回滚 | 有 | 有 | **无**（只回滚 plist/切换态, 无运行期概念） |

⇒ 迁移在明知会移动绑定的情况下**不比对、不协调、不验收**, 仍返回 `ok: true`。

**2. 迁移基线清单的身份形态, 运行期身份契约一律拒绝。**

- `bin/gac/zhixing-host-sync.py::_prepare_version()`（`:397`）对非 `HOST_DIR` 来源写
  `identity_kind="deployment_baseline"`; `_write_release_manifest()`（`:248`）随之写
  `commit_oid=None`。
- 运行期身份 helper `bin/panorama/assets/host/release_identity.py.asset:46-49` 要求
  `identity_kind == "git_commit"` 且 `commit_oid` 为 40-hex ⇒ **基线清单 fail-closed**,
  抛 `release_manifest_source_invalid`。
- 采集器 `bin/panorama/panorama-collect.py::collect_projection_dashboard_identity()`
  走 release 自带的 helper ⇒ 失败即 `projection_release_identity_invalid`;
  live server `bin/panorama/assets/host/live_server.py.asset::managed_dashboard_identity()`
  同理 ⇒ `CODE_DRIFT` ⇒ 全部路由 503 `projection_code_drift`。

**3. 更靠前一步: 迁移基线 release 里根本没有身份 helper。**

`_runtime_baseline_assets()`（`:607-652`）只从部署根 `DASHBOARD_DIR` 捕获运行时文件,
而部署根里**没有** `release_identity.py`（实测 `~/.local/share/zhixing-dashboard/`
 无此文件）⇒ 基线 release 里没有 helper ⇒ `release_identity_of()` 直接返回
`release_identity_helper_missing` ⇒ 连「可绑定」都谈不上。

**4. 发布器与运行期对同一份清单判定相反。**

`_base_manifest_valid()`（`:269-275`）接受
`(kind == "deployment_baseline" and oid is None)` —— 也就是**接受运行期必然拒绝的
那种清单**。两套判定同源不同义 ⇒ 发布器认为「这个基线没问题」, 运行期认为「这个
release 不可绑定」。

**5. 本机当前潜伏（未爆）。**

- `migrate()` 早退 `already_migrated`（plist entrypoint 已是 `current/live_server.py`）;
- `~/.local/share/zhixing-dashboard/releases/` 下 55 个 release **全部** `identity_kind:
  git_commit`, 无任何基线形态 release。

⇒ 缺陷是**潜伏**的, 但它是 `publish()` 前置条件（`publish()` 拒绝未迁移的 plist,
`reason=plist_not_migrated`）⇒ 一旦换机/回退到迁移前形态, 迁移必然交付一个
「切了 current、但运行期绑不了」的宿主, 且返回 `ok: true`。

### 问题定性

两处同源空洞:

1. **运行期收敛空洞**（T10-366 复盘登记的同族残留）—— 迁移不比对、不协调、不验收;
2. **身份契约空洞** —— 迁移基线是**内容寻址**的（`_baseline_version_id()` `:592-604`
   用 sha256 对被复制的字节取摘要[:40], 明确不是 git oid）, 而运行期身份契约只认
   `git_commit` ⇒ 内容寻址的基线**在契约层面不可表达**。

第 2 点是第 1 点的前提: 就算给迁移补上收敛, 收敛要验收的目标态（运行中 server 绑定
到基线 release）也要求基线**可被绑定**。两者必须一起收。

## 契约

> **迁移把 `current` 指向一个 release 之前, 该 release 必须能被运行期身份契约独立
> 验证并绑定; 迁移完成之后, 运行期必须已收敛到该 release —— 验证不了或收不敛,
> 迁移就不算完成, 必须回滚。**

发布器是唯一的指针写入方, 对这两条负责: 要么交付「可绑定且已收敛」的宿主, 要么
**保持迁移前的形态**并如实报错 —— 不得留下半迁移态。

## 方案

### 1. 内容寻址的迁移基线进入身份契约（发布器 ⇄ 运行期 对称）

**清单形态**（`zhixing-host-release-manifest/v1`, 基线）:

```json
{
  "schema": "zhixing-host-release-manifest/v1",
  "version_id": "<40-hex 内容摘要>",
  "identity_kind": "deployment_baseline",
  "commit_oid": null,
  "content_oid": "<40-hex 内容摘要>",
  "selected_assets": ["..."],
  "base_version": null,
  "files": {"...": "<sha256>"}
}
```

- `content_oid` = 被复制进基线的字节的内容摘要（与 `_baseline_version_id()` 同源）,
  必须等于 `version_id` 且等于版本目录名。
- `commit_oid` 保持 `null` —— **基线不是 git 提交, 不得冒充提交 oid**。

**运行期 helper 的判定**（`release_identity.py.asset`）:

- `identity_kind == "git_commit"` ⇒ 现行语义不变（oid 40-hex, v1 要求 `version == oid`）。
- `identity_kind == "deployment_baseline"` ⇒ 必须同时满足:
  1. `commit_oid is None`;
  2. `content_oid` 为 40-hex 且 `== version_id == 目录名`;
  3. `schema` 为 v1;
  4. **从 release 字节独立重算内容摘要**: 按 `selected_assets` 顺序, 对每个资产累加
     `name\0<bytes>\0` 后取 sha256 前 40 位, 必须等于 `content_oid`;
  5. release 树的文件集合必须恰好等于 `selected_assets`（清单文件本身除外）。
  不满足 ⇒ `ReleaseIdentityError`（fail-closed, 与既有损坏用例同一处置）。

> 第 4 条是关键: git 提交身份**无法**从字节反推（只能说「这个 oid 的提交产生了这些
> 字节」, 需要外部 git 才能验）; 内容寻址身份**可以**从字节独立重算 ⇒ 基线身份比
> git 身份**可验证性更强**, 不是放松。

**发布器侧对称**: `_write_release_manifest()` 对基线写 `content_oid`;
`_base_manifest_valid()` 改为与运行期 helper **同一判定**（接受带 `content_oid` 的
基线形态; 拒绝旧的、运行期必然拒绝的裸基线形态）⇒ 发布器不再认可运行期绑不了的
release。

### 2. 迁移基线自带身份 helper

迁移捕获的资产集合并入 `release_identity.py`（来源: 仓库宿主资产
`bin/panorama/assets/host/release_identity.py.asset`, 而非部署根）⇒ 基线 release
自带身份 helper, 采集器与 live server 才有可能绑定它。

- 资产来源解析新增一条规则: 资产来源可以是绝对路径（用于基线里的 helper）,
  其余资产仍相对 `source_dir` 解析;
- 内容摘要与 `selected_assets` 因此**覆盖 helper 自身** ⇒ 基线身份覆盖整棵 release。

### 3. `migrate()` 接入 T10-366 的运行期契约

复用同文件的既有机器, 不新增第二套判定:

| 阶段 | 动作 | 失败处置 |
|------|------|----------|
| 切换前 | `runtime_binding_snapshot()` + `check_runtime_binding(candidate, snapshot)` | 不可观测 ⇒ 跳过（不阻断）; 绑定将被破坏 且 重绑定通道不可用 ⇒ **拒绝迁移** (`runtime_coordination_unavailable`) |
| 切换前 | `release_identity_of(candidate)` 证明基线**可被运行期绑定** | 不可绑定 ⇒ **拒绝激活** (`baseline_release_unbindable`), 不切 current、不改 plist |
| 切换后 | `coordinate_runtime()` 收敛并验收 | 不收敛 ⇒ 回滚（plist + current + 新版本目录复原）+ `runtime_convergence_failed` |
| 迁移后 | `_registered_runtime()` 复核（既有） | 复核失败 ⇒ 回滚（既有） |

**收敛判据**: 运行期**报告身份**时（`/health` 带 `dashboard_code_oid`）⇒ 必须
`code_drift == false` 且 oid == 基线 `content_oid`; 运行期**不报告身份**时（旧代
运行期没有身份自校验）⇒ 判据降级为「服务可用（200）且进程已随迁移重启」, 并在结果
里显式标注 `criterion=service_available_only` —— **降级必须显式, 不得伪装成身份收敛**。

「进程已随迁移重启」的可观测口径: 切换前 `/health` 的 pid（`previous_pid`）与切换后
的 pid 必须不同 —— 只看「还活着」会把「重启没生效、旧进程仍在服务」当成收敛。
切换前运行期不可观测（pid 未知）时不作此比较: 探不到即当时没在服务, 之后能通
本身就说明进程起来了。

### 4. 返回值诚实化

`migrate()` 返回体新增 `runtime` 段: 切换前后的读数、判定态、收敛判据、是否收敛。
没协调就写 `coordinated: false` + 原因; 降级判据就写降级判据。

## 验收

| 项 | 判据 |
|----|------|
| 基线清单可被运行期绑定 | 单测: 迁移产出的基线 ⇒ `managed_release_identity(base)` 返回 `code_oid == content_oid` 且 `tree_sha256` / `code_bundle_sha256` 齐备 |
| 内容摘要可独立重算 | 单测: 篡改基线任一资产字节 ⇒ helper 抛 `ReleaseIdentityError`（摘要与清单不符）; 单独篡改 `content_oid` ⇒ 同样拒绝 |
| 基线自带 helper | 单测: 基线 release 内含 `release_identity.py`; 缺 helper 资产时迁移**拒绝**并给出可执行原因 |
| 发布器与运行期判定一致 | 单测: 旧形态裸基线清单 ⇒ `_base_manifest_valid()` 与运行期 helper **都**拒绝 |
| 迁移走收敛契约 | 单测: 绑定将被破坏且协调不可用 ⇒ 迁移拒绝, `current`/plist 不变; 协调可用 ⇒ 触发 refresh + dashboard 两次动作并验收收敛 |
| 降级判据不被「旧进程仍在服务」骗过 | 单测: 降级判据下 `/health` 的 pid 未变 ⇒ 不收敛 ⇒ 回滚 (`runtime_convergence_failed`) |
| 不收敛即回滚 | 单测: `/health` 持续异常 ⇒ `ok=false` / `runtime_convergence_failed`, plist 与 `current` 复原 |
| 接线钉在真实入口 | 单测走 `migrate()` 真实入口（沿用「测试绕过接线就钉不住接线」的纪律） |
| 发布面不回归 | `tests/unit/test_zhixing_release_identity.py`、`tests/unit/test_zhixing_publish_runtime_convergence.py`、`tests/test_zhixing_host_sync_publish.py` 全绿 |

## 非目标

- 不改 live server 与采集器的身份自校验语义（它们是正确的; 缺的是基线这一种形态的表达能力）。
- 不改 `publish()` / `restore()` 的既有语义。
- 不改宿主仓 `zhixing-dashboard` 的任何文件（含看门狗探针 `--fail` 缺失）—— 跨仓写面, 见「残留登记」。
- 不动 `code-main` 重锚（`bin/ssot/anchor-install-root.sh` 属机器级运行时变更, 属 principal 窗口）。
- 不改治理占比判据面（`GOVERNANCE_CEILING` / `_classify`）。
- 本轮**不在本机执行任何一次真实迁移或真实发布**（机器级变更, 属 principal 窗口）; 只交付
  发布器侧与身份契约侧的代码与判据。

## 残留登记

| 残留 | 位置 | 判据 |
|------|------|------|
| 看门狗探针把 503 当活着 | `~/.local/share/zhixing-dashboard/liveness-watchdog.sh` 的 `curl -s -o /dev/null` 缺 `--fail` | HTTP 层失败 ⇒ 只读故障永不自动恢复; 跨仓, 留宿主仓裁决 |
| 迁移基线的内容摘要只覆盖「被复制的资产」, 不覆盖部署根的其余状态 | `_runtime_baseline_assets()` 的捕获范围 | 基线是**运行时代码与打包资源**的快照, 不含可变宿主数据（仪表盘/缓存/历史）; 这是设计意图, 非缺陷 |
| 已迁移宿主的 plist 未随本轮改动 | `~/Library/LaunchAgents/com.omostation.zhixing-dashboard.plist` | 本轮不跑真实迁移, 线上形态保持不变 |

## 影响面

- `bin/panorama/assets/host/release_identity.py.asset` (身份契约: 内容寻址基线)
- `bin/gac/zhixing-host-sync.py` (清单对称 / 基线自带 helper / migrate 接入收敛契约)
- `tests/unit/test_zhixing_migrate_runtime_convergence.py` (新)
- `tests/unit/test_zhixing_release_identity.py`、`tests/test_zhixing_host_sync_publish.py` (回归面)
- `docs/plans/3y-bet-ledger.yaml` (台账条目)
- `docs/superpowers/specs/2026-11-27-host-migrate-runtime-convergence.md` (本规格)
- `.omo/_knowledge/retros/BET-Y2Q4-T10-367.md` (复盘)
- `docs/reports/2026-11-27-t10-367-migrate-runtime-convergence-closeout.md` (收口回执)
