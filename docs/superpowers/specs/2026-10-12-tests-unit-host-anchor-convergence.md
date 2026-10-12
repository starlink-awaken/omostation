---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B4b 前置 — tests/unit 残留 13 处 host 字面量改由 registry/home 派生
bet_id: BET-Y2Q4-T10-245
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-12
---

# ADR-0456 B4b 前置 — tests/unit 残留 host 字面量按 registry / home 派生

## 0 为什么是这一轮（不在本轮做 plist 改道）

B4b 批次 2+ 的真实动作是把 43 个指向 `Workspace` 的 plist 改到安装位；那批是**机器级需授权**。
本轮只做一件事：**让测试面不再把自己钉在这台机器上**。否则改道那一批一落地，这三条用例就以
「断言的绝对路径不再等于新 plist」的形式红掉，而红的那一层是测试而不是产品 ——
会让授权批次现场去找根因，代价最高。

## 1 实测基线

尺：`/usr/bin/grep -rn "/Users/xiamingxing" tests/unit --include="*.py"`（**不用 `git grep -E`**，
正则引擎不同读数不同 —— T10-231 实测）。测量对象 `origin/main` = `92c029436`，2026-10-12。

| 文件 | 命中行 | 定性 | 期望值新来源 |
|---|---|---|---|
| `tests/unit/gac/test_meta_doctor.py` | 10（`REAL_WS`） | **锚点** | `bin/lib/repo_root.code_root()` —— 该常量只用作 crontab 锚定根 + 「一个真实存在的仓内目标」（`:93` `scenarios/Y1Q4-B1/test_e2e.py` 在检出与 worktree 两侧都存在，实测） |
| `tests/unit/test_agent_cell_semantic_scheduler.py` | 23,33,34,35,36,37 | **锚点** | `.omo/_truth/registry/services.yaml` 的 `omostation.agent-cell-semantic-smoke` + `Path.home()` |
| `tests/unit/test_reference_cell_direct_local_schedule.py` | 22,31,33,34,35,36 | **锚点** | 同上，entry `omostation.reference-cell-direct-local-smoke` |
| `tests/unit/test_service_interpreter_stability.py` | 11 | **非锚点**：模块 docstring 叙述一次环境伪影，不参与断言 | 不动 |
| `tests/unit/test_spine_diff_adaptation.py` | 35,42 | **非锚点**：脱敏用例**要求**输入含真实用户名形状路径，才能证 `<REDACTED_USER>` 生效 | 不动，并反向钉住 |

⇒ 待收敛 **13 处 / 3 文件**；须保持原样 **3 处 / 2 文件**（改动它们等于收窄断言，禁止）。

## 2 派生规则（为什么不用 `canonical_root()`）

实测（2026-10-12）：`canonical_root()` 在 worktree 与主区都返回 `/Users/xiamingxing/Workspace`，
但在 `HOME=/tmp/emptyhome` + `env -u OMOSTATION_ROOT` 下**抛 RuntimeError**（`bin/lib/repo_root.py`
定位不到规范检出）。把测试期望挂在它上面 = 引入一个新的 host 依赖，与本轮去 host 的方向相反。
故分三类：

1. **仓内路径** → 由 registry 声明值给出（`program.args`、`outputs.stdout`）。registry 与被测的
   `runtime/cron/*.plist` 副本是**两份独立提交物**，符合 ISC-3 非同源。
2. **`$HOME` 下的外部路径** → 由 `Path.home()` 组合（`~/.local/share/zhixing-dashboard/…`、
   `~/agents/…`、`~/.local/bin`）。实测 `.omo/cron/registry.yaml` **无** PATH / EnvironmentVariables
   键，所以这类值不可由 registry 派生；这 3 处是本轮**唯一**保留的面向 host 的面（点数由判据用例钉死）。
3. **检出根本身**（meta-doctor 的锚定根）→ `code_root()`，它在任何检出下都不抛。

`WorkingDirectory` 在 registry 里没有同名字段，故由 registry 的 `outputs.stdout` 反推：
`Path(entry["outputs"]["stdout"]).parents[2]`（`<root>/runtime/cron/<name>.log` ⇒ `<root>`）。
这是 registry 两个独立字段之间的结构关系，不是从被测 plist 自己算期望。

