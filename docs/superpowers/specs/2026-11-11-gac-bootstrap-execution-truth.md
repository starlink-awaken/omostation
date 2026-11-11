---
schema_version: specification/v1
spec_version: 1.0.0
title: gac-bootstrap 层3/层4 结构性空绿收口 —— glob 落空与 indexed-only 存在性判据
bet_id: BET-Y2Q4-T10-347
owner: governance-team
status: accepted
lifecycle: contract
last-reviewed: 2026-11-11
---

# gac-bootstrap 层3/层4 结构性空绿收口

## 1. 问题（实测，2026-11-11，origin/main `d3c8d020a`）

`bin/gac/gac-bootstrap.py` 是 `CR-X2-GAC-BOOTSTRAP` 的实现，自述「GaC 用自己的机制检测自身完整性」，
分层为 层3 工具活/死、层4 source_ref 存在性、层5 executor 有效性。实机 `--json` 读数：

```json
{"tools": {"alive": 0, "dead": [], "total": 0},
 "indexed_integrity": {"ok": true, "missing_count": 0, "missing": []},
 "exec_effective": {"ok": true, "issues_count": 0}, "ok": true}
```

三处判据落空，全部**按构造就绿**：

| 层 | 判据实现 | 实际覆盖面 | 后果 |
|----|----------|-----------|------|
| 层3 | `GAC_TOOLS = sorted((WORKSPACE / "bin").glob("gac-*.py"))` | `bin/gac-*.py` 顶层匹配 **0 个**（真实 326 个工具在 `bin/gac/` 子目录，另有 `bin/gac/__init__.py` 包标记不计入普查） | 「9 个 gac-*.py 工具是否都能跑」从未跑过任何工具；`total=0` 仍 `ok=true` |
| 层4 | 只对 `source_type == "indexed"` 的规则查 `source_ref` 存在性 | 90 条规则里 `indexed` 只有 **6 条**（其余 84 条 `native`），路径型 `source_ref` 共 **75 条** | **12** 条 `source_ref` 指向不存在的路径，旧层4 只见其中 **0** 条 —— 12 条全是 `native`，一条都不在它的普查面内 |
| 层5 | 只查规则声明的 `executor` 字段在枚举内 | 不比对「脚本是否真被执行」 | 无法发现「登记了工具但无任何平面执行」 |

由此两类缺陷长期隐身（均已在 origin/main 复核）：

- **A 类：登记但不执行。** `bin/gac/check-gate-detail-contract.py`、`bin/gac/check-cron-interpreter-executability.py`
  两个脚本存在、`governance-checks.yaml` 有 `CR-X2-GATE-DETAIL-CONTRACT` / `CR-X2-CRON-INTERP-EXECUTABILITY` 两条规则、
  `.omo/_truth/registry/ci-surfaces.yaml:31/:18` 已登记为 CI 工具；但全库检索显示，这两个脚本路径**只出现在**
  `gac-local-gate.py` 的 `DEFAULT_POLICY`（`:251`、`:243`，位于 `GATES_LIST` 赋值 `:371` 之前，
  而 `POLICY = load_sgf_policy() or DEFAULT_POLICY` 使 `DEFAULT_POLICY` 在 sgf-policy 存在时永不执行）
  与 ci-surfaces 登记里 —— workflow / hook / sgf-policy / runtime `GATES_LIST` **四个执行平面全部缺席**。
- **B 类：source_ref 目录错。** `CR-X1-GOD-MODULE-LIMIT`、`CR-X2-GOD-MODULE-EDIT` 声明
  `bin/gac/check-god-module.py`，该路径在 main 不存在；真实文件是 `bin/ssot/check-god-module.py`
  （按 basename 全库检索唯一命中）。`bin/gac/advisory-checks-upgrade.py:45` 也硬编码了同一个错路径。

现有两个检查器都看不见这两类：`check-ci-surfaces.py` 用正则在**整个 `gac-local-gate.py` 文本**里扫
`"bin/...py"` 字面量，于是把 `DEFAULT_POLICY` 里的死字面量当「已接线」；
`check-rule-wiring-coverage.py` 的判据是规则 id 文本在执行语料里**出现过**，同样看不见「提到但没执行」。

## 2. 目标与交付面

在 `bin/gac/gac-bootstrap.py` 内收口，不新建第五个 ontology、不加第二个 dispatcher：

1. **层3 修尺**：工具集改为 `bin/gac/*.py` ∪ `bin/gac-*.py`；`total == 0` 判 FAIL（零分母 = 仪器没接上，不是「零问题」）；
   输出带 `audited/total` 分母。
