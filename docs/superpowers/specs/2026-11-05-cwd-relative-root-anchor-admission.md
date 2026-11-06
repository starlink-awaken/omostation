---
schema_version: specification/v1
spec_version: 1.0.0
title: 第四类根的准入 —— 仓内相对锚（CWD 落点）在两把根尺里按构造不可见
bet_id: BET-Y2Q4-T10-288
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-05
---

# 第四类根的准入

> 本规范是**准入裁决 + 检测器类目契约**，不是实现。实现由本 BET 的执行腿承担。
> 所有读数由 `origin/main = 3a1c0770290a5d2a1ddbd896fb3f9de358ecbc90` 产出，装置见 §4；
> 按 AGENTS.md §7「门禁的尺本身会随 base 变」，引用本文件任何读数时必须连带这个 base。

## 1. 问题：根的类目里漏了一类，而漏的形状是「不挂任何根」

ADR-0456（`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`，按**文件名**引用：
`id: ADR-0456` 的文件有两份，另一份是 governance-downshift-closeout-grading）把根收敛成三个可解析的
落点：`code_root()` 读、`state_root()` 写、`install_root()` 定位运行时代码。AGENTS.md §7 已登记
「根有四类落点，第四类是 CWD」，但**检测器没有第四类**：

| 落点 | 判别方式 | 现有尺是否覆盖 |
|------|----------|----------------|
| 检出根 | `__file__` / `parents[` / `code_root` | 是（`CHECKOUT_MARKERS`） |
| profile 的 state 根 | `state_root` / `event_ledger_path` / `state_file_read` / `projection_read` | 是（`_STATE_MARKERS`、`RESOLVERS`） |
| 运行时代码安装位 | `install_root` | 是（注册表内容驱动） |
| **进程 CWD** | 锚既不是上述任何一种，且其自身文本含仓内相对字面量 | **否 —— 按构造不可见** |

不可见不是「名单没更新」，而是两把尺的匹配规则都不认这种形状（§3 逐条给机制）。

## 2. 确证的两处站点（tip 上活着）

**① `projects/omo/src/omo/workflow/lock_graph.py`（根仓 pin `b22152e77a851f3825105a73fc8577724fd7fc3c`）**

| 行 | 内容 | 性质 |
|----|------|------|
| `:5` | `STATE_DIR = Path(".omo")` | 相对锚，不读 profile，落点随进程 CWD |
| `:10` | `state_dir = STATE_DIR / "state"` | 派生变量链 |
| `:11` | `state_dir.mkdir(parents=True, exist_ok=True)` | 写面创建 |
| `:24` | `out_file.write_text(json.dumps(...))` | 写面 = `<CWD>/.omo/state/lock-graph.json` |

唯一读者 `bin/gac/swarm-activity-dashboard.py:140` 把 `graph_file` 挂在 import 时求值的检出根上，
`:141 if not graph_file.is_file(): return {}` fail-soft ⇒ **生产者 / 消费者 / 契约三方错位**，
形状是「死写面 + 活读者」：`generate_lock_graph_snapshot` 在 tip 生产路径零调用点
（`git grep` 只命中定义本身、`tests/projects/omo/workflow/test_lock_graph.py`、一份 2026-08 的历史 plan 与 `docs/pitfalls.md`）。

gitlink 边界判据（防把「根仓侧看不见」读成「文件不存在」）：
`git -C projects/omo cat-file -e b22152e77:src/omo/workflow/lock_graph.py` → rc=0；
`git cat-file -e origin/main:projects/omo/src/omo/workflow/lock_graph.py` → rc=128
`exists on disk, but not in 'origin/main'` —— 那是 gitlink 边界，不是缺席（AGENTS.md §6）。

**② `bin/notification.py`（根仓 tip）**

| 行 | 内容 | 性质 |
|----|------|------|
| `:33` | `PROPOSALS_DIR = Path(os.environ.get("HITL_PROPOSALS_DIR", ".omo/_knowledge/hitl-proposals"))` | env 有默认值即默认生效；写落点随 CWD |
| `:35` | `DEFAULT_CONFIG_PATH = Path(".omo/_truth/registry/notification-config.yaml")` | 同形的读面 |

`HITL_PROPOSALS_DIR` 在全机任何 plist / registry / yaml / toml / sh 与 `crontab -l` 里都未被声明
（命中该名字的只有本文件、`bin/hitl-proposal.py` 与其测试）⇒ HITL 人在环提案面的落点是未裁定面。
实测该面在 canonical 检出 `is_dir()=False`、14 个已登记 worktree 全不命中 ⇒ **缺陷成立但从未发火**，
本条是准入项而不是事故。

## 3. 为什么两把尺结构性看不见 —— 机制逐条

- **尾段比较**：`tests/unit/test_resident_write_plane_split.py:325` `reader_pairs` 用
  `text = _strip_dynamic(_text(segs[1:]))`，即丢掉 `segs[0]`（锚）后再比对族名。
  `Path(".omo") / "state" / "x"` 的比较串因此是 `state/x`：既过不了 `scan_writers:288`
  的 `_repo_path()`（要求 `startswith(".omo/" | "runtime/")`），也过不了 `:326` 的
  `if "/" not in text: continue` ⇒ 开头的 `.omo` 藏在锚表达式里，比较串里永远没有它。
