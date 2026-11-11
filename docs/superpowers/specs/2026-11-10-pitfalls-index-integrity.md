---
schema_version: specification/v1
spec_version: 1.0.0
title: AGENTS.md §7 索引条首短语的字面可命中门禁
bet_id: BET-Y2Q4-T10-346
owner: governance-agent
status: accepted
lifecycle: contract
last-reviewed: 2026-11-11
---

# AGENTS.md §7 索引条首短语的字面可命中门禁

## 1. 缺陷与实测

`AGENTS.md` §7 的约定是：pitfalls 正文分册到 `docs/pitfalls.md`，§7 只留索引，且
「跨处引用一律按**条首短语**定位（如「六类静默失效形状」「Bash 工具跑的是 zsh」），不要按序号」。
这句话把「条首短语」当成了**寻址键**用。寻址键是否可用，取决于它能否在正文里被字面检索到。

三次实测同一判据，只读解析 `git show` 的 blob（不信本地工作树，PITFALL-COO-006）：

| main | 登记短语 | 字面可命中 | 不可命中 | 正文条目 |
|---|---|---|---|---|
| `e7f6c4586` | 42 | 28 | 14 | 123 |
| `aafc91bd6` | 43 | 29 | 14 | 123 |
| `b97281171`（本次交付基线） | **45** | 29 | **16（36%）** | 125 |

第三行的两条新增不可命中是 **#5284 在同一天刚写下的两条登记短语**——「判据描述的是代码属性，
实现却打在文件全文上」与「计数/覆盖面读数在测量装置缺席时静默偏低 —— 缺生可见」，其正文条首
分别是「判据描述的是**「代码属性」**，实现却打在文件全文上」与「…静默偏低 —— **「缺生可见」**三例」。
**落笔当天即 rg 不到**：这不是历史欠账，是缺少检测器时的稳态行为。

不可命中的 16 条全部是**措辞改写**，不是幻影条目——逐条按「去掉反引号/括号后的前 6 字」
在正文条目头里找近邻，16 条都能找到对应条目，只是索引写的不是条首原文。三条例子：

| §7 登记（不可命中） | `docs/pitfalls.md` 实际条首（可命中） |
|---|---|
| 「`git -C` gitdir 残缺形态与 pre-push 两套相反语义」 | 「`git -C <子模块>` 的第二种向上解析形态（目录在、`.git` 在、gitdir 残缺），与 pre-push 对「未初始化」的两套相反语义」 |
| 「release 守卫在浅检出子模块假报未推」 | 「release 守卫在浅检出子模块上假报「HEAD not on any remote branch」—— 是仪器没历史，不是有未推提交」 |
| 「YAML 日期字段的装载类型才是契约」 | 「YAML 日期字段的「装载类型」才是契约」 |

后果不是美观问题：本仓 §7 的定位规则明确禁止按序号引用，所以按索引抄一条短语去 `rg` 的人
（人或 agent）得到 0 命中，就会得出「这条 pitfall 不存在」的错判——与 §7 反复强调的
「声明 ≠ 执行」同族：**登记面存在，检索面缺席**。

**并且这道约定没有任何检测器**：`rg -l "docs/pitfalls.md" bin/gac bin/ssot` 返回空——
没有任何治理脚本读这个文件，§7 与正文之间零门禁。所以 36% 的失配率是长期无测状态的稳态读数，
不是某次回归。

## 2. 判据

1. **可命中 = 字面子串**。索引里的 `「X」` 必须在 `docs/pitfalls.md` 的文本里作为连续子串出现。
   不做模糊匹配、不做 embedding 召回、不做「前缀相似即算命中」的放宽——放宽后这条 gate 就不再
   检验「人能不能 rg 到」这件事本身，等于把 36% 的失配重新变成绿。
2. **只查索引→正文这一个方向**。反向（每条 pitfall 必须在 §7 登记）不做：正文有 125 条条目，
   §7 表头自陈只列「高频咬人条目」，反向检查必然上百条红，是把「索引」当「全量目录」的口径错误。
3. **解析范围 = §7 章节（`## 7.` 到 `## 8.`）内的表行**。该表在 main 上列数不齐
   （有 4 竖线无收尾竖线的行，也有 5 竖线的行），gate 按「行首是 `|`」识别表行、按提取式扫短语，
   因此天然容忍形状差异，不要求先规整表格——规整表格是另一个改动面，且会与本 gate 的修复互相掩蔽。
4. **提取式 `「([^」]+)」`**：只扫表行，散文里的引号不算登记。若某条登记短语在正文里因含 `」`
   而被截断，该条会以 MISS 暴露，由登记人改写成不含右引号的短形式——这是刻意的收敛压力。
5. **仪器自证优先于绿**：`AGENTS.md` / `docs/pitfalls.md` 任一缺失，或 §7 解析不出任何表行短语，
   输出 `error` 且**判红**（`should_block` 恒真）。不能把「没读到」交成一个空转的绿——
   同 §7「判据报警先 print 原始行」「按构造就绿」族。
6. **上线即 advisory，限期自动转阻断**：与同类 `CR-X2-CRON-INTERP-EXECUTABILITY` /
   `CR-X2-GATE-DETAIL-CONTRACT` 同形——脚本自带 `ENFORCE_AFTER = 2026-12-12`，到期前 `dead>0`
   仍 exit 0（只告警），到期后由脚本自己的退出码转阻断；`--strict` 是「不等限期」的显式提前判红，
   也是变异证明的开关。这样接线在 `gac-local-gate.py` 里**不进 `SOFT_CHECKS`**——
   进 SOFT 就把限期取消成了永久告警。

## 3. 方案

