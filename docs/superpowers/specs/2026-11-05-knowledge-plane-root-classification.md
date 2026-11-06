---
schema_version: specification/v1
spec_version: 1.0.0
title: "`.omo/_knowledge` 的根归类裁决 —— 四个来源对同一目录各说一遍"
bet_id: BET-Y2Q4-T10-289
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-05
---

# `.omo/_knowledge` 的根归类裁决

> 本规范是**归类裁决 + 判别量契约**，不是实现；实现由本 BET 的执行腿承担。
> 所有读数由 `origin/main = 3a1c0770290a5d2a1ddbd896fb3f9de358ecbc90` 产出，装置见 §6；
> 按 AGENTS.md §7「门禁的尺本身会随 base 变」，引用本文件任何读数都必须连带这个 base。
> 前置否证：草稿（`/tmp/t286-closeout/D2-spec-draft.md`）的分桶表「26 站点 / 36 站点」与
> 「25 个活文件 / 37 个站点」**均不成立**，订正见 §8。

## 1. 四个来源对同一目录各说一遍

| 来源 | 位置（tip） | 说的是 |
|------|-------------|--------|
| **A. `STATE_FAMILIES`** | `tests/unit/test_resident_write_plane_split.py:434-456`（42 族，其中 `​.omo/_knowledge` 系 **12 条** = 容器 + 11 后代族，逐条见 §5） | 写侧跟 profile 的 **state 根** |
| **B. `SPLIT_EXACT`** | 同文件 `:666-676` | 该目录的部分 `bin/` 读者**逐条钉在 CHECKOUT**（在册） |
| **C. pin-gate 排除面** | `tests/unit/test_writeplane_root_pin.py:27-29`（`GATED_MARKERS = (".omo/state", "runtime")`）+ `:37-48` `SPEC_MARKER_READINGS` 里 `.omo/_knowledge: 62` | 「其余面是读面 / 协调桥 / 署名文档面」⇒ **62 个检出钉站点可见但不计** |
| **D. `.gitignore` + `git ls-tree`** | tip `.gitignore:21,23,381,383,384,399,424` vs `git ls-tree -r origin/main -- .omo/_knowledge` | 同一批目录里，一部分**整目录被忽略**，一部分**上千文件被跟踪** —— 且有三面**同时**如此（§3） |

**矛盾核心**：C 的排除前提是「读面随检出 ⇒ 良性」；A 说同一个目录是 state 族（写者迁 state 根），
B 说它的读者钉在检出 ⇒ 一旦**声明 profile**，钉检出的读者就读到空面或陈旧面。
排除的前提对 A/B 已登记的那批站点**不成立**。这不是补缝，是归类裁决。

## 2. tip 上的分桶定稿（62 站点 = 13 + 5 + 44）

分子取自动：`pin.scan_checkout_pinned_sites()` 的 `.omo/_knowledge` 桶
（**扫描面 = `<root>/bin/**/*.py`**，见 `test_writeplane_root_pin.py:247,254`；口径与 §8 的 grep 尺不可比），
按 A 的族表切三桶。**「具体族」的站点数从草稿的 26 改为实测 13**：

| 桶 | 站点 | 文件 | 其中模块级常量 / 函数内 | 含义 |
|----|------|------|------------------------|------|
| `SPECIFIC_FAMILY`（落在具体 state 族下） | **13** | 12 | **10** / 3 | 写者已迁 state 根、读者钉检出 ⇒ **真缺陷候选** |
| `CONTAINER`（仅落在容器 `.omo/_knowledge`） | **5** | 2 | 0 / **5** | 需逐条裁，且 5 处**全是函数内**（§4 的既有裁决前提正覆盖不到它们） |
| `NOT_DECLARED`（不在任何登记族下） | **44** | 32 | 24 / 20 | 24 个面**根本不在 A 的族表里**，其中多数是跟踪文档面（合法读面），但有 1 个双面（§3 `signals`） |

`SPECIFIC_FAMILY` 逐面（站点 / 文件 / `ls-tree` 跟踪数 / `check-ignore` 规则）：