2. **层4 扩面**：存在性检查覆盖**所有**带路径型 `source_ref` 的规则（不再限 `indexed`）；`::` / `#` 锚点剥离后
   只判路径部分；子模块内路径改按 `git cat-file -e` 对 gitlink 树判定，判不了时显式标注「装置不可用」而非计入通过。
3. **层6 新增**：执行平面缺席检测 —— 对 `ci-surfaces.yaml` 登记的每个 check 类工具，比对 runtime
   `GATES_LIST`（`importlib` 实读，不用文本正则）∧ `.github/workflows/*` ∧ `.githooks/*` ∧ sgf-policy；
   四平面全缺席 ⇒ 点名（实测读数：声明执行 148/157，命中 138，**点名 10 条**，其中 A 类 2 条）。
4. **B 类处置**：2 条规则的 `source_ref` 目录改对 + `advisory-checks-upgrade.py:45` 路径改对。
5. **A 类与其余 10 条不可达 `source_ref` 只点名不私改**（12 条实测缺席 − B 类修掉的 2 条 = 10）：按仓内纪律登记为 debt 条目，交 principal 裁决
   （`CR-X2-CRON-INTERP-EXECUTABILITY` 已有 2026-11-10「先 warn + 限期收敛」裁决，接线方向属该裁决延续）。

## 3. 验收（每条都要实测读数）

- 改动前 `gac-bootstrap.py --json` 的 `tools.total=0`、`indexed_integrity.missing_count=0`；
  改动后实测读数 `tools.alive=320/total=326（audited=326）`、层4 `checked=75 missing=10 indexed_missing=0`、
  层6 `declared=148 reached=138 violations=10 manual_exempt=0`。
  **`ok` 不是布尔常量**：仪器类失效（层3 零分母、`indexed` 子集缺席、schema、executor）恒 `ok=false`；
  加宽的层4 / 层6 / 层3-无入口 属 advisory，`ok` 取决于 registry 规则
  `CR-X2-GAC-BOOTSTRAP.enforcement`。当前该字段是 `advisory` ⇒ 实测 `ok=true, blocking=false,
  advisory_gaps=true, rc=0`；把它改成 `blocking` 即 `ok=false`（脚本内无开关、无常量，见
  `tests/unit/test_gac_bootstrap_layers.py::test_advisory_switch_is_read_from_the_registry_rule`）。
  > 本节修订说明：本条原写「改动后 `tools.total>300` 且 `ok=false`」，是落笔时按「点名即红」的想象写的，
  > 与实际交付的「advisory/blocking 分界读 registry」形状不符。按原句验收会得到一个为了变红而变红的
  > 实现（把 20 条无人认领的发现一次性染红 CI）。此处按实现口径改正，并在 retro 里记为偏差，不是事后合理化：
  > 判据的正当性来自 A/B/C/D/E/F 六类发现的**可点名性**与**分母可读性**，`ok` 只承载「是否已达到阻断条件」。
- 判据变异：把 `GAC_TOOLS` 的 glob 换回 `bin/gac-*.py` ⇒ 层3 用例当场红；把层4 的「全部路径型」退回
  「仅 indexed」⇒ 层4 用例红；把层6 的平面比对换成文本正则 ⇒ 层6 用例红。三组各记红条数（实测 1 / 2 / 1）。
- 零回归：`projects/omo` 与 `tests/unit` 既有相关用例全绿；`make gac-local-gate` 不因新层失控
  （新层首月 advisory；转阻断单点是 `CR-X2-GAC-BOOTSTRAP.enforcement`，限期同规则
  `review_before: 2026-11-29` —— 不在脚本里另设 `ENFORCE_AFTER` 常量，避免两条限期口径漂移）。
- 实机 canary：`check-gate-detail-contract` / `check-cron-interpreter-executability` 必须被层6 点名，
  且点名理由写明「四平面缺席」；收据缺该读数视为该面未验。

## 4. 非目标

- 不改 `DEFAULT_POLICY` 的存在合理性（它是 sgf-policy 缺席时的兜底，本 BET 只禁止「把兜底当执行平面」这一误读）。
- 不放宽任何既有判据为模糊匹配；不做「按名字相似猜测」。
- 不改 `check-ci-surfaces.py:121` 的文本扫描形状（那是另一条已登记债务，#5287 已在动该文件，避免撞面）。
- 不动 `CR-AGE-*` / `CR-SEC-*` 的规则语义本体，只在层4 点名其不可达 `source_ref`。