- **只走 `Div` 节点**：`reader_pairs:317` 与 `scan_writers:282` 都只遍历 `ast.BinOp(op=Div)`。
  `bin/notification.py:33` 整条是**单个 `Path(...)` 调用**，没有 `Div` ⇒ 连候选都不是。
- **准入谓词要求 `__file__`**：`tests/unit/test_writeplane_root_pin.py:279-283`
  `pinned = ("__file__" in ast.dump(base)) or (isinstance(base, ast.Name) and base.id in aliases)`，
  未 pinned 直接 `continue` ⇒ 相对锚不进任何桶，包括 `:381`
  `test_detector_does_not_fire_on_seam_or_read_plane` 用来反证的那两个读面桶。
  它连「被看见但不计」都做不到 —— 与 §7「登记面的类目缺失」同源。

## 4. 读数与装置（可复跑）

装置：`git show origin/main:tests/unit/test_…py` 原样取尺，`importlib` 载入后调它自己的函数；
被检对象 = `git archive origin/main bin` 造的对照树 + 按根仓 pin 归档的 `src/omo` 树
（AGENTS.md §7⑦「反基线读数必须在判据指定的那把尺上复算」；§7③ 空绿不被接受）。
脚本：`/tmp/t286-closeout/probe-d1.py`（一次性装置，不进仓）。

| 读数 | 值 |
|------|-----|
| `reader_pairs(bin@tip, STATE_FAMILIES=42)` | **223 行**；含 `notification.py` **0**、含 `swarm-activity-dashboard.py` **0**、含 `lock_graph` **0**、行内出现 `Path(` 锚 **0** |
| `scan_writers(omo@b22152e77)` | 桶 `{state:120, bare_template:56, bare_inline:84, opaque:3}`；键中 `lock_graph` **0** |
| `scan_checkout_pinned_sites(tip 树)` | **456 站点**，桶 `{_truth:163, _state:103, _delivery:78, runtime:50, _knowledge:62}`；gated **153** / pairs **143** / files **95**（`_truth` 162→163 由 PR #5059 在 `bin/ssot/auto-pruner.py` 新增一处钉检出根站点，与本文件的第四类根无关；`_knowledge` 面逐项未变） |
| 反证（尺在该对象上复现自己写下的基线） | `SPEC_MARKER_READINGS` / `SPEC_GATED_SITES=153` / `PAIRS=143` / `FILES=95` **逐桶相等 ⇒ PASS** |

反证不通过时本轮读数一律作废，不得写进任何文档。

## 5. 契约（本 BET 的 done_when 依据）

**AC-01 检测器新增 `RELATIVE` 类目**，判据 = 以下两形之一：
 (a) `/`-链的锚既不是 `__file__` 派生、也不是 `RESOLVERS`/其别名、也不是函数形参，
 且该链的字面量部分以 `.omo/` 或 `runtime/` 开头；
 (b) 单个 `Path(...)`/`os.path.join(...)` 调用，其字面量实参以 `.omo/` 或 `runtime/` 开头
 （含 `Path(os.environ.get(NAME, "<仓内相对默认>"))` 这一形）。
正反用例各≥1，且必须给**变异对照**（摘掉类目 ⇒ 用例当场红；AGENTS.md §7③）。

**AC-02 两处站点分别处置**，结论写进 ADR-0456 addendum（按文件名引用）：
 `lock_graph` 面显式降级并登记（今天无写者，只把 `:5` 换成缝是化妆式修复——改完不改变任何读数；
 **删代码需另行授权**）；`notification` 面默认值改经 `state_root()` 拼接**或** env 缺席即拒写（fail-closed），
 `:35` 同形一起处理。

**AC-03 判据口径**：一次性粗扫的计数（如 `bare_inline 84`）一律**不得当契约名单引用**；
判某处写面是否仓内相对，按**派生变量链**展平（`STATE_DIR → state_dir → mkdir/write_text`），不按常量名。

**AC-04 见下面 §6 两条订正**，不得按旧措辞实施。

## 6. 对既有草稿措辞的订正（两处，均已复测否证）

- ~~「`_classify()` 只认 `parents[` / `__file__`」~~ ⇒ tip 上
  `CHECKOUT_MARKERS = ("__file__", "parents[", "code_root")`（`:68`，2026-11-02 已补 `code_root`）。
  看不见相对锚的原因不是标记集陈旧，是 §3 的「尾段比较 / 只看 Div / 准入要求 `__file__`」。
- ~~「`test_writeplane_root_pin.py` 只统计已登记 resolver 的站点」~~ ⇒ 它统计的是 `__file__` 派生站点；
  真正的失明在那条准入谓词，不在登记名单宽度。

## 7. 非目标

- 不改任何 plist、不动 cron、不 unshallow 主仓。
- 不在本 BET 内迁移 HITL 提案面的历史内容（若有）；只裁定其根。
- 不把 `lock_graph` 的死写面直接删除（需授权，见 AC-02）。
