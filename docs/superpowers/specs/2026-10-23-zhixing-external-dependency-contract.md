---
schema_version: specification/v1
spec_version: 1.0.0
title: Zhixing 驾驶舱外部依赖契约 —— 把 ADR-0456 决策 5 的三件套从散文变成可校验对象
bet_id: BET-Y2Q4-T10-267
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-23
---

# Zhixing 驾驶舱外部依赖契约 —— 把决策 5 的三件套变成可校验对象

> 范围：`.omo/_truth/registry/external-write-roots.yaml` 的 `zhixing-dashboard` 条目补三件字段；
> `bin/lib/repo_root.py` 增加外部根解析器；`bin/ops/cli.py` 的 `check-signals` 增加一条
> **observe-only** 的 `/health` 观测轴。
> 不改 plist、不改 crontab、不改 `services.yaml` 任何条目、不动本机 launchd 状态、
> 不把该仓并入主仓（实测已有 16 个子模块，并入 = 白多第 17 个）。

## 1. 缺陷证据（实测，2026-10-23T04:37–04:39Z）

`docs/plans/3y-bet-ledger.yaml` 里没有这条 BET；`ZHIXING_DASHBOARD_ROOT` 在全仓只出现在
**四处散文**里，零个代码消费点：

```
.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md:162   (契约声明本身)
docs/superpowers/specs/2026-09-26-dev-runtime-profile-root.md:128  (B1 时记为 "tracked separately")
docs/plans/3y-bet-ledger.yaml:36017                                (T215 note 里转述)
runtime/wip-snapshots/... 同文件的历史快照
```

也就是说 ADR-0456 决策 5 承诺的三件套，两年过去仍只是承诺。当前该依赖的唯一在案声明是
`.omo/_truth/registry/external-write-roots.yaml:3-11`：

```yaml
- id: zhixing-dashboard
  path: ~/.local/share/zhixing-dashboard
  kind: local_git
  status: admitted
```

它说了「这是一个被准入的本地 git 写根」，没说**是哪个 repo 的哪个 OID**，也没说**它的健康怎么判**。
而主仓有 12 处 plist 级字面量直接指进这个目录（`services.yaml:5568/5589/5650-5655/5809/5832/5869-5871/5979`），
`generate: false` 意味着 E1 的比较根本不覆盖它们。

实测的本机事实（用于钉契约取值，非猜测）：

| 量 | 实测读数 |
|---|---|
| 部署仓 origin | `git@github.com:starlink-awaken/zhixing-dashboard.git` |
| 部署仓 `git rev-parse HEAD` | `c2a8471b4a222ecc2eef38eecf66e2e2ebe7eb07` |
| 服务入口 | `live_server.py --port 43191`（`services.yaml:5979-5981`） |
| 端口 43191 | `protocols/port-registry.yaml:104` `ZHIXING_OBSERVATORY_PORT`、`:138-142` `zhixing-observatory` |
| `GET /health` | HTTP 200，键含 `code_drift` / `projection_status` / `dashboard_code_oid` / `state_revision` |
| `/health` 报的 OID | `e021642b37cac2f6784d1d207b36dba62a66a2ee` —— **与部署仓 HEAD 不相等** |
| `/healthz` | HTTP 404（通道只有 `/health`，探针不得探别的） |

## 2. 关键设计约束：`pinned_sha` 不得参与任何判定

`/health` 报 `dashboard_code_oid = e021642b` 而部署仓 HEAD 是 `c2a8471b` —— 两者按构造不相等，
因为服务跑在 `releases/<40 位 OID>` 目录里，不是仓的工作树（AGENTS.md §7「release worktree 目录必须用
40 位全名」条，2026-10-12 c855c4a 部署实证）。

同一族的自伤已经在 §7 记过一遍：**「观测器期望 OID 基线必须跟随当前部署 OID，否则重新部署后产生大量假失败」**
（T241 的 24h 观测门实测：303 个失败里 279 个只是 OID 前进）。所以本契约里的 `pinned_sha` 语义是
**「主仓上次验证该依赖时所用的 OID」= 溯源记录**，不是**「服务应该跑在这个 OID」**：

