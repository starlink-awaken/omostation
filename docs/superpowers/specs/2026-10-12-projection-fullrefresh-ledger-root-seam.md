---
schema_version: specification/v1
spec_version: 1.0.0
title: ADR-0456 B4b 前置 — projection-full-refresh 的 ledger 根由 __file__ 反推改为 profile/canonical 解析
bet_id: BET-Y2Q4-T10-247
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-10-12
---

# ADR-0456 B4b 前置 —— publisher driver 不得把自己所在的克隆当账本权威

## 0 现象（本轮实测，2026-10-12）

`bin/panorama/projection-full-refresh.py` 是 `com.omostation.zhixing-projection-fullrefresh`
的 driver（BET-Y2Q4-T10-227 交付）。它第 3 步把专用洁净检出 `~/.local/opt/omostation-publisher`
对齐 `origin/main`，第 4 步在该检出里跑 `panorama-collect.py` 全量发布。它的 ledger 落点是
模块级常量（`:41-42`）：

```python
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
EVENT_LEDGER_DB = WORKSPACE_ROOT / "runtime" / "omo" / "event-ledger.sqlite3"
```

而紧邻的注释（`:40`）写的是「**必须显式指向主树那份**」。`__file__` 在这个部署里就是
publisher 克隆自己 —— 代码与它自己的注释相反。测量读数：

| 量 | 读数 |
|---|---|
| `:131` 注入给子进程的路径 | `~/.local/opt/omostation-publisher/runtime/omo/event-ledger.sqlite3` |
| 该路径是否存在 | **不存在**（`ls` 报 No such file or directory） |
| 权威 ledger | `~/Workspace/runtime/omo/event-ledger.sqlite3`（397 KB，2026-10-12 10:58 仍在写） |
| 同一 driver 的第 3 步 | `git clean -fdx` —— 未跟踪文件每轮抹掉 |

⇒ 后果不是「读不到」而是**写进去的活不过下一次刷新**：publisher 每 30 min 触发，
第 3 步先 `clean -fdx`，第 4 步才向那个未跟踪路径写事件。这与 ADR-0456 §风险
「漏改的 plist 会永远跑旧代码」「双实例抢写 ledger」是同一族的失效形状。

## 1 为什么排在这里（而不是 B4b 批次 2）

B4b 的中止判据要求 `--reality-check` 干净（registry == 已安装集合、`--check` exit 0）。
本轮实测该判据**尚未成立**，且卡住它的三件事没有一件是代码问题：

| 判据项 | 读数 | 归属 |
|---|---|---|
| `--check` E1 drift | 1 条：`com.omostation.zhixing-projection-fullrefresh` 注册表 `entrypoint=~/dotfiles/bin/zhixing-refresh.sh` + `run_at_load=false`，实装 plist `-mbp.sh` + `RunAtLoad=true` | fleet 每主机变体机制缺位（ADR-0435 生成契约面），需署名裁定 |
| E2 未声明 | 1 条：`com.omostation.panorama-compact-observation`，其 driver `bin/panorama/compact-observation.py` **不在 origin/main**（只在主工作区未推的 WIP 快照 `ccecdd571` 里） | 并发 panorama 线，不可替它登记 |
| E5 | 2 条：`com.l4.omo.sync` 声明 enabled 未装、`com.cockpit.dashboard` 声明 disabled 仍装 | 机器侧动作，逐批授权 |

另有一条**正在失败的现网事实**（同属该服务，非本轮修复对象）：driver 的 publish 步自
2026-10-12 05:27Z 起每次 `rc=1`，子进程抛 `projection_dashboard_not_current_main`
（`panorama-collect.py:493` 要求 dashboard 根的 `HEAD == refs/remotes/origin/main`）。
根因是 `~/.local/share/zhixing-dashboard` 上有一枚**未推的本地 commit**
`3403d4e "fix(dcp20): 应用 GET 方法安全修复 (主仓 origin/main #4705 资产同步)"`
（ahead 1 / behind 0，工作树干净）。那是别线的在制产物，推送它不属于本 BET 授权面。

所以本轮只做**纯仓内、可测、不改机器**的那一块：把 driver 的 ledger 根从 `__file__`
反推改成调用时刻解析。它同时是 B4b 批次 2 的前置 —— 批次 2 要把 plist 改道到安装位，
届时任何仍由 `__file__` 反推运行根的代码都会在安装位里就地重定义「权威」，
把 B4b 变成静默的账本分裂（AGENTS.md §7「根是参数，不是事实」）。

