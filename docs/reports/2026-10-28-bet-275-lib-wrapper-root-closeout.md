---
schema: md/v1
status: completed
lifecycle: report
type: closeout-receipt
owner: governance-agent
last-reviewed: 2026-10-28
bet_id: BET-Y2Q4-T10-275
---

# BET-Y2Q4-T10-275 receipt —— lib/ wrapper 的仓根自解析（B4b 码面残差的第一块）

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-275`
规格：`docs/superpowers/specs/2026-10-28-bet-275-lib-wrapper-root-self-resolution.md`（spec_version 1.0.0，
content_digest `sha256:d0d15e64c4df5ff11e3c4ba4a891f2f3b8cbd658e6cd2cc6c084dba903283738`）
retro：`.omo/_knowledge/retros/BET-Y2Q4-T10-275.md`
run：`20261028T020024Z-project-doc-change-df1fb0b4`（profile `governance-agent`，workflow `project-doc-change`）
交付基线：`origin/main` = `9de3ba966`（claim 时刻），分支 `agent/governance-agent/t275-lib-root`

## 1. 这一腿消灭的是哪个谎

ADR-0456 B4b 把常驻族 6 条 plist 的**入口**改到了安装位 `~/.local/opt/omostation/lib/*.sh`。
T10-266 记下的判据是：**入口在 A 树、执行的 Python 码面在 B 树，就是没改道**。`lib/resident-role-tick.sh`
早已按 `BASH_SOURCE` 自推根，所以 `--reality-check` 的 `e6_non_ok = 0`；另外三条**未声明 `runtime_root`**，
因而不进 E6/E7 覆盖面，且把检出的绝对路径逐字节烤进了脚本 —— 安装位那三份与检出的那份 sha256 相同，
于是从安装位启动的 daemon 实际 `cd` 进检出树、跑检出的码面，而 E1（只比 plist 文本与注册表渲染）对它
结构性失明。本轮补的是这三支枪口指向的同一处：**根从哪来**。

| 文件 | 改前（`origin/main` 行号） | 改后 |
|---|---|---|
| `lib/agora-daemon.sh` | `:7 cd /Users/xiamingxing/Workspace/projects/agora` | `cd "$_REPO_ROOT/projects/agora"` |
| `lib/agora-sse.sh` | `:6 --project /Users/xiamingxing/Workspace/projects/agora` | `--project "$_REPO_ROOT/projects/agora"` |
| `lib/bet-claim-gc.sh` | `:9 python /Users/xiamingxing/Workspace/bin/plan/bet-ledger.py` | `python "$_REPO_ROOT/bin/plan/bet-ledger.py"` |

缝的形状与 `lib/resident-role-tick.sh:27-29` 逐字一致（`_SELF_DIR` 由 `BASH_SOURCE` dirname 取 pwd，
`_REPO_ROOT` 取其上一级）；`/opt/homebrew/bin/uv` 这类宿主二进制按 C-2 明文保留。

## 2. done_when 四条的实测读数

尺一律写明用哪个二进制（AGENTS.md §7⑦：同一判据换引擎读数可能不同）。

| # | 判据命令 | 改前基线 | 改后 |
|---|---|---|---|
| 1 | `git grep -c "/Users/" -- 'lib/*.sh'`（在 `origin/main` 上：`git grep -c "/Users/" origin/main -- 'lib/*.sh'`） | **3**（三份各 1，rc=0） | 读数为空，rc=1 |
| 1' | 对照 `/usr/bin/grep -c "/Users/" lib/*.sh`（BSD grep，全 6 份 `lib/*.sh`） | 同上 3 | 六份全 `:0` |
| 2 | `bash -n lib/agora-daemon.sh lib/agora-sse.sh lib/bet-claim-gc.sh` | — | 三份均 OK（rc=0） |
| 3 | `tests/unit/test_lib_wrapper_root_self_resolution.py` | 见 §3 | **7 passed** |
| 4 | `env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB HOME=$(mktemp -d) uv run --no-project --with pytest --with pytest-timeout --with pyyaml python -m pytest <该文件> -q -p no:randomly` | — | **7 passed**（依赖面由 uv 供给，host 面清空） |

⚠️ 宿主 `python3`（`/opt/homebrew/opt/python@3.15`）**没有 pytest**；`pyproject.toml` 的 `addopts` 带
`--timeout=300`，所以最小 venv 必须 `--with pytest-timeout`，否则当场 `unrecognized arguments`。
hermetic 复跑要分清「依赖面」与「host 面」（T10-235 装置面补记的同一条）。

### 2.1 `make gac-local-gate` 的真实读数（verify-6，交付时刻）

**不是全绿**，如实记录：66 项 PASS，唯一硬失败是 `service-config-drift`
（`bin/mof/gen-service-configs.py --check`）报 **4 条 drift**：
`com.l4.governance.watch` / `com.omostation.morning-brief` / `com.l4.mail.daemon` /
`com.omostation.zhixing-projection-republisher`；另 1 项 SOFT WARN
`governance-semantic`（`agent-workflow-status: active_runs=1`，并发 run 的存在，非本 PR）。

**这条硬失败不在本 PR 的输入面上**，判据是复现而不是推理：同一条
`gen-service-configs.py --check --json` 在 `~/Workspace`（canonical 检出本体）跑，读数**一字不差也是这 4 条**。
比较器的两份输入是 canonical 注册表与本机 `~/Library/LaunchAgents/*.plist`（那 4 份 mtime = 2026-10-28 10:26），
本 PR 改的是 worktree 里的 `lib/*.sh` 与测试，两者都不在这把尺的读面上。
读数还随时间翻动：10:26 那次 `gac-local-gate` 读 **0 drift / 74 services**，10:29 起稳定读 4。

**成因已指认（不是「大概是并发 agent 写坏了」）**：上游 `758ea5ec8`（PR #4929，
「B4b Batch 2 物理切道 —— 5 服务改道至安装位」，本轮交付期间合入 main）对注册表恰好新增 5 条
`runtime_root: install` —— `com.l4.governance.watch`、`com.l4.mail.daemon`、
`com.omostation.morning-brief`、`com.omostation.sunset-redirector`、
`com.omostation.zhixing-projection-republisher`（按 `git diff 9de3ba966 origin/main --
.omo/_truth/registry/services.yaml` 逐条比对 `runtime_root` 字段，改前一律 `None`）。
E1 报的这 4 条正是那 5 条的子集。所以这是 T10-265 记过的那条**声明与执行跨了两次交付的红窗**：
注册表已说 install、机器侧 plist 还指检出（那一半的执行属 #4929 自己的运行腿），
而 sunset-redirector 未落进 drift 说明它的机器侧已跟上。
**不是本分支引入的回归，也不是我的 wrapper 改动所致。**

顺带指认一条对本 BET 有直接后果的事实：本轮这三条服务的 label —— `com.agora.daemon`、
`com.agora.sse`、`com.l4.bet-claim-gc` —— 在 `origin/main` 的注册表里 `runtime_root` **仍是 `None`**
（同一次逐条比对读出）。所以「仓库里的 wrapper 不再钉根」之后，声明面与机器侧改道**都还没发生**，
E6/E7 也仍不覆盖这三条；那属 #91 的逐批授权面（receipt §7）。

**未做的事**：没跑 `--write`、没碰 plist、没 `bootout`/`bootstrap`。那 4 条 label 的机器侧处置属
B4b/#91 与 #4929 的运行腿（另见 #97 / #123 / #150 那几条署名面）。

## 3. 检测器自证与三组变异对照（C-4）

同一个 `_scan(files)` 函数同时产出 §2 的改前 3 与改后 0（不是两次不同探测），且 `PRE_FIX_WRAPPERS`
是 `git archive origin/main lib` 抽出的**逐字节内容**，不是手写近似。三组变异分别记读数 ——
「一次变异只红一组」不等于其余断言都承重：

| 变异 | 改法 | 读数 | 承重的是哪条 |
|---|---|---|---|
| A | 把 `lib/bet-claim-gc.sh` 整份换回 `origin/main` 那一份 | **2 failed / 5 passed**（改后 0 处 + 携缝两条红） | 「改后为 0」与「携缝」都依赖脚本内容，不看 argv |
| B | `_scan()` 首行 `return []`（尺摘掉） | **3 failed / 4 passed**（反基线 + 自证 + 反面三条红，**而「改后 0 处」仍绿**） | 这正是「只断言 0」的形状：空绿能骗过它，骗不过反基线与自证 |
| C | 尺改成只匹配本机根 `CHECKOUT_LITERAL in line`（spec §5 的断路形状） | **1 failed / 6 passed**（自证那条红） | 合成样本注入的是 `/Users/someone/Workspace/projects/x/run.py`，窄尺命中不了它 |

变异后一律 `/bin/cp -f` 还原并 `shasum -a 256` 与备份逐字节对拍（三次全等）。
⚠️ 这里差点出事故：`cp` 在本机 zsh 是 `cp -iv` 别名，第一次还原打印 `not overwritten`、rc=1 而**文件逐字节未变**，
若照"命令成功"读就成了「变异还在树上但以为还原了」。脚本化文件还原一律 `/bin/cp -f` 或 Python（§7⑤）。

四条 done_when-3 用例的最终形态（共 7 条，"含四条"之外的三条钉 C-1/C-3 与语法）：
反基线 3 处、改后 0 处、合成违规点名到行、`/opt/homebrew/bin/uv` 不被点名（并把同一份内容换成主目录前缀
断言**必须**命中 1 次 —— 证明差异是尺的判准，不是它没跑）、三份都携缝且消费该变量、命令负载归一化后逐行等值、`bash -n`。

## 4. C-3「语义不变」不是口头承诺

`_command_lines()` 剥掉 shebang / 注释 / `set -euo pipefail` / 自推根两行赋值，再把 `$_REPO_ROOT` 代回字面量根、
剥掉 shell 引号，与 `origin/main` 那一份的命令负载**逐行比对**。引号归一化是**语义**等值而非文本等值
（路径无空格无 glob，分词结果相同），这点在函数 docstring 里明写，不然读起来像 byte-equal。
`bet-claim-gc.sh` 本轮确实多加了一对引号（`python "$_REPO_ROOT/bin/plan/bet-ledger.py"`），
它是唯一一处非纯替换的差异，被这条判据明确覆盖。

## 5. 运行态实测（不只是文本检查）

把三份 wrapper 复制到假安装位 `/tmp/t275_fake_install/lib/`，把 `exec` 换成 `echo` 后从**第三个目录**
（`cwd=/tmp`）跑，读它将要执行的命令：

```
[checkout    ] agora-sse.sh:  --project /Users/xiamingxing/ws-t275-lib-root/projects/agora
[install-fake] agora-sse.sh:  --project /tmp/t275_fake_install/projects/agora
[checkout    ] bet-claim-gc.sh: python /Users/xiamingxing/ws-t275-lib-root/bin/plan/bet-ledger.py claim-gc
[install-fake] bet-claim-gc.sh: python /tmp/t275_fake_install/bin/plan/bet-ledger.py claim-gc
[checkout    ] agora-daemon.sh: CWD=/Users/xiamingxing/ws-t275-lib-root/projects/agora TARGET=…/src/agora/daemon.py EXISTS=yes
[install-fake] agora-daemon.sh: CWD=/tmp/t275_fake_install/projects/agora TARGET=…/src/agora/daemon.py EXISTS=yes
```

同一份字节在两棵树上各自推出自己的根，且**互不引用** —— 这是 C-1 的正向落点，文本断言给不出这个读数。
未执行任何 `exec` 后的真实命令：`claim-gc` 会删广播文件、daemon/SSE 是常驻服务，都不在本轮授权面内。

## 6. 消费面回归

`git grep -ln "agora-daemon|bet-claim-gc|agora-sse" -- tests bin lib config docs/plans` 命中 8 处，其中
测试侧两处（`tests/unit/test_writeplane_root_pin.py:185` 是 `runtime/agora-sse.log` 文件名、
`tests/test_compass_isc3.py:82` 是 service key 字符串）都不断言脚本内容。两个文件同跑 **13 passed**。

## 7. 本轮明确没做（不是遗漏）

- **没给这三条服务声明 `runtime_root: install`**：注册表内容是 principal 授权面（#91，B4b 批次 2+）。
  因此合并后 `--reality-check` 的 `e6_kernel_pin` 仍不覆盖这 6 条中的这三条 —— 本轮交付的是
  「码面不再钉检出」这个**性质**，不是「E6 归零」这个**读数**。
- **没动 launchd plist、没 `bootout`/`bootstrap`**：机器侧那半分属 principal 决定。
- **安装位那三份仍是旧字节**（本轮实测，非推断）：`~/.local/opt/omostation` 检出在
  `dee5d6356f876a45c24d6e943b2bfc551fb9240b`，其 `lib/` 三份各含 **1** 处 `/Users/` 字面量，
  与检出侧改后 sha256 全不等：

  | 文件 | 安装位 sha256[:16] | 检出改后[:16] | 判定 |
  |---|---|---|---|
  | `agora-daemon.sh` | `8190ba788d8be435` | `e6347f748f43dabc` | DIFF |
  | `agora-sse.sh` | `e367d93dbe58a935` | `6832d2f01081b315` | DIFF |
  | `bet-claim-gc.sh` | `6e30d1b574e06fbe` | `2bbd6f93912e234d` | DIFF |

  而安装位那份 `bet-claim-gc.sh` 的 sha256 与 §3 变异 A 里 `git show origin/main:lib/bet-claim-gc.sh`
  产出的 `6e30d1b574e06fbe…` **逐字节相同** —— 这就是 §1 那个谎的直接证据：安装位的码面就是检出的旧码面。
  由发布机制按记录在案的 OID 重新检出之前，机器侧仍跑改前那份。**判据**：比对
  `shasum -a 256 ~/.local/opt/omostation/lib/<name>.sh` 与检出侧同名文件，不等即尚未发布。
  别把「仓里修好了」读成「机器上修好了」（与 T10-265 红窗那条同族）。
- **没扩 E6 的准入条件**：把 `check-services-runtime-root.py` 扩到未声明 `runtime_root` 的条目是独立
  工程腿；本轮的 C-2 判据先由测试钉住，不新增门禁 flag。