## 3 ISC（每条自带否证方式）

- **ISC-1 同尺差分**：改前 13 / 改后 0 由**同一次扫描**产出并断言，扫描对象是 `tests/unit/**` 全量
  （非三个文件名），尺为 `/usr/bin/grep -rn`。否证：把扫描面缩到具体文件也能得 0 ⇒ 用例必须扫全量。
- **ISC-2 断言强度不降**：13 处一律改**关系断言**而非删除。`==` 不得换成 `in` / `is not None`。
  否证：任一 `==` 放宽 ⇒ 变异对照当场红。
- **ISC-3 非同源**：期望值来自 `services.yaml` 与 `Path.home()`，被测对象是 `runtime/cron/*.plist`
  副本。否证：把 `services.yaml` 中该 entry 的 `program.args` 改一个字节 ⇒
  `test_agent_cell_semantic_scheduler` 与 `test_reference_cell_direct_local_schedule` 必须红。
- **ISC-4 反向钉住合法项**：新增断言声明 §1 表 2 个非锚点文件的 3 处命中**必须存在**。
  否证：删掉那 3 处 ⇒ 反向断言当场红 ⇒ 挡住「顺手清理」。
- **ISC-5 三环境读数（实测记法，不写「同判」这种含糊话）**：四条用例（3 改造 + 1 判据）在
  ① 未声明 profile、② `OMOSTATION_STATE_ROOT=<tmp>`、③ `HOME=<空目录>` + `env -u OMOSTATION_ROOT`
  三种 env 下各跑一遍。**①② 必须逐字节同判**（实测各 25 passed）—— 证明写面声明不影响测试面。
  **③ 只允许 §2 第 2 类那 3 处 `str(HOME / …)` 组合断言转红**（reference-cell 的 `--code-root`、
  `--attempts-root`、`PATH` 里的 `~/.local/bin`），其余必须绿。
  这条不是回归：registry 不声明 PATH / EnvironmentVariables（实测 `registry.yaml` 无该键），
  这 3 处无法由 registry 派生，只能由 home 组合；**基线的 host 字面量在 ③ 下会「绿」，那是假绿**
  —— 它断言的是绝对字面量等于 plist 里的值，而 plist 本身也是同一字面量，敌意 HOME 照样通过。
  改后 ③ 转红是**测对了**：期望值现在随真实 home 变，home 被换成空目录就应当不匹配。
  否证：由 `test_home_composition_is_confined_to_declared_sites` 把点数钉成
  reference-cell 3 / agent-cell 0 —— 想靠「撤销这 3 处」把 ③ 洗绿 ⇒ 当场红。
- **ISC-6 门禁零新增硬失败**：判据是**差分**而非绝对绿 —— `make gac-local-gate` 在本轮后的硬失败集合
  必须等于基线硬失败集合。实测基线有 **2 条预存硬失败**（`service-config-drift` 与 `check-work-landed`）；
  `check-work-landed` 在主工作区（origin/main 检出）与本轮 worktree 读数**逐字相同**
  （`blocking=2`：另两个会话 2026-10-04 的两条 run `missing_landing`），不是本轮引入，
  也**不得**为了让门禁变绿去登记它的债或改窄它。
  否证：在任一环境跑出第 3 条硬失败 ⇒ 不满足。

## 4 交付形态

一个 BET 一轮：spec 落 `docs/superpowers/specs/`、台账绑定 `accepted_specifications`、
改动只碰 3 个测试文件 + 1 个新增判据用例 + spec + 台账。`projects/omo` 零改动，无 gitlink。

## 5 明确不做

- 不改 `services.yaml` 里的 host 字面量（那是 B4b 批次 2+ 需授权的本体）。
- 不改 `runtime/cron/*.plist` 副本（`generate: false`，是外部安装态的镜像，改它 = 伪造现实）。
- 不动 §1 表的 2 个非锚点文件。
- 不放宽 `service-config-drift`、不登记它的债。
- 不使用 `canonical_root()` 作测试期望源（§2 实测抛错）。