## 2 规范（WHAT，不是过程）

裁决规则三行，按优先级：

1. `OMO_EVENT_LEDGER_DB` 已声明 → 原样采用（既有 canonical env 名，行为不变）。
2. `OMOSTATION_STATE_ROOT` 已声明 → `state_root()/runtime/omo/event-ledger.sqlite3`
   （profile 说了算，与 `bin/lib/repo_root.py:94-99` 逐字同口径）。
3. 两者皆未声明 → `canonical_root()/runtime/omo/event-ledger.sqlite3`，
   **而不是** `code_root()`。理由：本 driver 的常驻执行位置是一个运行时克隆，
   它不是任何 profile 的权威；把它当权威就会得到 §0 的形状。

**为什么不调 `repo_root.event_ledger_path()`**：它第 99 行走 `state_root()/LEDGER_RELATIVE`，
而未声明 profile 时 `state_root() == code_root()`（`bin/lib/repo_root.py:86-91`）—— 正是规则 3
要避开的落点。且它内部用名字常量 `LEDGER_RELATIVE`，本文件里就不剩字面 `/` 链；`reader_pairs`
只认 `BinOp(Div)` 的字面段（`_text()` 对非字面量给 `*`，`if "/" not in text: continue`），
调它会让本文件**从 ledger 族的读者表里消失** —— 判据静默失效，不是收敛。所以缝落在 driver 内，
两个分支各自**内联字面段**，与 `bin/lib/repo_root.py:94-99` 保持同读数而不是同代码路径。

`canonical_root()` 定位不到规范检出时抛 `RuntimeError`（该函数规定行为）。driver 的
fail-closed 契约是「任何步骤失败 → 退出非零 + JSON 行日志」，因此这一抛必须被
转成一条 `failed` 日志（`step="ledger_root"`），不能是裸 traceback。

**明确不在范围内**：不改 `panorama-collect.py` 的 `:92-97` 默认值（那是子进程侧，
env 已由父进程注入）；不改任何 plist；不动 `~/.local/share/zhixing-dashboard`；
不替并发线登记任何 label。

## 3 ISC（每条带否证方式）

- **ISC-1 落点正确**：在 publisher 克隆里执行 driver 的解析函数，未声明 profile 时
  返回值 == `canonical_root()/LEDGER_RELATIVE`，且**不在** `CHECKOUT` 之下。
  否证：返回路径落在 publisher 克隆内 → 失败。
- **ISC-2 profile 优先不被破坏**：声明 `OMO_EVENT_LEDGER_DB` 或 `OMOSTATION_STATE_ROOT`
  时逐字采用声明值（与 `repo_root.event_ledger_path()` 同读数）。
  否证：任一声明被 canonical 覆盖 → 失败。
- **ISC-3 无 import 时冻结**：解析发生在调用时刻，模块级**不存在任何**由 `__file__` 导出的
  常量（含传递导出 —— 右侧引用了另一个 `__file__` 系模块级名）。否证：AST 扫出这类模块级
  赋值 → 失败。
- **ISC-4 检测器自证**（AGENTS.md §7 ②⑤ ）：ISC-3 的扫描器对**合成违规样本**必须逐个点名
  （`ROOT = __file__` / `FOO = Path(ROOT)…` / `LEDGER = FOO / …` 三件，含传递件），
  且「改前 = 2 / 改后 = 0」由同一次扫描产出并同时断言。只断言 0 不算。
  改前 = 2 的实测依据：`:41 WORKSPACE_ROOT` 与 `:42 EVENT_LEDGER_DB`，后者是前者的传递导出。
  ⚠️ 直串判定（只看字面量含 `runtime/`）实测对 pre-fix 文本报 **0** —— 那是检测器没命中，
  不是没有违规（本轮 06:20:51Z 实录）。