- `pinned_sha` 只写进 registry，**任何代码路径都不得拿它跟实时读数比较并据此报警**。
- 扫描面**由 registry 自己的文件名导出**（引用 `external-write-roots` 的 `.py`），不是手写名单，
  也不是「整个 `bin/` 里不许出现这个词」：实测 `bin/` 有 13 处 / 4 个文件读 `pinned_sha`，全部属于
  `bin/gac/agent-clone.py` 的 submodule gitlink pin 概念（那里跟 live HEAD 比较是**正确行为**）。
  判据两条并存：消费者集合内零命中 + 全 `bin/` 命中文件集合与被评审名单**集合相等**（AGENTS.md §7③）。
- 探针的分类只看通道可达性与 `/health` 自身报的 `code_drift` / `projection_status`，
  前进部署属正常态。
- 判据：测试里注入「部署仓 HEAD ≠ registry pinned_sha」这一事实，探针分类必须**不变**。

## 3. 契约三件套（本 BET 的交付面）

### 3.1 registry 条目锁 repo + SHA

`external-write-roots.yaml` 的 `zhixing-dashboard` 条目追加：

```yaml
    root_env: ZHIXING_DASHBOARD_ROOT
    repo: git@github.com:starlink-awaken/zhixing-dashboard.git
    pinned_sha: c2a8471b4a222ecc2eef38eecf66e2e2ebe7eb07
    health:
      env: ZHIXING_OBSERVATORY_PORT
      path: /health
```

字段全部 optional —— 现有条目零破坏，缺 `health` 的条目不进探针面。`env` 而非端口数字：
端口号已在 `protocols/port-registry.yaml` 有唯一真源，写第二份就是并行第二套机制
（ADR-0456 决策 2 的「不并行」约束），而且本仓 CI 有 `port hardcode check`。

### 3.2 `ZHIXING_DASHBOARD_ROOT` 解析器

`bin/lib/repo_root.py` 增加 `external_root(root_id)`：

- 解析序：registry 该条目 `root_env` 指名的 env（zhixing 条目声明
  `root_env: ZHIXING_DASHBOARD_ROOT`）→ registry 声明的 `path`（`~` 展开）→ 目录不存在时返回
  `None`。
- env 名**写在登记表里而不是代码里**：代码侧手抄一张 `id → env` 名单就是第二份真源，登记表改名而
  名单不跟着改正是 AGENTS.md §7「契约名单单一来源」条的形状（T10-239 的两份手抄名单各缺半边，
  `1 failed / 3040 passed`）。`root_env` 缺省即该条目没有 env 覆盖通道，行为不变。
- 语义与 `install_root()` 同族：**只是定位器，什么都不搬**；未落位返回 `None` 而不是抛异常。
- registry 里查不到该 `root_id` → `KeyError`（调用方写错 id 是编码缺陷，不能静默给 `None`）；
  查得到但没有 `path` → `ValueError`（registry 自身坏了必须响）。
- 它是**一参 callable**，因此不落入 `repo_root.__all__` 零参探测面（T10-231 的写面扫描按零参
  callable 归类 resolver），也不会移动 `code_root()` / `state_root()` —— 双根等式不变量
  （`tests/unit/test_repo_root_profile.py`）不受影响。
- 解析器**不 import yaml**（与 `_projection_registry` 同一理由：meta-doctor 与 cron 用裸
  python3 跑）；`health.path` 与根 `path` 同名，靠缩进区分，收进来就会把 `/health` 当目录根 ——
  这一条有反例用例钉住。

### 3.3 `check-signals` 的 `/health` 观测轴

`cmd_check_signals()` 末尾增加一段独立观测，**默认 observe-only**：

- 遍历 `external-write-roots.yaml` 中带 `health` 的条目，读 `os.environ[health.env]` 取端口
  （env 缺席 → 该条目分类 `undetermined`，不报错），`GET http://127.0.0.1:<port><path>`，
  超时 2s。
