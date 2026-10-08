---
schema_version: specification/v1
spec_version: 1.0.0
title: system.yaml 空形的消费侧折叠 —— 生成器在「键存在但为 null」时不得比「键缺席」更笨
bet_id: BET-Y2Q4-T10-236
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-07
---

# T10-235 的补料侧 —— 创建者写空形是对的，消费方把空形读成 0 是错的

## 1 判据现状（2026-10-07 实测，非引用）

BET-Y2Q4-T10-235 交付了 `.omo/state/system.yaml` 的创建者并把它摘库（PR #4671 → `bbcb4e279`）。
其 receipt §5 记录了一处**由该交付暴露**的消费侧红，本轮把它做实。合并后检出上的直接读数：

| 量 | 读数 |
|---|---|
| `python3 bin/gac/materialize-system-state.py --json` 后 `.omo/state/system.yaml` 的 null 键 | 6 个：`health_score` / `health_score_source` / `health_score_generated_at` / `governance_anomaly_score` / `governance_feedback_last_run` / `service_online_ratio` |
| `python3 bin/mof/generate-brief.py --protect`（缺文件） | rc=0（`:390 health_score = 90` 兜底） |
| 同上（#4671 之前的跟踪快照，`health_score: 46`） | rc=0 |
| 同上（创建者物化后的空形） | **rc=1** `TypeError: '>=' not supported between instances of 'NoneType' and 'int'`，栈顶 `generate-brief.py:509` |
| `make gac-local-gate-strict`（CI 同装置） | rc=1 / 86 checks，其中 `brief-protect` 落 `soft_warns`（不进 blocking） |

三态里失效形状恰好落在**中间**：缺席能跑、有值能跑，「键存在但为 null」不能跑。
空形本身是 T10-235 的**契约**而非缺陷 —— `bin/gac/omo-state-write-guard.py::check_field_ownership()`
对 present 与 `write-owners.yaml` declared 做**双向**比对（`:191` undeclared-key / `:200` ghost-declaration），
创建者必须产出恰好等于声明集的键集合，所以生成者不拥有的 13 个键只能以空形出现。
⇒ 要改的是消费面，不是 §7.1 的空形语义，也不是摘库。

## 2 语义：null ≠ 缺席，而 `.get(key, default)` 只看缺席

`bin/mof/generate-brief.py:397-399`：

```python
data = yaml.safe_load(system_yaml.read_text(encoding="utf-8")) or {}
health_score = data.get("health_score", 90)          # present-but-null ⇒ None，默认值不生效
gov_anomaly  = data.get("governance_anomaly_score", 100)
```

`dict.get` 的第二参数只在**键不存在**时返回；键存在且值为 `None` 时返回 `None`。于是同一个脚本里
出现两种「未测量」的读法：`:390-392` 的模块内默认（90/100/1.0）代表「没测」，而 `None` 代表「测了，
值是空」—— 但下游 `:509 if health_score >= 90`、`:511/:513/:522` 的 f-string 都只准备了数值。

崩溃点只有 `:509` 一处（比较运算），`:513` 的 `gov_anomaly` 是纯插值，会把 `None/100` **渲染**出来。
所以这一处缺陷有两个面：一个 rc=1，一个把「未测量」显示成 `None/100`。折叠必须同时覆盖两者，
判据用「空形 ≡ 缺席」的等价性表达，正是为了不把修复窄化成「只补那条比较」。

## 3 站点面：AST 可复算清单（装置写明，不靠正则）

同一形状的站点由 AST 扫描产出（`ast.Call` 且 `func.attr == "get"`、首参为这 6 个键之一的
`ast.Constant str`、位置参数 ≥ 2）；正则量不出这条判据，因为它对换行包裹的调用和嵌套默认值
给出的读数在 10 / 11 / 13 之间摇摆（本轮实测过三种写法各给一个数）。

| 面 | 站点数 | 明细 |
|---|---|---|
| `bin/**`（root 侧，本 BET 交付面） | **11** | `gac/governance-readiness.py:160`、`gac/m1-closeout-report.py:179`、`gac/unified-health-score.py:281`、`mof/generate-brief.py:398` `:399`、`reports/quarterly-report.py:133` `:134` `:139` `:395` `:406`、`ssot/weekly-review.py:77` |
| `projects/**`（跨仓，另议） | **13** | `cockpit` 4 处、`model-driven` 3 处、`omo` 6 处 |
| 合计 | **24** | 与 T10-235 receipt §5 的总数一致 |

⚠️ T10-235 receipt 把这一组数写成了「11 处在子模块 / root 侧 13 处」—— **拆分写反**，本轮同一次
AST 扫描的两列读数订正为 root 11 / 子模块 13（总数 24 未变）。该 receipt 的证据摘要随本轮重算。