- **ISC-5 子进程仍收到同一读数，且比较发生在可分辨的面上**：driver 注入的 `OMO_EVENT_LEDGER_DB`
  值 == 解析函数返回值。⚠️ 本条原先那句「两处在任何测试里不可能不一致」被**本轮变异实测否证**
  （07:03Z）：未声明 profile 时把注入点写成 `__file__` 反推，两侧按构造读到同一个路径，
  全套用例 11 passed —— 那是判据没牙齿，不是实现正确。故 ISC-5 由三面共同钉住：
  ① 在 import **后**声明 `OMOSTATION_STATE_ROOT` 的面上比（解析器给 state 根读数，自行重算当场分叉，
  同时再压一遍 ISC-3 的时机面）；② 同一次用例内断言注入值分别 ≠ `__file__` 反推、≠ canonical 检出
  读数、≠ publisher 检出读数（判别自证 —— 见 AGENTS.md §7 ③「按构造就绿」）；③ 在 publisher 克隆树里
  比（未声明 profile → 必须落 canonical 而非克隆）。
  否证：注入点与解析点分别求值且不同；或①②③任一形状下「两侧本来就读不出差别」却算通过。
  变异对照读数（同一套 11 条用例；08:31Z 在本仓真树复测，读数与 07:0xZ 首轮逐字相同）：
  M5（`__file__` 反推）2 failed、M7（`CHECKOUT` 常量）2 failed、
  M1（退回改前）9 failed、M2（第③支用 `code_root()`）4 failed、M3（第③支委托 `event_ledger_path()`）
  4 failed、M4（解析挪到同步步之后）2 failed、M6（逐字节对照）11 passed。
- **ISC-6 现网零扰动**：不写任何 plist、不动 `~/.local/share/zhixing-dashboard` 与
  publisher 检出的 git 状态；`--reality-check` 六个桶与改前逐字段相同。
  否证：任一 plist 字节变化，或 E1/E2/E3/E4/E5/installed_total 读数漂移。