| 面 | 站点 | 跟踪 | 忽略规则 |
|----|------|------|----------|
| `.omo/_knowledge/workflow-mesh/events.jsonl` | 6 | 0 | `.gitignore:23` |
| `.omo/_knowledge/evolution-proposals` | 4 | **1065** | `.gitignore:381` |
| `.omo/_knowledge/decision-proposals` | 1 | **128** | `.gitignore:399` |
| `.omo/_knowledge/omo-events.jsonl` | 1 | 0 | `.gitignore:21` |
| `.omo/_knowledge/sediment` | 1 | 0 | `.gitignore:383` |
| 容器 `.omo/_knowledge` | 5 | 4400 | 容器目录本身不被忽略（`:21` 只作用于直接子层 `*.jsonl`，见 §6 装置说明） |

13 个具体族站点的读者（`bin@tip`，`文件:行` + 根）：
`bc-os/north_star_meter_v3.py:40`、`bc-os/north_star_meter_v4.py:35`、`gac/event-loop-lint.py:29`、
`ssot/decision-agent.py:22`、`ssot/event-ingest-adapter.py:37`、`ssot/knowledge-sediment.py:22`、
`ssot/resident-orchestrator-daemon.py:36`、`ssot/scene-evolution-loop.py:27`、`ssot/system-health-check.py:27`
（以上 9 处为**模块级 `Assign`**，import 时冻结根；`evolution-proposals` 的第 4 处站点
`ssot/evolution-agent.py:230` 与 `panorama/panorama-collect.py:4088,4600` 在函数内）。

容器 5 站点（**逐处复核到消费语句**）：
`gac/check-gateway-status-doc.py:90`（容器列进 `:87` 的 doc-dir 列表，被 `:93 doc_dir.rglob("*.md")` + `:94 read_text()` 消费）；
`panorama/panorama-collect.py:4313`（`_kp = _P(ROOT / ".omo/_knowledge")` → `:4314 _kp.rglob("*.md")`）、
`:4370`、`:4478`、`:4571`（三处内联 `_P(ROOT / ".omo/_knowledge").rglob("*.md")`）。
⇒ **容器 5 站点全部落到递归读 `*.md`**，即读的是已跟踪的治理文档面（见 §4(c)）。
另有 4 处站点直接钉在**子面 glob** 上（`panorama-collect.py:4412 pitfalls/PITFALL-*.yaml`、
`:4427 decisions/0*.md`、`:4438 retros/BET-*.md`、`:4449 patterns/*.md`），它们属 `NOT_DECLARED` 桶，
读的是跟踪内容且未被 ignore ⇒ 这 4 处是**合法检出钉读面**，不在本 BET 的收敛对象里。

## 3. D 面：跟踪与生成对同一目录各说一遍（本轮最硬的一条）

**三个面同时**是「被 gitignore 的生成面」和「已提交文件的跟踪面」（ignore 只作用于未跟踪项，
所以两种状态按字节共存）：

| 面 | `ls-tree` 跟踪 | `.gitignore` |
|----|----------------|--------------|
| `.omo/_knowledge/evolution-proposals` | **1065** | `:381` 整目录 |
| `.omo/_knowledge/decision-proposals` | **128** | `:399` 整目录 |
| `.omo/_knowledge/signals` | **7** | `:424` 整目录 |

（`signals` 是本轮新发现，草稿只列了两个 proposal 面。）
对照：`sediment` `:383` / `sediment-archive` `:384` / `workflow-mesh/` `:23` / `_knowledge/*.jsonl` `:21`
跟踪数均为 0 —— 那些是**纯生成面**，无冲突；
`decisions` 432、`retros` 656、`audits` 242、`design/plans/archive` 880、`pitfalls` 60、`bos-registry.json` 1
均为「跟踪且不被忽略」—— 纯读面，也无冲突。

⇒ 与 AGENTS.md §7「已提交的 legacy 兜底不是仓库性质」「`.omo/state/system.yaml` 摘库」同族：
**跟踪 ≠ 有意保留，缺席 ≠ 无产物**。

