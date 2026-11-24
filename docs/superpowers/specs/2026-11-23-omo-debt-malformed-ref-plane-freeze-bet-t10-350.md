---
schema: md/v1
schema_version: specification/v1
status: accepted
lifecycle: spec
owner: governance-team
last-reviewed: 2026-11-23
accepted: "2026-11-23 Principal 授权全面推进（「我给你充分授权，全面推进吧，完成剩余所有任务」）— 纯缺陷加固：不改任何策略/安全默认值，仅止住单个畸形条目冻结整个投影平面"
bet_id: BET-Y2Q4-T10-350
spec_version: 1.0.0
---

# omo-debt 投影平面存活 — 非 str 条目 ref 判 stale 而非崩平面

台账：`docs/plans/3y-bet-ledger.yaml` `BET-Y2Q4-T10-350`
数据腿：主仓 #5487（`origin/main@01948b6b1`，已合并）—— 修的是那条把散文写成 ASCII `run: ` 的条目本身。
本 BET 是**代码腿**：让下一个这样的条目不再有能力停摆整个平面。

## 目标

`projects/omo` 的债务度量/评审队列在遇到**任一**条目 refs 元素非 `str`（YAML 把它解析成
mapping/序列/int）时，必须：

1. 不抛异常 —— `refresh_outputs()` 的 5 份投影照常产出；
2. 把该条目**判为 stale evidence**（可见），而不是静默丢弃；
3. 其余条目的读数不受影响。

## 根因（2026-11-23 实测）

`.omo/debt/items/*` 的 refs 里写散文注解是**既有用法**：全库 352 个 ref 元素中 142 个带注解、
210 个是裸路径。散文一旦出现 ASCII `: `，YAML 就把整个列表项解析成 mapping。实证触发条目
`.omo/debt/items/GAC-BOOTSTRAP-REGISTERED-NO-EXECUTION-PLANE.yaml` 的 `mitigation_refs[0]`：

```
- bin/gac/gac-bootstrap.py —— 层6 check_plane_coverage()：… CI workflow run: / .githooks+hook-runner.sh …
```

链条（每层都已实测，非推断）：

| 层 | 事实 |
|----|------|
| 模型契约 | `DebtItem.evidence_refs: tuple[str, ...]`（`projects/omo/src/omo/omo_debt_registry.py:24`） |
| 装载器 | `_as_tuple`（`omo_debt_registry.py:105-115`）只把**顶层** dict 归一成 keys，**逐元素不做类型校验** ⇒ dict 原样进入 `tuple` |
| 崩点 | `_resolve_ref_path()` 直接 `Path(ref)` → `TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'dict'`（`pathlib/__init__.py:150`） |
| 放大 | 同一调用点在 `collect_stale_evidence_item_ids()` 内，被 `compute_debt_metrics()` 与 `build_review_queue()` 共同下游依赖，`refresh_outputs()` 一次写 dashboard/reviews/review-queue/action-packet/owner-routing |
| 停摆 | launchd `com.omostation.omo-debt-refresh` 的 `bash -c` 链是 `refresh && dispatch && campaign && report` —— 首环非零 ⇒ 后三环不执行 |
| 潜伏期 | 该条目 2026-11-12 落笔即带畸形 ref；`--now` 路径在此之前未对它求值，崩溃 2026-11-22 起显形 |
| 假绿 | 冻结投影对外仍发布 `debt_health: 100.0`、四项熵 `0.0`、`backlog_pressure 0`、队列 `[]`；同一条数据重算为 `0.0 / 7.45 / pointer_entropy 1.16 / watchlist 6 项` |
| 检测器 | `state-freshness-check.py` 确实检出（`score:50`、`stale:true`）但 `exit 0` 非阻塞；无人消费 launchd 退出码 |

## 修复方案

1. `_resolve_ref_path(repo_root, ref) -> Path | None`：非 `str` 返回 `None`，不再 `Path(dict)`。
2. `collect_stale_evidence_item_ids()`：某条目的 refs 解析出 `None` ⇒ 加入 `stale_ids` 后 `continue`。
   判 stale 而非丢弃是刻意的：畸形 ref = 证据指针不可核验，与「指针指向不存在的文件」同类，
   必须进 `pointer_entropy` 与 review queue 才可见。
3. `build_review_queue()` 经同一调用点继承保护，不单独改。
4. 用例 `projects/omo/tests/unit/test_omo_debt_malformed_refs.py` 走**真实入口** `refresh_outputs`，
   不从生产脚本抽函数直调（AGENTS §6：测试绕过接线就钉不住接线），并单独钉住
   「YAML 确实把该行解析成 dict」这一前提。

## 验证

```bash
cd projects/omo && uv run pytest tests/unit/test_omo_debt_malformed_refs.py -q
# → 4 passed
uv run pytest tests/unit/test_omo_debt_naive_timestamps.py \
    tests/unit/test_omo_debt_metrics_terminal_vocab.py \
    tests/unit/test_omo_debt_malformed_refs.py -q
# → 10 passed, 3 skipped
```

变异证明（判据能红）：在未修树（`git archive` 自 pin `d87a680` 的 `src`）上跑同一用例
→ 复现生产签名 `TypeError: ... not 'dict'`。**先证仪器能红，再谈绿。**

## 回滚

`projects/omo` gitlink 退回上一 pin + 主仓 revert 本 PR 的指针提交；无数据写入、无迁移，
回滚即恢复原行为（含原崩溃行为）。

## 非目标

- **不改装载器**去拒绝或归一畸形 refs —— 那会让 142 个既有用法当场报错，属数据迁移面，
  且裁定权在 principal（见 `DEBT-DASHBOARD-STALE-CHECKOUT-FALSE-GREEN` 的 A/B/C 菜单）。
- **不把 stale/frozen 投影改成阻塞门禁** —— 属门禁严格度变更，同一待裁项。
- **不批量给 142 个带注解 ref 加引号** —— 独立数据迁移。
- **不动 `close` 旗标语义 / reclassify 时间戳** —— 已由 `projects/omo@00b809d` 与主仓 #5478 承载，
  不属本 BET，避免并行交付互相回退。