- 分类：`ok`（2xx 且 `/health` 自报 `code_drift` 为假）/ `code_drift`（2xx 但自报漂移）/
  `unreachable`（连接失败或超时）/ `undetermined`（端口 env 缺席，或非 2xx，或响应体不是 JSON object）。
- 只有条目显式声明 `require_health: true` 时才把非 `ok` 计入 `drifts`，从而影响 exit code。
  缺省不声明 ⇒ `check-signals` 的 exit code 与本轮改动前**逐字节等价**。
- `require_health` 只接受 `true`，且要求同条目已声明 `health`（照 E6 的 `require_kernel_root_match` 校验形状）。
- 探针失败不得抛出：任何异常折叠成 `undetermined`，因为「探测装置不可用」与「依赖不健康」
  必须同形于「非阻塞」，绝不能让一次网络抖动变成每日 cron 的 exit 1。

## 4. 为什么这是「可见性」而不是「行为变更」

主仓对这 12 处字面量的处置（改道 / 参数化）属于 B4b 批次 2+，需逐批授权，**不在本 BET**。
本 BET 只把「这个外部依赖是谁、锁在哪个 OID、健康怎么判、根怎么定位」变成可校验对象，
使后续批次的准入判断有地方落。判据同 E6：加观测面、不动执行面。

## 5. done_when（每条都可实测，不写想象中的通道行为）

1. registry 的 `zhixing-dashboard` 条目同时含 `repo` / `pinned_sha` / `health.env` / `health.path`，
   且 `health.env` 在 `protocols/port-registry.yaml` 的 env 名单里存在（集合反查，不是手抄）。
   env 名另有一条 `root_env: ZHIXING_DASHBOARD_ROOT`，由 `external_root()` 读——写在这里而不是代码里，
   是为了只有一份来源（AGENTS.md §7 T10-239 抽样名单缺名那次）。
2. `external_root("zhixing-dashboard")` 三种解析序各有一条断言：登记表 `root_env` 指名的 env 覆盖 → 赢；
   无 env → registry 路径（`~` 展开）；registry 路径不存在 → `None`（且此时不抛异常）。
3. `check-signals --json` 输出含 `health_checks` 数组，本轮实测该数组里 `zhixing-dashboard`
   分类为 `ok`（本机服务在跑，`/health` 200、`code_drift=false`）。端口必须由 `port-registry.yaml`
   反查得出而非依赖本机 shell：实测没有任何 rc 文件、hook 或 cron 导出 `ZHIXING_OBSERVATORY_PORT`，
   裸跑只会得 `undetermined`——那是装置没搭对，不是服务不健康。
4. 缺省声明下 exit code 不变：拿改动前/改动后同一棵树跑 `check-signals`，drifts 计数与 rc 相等。
5. 「部署仓 HEAD ≠ pinned_sha」时探针分类不变（§2 的变异对照），且 `pinned_sha` 不得进任何判定路径——
   由两台不共享失效模式的装置钉住：读该 registry 的源文件（扫描面由 registry 文件名导出）内 AST 零
   `pinned_sha` 读取点；全 `bin/` 读 `pinned_sha` 的文件集合与被评审的 4 个 submodule-gitlink 站点
   集合相等。原措辞「`git grep -w pinned_sha -- bin/` 只允许出现在 registry 校验/文档语境」按实测
   不可达：那 13 处 / 4 个文件读的是无关的子模块 gitlink 概念（`agent-clone.py` 一族），不在本契约面上。
6. `tests/unit/test_zhixing_external_root_contract.py` 全绿，且在 `HOME=<空目录>` +
   最小 venv 下复跑同样全绿（hermetic：探针不得摸真实服务）。

## 6. 非目标

- 不改 `services.yaml` 的任何条目（那 12 处字面量的收口属 B4b 批次 2+，逐批授权）。
- 不启停任何 launchd job，不写 `~/Library/LaunchAgents`，不碰 crontab。
- 不把 zhixing-dashboard 并入主仓、不新增子模块、不改其 gitlink。
- 不拿 `pinned_sha` 做版本守门（§2）。
- 不新增 `bin/` 脚本（受 `check-bin-quota-diff.py` 净增配额约束），只改既有两个文件。