**可机械化的判别量**（作为裁决规则，而不是逐条人工拍）：某面的权威根 = **它自己的字节来源**——

```
tracked(ls-tree > 0) 且 not-ignored          ⇒ 检出根（读面）
tracked == 0        且 ignored               ⇒ profile 的 state 根（生成面）
tracked(ls-tree > 0) 且 ignored              ⇒ 冲突，必须当场点名（本例 3 个面）
```

## 4. 容器挂 state 根**原本是裁过的** —— 要引用，不能假装没这回事

`projects/omo/src/omo/omo_logs.py:29-36`（pin `b22152e77a851f3825105a73fc8577724fd7fc3c`，原文）：

> `def knowledge_dir() -> Path:` —— 「`.omo/_knowledge` 的 jsonl 日志面 —— 写面，跟随 profile 的 state 根
> (BET-Y2Q4-T10-239)。本模块**只在该目录里 glob/读 `*.jsonl`**（AppendOnlyLog 消费者的落点），
> 不读 `_knowledge/decisions/**` 那类已跟踪内容，所以整目录挂 state 根是安全的；
> 治理 SSOT 的已跟踪知识面走 `omo_paths.DECISIONS_DIR`（检出根），两者不同名也不同根。」
> `return state_root() / ".omo" / "_knowledge"`

`omo_observability.py:26-32` 同契约（「与 `omo_logs.knowledge_dir()` 同契约；本模块同样只在该目录
glob `*.jsonl`」）。

⇒ 该裁决的适用范围**只覆盖「omo 侧只 glob `*.jsonl`」这一条前提**，它**没有**覆盖：
(a) `bin/` 侧这 62 个检出钉读者；(b) 三个既 ignore 又跟踪的面（§3）；
(c) **容器上的 5 处读者全部落到递归 `rglob("*.md")`**（§2 逐处到消费语句）——
即「只 glob `*.jsonl`」这条前提在 `bin/` 侧**按构造不成立**，而这些读者钉的是检出根。
立案时必须写成「**延伸 / 复核既有裁决**」，而不是「新决定」——否则是重复裁决同一个问题。
裁决要回答的具体问题是：`knowledge_dir()` 把容器挂到 state 根之后，
`bin/` 侧「读整目录 `*.md`」的读者在声明 profile 的机器上读到的是**检出那份**（与写侧不同根，
两份内容会各自漂移），还是应当显式改走 `omo_paths.DECISIONS_DIR` 那类**具名跟踪面**常量。

## 5. 写侧登记读数（A 面的内容，逐族有名）

`scan_writers(projects/omo/src/omo @ b22152e77)` 在本目录的命中（n = 该尺登记的条目数）：

| 族 / 面 | `state` 桶 | `bare_template` 桶 | `bare_inline` 桶 |
|---------|-----------|--------------------|------------------|
| `.omo/_knowledge`（容器） | 2（`omo_logs.py:36`、`omo_observability.py:32`，均 `state-anchored`） | — | — |
| `workflow-mesh/events.jsonl` | **17**（`resident/daemon.py` `DEFAULT_EVENTS_JSONL`、`resident/heartbeat.py` `EVENTS_JSONL`、`resident/inbox.py` …） | 9 | 1（`omo_agent_host.py:603` `root_state`） |
| `sediment` | 10（`resident/promote.py`/`sediment.py` `SEDIMENT_ROOT`） | 3 | — |
| `decision-proposals` | 7（`resident/decision.py` `INBOX_DIR`） | 3 | — |
| `evolution-proposals` | 7（`resident/decision.py` `PROPOSAL_DIR`） | 1 | — |
| `retros/resident` | 3（`resident/promote.py` `RETRO_ROOT`） | 1 | — |
| `sediment-archive` | 1（`promote.py` `ARCHIVE_ROOT`） | 1 | — |
| `bos-metrics.jsonl` / `omo-alerts.jsonl` / `omo-events.jsonl` / `omo-sync.jsonl` / `omo-trail.jsonl` | 各 1（`omo_bos_metrics.py:47` / `omo_alert.py:39` / `omo_event.py:27` / `omo_sync.py:30` / `omo_trail.py:54`，`state-anchored`） | — | — |
| **未登记为族的面** | — | 1（`retros` ← `memory_distiller.py` `RETROS_DIR`）+ `sediment/failures`、`sediment/runs`（`interact.py`） | 2（`bos-registry.json` ← `omo_bos.py:105` **`code_root`**；`workflow-mesh/journey-states` ← `omo_agent_host.py:483,581` `root_state`） |

