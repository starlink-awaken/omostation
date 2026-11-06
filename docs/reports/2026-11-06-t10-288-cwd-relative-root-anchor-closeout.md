---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-06
type: report
bet_id: BET-Y2Q4-T10-288
title: BET-Y2Q4-T10-288 收口收据 —— 第四类根（CWD 相对锚）准入与两处站点裁决
---

# BET-Y2Q4-T10-288 收口收据

工程腿 = PR #5070 squash `c3a93e9cc1c583f0083b5da302f9f9922645d4b2`（`2026-11-06T03:57:56Z` 入 main，4 件：
`tests/unit/test_resident_write_plane_split.py`、`tests/unit/test_writeplane_root_pin.py`、
`bin/notification.py`、`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md`）。
分支 base = `25d7a6ee7`，交付分两个 commit（lane 门禁 ADR-0122 §46）：code lane `8584a2394`、
governance_state lane `2b735dffb` + 行号订正 `efc62e4b7`。
契约：`docs/superpowers/specs/2026-11-05-cwd-relative-root-anchor-admission.md`
（`content_digest sha256:0bb74afcc60ae553e9760794226b85b852fc3f22a01a586bab3de35817c25eb1`，本轮未改正文）。

## 1. 交付内容

**尺 A** `tests/unit/test_resident_write_plane_split.py`（31 用例）
- 新增 `RELATIVE` 类目：`scan_relative_writers(src, shapes=("chain","call"))` + 每文件的
  `_relative_in_file(rel, tree, shapes)`；`scan_writers` 增第 5 桶 `relative`。
- 两形各自可关：`chain` = 根锚参与 `/` 拼接（`STATE_DIR / "state" / file`），
  `call` = 单个 `Path(...)` / `os.path.join(...)` 直接带仓内相对字面量，含
  `Path(os.environ.get(NAME, "<仓内相对默认>"))`。
- 判别式按 **派生变量链展平**（spec §5 AC-03）：`STATE_DIR → state_dir → mkdir/write_text`，不按常量名。
- 根/后缀只由正向枚举的根用处决定（R1 链最左、R2 `ROOT_ACTION_ATTRS` 的接收者、R3 `FS_CALLS` 的直接实参、
  R5 一跳进入模块内 callee 的形参；BoolOp 流向赋值目标；Tuple/List/Set 透明；默认 False）。
- 与尺 B 在相对面上同源对拍：`test_two_rulers_agree_on_the_relative_face` 断言
  `b_keys ⊆ a_keys` 且 `a_keys - b_keys == RULER_B_MARKER_BLIND`（唯一一条
  `bin/gac/check-debt-closure-discipline.py` / `.omo/debt/items`，因尺 B 的 `ALL_MARKERS` 不含 `.omo/debt`）。

**尺 B** `tests/unit/test_writeplane_root_pin.py`（12 用例）
- `BASELINE_RELATIVE_SITES` 收成 6 条；`test_relative_category_is_load_bearing` 改为两形分别断言。
- 头部注释记录本轮还掉的一处（`bin/notification.py` 的 `.omo/_truth/registry/notification-config.yaml`）。

**站点裁决两处**
- `projects/omo/src/omo/workflow/lock_graph.py`：**显式降级 + 登记**，不加缝、不删码
  （死写面 + 活读者；`generate_lock_graph_snapshot` 生产路径零调用点，删代码需另行授权，spec §7）。
- `bin/notification.py`：写面 `HITL_PROPOSALS_DIR` 未声明即**拒写**（`_anchored_proposals_dir()`，rc=1 并打印具名原因）；
  读面 `:35` 配置改 `_config_path() = code_root() / CONFIG_RELATIVE`，**调用时刻**解析。
  选 fail-closed 而不是 `state_root()` 拼接：该 env 在全机任何 plist/registry/yaml/toml/sh 与 `crontab -l`
  里都未被声明，凭空拼一个 state 根等于替机器做一个未获授权的决定。

**ADR-0456**：addendum 五节（类目补齐与两尺对拍 / lock_graph 裁决 / notification 两面 /
尺 B 对 `code_root()` 的结构性盲区 / 后续项与一条不裁决的裁决）。

## 2. done_when 逐条读数

所有尺读数由**本轮改造后的尺**产出；尺 A / 尺 B 的 base 分别是分支 `25d7a6ee7` 与工作树 tip，
对照树 base = `159ca353e`（当时的 `origin/main`）。按 AGENTS.md §7「门禁的尺本身会随 base 变」，引用以下任何
数字都必须连带这一行。

| done_when | 读数 | 判据命令 |
|---|---|---|
| ① 两形各命中、正反齐、各配变异对照 | 尺 A **31 passed** / 尺 B **12 passed**（合并 43 passed）；尺 A 变异（`_relative_in_file` 首行 `return {}`）**5 failed / 38 passed**，红项恰为 5 条承重用例（`test_relative_detector_fires_on_both_shapes` / `test_relative_register_is_the_reviewed_list` / `test_relative_category_is_load_bearing` / `test_relative_category_hits_shape_a_on_the_omo_write_plane` / `test_two_rulers_agree_on_the_relative_face`）；尺 B 变异（`scan_cwd_relative_sites` 早退 `return []`）**3 failed / 9 passed** | 见 §3 的两次变异复跑 |
| ② 两处站点结论进 ADR-0456 addendum | addendum §2（lock_graph）与 §3（notification 写读两面），按文件名引用 | `git show c3a93e9cc --stat` = 4 件 |
| ③ tip 对照树仍复现基线 | 对照树 `/tmp/t288_ctl`（869 个 `.py`，tip `159ca353e`）读数 `sites=456 gated=153 pairs=143 files=95` 与本分支**逐值相同**，`SPEC_MARKER_READINGS` 五族逐值相同 `{_truth:163, _state:103, _delivery:78, runtime:50, _knowledge:62}`；相对面 **tip 8 → 分支 6**，差额恰为 `bin/notification.py` 两处 | `test_one_scan_reproduces_the_spec_readings` + 一次性对拍探针 |

