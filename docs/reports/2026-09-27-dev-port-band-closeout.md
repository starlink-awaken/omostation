---
schema: md/v1
status: completed
lifecycle: history
owner: governance-team
last-reviewed: 2026-09-27
type: report
bet_id: BET-Y2Q4-T10-205
title: BET-Y2Q4-T10-205 端口注册收口 + dev 端口段门禁 — closeout receipt
created: '2026-09-27'
run_id: 20260926T170014Z-project-code-change-00116568
---

# BET-Y2Q4-T10-205 closeout receipt — ADR-0456 B2-A

> 本文件是 ledger `completion_evidence` 指向的 receipt。所有数值为本 run 实测，非复述。
> 契约定义见 `docs/superpowers/specs/2026-09-26-dev-port-band-and-prod-ui.md`。
> 复盘（含打假条目）见 `.omo/_knowledge/retros/BET-Y2Q4-T10-205.md`。

## 1. 交付物

| 项 | 值 |
|---|---|
| 主仓 PR | #4411（`state: MERGED`，`mergedAt 2026-09-27T00:31:06Z`） |
| 主仓 merge commit | `d2b97b2ee8b85b15140da79c545a35f92015243e` |
| 分支 commit（按 change-lane 拆分） | `3f12e7206` docs(spec) / `b0d7b1bf6` code / `fcd59c1c0` docs_data(ledger) / `4d77de21f` docs(spec 纠错) / `938d318e4` docs_data(digest 重绑) |
| 契约 spec | `docs/superpowers/specs/2026-09-26-dev-port-band-and-prod-ui.md`，`spec_version 1.0.0`，digest `sha256:054922c8233accb04540294a755f39b7b7773949cd6e20ae5f24dc6a8beba8e2` |
| 端口注册表 | `protocols/port-registry.yaml` `54 → 57` 条：新增 `4000 aetherforge-openai-proxy`、`43910 panorama-sunset-redirector`（+ `env_vars: SUNSET_PORT`）、`5173 cockpit-ui-vite-dev`（由豁免改判自有）；新增顶层 `dev_band {15000–15099}` 与 4 条 `dev_ports` |
| 扫描器 | `bin/ssot/check-hardcoded-ports.py`：`LEGACY_OK_PORTS` 由 5 项收窄为 `{1234, 3000, 3001, 4318}`；新增 `load_dev_ports()` / `render_dev_env()` 与 `--dev-env` / `--profile {dev,prod}`；`--json` 增 `dev_band` / `dev_ports` |
| 测试 | `tests/test_hardcoded_ports.py` `10 → 20` 用例（dev 段 contained / injective / disjoint / prod_port 已注册 / env seam 存在 / 冲突拒绝 + 打印模式） |
| 台账 | `BET-Y2Q4-T10-205` 经 `bin/gac/ledger-safe-insert.py` 原子入账，`bets 485 == meta.total_bets` |

内容等价性（测量时点：本 worktree 切到 `d2b97b2ee` 之后、本 receipt 撰写之前）：
`git diff origin/main HEAD -- <5 paths>` 在合并后仅剩 `docs/plans/3y-bet-ledger.yaml`
的 base 漂移（main 侧更新的 `BET-Y2Q4-T10-01` 等条目，非本 bet 所为，且 squash 未回退它们），
`protocols/port-registry.yaml` / `bin/ssot/check-hardcoded-ports.py` /
`tests/test_hardcoded_ports.py` / spec 四个文件与当时 `origin/main` **逐字节一致** ——
§2 的 V1–V4 即在该等价态执行，故读到的就是生产内容。
**本 receipt 合并时该等价已不成立**：closeout wave 按 §3 第 2 行有意追加一个 `code` lane
差量（`5173` 补 `owner: cockpit-ui`），这是唯一偏离项，其余四文件不动。

## 2. verify 实测（ledger `verify` 四条，逐条）

| # | 命令 | 实测结果 |
|---|---|---|
| V1 | `python3 bin/ssot/check-hardcoded-ports.py --json` | `exit=0`；`ok=true`、`unregistered=0`、`registered_total=57`、`threshold=0`、`dev_band=[15000,15099]`、`dev_ports={cockpit-dashboard:15090, llm-gateway:15091, kos-rest-api:15092, ecos-event-listener:15093}` |
| V2 | `python3 -m pytest tests/test_hardcoded_ports.py -q -p no:cacheprovider` | `exit=0`，`20 passed in 234.67s`（耗时来自 root conftest，非用例） |
| V3 | `python3 bin/ssot/check-hardcoded-ports.py --dev-env --profile dev` | `exit=0`，4 行，每行 `NAME=PORT  # dev 覆盖 <prod_port> (<name>)`；打印前重验 contained/injective/disjoint/prod_port 已注册，任一违反即 `exit 1`（V3-负例由 `test_dev_port_collision_is_rejected` 覆盖） |
| V4 | `python3 bin/ssot/check-hardcoded-ports.py --dev-env --profile prod` | `exit=0` 且 **stdout 0 字节** —— prod 永不接收 dev 覆盖 |