- **ISC-7 既有测量面诚实跟进（四项，逐条由测量产出）**：本轮 06:31:59Z 用**本仓自己的**
  `reader_pairs` 在 /tmp 假树上对改前/改后两份文本实测 —— 改前 1 行 `CHECKOUT`（锚点
  `WORKSPACE_ROOT`），改后 2 行：`state_root() / "runtime" / "omo" / "event-ledger.sqlite3"`
  记 **STATE**、`canonical_root() / "runtime" / …` 记 **CALLER**。因此四项同批改：
  ① `SPLIT_EXACT["runtime/omo/event-ledger.sqlite3"]` 中本文件的类 `CHECKOUT → CALLER`；
  ② `CALLER_EVIDENCE` 新增 `(本文件, "canonical_root")` —— `test_caller_class_anchors_are_checkout_anchored`
  把 `seen` 与它钉成**集合相等**，未登记即红，所以这条不是可选项；
  ③ `test_no_bin_reader_resolves_to_state_root` 的 `_state_readers(rows) == []` 转为「在册 STATE 读者
  恰为这一条」的评审集（新常量 `REVIEWED_STATE_READERS`，键 `rel`、值在册理由；该用例 `:659-661`
  的措辞本来就规定了这个转法，并附反向哨兵：新增第二条
  未在册的 STATE 读者必须红）。**用例随之改名** `test_bin_state_readers_are_the_reviewed_set`：
  旧名断言的是「bin/ 侧零 STATE 读者」，本轮之后它按事实为假，留一个说谎的用例名比留一个旧断言更糟。**评审集按 `(rel)` 归合，不得钉行号** —— `_state_readers` 返回
  `(rel, line)` 对，本轮 06:53:17Z 用本仓 `reader_pairs` 对改后文本实测该行 line=58，而行号随 driver
  自身的后续改动漂移；钉行号会让判据在无关改动当天假红；
  ④ `test_ledger_family_has_a_single_root_contract_in_bin` 的读者**文件集合不变**（仍两个文件）——
  它应继续绿；若它变红，说明读者是**消失了**而不是改了类（用名字常量代替字面段就是这个形状）。
  否证：任一期望值手改而无对应测量记录；或 ② 走 `checkout: True` 配一条恰好含 `parents[` 的
  **无关**表达式当证据 —— 那是该表注释警告的橡皮章。`canonical_root()` 是检出根的证据必须来自
  该 resolver 自身，故 ② 用新增的 `checkout_resolver` 模式：断言该名在 `bin/lib/repo_root.py`
  是公开 callable，且其函数体经 **AST 谓词**满足五条 —— ① 体内既不存在 `ast.Name` id==`__file__`
  也不存在 `Attribute(value=Name "__file__")`；② 不引用也不调用 `_STATE_MARKERS` 里任何名字；
  ③ 体内引用 `MARKER`（以「这份检出是不是规范检出」为定位依据）；④ 存在 `ast.Raise`（定位不到即
  失败关闭，不得静默给 `None` 或回退）；⑤ **零必填参数**（读点写 `canonical_root()` 而不是传参猜根）。
  **为什么必须写成 AST 谓词而不是子串判定**（本轮实测）：`"__file__" in ast.unparse(fn)` 对
  `canonical_root` 读数为 **True** —— 只因它的 RuntimeError 文案里就写着 `__file__`；同源失误的
  反向形状是 `code_root`，`Path(__file__)` 是 Name 作实参，`X.__file__` 的 Attribute 判据对它
  恒 False。
  **为什么是五条而不是三条**（07:15:56Z 实测，谓词在本仓 `bin/lib/repo_root.py` 真树上逐个跑）：
  原先写的三条判据通过集是 **`{canonical_root, projection_rels}`** —— `projection_rels` 无 `__file__`、
  只调 `_projection_registry`（不碰 state 面）、体内有 `raise KeyError`，三条全过。它是投影相对路径
  查询器而非检出根定位器，被 `checkout_resolver` 当证据就是橡皮章；③⑤ 两条把它否掉（实测原因
  `③no-MARKER-identity-check`、`⑤takes-args:['name','registry_root']`）。
  判别对照（同一棵树、同一份谓词，按 `__all__` **全集**求交而非手写名单）：通过集**恰为
  `{canonical_root}`**；逐名实测被违反的条款集（不是「笼统拒绝」）：`code_root` ①③④、
  `state_root` ③④、`event_ledger_path` ②③④、`install_root` ④、`is_worktree` ③④⑤、
  `projection_name_for` ③④⑤、`projection_read` ②③④⑤、`projection_rels` ③⑤、`state_file_read` ②③④⑤。
  `install_root` 只中 ④ 不是它有误（没有安装位的机器上它按设计返回 `None`），而是**可能静默给
  `None` 的定位器不能当检出根的证据**。
  检测器自证由一件**合法最小体**派生（`_LEGIT_RESOLVER`）：每次**只**破坏一条 ⇒ `_violated_clauses`
  必须**恰等于**那一条（5 件，逐条）；合法体本身必须 `violated == []`（只断言「全拒绝」时谓词恒假也是绿）；
  另加一件同时破坏 ③④⑤ 的合体样本，断言谓词**逐条全报**而不是只报第一条。既有 `checkout` /
  `checkout_via` 两条路径逐字不动（这一项是**加强**判据，不是放宽）。
  **五条各有活线（08:28Z 在本仓真树复测；命名 selection，逐字节还原）**：selection =
  本新增文件的 11 条 + `test_checkout_resolver_predicate_is_discriminating` +
  `test_checkout_resolver_predicate_names_each_synthetic_violation` +
  `test_checkout_resolver_evidence_mode_is_not_a_rubber_stamp` +
  `test_caller_class_anchors_are_checkout_anchored`，共 15 件。基线 **1 failed / 14 passed** ——
  唯一红是 `test_caller_class_anchors_are_checkout_anchored`，它**在 `origin/main` 上按构造即为红**：
  该用例把实测 `seen` 与 `CALLER_EVIDENCE` 钉成集合相等，而 main 的名单只有 5 个 rel，
  `bin/_archive/**`（175 个被跟踪 .py）、`bin/ssot/**`（228 个中的其余）、`bin/kb/**`（3 个）、
  `bin/gac/m1-closeout-report.py` 全都不在册；`tests/unit/**` 不在 CI 白名单，所以这条红 CI 看不见。
  本轮**不**代偿这份陈旧名单（不属 T10-247 面），也不写进 `gate-known-debt.yaml`（shrink-only，
  且它记门禁阻断项，这四条不阻断任何门禁）—— 报告主责人并落 retro 待办。
  在本仓 `bin/lib/repo_root.py::canonical_root` 上逐个破坏一条，每次由**同一个谓词**指名被违反的
  **那一条**（`violated` 长度恰为 1），且红集合相对基线**只增不减**、每次都含
  `test_checkout_resolver_predicate_is_discriminating`：R1 改道 `state_root()` → `no-state-marker`
  **6 failed**（新增 5 红）；R2 `__file__` 反推 → `no-file-anchor` **6 failed**（新增 5 红）；
  R3 去掉 `raise` 给 `Path.home()` → `raises` **4 failed**（新增 3 红）；R4 去掉 `MARKER` 验真 →
  `refs-marker` **4 failed**（新增 3 红）；R5 加必填参数 → `zero-required-args` **7 failed**（新增 6 红）。
  逐字节还原后回到 **1 failed / 14 passed** 且红集合与基线逐项相等（还原校验 sha `37c5b2746939…`）。
  ⚠️ 作废措辞（诚实记录，不悄悄换）：本条此前写作「每次 … 均 2 failed；未变异与逐字节还原后 4 passed」，
  那读数是在 /tmp 最小合成树上量的，在本仓真树**不可复现**；合同读数必须由被测树产出。
  反橡皮章件 `test_checkout_resolver_evidence_mode_is_not_a_rubber_stamp` 仍在 selection 内且为绿：
  它实测本条 `exprs` 拼接文本里 `CHECKOUT_MARKERS` 一个都不出现，而整个文件里 `parents[` 出现 ——
  即 `checkout: True` 若被用在这里，标记会从一句无关的 `sys.path.insert` 蹭来。

