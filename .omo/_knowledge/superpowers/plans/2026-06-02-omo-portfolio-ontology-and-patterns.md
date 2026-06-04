# OMO Portfolio Ontology And Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the external OMO method system beyond the current portfolio-governance playbooks by adding dedicated portfolio object/contract knowledge docs and deriving the next pattern wave from those stabilized objects.

**Architecture:** First deepen the knowledge plane so `39/40/41` no longer rely only on playbook prose and instead rest on first-class portfolio objects plus an explicit contract appendix. Then derive new patterns from the combined playbook/object/contract set, and finally sync every navigation surface and rerun document-level verification so the new layer is discoverable without creating shadow SSOT drift.

**Tech Stack:** Markdown docs, ripgrep (`rg`), `find`, `wc`, `git`

---

## File map

### Create

- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/05-OMO联邦Portfolio对象子字典.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/06-OMO联邦Portfolio契约附录.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/07-从对象契约到长期重组纪律的演化模式.md`

### Modify

- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/03-OMO对象字典.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/04-OMO与Repo-SSOT引用契约.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/INDEX.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/02-OMO增长路线图.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/INDEX.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/INDEX.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_control/STATE.md`

### Reference while implementing

- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_control/39-OMO联邦Portfolio Routing、Multi-Federation Chooser与Default Arbitration Playbook.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_control/40-OMO联邦Meta-Governance、Policy Inheritance与Exception Control Playbook.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_control/41-OMO联邦Lifecycle Portfolio Review、Sunset Radar与Recomposition Backlog Playbook.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/04-从纠偏到收敛的闭环模式.md`
- `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/05-从方法闭环到用户价值闭环的转译模式.md`

---

### Task 1: Create the portfolio object subdictionary

**Files:**
- Create: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/05-OMO联邦Portfolio对象子字典.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/03-OMO对象字典.md`
- Test: document-level `rg` checks on both files

- [ ] **Step 1: Write the failing coverage check**

Run:

```bash
rg -n 'Federation Portfolio|Chooser Contract|Arbitration Record|Policy Inheritance Model|Exception Ledger|Sunset Radar|Recomposition Backlog' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/05-OMO联邦Portfolio对象子字典.md'
```

Expected: fail because the file does not exist yet.

- [ ] **Step 2: Create the subdictionary with the exact sections below**

Write this file skeleton first, then fill the prose using the existing tone from `03-OMO对象字典.md`:

```md
# OMO / 联邦Portfolio对象子字典

> 用途：把 `39/40/41` 引入的 portfolio-level first-class objects 单独压缩成对象子字典，回答这些对象各自的 authority、关系、边界、生命周期与不等于什么。

---

## 0. 这份子字典回答什么问题
## 1. 这份子字典与对象总字典/引用契约/playbooks 的分工
## 2. Portfolio 对象总表
## 3. 入口与路由对象
## 4. 治理与例外对象
## 5. 生命周期与重组对象
## 6. 对象关系图（portfolio 版）
## 7. 最容易混淆的对象对
## 8. 与 `39/40/41` 的对应关系
## 9. 一句话总纲
```

`## 2. Portfolio 对象总表` 至少要包含这 7 个对象行：

```md
| **Federation Portfolio** | 组合治理对象 | Control / Knowledge | Authority | 由多个 stable federations 组成、需要统一入口与治理解释的组合层对象 |
| **Chooser Contract** | 路由对象 | Control / Truth | Authority | 规定何时进入 portfolio chooser、按什么信号选择默认去向的契约 |
| **Arbitration Record** | 决策对象 | Control / Delivery | Authority | 多 federation route 冲突时留下的默认仲裁结果、理由与 fallback 记录 |
| **Policy Inheritance Model** | 治理对象 | Truth / Control | Authority | 说明 shared policy、local override 与 precedence 如何咬合的结构 |
| **Exception Ledger** | 治理对象 | Control / Delivery | Authority | 记录 approved exception、expiry、owner 与 removal path 的账本 |
| **Sunset Radar** | 生命周期对象 | Control / Delivery | Authority | 标记已进入持续观察、可能退出默认路径的 federations 的观察对象 |
| **Recomposition Backlog** | 生命周期对象 | Control / Truth | Authority | 记录需 merge / downgrade / exit / split-back 的组合层重组提案 |
```