CI（PR #4411）：`gh pr checks` 共 27 项，**23 pass / 4 skipping / 0 fail**，含 required 的
`gac-gate`、`phase-gate`、`bet-done-transition`。

本地门禁：`make gac-local-gate` 两次实测口径不一致，逐条重跑后定性为**瞬态争用**：
01:31:32Z 那次 `[FAIL] check-conflict-markers :: bin/gac/check-conflict-markers.py --all`
（唯一红项，其余 67 项 PASS）；随后 `python3 bin/gac/check-conflict-markers.py --all`
（RC=0，17.9s）与 `uv run --with pyyaml python …`（RC=0，18.5s，即 make 的同一环境）
**同参数双环境皆绿**，01:44Z 整条 `make gac-local-gate` 复跑 → `PASS (68 checks executed,
ALL GREEN)`。该检查是纯 I/O 型（user 2.3s / real 18s，靠 `git ls-files` + 逐文件读盘），
当时 `ps` 实测本机同时有两组 gate 进程栈（`make`→`uv run`→`python gac-local-gate.py`
pid 87508/87544/87556，以及另一组 90894/90899）⇒ 判定为争用性 flake，非本次改动引入。
未提交差量的正确覆盖形状是 `--scope files --file <path>`
（`--scope staged` 在未 stage 时打印 `scope=staged change_lane_files=0`，属空跑；
`bin/change-lane-check.py --file docs/plans/3y-bet-ledger.yaml` 单独跑 → `PASS (1 files, lanes=docs_data)`）。

## 3. done_when 逐条判定

| done_when | 判定 | 证据 |
|---|---|---|
| 1 `--json` unregistered==0 且测试文件整体通过 | **通过** | V1 + V2（main 上原本恒红的 `test_unregistered_is_zero` 现为绿） |
| 2 `4000` 与 `5173` 以 owner + transport 声明，且 `5173` 不在 `LEGACY_OK_PORTS` | **交付时未达、closeout wave 补齐**：PR #4411 合并态里 `4000` 有 `owner: aetherforge` 而 `5173` 只有 `name/status/transport`（注册表 57 条中 51 条本来就没有 `owner`，它不是必填字段，所以我合并时没察觉）。本 wave 以单 `code` lane commit 补 `owner: cockpit-ui`（`docs/project-registry.yaml:285` 已登记 `cockpit-ui` 项目，非自造 owner token），使本条按字面成立；补后复跑 V1 仍 `ok=true / unregistered=0 / registered_total=57` | `protocols/port-registry.yaml:124-131`；豁免表断言 `assert 5173 not in scanner.LEGACY_OK_PORTS`（`tests/test_hardcoded_ports.py:84-92`） |
| 3 dev 段与生产端口可证不相交、映射单射、且测量时不与任何 LISTEN 端口相撞 | **通过** | §4 |
| 4 spec accepted 并绑定 | **通过** | `shasum -a 256` == ledger `content_digest`（§1） |

## 4. 端口现实测量（ADR-0456 B4 的前置事实）

`netstat -an -p tcp | grep LISTEN` → **76** 个监听端口。

| 判据 | 实测 |
|---|---|
| dev 段 `15000–15099` ∩ LISTEN | `∅` |
| `{15090,15091,15092,15093}` ∩ LISTEN | `∅` |
| dev_ports 与 prod_port 是否同号 | 4 条全部不同号（8090→15090、9290→15091、8766→15092、7432→15093） |
| dev_ports 单射 | 4 值 4 端口，成立 |
| 生产侧在听 | `4000`、`5173`、`43910`、`8766`、`9290`、`7432` 均 LISTEN |
| 生产人类入口 | **`8090` idle** —— 注册为"唯一人类 Web 入口"的 `com.cockpit.dashboard` 没有任何监听者；人类当前实际看到的是 dev-profile 的 vite `:5173` |

`8090 idle` 是本 bet 把 B2-B（切生产 UI）定性为"入口虚构"而非"入口慢"的唯一直接证据，
也是 principal 决定"先推 B3、UI 切换押后"的输入。

## 5. 端口门禁的真实执行面（实测机制，只报告不处置）

合并前后各读一次，机制如下：