⇒ 两面新信息：① 草稿的写侧计数（「`DEFAULT_EVENTS_JSONL` ×2 + `EVENTS_JSONL` ×2」）是**局部读数**，
该尺对 `events.jsonl` 的登记是 **17 条**；② **`workflow-mesh/journey-states` 有 state 根写者但不在族表**
（A 面登记不完整，与 §2 的 24 个未登记读面同源 —— 族表与读者名单都不是闭合集）。

## 6. 装置与读数（可复跑）

- 尺：`git show origin/main:tests/unit/test_writeplane_root_pin.py` 与
  `…test_resident_write_plane_split.py` 原样取来，`importlib` 载入后**调它们自己的函数**
  （tip sha256 前 12：`419836601de2` / `6fa5ecbac09d`）。
- 被检对象：`<root>/bin`（pin-gate 自己的扫描面）+ 按 pin 归档的 `src/omo`（archive 源见探针打印）。
- 反证（AGENTS.md §7③，空绿不被接受）：同一把尺在该对象上须复现它自己写下的基线 ——
  `SPEC_MARKER_READINGS` 逐桶相等（`{_knowledge:62, _truth:163, _state:103, _delivery:78, runtime:50}`，
  sites 456 / gated 153 / pairs 143 / files 95）⇒ **PASS**。反证不过则本轮读数一律作废。
  （`_truth` 162→163 / sites 455→456 是 PR #5059 在 `bin/ssot/auto-pruner.py` 新点的一处钉检出根站点，
  尺的基线与被检对象在同一次交付里同步前进；本规范裁决的 `_knowledge` 面 62 站点逐项未变，
  `probe-d2c` 在两个 base 上的输出除基线行外逐字节相同。）
- **`check-ignore` 的装置说明（两条必须连带）**：
  ① 对**目录面**提问时探针写入占位文件 `__qoder_probe__.jsonl`，好让 `*.jsonl` 这类 glob 有机会命中 ——
  所以「容器 `.omo/_knowledge` 命中 `:21`」是**方法诱导**，容器目录本身不被忽略，裁决不得据此写「容器整目录被忽略」。
  ② 对**已跟踪文件**在其原始检出上提问会得到 `rc=1`（本装置所在对照树的 `.gitignore` 根本不在盘上），
     承重读数是**只在解出 tip `.gitignore` 的隔离树里**提问那一次：三面均 `rc=0`，
     分别命中 `:381` / `:399` / `:424`。跟踪数由 `git ls-tree -r origin/main` 独立给出。
- **`ls-tree` 的 `undetermined` 项**：4 个面的渲染串含 `*`（`decisions/0*.md`、`patterns/*.md`、
  `pitfalls/PITFALL-*.yaml`、`retros/BET-*.md`），对它们问 `ls-tree` 得到 0 不是「无跟踪内容」而是
  **判别量不适用**；裁决时按父面（`decisions` 432 / `patterns` / `pitfalls` 60 / `retros` 656）计算。
- 探针：`/tmp/t286-closeout/probe-d2b.py`（分桶 + 跟踪/忽略对账）、`/tmp/t286-closeout/probe-d2c.py`
  （族名、写侧登记、`.gitignore` 原文、既有裁决原文、双面样本）、`probe-d2{b,c}.out` 为其原始输出。一次性装置，**不进仓**。

## 7. 契约（本 BET 的 done_when 依据）

