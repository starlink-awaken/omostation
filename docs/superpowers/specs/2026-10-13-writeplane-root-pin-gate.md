---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B1 残留 —— bin/ 内由 __file__ 反推检出根再拼 profile 写面路径的站点，收成 shrink_only 基线门禁
bet_id: BET-Y2Q4-T10-250
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-13
---

# 写面根钉死门禁 —— 让「新增一处检出根拼法」当场变红

## 0 需求出处

`/Users/xiamingxing/.qoder-cn/plans/nimble-bay-asp.md` B1 的交付是「`canonical_root()` 升级为
code/state 双根；`omo_paths` + 9 处 `DEFAULT_LEDGER` + `OMO_PRINCIPAL_ID` 接入」，完成判据是
`grep -rE "DEFAULT_(EVENT_)?LEDGER\s*=" bin/` → 0 命中。该判据已达成（本轮复测：`/usr/bin/grep -rE`
在 `origin/main` 上 0 命中），但它只覆盖**常量命名形状**，覆盖不到 B1 的真正意图：
「写目标跟随 profile 声明的根」。

本轮实测到的残留是这个意图的反面：**路径由 `__file__` 反推的检出根拼出来**，于是无论
`OMOSTATION_STATE_ROOT` 声明成什么，写面都落在检出里。ADR-0456 的读/写分界因此在这批站点上
不是被违反了，而是**根本没有到达** —— 它们从未调用过缝。

## 1 实测读数（2026-10-13，`origin/main` @ `ae26d090d`，判据即 §3 的 AST 规则）

> 2026-10-25 复核：`bin/gac/check-work-landed.py` 新增 BET retro 兜底读面
> (`RETROS_DIR = WORKSPACE / ".omo/_knowledge/retros"`)，落在**排除面**
> `.omo/_knowledge`（读面/署名文档面，随检出）—— 门禁管辖的
> `.omo/state` + `runtime` 读数与基线**零变化**（仍 154 站点 / 144 对），
> 仅排除面 `.omo/_knowledge` 62 → 63、全表 460 → 461。

| marker | 站点 | 本轮判定 |
|---|---|---|
| `.omo/_truth/**` | 160 | 排除 —— 读面 SSOT，按 ADR-0456 跟随当前检出，`__file__` 拼法在此是契约不是缺陷 |
| `.omo/state/**` | 103 | **纳入** 门禁 |
| `.omo/_delivery/**` | 82 | 排除 —— 全机 symlink 桥（`delivery_anchor.py:87`），AGENTS.md §7「gitignore ≠ 本地化」；改道它等于改协调面语义 |
| `.omo/_knowledge/**` | 63 | 排除 —— 署名文档/历史面，随检出 |
| `runtime/**` | 51 | **纳入** 门禁 |
| `kos/**` | 2 | 排除 —— 运行时产物但不在 ADR-0456 的写面列举内，另案 |

纳入部分 = **154 个行级站点 / 144 个 (文件, 拼出的整条相对路径) 去重对 / 95 个文件**（全表 461 站点）。
与既有 `tests/unit/test_system_yaml_write_plane.py` 的重叠 = **1 处**
（`bin/gac/architecture-check.py:47` 的 `.omo/state/system.yaml`）—— 该文件在邻居门禁里已被判为
死码（`CORE_DOCS` 常量零消费者，T10-220 决定不为它造判据），本面仍如实登记它一次：
两面各自完整，不互相代答。

⚠️ 第一次作废读数 = 「63 处 / 52 文件」：一次性粗扫按路径**首段**匹配，使 `.omo/state/**`
整体漏认（首段是 `.omo`），且未排除 `bin/_archive/**`。

⚠️ 第二次作废读数 = 「81 处 / 64 对 / 46 文件」，同一形状的**另一面**（AGENTS.md §7⑧：实测集合
⊋ 允许清单时先怀疑匹配规则）：规则 ② 只认「链最左端是模块级 `__file__` 派生**名字**」，
于是结构性看不见直接内联拼法的 `bin/plan/bet-ledger.py:477`
（`Path(__file__).resolve().parents[2] / "runtime" / "omo" / …`）—— 该处 `runtime/**` 因此漏计。
按名匹配的判据与「名字常量」这一种书写习惯同源，换成内联表达式就瞎 ⇒ §3 规则 ② 已放宽到
「最左端子表达式自身含 `__file__`」**或**「绑定到 `__file__` 派生值的名字」。

⚠️ 第三次作废读数 = 「154 站点但路径渲染成 82 / 65 / 47」，方向反了的那条实现：§3 原句
「只统计最外层 `/` 链」若写成「`node.left` 是 Div 就跳过」，跳过的其实是**外层**（外层节点的正是要留的那个），
于是每条链只剩第一段 —— `WORKSPACE / ".omo" / "state" / "health.yaml"` 渲染成 `.omo`，
匹配不上任何 marker，整形漏认（`.omo/state` 因此从 103 掉到 31）。这条由本 BET 自己的
ISC-2 自证用例在写完后第一次运行时抓到，判据已改为「凡 `id(node)` 是某个 Div 节点的左操作数即内层，跳过」，
并留 `test_detector_renders_the_whole_chain_not_just_its_first_segment` 钉住渲染方向。
本 spec 的所有读数由 §3 那条将要发布的判据本身产出，两者同源。

**合并后复测（2026-10-13，`origin/main` @ `b59797e6d` 合入本分支后）**：三个读数逐字不变 ——
154 / 144 / 95。main 期间落下的 `bin/gac/dual-profile-verify.py`（BET-Y2Q4-T10-248）**不进门禁集合，
且不是漏认**：它唯一的 `__file__` 用法是 `sys.path.insert(0, … parents[1] / "lib")`（读面），
写目标走 `state_root()`，而 `SYSTEM_YAML_REL = Path(".omo") / "state" / "system.yaml"`
是无根的相对常量 —— ISC-3 那条「相对常量不得命中」的反面控制由此有了生产代码里的活样本，
不只活在 fixture 里。

