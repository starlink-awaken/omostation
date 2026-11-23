---
schema: md/v1
status: active
lifecycle: history
owner: governance-team
last-reviewed: 2026-11-22
type: ssot
schema_version: standard/v1
standard: reading-honesty-checklist
created: 2026-11-23
---

# Reading-Honesty Checklist（读数诚实性判据清单）

## 问题

一个检查报「通过」，可能只是因为**它什么都没量到**。这类假绿比真红更危险：
它让 CI 面板保持绿色，同时把真正的缺口整块藏起来。本清单把「读数诚实性」拆成
可逐条执行的判据，用于**新写或审查任何「扫一遍 → 下结论」的检查器**。

同一类缺陷在 2026-11 被反复遇到（每一条都有实测，见下），因此值得单列一份标准。

## 五条判据

**① 分母必须可见，且为 0 时必须判红。**
「扫了 N 个 / 发现 M 个问题」——只有 M 时，`M=0` 与「一个都没扫」在输出里同形。
新写的检查器必须在结论行带分母；分母为 0 时不得判通过。
反例（已修）：`check-test-collection` 旧实现 `ok = not repo_errors`，
pytest 没产出收集计数、也没有 ERROR 行时读成 `pass/collected=None`。

**② 折叠 ≠ 判过。**
把两个不同的量折叠成同一个键之前，先问「折叠后还能不能区分它们没被满足」。
反例（已修）：`check-ci-surfaces` 只报 `wired=N/M`、`error=0`、
总结写「CI 平面干净」——那 M-N 条**一个名字都没有**，读者要自己去差集。

**③ 计数必须带名字，名字必须说清「按哪个面量的」。**
只报比例/计数时，「哪几条」要人自己算；而若判据只覆盖某一个面（workflow / cron /
已装面 / 本地门禁），被它漏掉的面里的项会显得像「从不运行」。
反例（已修）：cron 每天在跑的 `log-rotate` 出现在「未接线」名单里 ——
因为该名单只扫 workflows + sgf-policy + gac-local-gate，**不含 cron 面**。

**④ 「读不到」与「为空」必须可分。**
扫描面可能因**检出不完整**而落空（子模块未 init、生成物未物化）。
同一份配置在完整检出与残缺检出上会给出不同读数 —— 两者都不算错，但报告必须
声明自己量的是哪个面。
实例：`gen-dependency-baseline.py --check` 在带全部子模块的检出里读 **75 deps 全对齐**，
在未 init 子模块的 worktree 里读 **57 项 drift（49 STALE）** ——
后者全是「子模块 pyproject 不在 ⇒ 依赖已移除」的误判。
纪律：**重生成类操作只能在完整检出里做**；报告里写明扫描面。

**⑤ 结论必须声明读数来源（哪棵树 / 哪个 root）。**
「仓里是什么」的断言对陈旧检出最敏感 —— 陈旧检出只给前半段。
反例：在落后 20+ 提交的检出上跑 `gen-service-configs.py --check`，
它因 `calendar` 只认单 dict 而**整条崩溃**，而 origin/main 上早已支持 list[dict]
—— 不声明基线就会把「陈旧」读成「有 bug」。

## 自检（新检查器上线前逐条打勾）

- [ ] 结论行有分母；分母为 0 → 红（不是「通过」也不是「跳过」）
- [ ] 名单类输出**点名**到条目，不只给计数
- [ ] 判据覆盖的面被写明（workflow / cron / 已装 / 门禁 / 本地）
- [ ] 缺失输入（子模块、生成物）导致的红**与真红可分**，或有显式前提声明
- [ ] 报告带来源（root / HEAD / 基线），或至少不声称覆盖未覆盖的面

## 反例 → 判据 速查（本仓实证）

| 位置 | 症状 | 判据 |
|---|---|---|
| `bin/gac/check-test-collection.py` | 收集没跑成却读成 pass | ① |
| `bin/gac/check-ci-surfaces.py` | `wired=144/158` + 「干净」，14 条无名 | ②③ |
| `bin/gac/check-cron-interpreter-executability.py` | cron 在跑的进「未接线」名单 | ③ |
| `bin/mof/gen-dependency-baseline.py` | 空 worktree 读出 57 项假 STALE | ④ |
| `bin/mof/gen-service-configs.py` | 陈旧检出上整条崩溃，被读成有 bug | ⑤ |
| `bin/ssot/check-doc-l0-mapping.py` | 文档分母不可见，扫描面落空即判绿 | ① |
| `bin/gac/debt-review-scheduler.py` | 「终态无实证」与「真的没问题」同形 | ② |

## 与既有标准的关系

- `.omo/standards/honest-degrade-contract.md` 管**依赖不可用时的降级**（运行时语义）；
  本标准管**检查器读数本身可不可信**（测量语义）。两者互补：一个是「被测对象
  不在」，一个是「尺子没量到」。
- 每条实测记录仍追加在 `docs/pitfalls.md`（append-only）；本标准只给判据，不复制案例。