root 侧 11 处里，实测行为在空形下改变的只有 `generate-brief.py` 的 2 处（同一函数内的键对）；
`governance-readiness.py` / `unified-health-score.py` / `weekly-review.py` / `quarterly-report.py`
在「缺席」与「空形」两种内容下读数相同，`m1-closeout-report.py` 的 `--help` 失败在两侧同为 rc=1
（`repo_root` 的 PYTHONPATH 预存问题，与本 BET 无关）。⇒ 本轮的**行为**修复面是 1 个函数，
**认知**修复面必须覆盖全部 11 处 —— 否则下一个往 `quarterly-report.py` 加数值比较的人会重犯同一件事。

## 4 契约：折叠的是「未测量」，不是默认值

I1 **等价性（主判据，hard-to-vary）**：对同一棵检出，只换 `.omo/state/system.yaml` 的内容 ——
「文件缺席」与「创建者物化后的空形」两侧，`generate_brief_content()` 的输出经
`normalize_brief_content()`（剥掉 `> **Generated**:` 时间戳行）后**逐字节相等**，且两侧 rc 均为 0。
等价性同时钉住 `:509` 的崩溃与 `:513` 的 `None/100` 渲染，且不冻结任何具体默认值。

I2 **真值不被折叠吞掉**：`health_score: 46` 的快照内容下，读数必须仍是 46（走 `:519` 的 else 分支，
显示「警戒」）。折叠只在「键存在且值为 `None`」这一条路径上生效 —— 把它写成 `data.get(k) or default`
会连带折叠合法的 `0`，本判据正是为了排除这种写法。

I3 **改法局部化**：折叠发生在读取处（`bin/mof/generate-brief.py` 内，两个键各一次），
不新增 `bin/lib/` 公共装置、不改创建者的空形语义、不改 `write-owners.yaml` 声明集。
理由：root 侧其余 9 处实测不受空形影响，为它们预先造抽象就是把 HOW 写死；
I4 的集合相等判据负责在**下一处**需要它时把作者逼到同一条判据前。

I4 **站点清单钉成集合相等**：新增用例对 `bin/**` 跑 §3 的 AST 扫描，断言实测集合与该清单
**相等**（多一个即红），并对每一条给出可指认的处置（已折叠 / 实测同读数）。先例与纪律：
`tests/unit/test_system_yaml_write_plane.py:240`（清单本体）、`:293`（断言集合相等）、
`:296`（每条理由指向真实文件）—— AGENTS.md §7「扫源码的门禁必须自证」③。

## 5 可见性：让这条红成为阻塞信号

T10-235 receipt 先前写「`brief-protect` 在 `.github/workflows/` 零调用」，本轮复测**否证**：
`gac-gate.yml:144-150` 的 `python3 bin/gac/gac-local-gate.py --strict` 确实调它。让它对 CI 失效的是
`bin/gac/gac-local-gate.py:601-602` 的 `SOFT_CHECKS`：`:1200` 把 `name in SOFT_CHECKS` 的失败从 blocking
剔除、`:1203` 归入 warnings ⇒ rc=1 也只是一条 warning，CI 照绿。

所以本 BET 的可见性判据不是「纳入 CI 面」（已成立），而是「**有一条阻塞的 CI 面会因它变红**」。
两条候选，取前者：

| 方案 | 判定 |
|---|---|
| **A（取）** 新增 `tests/unit/test_brief_null_shape.py`，在 `.github/workflows/governance-check.yml` 的显式 pytest 白名单里点名 | 有先例（同 workflow `:196` / `:200` 点名 T10-235 两条用例）；作用面对象是被测契约本身，红=契约破 |
| B（舍） 把 `brief-protect` 摘出 `SOFT_CHECKS` | 该检查给的命令是 `["bin/mof/generate-brief.py", "--protect"]`，**不带 `--write`**，而 protect 分支的前置是 `:576 if args.protect and args.write and BRIEF.md.exists()` ⇒ 分支恒不进入。把它升级成阻塞等于放大一条没在做保护的检查，并把所有 BRIEF 噪声一起变红 |

I5 **反基线**：把折叠退回改动前（`:398` 恢复 `data.get("health_score", 90)`）时，A 的用例必须**点名失败**，
且失败消息含 `NoneType`；折叠存在时同一用例绿。只有「绿」不构成判据 —— AGENTS.md §7⑤
「『改后为 0』必须与『改前为 N』由同一次扫描产出」。