- 新增 `bin/gac/check-pitfalls-index.py`（stdlib-only；`--workspace` / `--json` / `--strict` /
  `--enforce-after`；默认 workspace 按 `__file__` 上溯两级解析，不硬编码仓根，ADR-0456）。
- 注册 GaC 规则 `CR-X2-PITFALLS-INDEX-INTEGRITY` 于 `.omo/_truth/registry/governance-checks.yaml`
  （`dimension: X2`、`layer: meta`、`check_type: consistency_drift`、
  `executor: [ci_gate, gac_local_gate]`、`enforcement: advisory`、
  `source_ref: bin/gac/check-pitfalls-index.py`、`target: AGENTS.md §7 + docs/pitfalls.md`、
  `review_before: 2026-12-12`）。X2 现有 21 条 / 上限 35，在预算内。
- 接线两处，缺一不可：
  - `.omo/_truth/registry/ci-surfaces.yaml` 加 `bin-gac-check-pitfalls-index-py`
    （`workflow: gac-gate.yml`、`gate: false` 到 2026-12-12、`triggers: [gac_local_gate, per_pr]`）；
  - `bin/gac/gac-local-gate.py` 的 `GATES_LIST` 加 `pitfalls-index` 条目——**只有 registry 没有
    GATES_LIST 等于没跑**（§7「判据不被任何 CI 路径跑 = 不存在」）。
- 同批把 §7 里 16 条不可命中的短语改写为**条首原文的字面片段**（可 rg 命中的最短形式），
  使 gate 落地即绿。改写用 `read → check → modify → write` 脚本（`/tmp/gdc/346/fix-index-phrases.py`，
  18 对映射、幂等：已改写的行报 SKIP），禁 `sed -i`。两条改写因正文命中 2 次（另一条目交叉引用了
  同一段文字）而加长，保证寻址键唯一指向一条 pitfall。
- 新增 `bin/` 脚本要同批把 `gac.subtraction_quota.script_baseline` 741→742，
  否则 `check-bin-quota-diff` 判红（§7「新增 `bin/` 脚本要同批 bump `script_baseline`」条，
  且该 gate 读 committed HEAD ⇒ 编辑态自测必红是预期，不是回归）。
- 新增 `tests/unit/test_check_pitfalls_index.py`：6 条用例全在 `tmp_path` 造 AGENTS.md +
  pitfalls.md，断言①字面命中计数正确；②改写措辞判 dead 且限期/strict 两档退出码正确；
  ③仅标点差异（`·` vs 空格）判 dead；④正文缺失 → `error` 且判红；⑤§7 无表行 → `error` 且判红；
  ⑥反引号代码段与全角括号逐字命中。

## 4. 消费面

- 人：`python3 bin/gac/check-pitfalls-index.py`（仓根，输出中文摘要 + DEAD 明细行号）；
  `make gac-local-gate` 与 CI `gac-gate` 经 `GATES_LIST` + ci-surfaces 接线后自动跑到。
- 机器：`--json` 字段固定 10 个，缺值写 `null` 不省略键——`ok` / `total` / `hittable` / `dead` /
  `dead_list[{line, phrase}]` / `body_entries` / `error` / `checked_at` / `enforce_after` / `blocking`。
  `dead_list[].line` 是 `AGENTS.md` 的行号，便于直接定位。
- 退出码：advisory 期内 dead>0 → 0（只告警）；`ENFORCE_AFTER` 起或 `--strict` 或 `error` 非空 → 1。
- 不改 `docs/pitfalls.md` 任何条目正文（实测字节数 187778 不变），不动 §7 表的行序与簇名，
  不动 `AGENTS.md` 其余章节。

## 5. 验收

1. gate 在修复前的 main（`b97281171`）上跑出 `total=45 dead=16`，与 §1 实测一致；
   数字对不上说明解析面不同，先查解析面再动判据（首版在 `aafc91bd6` 上是 43/14，同一判据）。
2. 修复后同一条命令 `dead=0`，且 `docs/pitfalls.md` 字节数不变（只动 `AGENTS.md`）。
3. 变异证明：把一条已修好的短语改写成同义措辞后，advisory 仍 exit 0（限期未到）但 `dead=1`，
   加 `--strict` 立即 exit 1；还原后字节一致。证明 gate 真挂在字面命中判据上，不是「按构造就绿」。
4. `tests/unit/test_check_pitfalls_index.py` 6 条用例全绿，且全部在 `tmp_path` 内跑，
   不读 canonical 工作区的真实 `AGENTS.md`（不写穿、不依赖 host 状态）。
5. 接线自证：`rg -n "check-pitfalls-index" bin/gac/gac-local-gate.py` 有命中，且
   `governance-checks.yaml` 里该规则的 `source_ref` 与 ci-surfaces 的 `tool` 指向同一脚本。

**已知偏离（如实记）**：16 条改写里有 2 条（closeout verify / release 守卫）的字面片段在正文
命中 2 次——另一次是别的条目**逐字引用**了这条条首。唯一指向不是本 gate 的判据（§2.1 只要
字面可命中），且这两条已无更长的括号无关唯一片段可用，故按命中即通过处理。

## 6. Verification

```
python3 bin/gac/check-pitfalls-index.py                        # 期望 [OK] total=45 dead=0
python3 bin/gac/check-pitfalls-index.py --strict               # 期望 exit 0（修好后）
uv run --with pytest --with pytest-timeout -q pytest tests/unit/test_check_pitfalls_index.py -q
rg -n "check-pitfalls-index" bin/gac/gac-local-gate.py .omo/_truth/registry/ci-surfaces.yaml
git diff --stat omostation-root/main...HEAD                     # docs/pitfalls.md 不得出现在列表里
```