## 4 验收命令

```bash
uv run pytest tests/unit/test_projection_fullrefresh_ledger_root.py -q
uv run pytest tests/unit/test_resident_write_plane_split.py -q
python3 bin/mof/gen-service-configs.py --reality-check --json   # 六桶读数与 §1 表一致
make gac-local-gate                                            # 硬失败集不得新增
```

`tests/unit/**` 不在 `governance-check.yml` 的显式 pytest 白名单里（`:118-127`），
因此「CI 绿」不是这批用例的证据 —— 本地逐条跑并留 receipt。

**预期读数（08:2xZ 在本仓真树复测，写明才是可复核的）**：复现要在**剥掉 profile env** 的面上看，
否则测的是别的根 ——

```bash
env -u OMOSTATION_ROOT -u OMOSTATION_STATE_ROOT -u OMO_EVENT_LEDGER_DB \
  PYTHONDONTWRITEBYTECODE=1 uv run --with pytest --with pyyaml --python 3.13 \
  python -m pytest tests/unit/test_projection_fullrefresh_ledger_root.py \
  tests/unit/test_resident_write_plane_split.py -q -p no:cacheprovider
```

- 新增文件 11 件：**11 passed**。
- `test_resident_write_plane_split.py` 全套 24 件：**4 failed / 20 passed**。四条红全部**预存**
  （用 origin/main 自己那份测试文件在同树跑是 **5 failed / 16 passed**，多出的那条
  `test_no_bin_reader_resolves_to_state_root` 正是本轮按事实改名转绿的），
  成因都是「在册名单没跟上被跟踪的面」，不是环境或 host 泄漏 —— 逐条指认：
  ① `test_scan_loads_the_real_omo_surface` 与 ② `test_state_reached_families_are_the_declared_set`：
  实测多出 `.omo/_knowledge/{omo-events,omo-alerts,omo-trail,omo-sync,bos-metrics}.jsonl` 与
  `.omo/_knowledge`，它们由 `scan_writers(projects/omo/src/omo)` 从**被跟踪的 omo 源码字面量**
  （`omo_event.py`/`omo_alert.py`/…）得出，且子模块 gitlink `e8c7aa0ed002` 与 `origin/main` 逐字一致
  ⇒ CI 干净检出同样会多出这六项；③ `test_exact_root_split_pairs_are_the_reviewed_list`：
  `SPLIT_EXACT`（main 与本轮同为 12 项，未被改动）缺 `.omo/_knowledge` 面，其写者全在
  `bin/_archive/**`；④ `test_caller_class_anchors_are_checkout_anchored`：`CALLER_EVIDENCE` 在册
  5 个 rel，实测多出 `bin/_archive/**`、`bin/ssot/**`、`bin/kb/**`、`bin/gac/m1-closeout-report.py`
  等锚点。本轮只按合同**新增** `(本文件, "canonical_root")` 一条（AST 对拍：5→6，
  `ADDED` 仅此一条、`LOST=[]`），不代偿其余陈旧名单。
- ISC-7 selection（15 件）：**1 failed / 14 passed**（红即上面第 ④ 条）。