I6 **登记面**：`governance-check.yml` 的点名行、`.omo/_truth/registry/ci-surfaces.yaml`（若 CR-CI-SURFACE-SSOT
要求该 workflow 面已登记）与 `governance-checks.yaml`（本轮不新增 `bin/` 脚本，`script_baseline` 不动）。
指认命令：`python3 bin/gac/check-ci-surfaces.py` rc=0。

## 6 非目标

- 不动 `bin/gac/materialize-system-state.py` 的空形语义与键集合（13 个生成者所有的空形键原样保留）。
- 不撤 `.gitignore:297` 的摘库，不把 `system.yaml` 放回跟踪。
- 不改「未测量」的**显示文案**：等价性判据（I1）要求空形与缺席同读数，而缺席今天显示 `90/100`。
  把「未测量」显示成「未测量」会同时改变缺席侧的行为，那是另一条判据、另立 BET。
- 不碰 `projects/**` 那 13 处（跨仓，需 re-pin 指针与另一条 CI 面）。
- 不把 `brief-protect` 摘出 `SOFT_CHECKS`（理由见 §5 方案 B），也不动 `:1200/:1203` 的 blocking/warning 划分。
- 不接 `state-freshness-check` 那条红 —— 它在 CI 因 `ci_skip` 根本不执行，且其均分语义归 G9。

## 7 验收（逐条可跑）

| # | 命令 | 期望 |
|---|---|---|
| 判据-1 等价性（I1） | 同一棵检出两侧对照，装置 = **无 flag 的 stdout 运行** `python3 bin/mof/generate-brief.py`（只打印、不写文件，`:589-604`）：先移走 `system.yaml` 取一份 stdout，再 `python3 bin/gac/materialize-system-state.py --json` 物化空形后取第二份 | 两侧 rc=0；两份经 `normalize_brief_content()` 后 `diff` 为空 |
| 判据-2 真值不吞（I2） | 放回 #4671 之前的快照内容（`health_score: 46`）后跑 `--protect` 与 `--write` | rc=0 且输出含 `46/100`，不含 `90/100`（防默认值反噬） |
| 判据-3 用例绿 | `python3 -m pytest tests/unit/test_brief_null_shape.py -q -p no:randomly` | 全绿；含三态用例 + I4 的 AST 集合相等用例 |
| 判据-4 反基线（I5） | 临时把 `:398-399` 改回 `data.get(key, default)` 后单跑判据-3 的等价性用例 | 该用例 FAILED 且消息含 `NoneType`；改回后绿 |
| 判据-5 检测器不自证为空（I4） | 向 AST 扫描喂一棵含 `bin/` 合成站点（新增一处 `.get("health_score", 0)`）的复刻树 | 扫描点名该合成站点（清单外）⇒ 集合相等断言非空绿 |
| 判据-6 CI 点名（I6） | `git grep -n test_brief_null_shape -- .github/workflows/` | 命中 `governance-check.yml` 一行 pytest 调用（`tests/unit/**` 不在任何 CI 白名单，未点名即不算交付） |
| 判据-7 空形语义未动 | `python3 bin/gac/materialize-system-state.py --dry-run --json` + `python3 bin/gac/omo-state-write-guard.py --json` | `key_set_equals_declared: true`、`empty_shape_keys: 13`；ownership 三类计数全 0 |
| 判据-8 摘库未撤 | `git ls-files .omo/state/system.yaml`；`git check-ignore -v` | 空 / 命中 `.gitignore:297` |
| 判据-9 门禁不瞎 | `python3 bin/gac/gac-local-gate.py` 与 `python3 -m pytest tests/unit/test_system_yaml_materializer.py tests/unit/test_system_yaml_consumer_inputs.py tests/unit/test_system_yaml_write_plane.py tests/unit/test_projection_reader_resolution.py -q -p no:randomly` | 非 strict PASS、`.omo/state` 跑后仍空；81 passed 不减 |

## 8 交付面（预列，实施时逐条对齐）

`bin/mof/generate-brief.py`（折叠读取处 2 行）、`tests/unit/test_brief_null_shape.py`（新）、
`.github/workflows/governance-check.yml`（点名一行）、`docs/plans/3y-bet-ledger.yaml`（本条目 + 状态）、
本 spec、`.omo/_knowledge/retros/BET-Y2Q4-T10-236.md`、`docs/reports/` 下对应 receipt。
登记面若 `check-ci-surfaces.py` 要求则同步 `.omo/_truth/registry/ci-surfaces.yaml`。

同批回补 T10-235 的两处证据订正（本轮实测）：`docs/reports/2026-10-07-system-yaml-materializer-closeout.md`
§5 的站点拆分（11 root / 13 子模块）与其证据摘要重算。