- [ ] **Step 3: Link the parent object dictionary to the new subdictionary**

Add a “详见 `05-OMO联邦Portfolio对象子字典.md`” pointer in `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/03-OMO对象字典.md` directly under `## 3.6 组合治理与生命周期对象` using this exact line:

```md
> 若需要 portfolio-level 对象的更细 authority / lifecycle / confusion matrix，继续看 `05-OMO联邦Portfolio对象子字典.md`。
```

- [ ] **Step 4: Run verification**

Run:

```bash
rg -n '## 2. Portfolio 对象总表|## 6. 对象关系图（portfolio 版）|## 8. 与 `39/40/41` 的对应关系|Federation Portfolio|Chooser Contract|Recomposition Backlog' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/05-OMO联邦Portfolio对象子字典.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/03-OMO对象字典.md'
```

Expected: matching lines from both files.

- [ ] **Step 5: Commit**

```bash
git add \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/03-OMO对象字典.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/05-OMO联邦Portfolio对象子字典.md'
git commit -m "docs: add portfolio object subdictionary"
```

---

### Task 2: Add the portfolio contract appendix

**Files:**
- Create: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/06-OMO联邦Portfolio契约附录.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/04-OMO与Repo-SSOT引用契约.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/INDEX.md`
- Test: `rg` checks for appendix sections and index pointers

- [ ] **Step 1: Write the failing check**

Run:

```bash
rg -n 'Portfolio 契约|Chooser Contract|Exception Ledger|Pointer-not-usurpation' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/06-OMO联邦Portfolio契约附录.md'
```

Expected: fail because the file does not exist yet.

- [ ] **Step 2: Create the contract appendix**

Write this exact section structure:

```md
# OMO / 联邦Portfolio契约附录

> 用途：把 portfolio-level objects 如何与 repo `.omo/`、外部 OMO knowledge/docs、以及 `39/40/41` 的默认动作关系固定成更细的 contract appendix。

---

## 0. 这份附录回答什么问题
## 1. 这份附录与 `04-OMO与Repo-SSOT引用契约.md` 的分工
## 2. Portfolio object -> repo object contract 表
## 3. Portfolio object -> OMO doc contract 表
## 4. Pointer-not-usurpation 在组合治理对象上的特殊规则
## 5. Exception / expiry / removal path 的最小契约
## 6. 更新协议
## 7. 一句话总纲
```

In `## 2. Portfolio object -> repo object contract 表`, include rows for at least:

```md
| **Chooser Contract** | `/.omo/scenarios/`, `/.omo/standards/`, route-related evidence | 指向 scenario / rule / evidence | 不在外部 OMO 复制 live route truth |
| **Arbitration Record** | `/.omo/evidence/`, `/.omo/summaries/`, run outputs | 指向仲裁证据与 closeout | 维护外部并行的 live arbitration ledger |
| **Policy Inheritance Model** | `/.omo/standards/`, `/.omo/goals/`, capability policy surfaces | 抽象 shared / local precedence | 发明与 repo 冲突的第二套 live policy source |
| **Exception Ledger** | approved exception evidence and standards refs | 记录边界与 expiry contract | 把例外直接写成永久事实 |
| **Sunset Radar** | phase / evidence / closeout pointers | 解释观察与候选退出 | 在外部 OMO 宣布 live federation 已退役 |
| **Recomposition Backlog** | design / plan / decision pointers | 记录未来提案与 owner | 把 backlog 当成当前 reality |
```

- [ ] **Step 3: Extend the parent contract doc and knowledge index**

Add these exact pointer lines:

In `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/04-OMO与Repo-SSOT引用契约.md` under `## 8. 与现有工件的关系`:

```md
7. `_knowledge/05-OMO联邦Portfolio对象子字典.md`
8. `_knowledge/06-OMO联邦Portfolio契约附录.md`
```

In `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/INDEX.md`, add:

```md
| `05-OMO联邦Portfolio对象子字典.md` | 把 `39/40/41` 引入的 portfolio-level objects 细化成 authority / relation / lifecycle 子字典 |
| `06-OMO联邦Portfolio契约附录.md` | 把 portfolio-level objects 与 repo `.omo/`、外部 OMO surfaces 的边界 contract 细化成附录 |
```

- [ ] **Step 4: Run verification**

Run:

```bash
rg -n '05-OMO联邦Portfolio对象子字典|06-OMO联邦Portfolio契约附录|Portfolio object -> repo object contract 表|Pointer-not-usurpation' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/04-OMO与Repo-SSOT引用契约.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/06-OMO联邦Portfolio契约附录.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/INDEX.md'
```

Expected: appendix sections exist and both index surfaces point to the new files.

- [ ] **Step 5: Commit**

```bash
git add \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/04-OMO与Repo-SSOT引用契约.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/05-OMO联邦Portfolio对象子字典.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/06-OMO联邦Portfolio契约附录.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/INDEX.md'
git commit -m "docs: add portfolio contract appendix"
```

---

### Task 3: Derive patterns 06 and 07 from the stabilized portfolio layer

**Files:**
- Create: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md`
- Create: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/07-从对象契约到长期重组纪律的演化模式.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/INDEX.md`
- Test: `rg` checks for samples, sections, and index references

- [ ] **Step 1: Write the failing checks**

Run:

```bash
rg -n '组合治理稳定|长期重组纪律' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/07-从对象契约到长期重组纪律的演化模式.md'
```

Expected: fail because neither file exists yet.

- [ ] **Step 2: Write pattern 06 using the current samples**

Use these sources explicitly in the header of `06-从Portfolio对象到组合治理稳定的模式.md`:

```md
> 基于 `39/40/41` 与 portfolio-level object/contract docs 抽取的第 6 份 patterns。  
> 样本来源：  
> 1. `_control/39-OMO联邦Portfolio Routing、Multi-Federation Chooser与Default Arbitration Playbook.md`
> 2. `_control/40-OMO联邦Meta-Governance、Policy Inheritance与Exception Control Playbook.md`
> 3. `_control/41-OMO联邦Lifecycle Portfolio Review、Sunset Radar与Recomposition Backlog Playbook.md`
> 4. `_knowledge/05-OMO联邦Portfolio对象子字典.md`
> 5. `_knowledge/06-OMO联邦Portfolio契约附录.md`
```

Write it with the same structure as patterns `04` and `05`:

```md
## 0. 作用
## 1. 模式一：……
## 2. 模式二：……
## 3. 模式三：……
## 4. 模式四：……
## 5. 模式五：……
## 6. 模式六：……
## 7. 当前最稳的一条组合治理路径
## 8. 一句话总纲
```

- [ ] **Step 3: Write pattern 07 as the long-horizon evolution pattern**

Use this exact header block in `07-从对象契约到长期重组纪律的演化模式.md`:

```md
> 基于 portfolio object / contract layer 与现有 lifecycle playbooks 抽取的第 7 份 patterns。  
> 主要锚点：  
> 1. `_knowledge/05-OMO联邦Portfolio对象子字典.md`
> 2. `_knowledge/06-OMO联邦Portfolio契约附录.md`
> 3. `_control/36-OMO联邦Permanent Downgrade、No-Retry判定与Exit Finalization Playbook.md`
> 4. `_control/37-OMO联邦Split、Fork与Sub-Federation Boundary Reset Playbook.md`
> 5. `_control/41-OMO联邦Lifecycle Portfolio Review、Sunset Radar与Recomposition Backlog Playbook.md`
```

Make section `## 6` describe the exact path:

