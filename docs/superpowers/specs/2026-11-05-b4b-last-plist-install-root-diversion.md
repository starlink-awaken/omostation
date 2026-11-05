---
schema_version: specification/v1
spec_version: 1.0.0
title: B4b 批次 3——把最后一条指向检出根的常驻 plist 改道到安装位
bet_id: BET-Y2Q4-T10-286
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-05
---

# B4b 批次 3：`com.omostation.test-archive-purge-7d` 改道安装位

## 0. 事实（2026-11-05 实测，全部给可复跑命令）

### 0.1 它是 ADR-0456 B4b 的唯一真残差

`python3 bin/mof/gen-service-configs.py --reality-check --json` 在 base `0b67fac45` 上：

- `e7_checkout = 0`、`e7_non_ok = 0`、`e7_undeclared = 0`，28 条声明服务全部 `state=profile`；
- 已安装 label 总数 `installed_total = 87`，`owned_installed = owned_declared = 51`；
- `workspace_scoped = 2` —— `ai.hermes.gateway`（PATH 子串假阳，属另一把尺 `bin/mof/gen-service-configs.py:729` 的整 blob 子串命中，**本 BET 不含**，见 §3）与 `com.omostation.test-archive-purge-7d`（真残差）。

计划文档 B4b 的判据是「指向 `Workspace` 的 plist 由 43 → 0」。43→0 已推进到 1，这 1 条就是本 BET 的对象。

### 0.2 它钉在检出根的理由已被否证

plist 注释 `:8`、`services.yaml` notes `:6406`、`.omo/cron/registry.yaml:136` 三处都写着同一句理由：

> 派发归档 `.omo/tasks/archived/dispatches_test_archive/` 是**主仓数据面**，安装位那份是独立 clone 的副本，删错地方等于没删。

三处独立证据否证它：

1. ADR-0466 自己的复核段（`.omo/_knowledge/decisions/0466-system-authenticity-and-zero-mock-contract.md:76`）：
   「`.omo/tasks/archived/dispatches_test_archive/` 在 main 上从未存在（仅见于未合并分支 `chore/closeout-20261022`），故实际销毁条目为 0，两机均一致。」
2. 2026-11-05 实测该目录在三个候选根下 **ABSENT**（不是空目录）：
   `/Users/xiamingxing/Workspace`、`/Users/xiamingxing/.local/opt/omostation`、`/Users/xiamingxing/.local/state/omostation/prod`。
3. 全仓 `dispatches_test_archive` 命中仅 6 处，其中唯一的代码引用是常量定义本身
   （`bin/ops/purge-test-archive-7d.py:31`），**无任何写者**。

另一个更硬的理由：当前 argv 里的 `>> runtime/cron/purge-test-archive.log` 与 `WorkingDirectory=/Users/xiamingxing/Workspace`
本身就在往检出根写日志 —— 这条 plist 不只是「从检出根启动」，它还**写检出根**。ADR-0456 决策 1 的正是这件事。

### 0.3 改道后的行为等价性（read-only 实测，非推断）

`purge-test-archive-7d.py` 无参数分支走 `status()`，只读不删。两侧实跑：

| 运行根 | `Cards Archive` | `Dispatches` | Total / Due |
|---|---|---|---|
| 安装位 | `~/.local/share/omostation/cards_archive` | `~/.local/opt/omostation/.omo/...`（0） | 0 / 0 |
| 检出根 | 同上（同一机器级路径） | `/Users/xiamingxing/Workspace/.omo/...`（0） | 0 / 0 |

即：范围 1 是宿主机器级路径，与根解析无关；范围 2 在任何根下都是 no-op。改根**行为等价**，且脚本在安装位可正常 import `repo_root`。

### 0.4 三方同源基线

`bin/ops/launchd/com.omostation.test-archive-purge-7d.plist`、`~/Library/LaunchAgents/` 同名副本、
`services.yaml:6379 content_digest` 三者当前同为 `sha256:189cc38ad622bf1c928a07b0395a016a2f5eb65cda83017d9c99b9251757d6c1`。
本 BET 结束后三者必须重新同源（这是 notes 已经承诺的不变量）。

## 1. 改动面

| 文件 | 改什么 |
|---|---|
| `bin/ops/launchd/com.omostation.test-archive-purge-7d.plist` | `ProgramArguments` 的 `cd` 目标、`WorkingDirectory` → 安装位；删除 argv 内 `>>` 重定向；新增 `OMOSTATION_STATE_ROOT`；`StandardOut/ErrorPath` → `~/.local/log/com.omostation.test-archive-purge-7d.log`；注释块「为什么从检出根跑」整段替换为 §0.2 的否证结论 |
| `.omo/_truth/registry/services.yaml` | 该条 `program.args` / `outputs` / `content_digest`，新增 `runtime_root: install`，notes 追加改道段与否证出处 |
| `.omo/cron/registry.yaml` | 同步 `:136` 那处已被否证的措辞（同一句理由的第三份副本） |
| `~/Library/LaunchAgents/…plist` + `launchctl bootout/bootstrap` | 机器侧落位，与仓内源逐字节同源（principal 于 2026-11-05 明确授权含 bootout/bootstrap） |

## 2. done_when

- **AC-01** 仓内镜像 plist 被 `plistlib` 解析通过，且 `ProgramArguments[2]` / `WorkingDirectory` / `StandardOutPath` 三处均不含 `/Users/xiamingxing/Workspace` 字面量。判据：一条 grep 计数为 0 的可执行检查，不看措辞。
- **AC-02** 三方同源重新成立：`shasum -a 256` 仓内镜像 == 已安装副本 == `services.yaml` 记录的 `content_digest`。
- **AC-03** 尺读数移动且只朝预期方向：`--reality-check --json` 的 `workspace_scoped_labels` 改后为 `['ai.hermes.gateway']`（长度 2 → 1），`e1_drift / e2_undeclared / e3_malformed` 保持 0，`e7_checkout` 保持 0。
- **AC-04** 反证自证：把 argv 的 `cd` 目标临时改回检出根，AC-01 的计数必须变非 0；否则那条检查没有判别力（本仓「按构造就绿」族）。
- **AC-05** 机器侧真跑：`launchctl print` 该 label 的 `state` 可读，且以无参数（只读 `status()`）路径不产生任何删除；不跑 `--auto`，因为保留期已过、真跑 `--auto` 属数据销毁，需另获授权。

## 3. 非目标

- 不修 `gen-service-configs.py:729` 的整 blob 子串命中（尺尺改造，另案 #194）。本 BET 只让**真实**残差归零，`ai.hermes.gateway` 那条假阳留在案上，AC-03 因此显式期望长度 1 而非 0。
- 不迁移 `cards_archive`，不跑 `--auto`/`--purge`，不删任何归档数据。
- 不把该条从 `generate: false` 改成 `true`（plist 含 `WorkingDirectory`，`gen_launchd_plist` 从不输出该键，改 true 会立刻产生 E1 漂移）。
- 不碰其它 22 条 E4 未分区异主 label（署名裁定 #147）。

## 4. 回滚

`git revert` 本 BET 的 squash commit，随后把 `~/Library/LaunchAgents/` 副本换回回滚后的镜像并重新
`bootout/bootstrap`。因为 §0.3 证明了改根不改变任何删除语义（两侧 Total=0），回滚不需要数据恢复步骤。