⇒ **修复没有移动钉检出根的基线**，spec §4 的反证未退化成「不可见」；相对面 8→6 是唯一变化。

## 3. 复跑判据（可机械复现）

```bash
# 尺 A + 尺 B，hermetic（三面：HOME 空目录 + git 系统/全局 config 摘除 + profile env 摘除）
rm -rf tests/unit/__pycache__ && env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB \
  HOME=$(mktemp -d) GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null \
  uv run --no-project --with pytest --with pytest-timeout --with pyyaml \
  python -m pytest tests/unit/test_resident_write_plane_split.py tests/unit/test_writeplane_root_pin.py \
  -q -p no:randomly --timeout=300        # → 43 passed

# 行为面：外部 CWD 下读落点跟随检出、写落点缺席即拒
cd /tmp && python3 <检出>/bin/notification.py notify 1 --channels stdout   # → 打印「未声明 … 拒写」rc=1
```

变异对照两次（改前 `sha256` 备份 + 改后按 sha 逐字节还原，不用 `cp`）：
- 尺 A：备份 `2c66b64ec1be95c7…`，摘类目 ⇒ **5 failed / 38 passed**，还原后 43 passed。
- 尺 B：备份 `7f498fc3c28199a1…`，摘 `scan_cwd_relative_sites` ⇒ **3 failed / 9 passed**，还原后 12 passed。
- ⚠️ 尺 B **第一次变异是假绿**：插桩点落在函数 docstring 内部（语句在字符串里 ⇒ 无害），读数 12 passed。
  改用 `ast` 定位函数体 docstring 的 `end_lineno` 后才得到 3 failed。教训见 retro §4。

`make gac-local-gate`：**PASS**（69 checks，2 SOFT WARN）。
`bin/ssot/doc-governance-check.py --no-new-warnings --scope tracked`：**PASS**（4770 files / 45 warnings，0 error）。
`verify[1]`（`git -C projects/omo cat-file -e origin/main:src/omo/workflow/lock_graph.py`）：rc=0。

## 4. 台账 verify[0] 的缺陷与订正

台账原文 `uv run --no-project --with pytest --with pyyaml …` **按原文不可执行**：本仓
`pyproject.toml:47` 的 `addopts = "--timeout=300 --timeout-method=signal"` 需要 `pytest-timeout` 插件，
缺它时 pytest 当场 `error: unrecognized arguments: --timeout=300 --timeout-method=signal`（rc=4，0 个用例跑过）。
本轮已在台账里为 288/289 两条补 `--with pytest-timeout`。这是「判据文本本身跑不动」的一类，
不是判据过宽或过窄 —— 改前该条 verify 的「绿」永远不可能出现，改后才第一次真正被执行过。

覆盖面读数（同一把尺在全台账的量）：`--with pytest --with pyyaml python -m pytest` 这一形状在
`docs/plans/3y-bet-ledger.yaml` 里还有 **19 处**（含本轮两条），而 `pytest-timeout` 在别处已出现 17 次
⇒ 补齐装置是本仓既有约定，不是本轮新发明的口径。**本轮只改在制的 288/289 两条**：其余多在 `status: done`
的条目里，那条 verify 是**历史记录**而不是待跑判据，批量改写等于动别人已合入的登记
（改前也无法确认那 17 处当时是否用别的装置跑的）。判据留待后续：一条命令枚举「`status != done` 且
verify cmd 含 `python -m pytest` 且缺 `pytest-timeout`」，那才是仍然会咬人的集合。

## 5. 未做与后续（具名）

- `bin/hitl-proposal.py:30` 的模块常量 `PROPOSALS_DIR`（提案面**生产者**）仍随 CWD 且 import 时冻结。
  消费者已 fail-closed，故现状是「未声明即拒写」而非读写分叉；一旦只给消费侧声明 env，两半就会落到不同目录
  ⇒ **两半必须同一次交付改**。该文件不在本 BET 的 `write_surfaces` 里，本轮只登记不动。
- 尺 B 的 `pinned` 谓词（`_checkout_root_aliases` + `"__file__" in ast.dump(base)`）对 `code_root()` 锚点结构性
  失明：tip 实测 188 条命中 marker 而未按 `__file__` 归类的 `/`-链中，`code_root()` Call 形仅 1 条被认。
  本轮**不扩这把尺**（扩它会让 spec §4 基线不可复算，与 done_when③ 冲突），已在 addendum §4 登记。
- notification 的两处还清使 `RELATIVE_REGISTER` 8 → 6；尺 B 的 `BASELINE_RELATIVE_SITES` 同步为 6。
- BET 的 `write_surfaces` 本轮补记 retro 与 receipt 两条路径（沿用 282/284/286 的既有约定），
  否则收口腿的 claim 按构造必然 `WORK_PACKET_SCOPE_MISMATCH`。

## 6. 清理

`runtime/affected/t288-closeout.json`（affected-graph receipt，claim 前置件）为一次性产物，**不进 commit**；
两个 worktree（`ws-t288-relative-root`、`ws-t288-closeout`）在收口后 `gac-worktree.sh release`。