```text
对象层被固定
  -> contract 边界被写硬
  -> chooser / inheritance / exception 不再只靠语义说明
  -> sunset radar 提前暴露过期结构
  -> recomposition backlog 承接未来结构变更
  -> patterns 反过来缩短下一轮 portfolio review 路径
```

- [ ] **Step 4: Update the delivery index**

Append these rows to `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/INDEX.md`:

```md
| `patterns/06-从Portfolio对象到组合治理稳定的模式.md` | 从 `39/40/41` 与 portfolio object/contract docs 中抽出的组合治理稳定模式文档 |
| `patterns/07-从对象契约到长期重组纪律的演化模式.md` | 从 portfolio object/contract layer 与 lifecycle reset/review docs 中抽出的长期重组纪律模式文档 |
```

Also update the summary sentence so `patterns/` mentions the new portfolio governance pattern wave instead of stopping at pattern 05.

- [ ] **Step 5: Run verification**

Run:

```bash
rg -n '第 6 份 patterns|第 7 份 patterns|当前最稳的一条组合治理路径|长期重组纪律|patterns/06-|patterns/07-' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/07-从对象契约到长期重组纪律的演化模式.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/INDEX.md'
```

Expected: matches in both new pattern docs and the delivery index.

- [ ] **Step 6: Commit**

```bash
git add \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/07-从对象契约到长期重组纪律的演化模式.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/INDEX.md'
git commit -m "docs: add portfolio governance patterns"
```

---

### Task 4: Sync navigation and growth surfaces

**Files:**
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/INDEX.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/INDEX.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/INDEX.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/02-OMO增长路线图.md`
- Modify: `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_control/STATE.md`
- Test: dynamic count + search verification

- [ ] **Step 1: Compute the new counts before editing**

Run:

```bash
ROOT='/Users/xiamingxing/Documents/学习进化/经验积累/OMO'
printf 'knowledge_count=%s\n' "$(find \"$ROOT/_knowledge\" -maxdepth 1 -type f | wc -l | tr -d ' ')"
printf 'pattern_count=%s\n' "$(find \"$ROOT/_delivery/patterns\" -maxdepth 1 -type f -name '*.md' | wc -l | tr -d ' ')"
```

Expected: counts higher than the current `4` knowledge docs and `5` pattern docs.

- [ ] **Step 2: Update the root navigation docs**

Make these content changes:

1. In `README.md`, add one route row for the new knowledge appendix wave and one route row for the new pattern wave.
2. In `INDEX.md`, update the top summary counts and append the new knowledge/pattern files to the master file table.
3. In `_knowledge/INDEX.md` and `_delivery/INDEX.md`, make sure the newly created files appear in order.

Use this wording in `README.md` for the two new quick-route rows:

```md
| 看 `39/40/41` 背后的 portfolio-level objects、authority、lifecycle 与混淆边界 | `_knowledge/05-OMO联邦Portfolio对象子字典.md` |
| 看 portfolio-level object / contract 稳定后抽出的下一波组合治理 patterns | `_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md` |
```

- [ ] **Step 3: Update the roadmap and state phrasing**

In `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/02-OMO增长路线图.md`, add wording that the next stage is no longer “invent more playbooks first” but “deepen object/contract/pattern compression around the already-closed portfolio layer”.

In `/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_control/STATE.md`, add one bullet that the current system is now entering an ontology/pattern compression wave on top of the closed portfolio-governance layer.

- [ ] **Step 4: Run verification**

Run:

```bash
ROOT='/Users/xiamingxing/Documents/学习进化/经验积累/OMO'
rg -n '05-OMO联邦Portfolio对象子字典|06-OMO联邦Portfolio契约附录|patterns/06-从Portfolio对象到组合治理稳定的模式|patterns/07-从对象契约到长期重组纪律的演化模式|ontology/pattern compression|对象子字典|契约附录' \
  \"$ROOT/README.md\" \"$ROOT/INDEX.md\" \"$ROOT/_knowledge/INDEX.md\" \"$ROOT/_delivery/INDEX.md\" \"$ROOT/_knowledge/02-OMO增长路线图.md\" \"$ROOT/_control/STATE.md\"