1. `bin/gac/ci-check-runner.py:65` 的选取谓词是
   `surface["workflow"] == 请求的 workflow 且 surface.get("status","active") != "orphan"`，
   **从不读 `also_in`，也从不读 `gate`**；`:77-78` 构造
   `[sys.executable, tool] + surface["args"]`（本 surface 无 args ⇒ 走默认 `--threshold 0`）。
2. 本扫描器登记为 `status: active` / `workflow: mof-update.yml` / `gate: false` /
   `also_in: [port-registry-enforce.yml]`（`.omo/_truth/registry/ci-surfaces.yaml`）。
3. 因此 `--workflow port-registry-enforce.yml`（每个 PR 上那个名为 "port hardcode check" 的 job）
   恒得 `(0 checks) ✅`；真正执行扫描的只有 `mof-update.yml`，其触发是
   `schedule: "0 6 * * 1"` + `workflow_dispatch`。
4. 同一描述的另两处死信：`.pre-commit-config.yaml` 的 `port-hardcode-check` 指向不存在的
   `scripts/check-vault-paths.py --check-ports`；root 扫描器 argparse 从来没有 `--check-ports`
   （只有 `--json / --threshold / --env-var-check`，本 bet 新增 `--dev-env / --profile`）。
   `protocols/port-hardcode-baseline.yaml` 亦无执行者，只有 ecos MOF 节点
   `PROTOCOL-WS-port-hardcode-baseline.yaml` 声明它。

**结论**：端口"增量 enforce"在三处被描述、零处存在；本 bet 只让门禁的**真值**变对
（`unregistered 1 → 0`），未改动门禁**是否执行**——翻转门禁效力属 principal 决策
（与 PR 4209 移除 `--require-main` 同量级），本 bet 的 circuit breaker 明确禁止改
`ci-surfaces.yaml` 与 `.pre-commit-config.yaml` 的接线。

## 6. 报告给 principal、本 bet 不处置

| 项 | 实测 |
|---|---|
| 门禁效力半死 | §5（PR 可见的绿是零检查的绿） |
| `gac-worktree.sh merge` 改共享主工作区 | `:735-804` 在 `gh pr merge` 后 `cd $WS_ROOT; git checkout main; git pull --ff-only`。当时主工作区停在他人 `feat/panorama-mof-loops-data-pipeline` 且带 39 个未提交文件 ⇒ 本次改用 `gh pr merge 4411 --squash --delete-branch`（纯远端效应） |
| run 内无"契约合法演进"路径 | 事后改 spec/重绑 digest ⇒ 该 run 任何 `claim` 撞 `WORK_PACKET_SOURCE_DRIFT`（`bin/plan/bet-ledger.py:2334`）；唯一重绑动词 `agent-workflow.py refresh-packet` 又要求 ledger 已 commit 到 run 记录的 revision（实测 `WORK_PACKET_REFRESH_SOURCE_UNMERGED: ledger differs from d2b97b2ee…`）。⇒ 教训：`write_surfaces` 必须在 `start` 前写全（含 receipt/retro 路径） |
| vendored 副本 | `projects/agora/bin/ssot/check-hardcoded-ports.py` 与 root 扫描器 `LEGACY_OK_PORTS` 相同、仅格式漂移（在 `projects/` 下，circuit breaker 禁碰） |
| 硬编码端口而非读 `types:` | `bin/ssot/check-hardcoded-ports.py:189` 写死 `(7422, 7456, 8090)` |
| 生产入口的两处 vite 倾向 | `projects/cockpit/src/cockpit/_subcommands.py:1004`（`cockpit panorama --web` 默认 `:5173`）、`projects/metaos/src/metaos/run.py:25`（把 `127.0.0.1:4000/health` 当 Ollama 探针，真身是 aetherforge 网关） |
| sunset redirector 多实例 | 同一时刻 `43910 / 43922 / 43924` 三个实例在听，均非 launchd 声明服务 |
| B3 基数（2026-09-27 双口径重测，替换 plan 估算与本 receipt 先前版本） | `~/Library/LaunchAgents` 共 **56** 个 plist，其中字面引用本 Workspace 的 **43**；registry `services.yaml` 是**多文档 YAML**（`safe_load` 会只读第一段），340 条服务里声明 label **34** 条。**installed-but-undeclared：全集 37 / Workspace 口径 27**（回填面按 27 算）。launchd 实际 loaded：全集 43/56、Workspace 口径 31/43。declared-without-plist **15**，其中 8 条 `generate: false`；真缺口 7 = 2× `com.l4.*` + 5× `docker:*` —— **`docker:` 前缀是容器服务标记，不是 launchd label**，等式门禁须按命名空间分区而非只按 `generate` 排除。declared+enabled+**未 loaded** = 6（`com.cockpit.dashboard` + 5× `com.l4.*`）。**枚举必须走 `plutil -convert json`**：56 条里 2 条（`com.omostation.expiry-radar`、`com.omostation.zhixing-host-drift`）注释内含 `--`（`--strict` / `drwx------`），`plistlib`（expat）抛 `ExpatError`，但 `plutil -lint` OK 且 launchd **正常加载** —— 用 stdlib 解析枚举会得到天生少 2 条的 installed 集合（本 receipt 先前版本的 "54 可解析 / 25 未登记" 即由此而来，现已作废）。`gen-service-configs.py --check` 只做 registry→plist 单向字节比较（实测 `drift_count 0`），**看不见"装了但没登记"** ⇒ B3 的等式门禁必须新造，且需**所有权谓词**（37 条 undeclared 里 `com.amazon.codewhisperer.launcher`、`com.macpaw.CleanMyMac5.Updater` 是第三方软件，无谓词的等式等于要求把 CleanMyMac 登记进本仓） |
| ADR-0456 状态 | 本 receipt 撰写期间由 principal 升档：`72c93f896 decision(adr): ADR-0456 PROPOSED → ACCEPTED`（PR #4413，实测 2026-09-27T01:38Z `git fetch` 后位于 origin/main，本 worktree 落后 3 个 commit）。B2-A 报告项之一就此闭合 |