**AC-01 归类裁决落 ADR**：结论写进
`.omo/_knowledge/decisions/0456-dev-runtime-profile-root.md` 的 addendum
（按**文件名**引用：`id: ADR-0456` 有两份，另一份是 governance-downshift-closeout-grading，AGENTS.md §1），
裁决规则用 §3 的判别量，**逐面给结论**：3 个冲突面 + 容器 + 5 个纯生成面 + 6 个纯跟踪读面。

**AC-02 pin-gate 的排除面改成按族而不是按 marker 前缀**：现按 `.omo/_knowledge` 整串排除
（`GATED_MARKERS` 只含 `.omo/state`、`runtime`）⇒ 容器下的真缺陷（§2 的 13 处）与合法读面（§2 的 44 处）**同形**。
改法要同时保住 `test_detector_does_not_fire_on_seam_or_read_plane`（`test_writeplane_root_pin.py:381`）
的反过宽语义 —— **「可见不计」不得退化成「不可见」**（正反用例各≥1 + 变异对照）。

**AC-03 收敛读者按 §2 的第三列分流**：
- **模块级常量 10 处**（`SPECIFIC_FAMILY`）：import 时冻结根 ⇒ 改调用时刻解析（AGENTS.md §7「写路径要在调用时刻解析」）；
- **函数内 3 处**：先证调用方给的根，再决定改不改（形参 `root` 不是站点自己的事实）；
- **容器 5 处**：全部是函数内的 `rglob("*.md")` 类遍历 ⇒ 与 §4 前提冲突的是**语义**而不是时序，
  这 5 处属**新事实**（不属既有裁决的延伸），裁决要给「改走具名跟踪面常量」或「显式声明容器为双面」二者之一。

**AC-04 三个冲突面一次裁掉**：要么 `git rm --cached` 摘库并显式跑生成者，要么删 ignore 规则承认它是跟踪面。
**改跟踪面需授权**，本 BET 只立案并给判别量，执行腿动手前须拿到该授权。

**AC-05 族表闭合性**：`STATE_FAMILIES` 与读者名单**都不是闭合集**（§5 的 `journey-states`、§2 的 24 个未登记面）。
裁决文档必须显式写出「本次裁的是 `.omo/_knowledge` 桶 62 站点这一扫描面，不代表族表完整」，
并给一条后续判据（写侧有 state 根锚但族未登记 ⇒ 检测器点名），否则 §3 的判别量会被当成全量结论误用。

## 8. 对旧草稿的订正（三处，均已复测否证）

- ~~「25 个活文件 / 37 个站点、两把尺都看不见」~~ ⇒ tip 实测：这族**由 B 逐条登记、由 C 计入桶**
  （`.omo/_knowledge: 62` 就在 `SPEC_MARKER_READINGS` 里），**尺看得见**；
  看不见的是**归类的相互矛盾**（A 说 state、C 说读面）。草稿的 37/25 是另一把 grep 尺的读数，不可比。
- ~~「26 站点落具体族 / 36 站点仅落容器」~~ ⇒ 实测 **13 / 5 / 44**（三分，不是二分）。
  草稿把 44 个「不在任何族下」的站点并进了「容器」桶，于是把合法读面（`decisions`、`retros`、`audits`…）
  与容器遍历读者混成一桶，也才得出「需逐条裁 36 条」。
- ~~「具体族分布：`workflow-mesh/events.jsonl` 11 · `retros/resident` 8」~~ ⇒ 实测
  `events.jsonl` **6** 站点、**`retros/resident` 0 站点**；草稿的「retros 8」实际落在
  `.omo/_knowledge/retros` 面（跟踪 656、未被忽略、**且不在 A 的族表里**），属 `NOT_DECLARED`。
  草稿 §6 的否证记录（三文件 `literal=True` 只是散文里出现 "Workspace"）**仍有效**，保留。

## 9. 非目标

- 不改任何 plist、不动 cron、不 unshallow 主仓、不 `git rm --cached`（需授权，见 AC-04）。
- 不在本 BET 内迁移 `_knowledge` 下的历史内容；只裁根。
- 不把 §5 的粗扫计数（`state` 桶条目数）当契约名单引用 —— AGENTS.md §7「抽样探测的覆盖面上限是它的样本集」。