## 2 Ideal State Criteria（每条带反证）

- **ISC-1 覆盖性**：判据对 `.omo/state/**` 与 `runtime/**` 两类拼法的读数为 154 行级站点，
  且**同一**次扫描产出「改前 N」与「改后 0（新增项）」两个数。
  反证：把检测器的 marker 表砍掉 `.omo/state`，基线对拍用例当场红。
- **ISC-2 自证（§7②）**：向临时目录注入**三种**命中形状 —— ① 名字派生
  （`WORKSPACE = Path(__file__).resolve().parents[2]` + `WORKSPACE / ".omo/state" / "x.json"`）
  ② 内联派生（`Path(__file__).resolve().parents[2] / "runtime" / "y.json"`）
  ③ 分段拼法（`WORKSPACE / ".omo" / "state" / "history.json"`，渲染必须是整条
  `.omo/state/history.json`）—— 检测器必须点名三条。
  反证：空绿不是证据 —— 没有这条，「绿」可能只是检测器压根没命中；只注入 ① 则 §7⑧ 那一面的
  漏认（改名/内联）看不见；不注入 ③ 则「链截到只剩第一段」也能绿（第三次作废读数即此）。
- **ISC-3 反过宽（§7④）**：同一注入里放三条**不该命中**的形状 —— ① 经 `state_root()` 取根
  ② 拼 `.omo/_truth/registry/**` ③ 拼 `.omo/_knowledge/**` —— 三条都不得进入门禁集合，
  且 ②③ 必须由同一扫描**分类**出来（可见但不计），否则「宽到把读面也吞掉」也能凑过对拍。
  反证：若检测器宽到把读面也吞掉，它可以用「往基线里塞几百条」自证通过。
- **ISC-4 shrink_only**：基线是一份显式 (文件, 路径) 集合，实测集合与之**双向相等**：
  新增一处 ⇒ 红；改掉一处不缩基线 ⇒ 红。
  反证：只断言「实测 ⊆ 基线」则清完的债可以从名单里悄悄消失而无人记账。
- **ISC-5 零运行时效应**：本轮**不改任何真实写目标**，一条路径的落点都不动。
  反证：`git diff --name-only origin/main...HEAD`（**三点**，取 merge base）里不得出现 §1 表列的 95 个文件中的任何一个。
  尺必须是指名那把：两点式 `origin/main..HEAD` 在 base 落后时把「main 新增而我这棵树没有」
  也读成自己的改动（本轮实测：main 落了 #4741 后，两点式多报 5 个 `D` 行，全是别人的交付）。
- **ISC-6 CI 可见**：用例进 `.github/workflows/governance-check.yml` 的显式 pytest 白名单
  （该名单按文件逐一点名、无 `tests/unit/**` glob，不加这行则「CI 绿」不是它的证据）。

## 3 判据（写侧形状）

命中条件三条同时成立：① 文件在 `bin/**/*.py`，排除 `bin/_archive/**` 与任何 `_vendored` 段；
② 表达式是 `Path` 的 `/` 链，**链最左端**要么是该文件**模块级**由含 `__file__` 的赋值绑定的名字，
要么**其自身子表达式**含 `__file__`（内联拼法 `Path(__file__).resolve().parents[2] / "runtime" / …`）
—— `ast` 里 `Path(__file__).resolve().parents[2]` 是 `Subscript`，按 `Call` 匹配会漏，
只按名字匹配也会漏（§1 第二次作废读数即此），因此一律按 `ast.dump` 是否含 `__file__` 判，不按节点类型判；
③ 去掉变量段后的**字面量前缀**以 `.omo/state` 或 `runtime` 开头（按整串前缀匹配，不按首段；
`== marker` 或 `startswith(marker + "/")`，不做裸 `startswith`，否则 `runtimefoo` 会被吞）。
**只统计最外层 `/` 链**：`Path("/a") / "b" / "c"` 在 `ast` 里是两层嵌套的 Div，`ast.walk` 会同时访问
外层与内层，若不过滤则同一行按前缀重复计入。判据是**方向明确的那条**：先收集「凡是某个 Div 节点的
`left` 操作数」的节点 id 集合，命中节点不得在该集合内。
⚠️ 写成反方向（"`node.left` 是 Div 就跳过"）跳过的是**外层**——外层节点正是要留的那个，
于是每条链只剩第一段，`.omo/state` 从 103 掉到 31（§1 第三次作废读数）。
同一行内即使有多条互不嵌套的链也只按 (文件, 行) 计一次 —— 读数因此是**行级站点数**，
不是表达式数；ISC-4 的 (文件, 整条路径) 去重对另有 144 个，两个数不可互换。

## 4 范围边界

- 门禁只做**登记与止损**：让债可枚举、让新增当场变红。把这 154 处（95 个文件）改道到 `state_root()` 是
  与 B4b 同类的**分批授权**工作 —— 每处都要回答「这个写目标该不该跟随 profile」「改后读者在哪读」，
  不在本轮范围内，也不得由本轮顺手动。
- 不动 launchd/cron/plist、不动 `.omo/_truth/registry/**` 内容、不动权威 ledger。
- 本 BET 不新增 `bin/` 脚本（判据落在 `tests/unit/`，与 `test_system_yaml_write_plane.py` 同形），
  因此不触发 `check-bin-quota-diff`，`script_baseline` 一行不动。