## 7. live canary / 副作用边界

本 bet 的 `circuit_breaker` 要求"零运行时效应"。两个观测点：2026-09-26 交付前（spec 的
证据段）与 `d2b97b2ee` 合并后（本 receipt §4），全部为**只读**观测：

- **未** start / stop / bootstrap / unload 任何 launchd job；**未**写或改任何
  `~/Library/LaunchAgents/*.plist`（B3 之前这是硬边界）。
- **未**读写 crontab；**未**改 `governance-checks.yaml` / `ci-surfaces.yaml` /
  `.pre-commit-config.yaml` / `port-hardcode-baseline.yaml`。
- **未**触碰 `projects/**`（含 vendored 副本）。
- **未**改变任何在听进程的端口：`4000 / 5173 / 43910 / 8766 / 9290 / 7432` 在合并前后
  同状态（§4 是合并后的复测）。
- live canary = **合并后的 main 自身**：在 `d2b97b2ee` 内容上跑 V1–V4 四条契约命令全绿，
  即"dev 端口供给口已可从权威状态读取"这一行为在生产状态下成立，无需启停任何服务。
- `--dev-env` 至今**没有任何调用者**注入到真实进程（B4 才接），因此注册本身对
  在跑系统的影响是零。

## 8. 回滚路径

单点回滚 = revert `d2b97b2ee`（squash 合并，无子模块 gitlink、无生成态、无运行时副作用）：

```bash
git revert --no-edit d2b97b2ee8b85b15140da79c545a35f92015243e
```

回滚后可观测后果（与合并前 main 一致）：`tests/test_hardcoded_ports.py::test_unregistered_is_zero`
转红（`unregistered 0 → 1`，即 4000），`--dev-env` 参数消失（`argparse` exit 2），
`LEGACY_OK_PORTS` 回到 5 项。回滚**不会**影响任何进程、plist 或 cron（本 bet 未产生这类副作用）。

## 9. cleanup

- 工作树：交付 PR #4411 合并后，本 worktree `ws-b2-devport-ui` 保留至 closeout wave
  （receipt + retro + evidence 矩阵）合并，随后 `bash bin/gac/gac-worktree.sh release b2-devport-ui`。
  主工作区 `/Users/xiamingxing/Workspace` 全程只读未动（其 HEAD 仍在
  `feat/panorama-mof-loops-data-pipeline`，39 个未提交文件属并发 agent，未被本次任何动作波及）。
- run：交付 run `20260926T170014Z-project-code-change-00116568` 已 `closeout --status ok`
  （`finished_at 2026-09-27T01:47:57Z`，3 条 evidence：PR SHA + verify 3 checks ok + observe continue）。
  closeout wave 另起 `project-doc-change` run `20260927T015120Z-project-doc-change-168a29d3`
  承载本 receipt、retro、ledger evidence 矩阵与 `5173` owner 四条路径的 claim
  （因 §6 第 3 行的 claim 通道限制）。
- 未伪造项：`BET-Y2Q4-T10-203` 的 evidence 未代其补写；30 条 value 记录未回填
  （本 bet `value_indicator_policy: false`，value 轴诚实为 `NOT_PROVEN`）。