```

Expected: all six surfaces mention the new knowledge/pattern wave.

- [ ] **Step 5: Commit**

```bash
git add \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/INDEX.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/INDEX.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/INDEX.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/02-OMO增长路线图.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_control/STATE.md'
git commit -m "docs: sync portfolio ontology wave surfaces"
```

---

### Task 5: Final verification and closeout

**Files:**
- Verify the entire changed set from Tasks 1-4
- Modify: this plan file only if self-review finds a gap

- [ ] **Step 1: Run the full document verification sweep**

Run:

```bash
set -euo pipefail
ROOT='/Users/xiamingxing/Documents/学习进化/经验积累/OMO'
KNOW05=\"$ROOT/_knowledge/05-OMO联邦Portfolio对象子字典.md\"
KNOW06=\"$ROOT/_knowledge/06-OMO联邦Portfolio契约附录.md\"
PAT06=\"$ROOT/_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md\"
PAT07=\"$ROOT/_delivery/patterns/07-从对象契约到长期重组纪律的演化模式.md\"

test -f \"$KNOW05\"
test -f \"$KNOW06\"
test -f \"$PAT06\"
test -f \"$PAT07\"

rg -n 'Federation Portfolio|Chooser Contract|Arbitration Record|Policy Inheritance Model|Exception Ledger|Sunset Radar|Recomposition Backlog' \"$KNOW05\" \"$KNOW06\"
rg -n '第 6 份 patterns|第 7 份 patterns|组合治理稳定|长期重组纪律' \"$PAT06\" \"$PAT07\"
rg -n '05-OMO联邦Portfolio对象子字典|06-OMO联邦Portfolio契约附录|patterns/06-|patterns/07-' \
  \"$ROOT/README.md\" \"$ROOT/INDEX.md\" \"$ROOT/_knowledge/INDEX.md\" \"$ROOT/_delivery/INDEX.md\" \"$ROOT/_knowledge/02-OMO增长路线图.md\" \"$ROOT/_control/STATE.md\"
```

Expected: all four files exist and all shared surfaces reference them.

- [ ] **Step 2: Run placeholder and ambiguity scan on the new docs**

Run:

```bash
rg -n 'TODO|TBD|待补|占位|稍后|类似上文|之后补' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/05-OMO联邦Portfolio对象子字典.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/06-OMO联邦Portfolio契约附录.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/07-从对象契约到长期重组纪律的演化模式.md'
```

Expected: no matches.

- [ ] **Step 3: Write the closeout note**

Append a short closeout paragraph to the active session plan or summary noting:

```md
- portfolio-level playbooks now have matching object and contract docs
- pattern wave 06/07 now compresses the portfolio layer instead of reopening playbook gaps
- future work, if any, should deepen specific contracts or cases, not recreate the same portfolio seam
```

- [ ] **Step 4: Final commit**

```bash
git add \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/05-OMO联邦Portfolio对象子字典.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/06-OMO联邦Portfolio契约附录.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/06-从Portfolio对象到组合治理稳定的模式.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/patterns/07-从对象契约到长期重组纪律的演化模式.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/03-OMO对象字典.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/04-OMO与Repo-SSOT引用契约.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/INDEX.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_delivery/INDEX.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/README.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/INDEX.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_knowledge/02-OMO增长路线图.md' \
  '/Users/xiamingxing/Documents/学习进化/经验积累/OMO/_control/STATE.md'
git commit -m "docs: deepen portfolio ontology and pattern wave"
```

---

## Self-review

- **Spec coverage:** This plan covers both requested follow-ups: the knowledge-layer object/contract deepening and the next pattern wave.
- **Placeholder scan:** No `TODO` / `TBD` / “similar to above” placeholders are left in the plan.
- **Type consistency:** The plan consistently uses the same seven portfolio objects and the same target file names across all tasks.
