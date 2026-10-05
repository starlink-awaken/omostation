---
schema: md/v1
status: PROPOSED
lifecycle: spec
owner: architecture-governance
last-reviewed: 2026-10-05
type: ssot
id: ADR-0463
related: ADR-0455, ADR-0461, ADR-0462
tags: [claims-authority, producer-gap, publication-scope, fail-closed, observability]
---

# ADR-0463 — 「契约已定义并测试，但生产侧无生产者」的三例缺口

- **Status**: ACCEPTED（2026-10-05 principal 裁定取「不应带」一支；见文末决策记录）
- **Date**: 2026-10-05
- **Owner**: architecture-governance
- **Related**: ADR-0455（publication-scoped allow）、ADR-0461（fence 绑定）、
  ADR-0462（provenance 区间下界）

## 背景

2026-09-30 ~ 10-05 的一次系统性排查中，同一种形态**三次**出现：

> **契约/校验已在代码里定义，且被测试覆盖；但生产调用路径从不提供该值。**
> 于是该分支在生产中要么永远失败，要么从未被真正走过——而测试是绿的。

三次的形态完全一致，只是位置不同。

## 三例

| # | 符号 | 形态 | 处置 |
|---|---|---|---|
| 1 | `gh_json` | `bin/lib/gh_query.py` 有定义；`clone-lifecycle.py` 在 PR 查询段调用它**却从未 import** | 已修（父仓 #4596），并连带修好一个长期红的测试 |
| 2 | `claims_authority_fence_context` | `clone-lifecycle.py:1296` 唯一读取方；**全仓无写入方** | 已补只读动词 `describe-claim`（omo#206，父仓 #4615） |
| 3 | **`publication_scope`** | authority 侧 `_validate_publication_scoped_allow` 严格校验；**生产 `lifecycle.py` 从不构造** | **未解** |

## 第 3 例详解（当前阻塞项）

### 事实

```
projects/omo/src/omo/workflow/lifecycle.py:486
    "requested_paths_digest": _authority_digest({"paths": sorted(...), "surfaces": sorted(...)})

projects/omo/src/omo/workflow/claims_authority.py:440
    scope = request.get("publication_scope")
    if not isinstance(scope, Mapping):
        raise AuthorityError("V1_AUTHORITY_FORBIDDEN", "managed_clone")     # ← 生产命中此处
```

全仓搜索 `publication_scope`：只出现在 authority 的**校验器**与本会话新写的
「从回执读出」那段，**生产调用方从不提供**。

### 后果

生产环境下 `observe-claim` 必然被 `V1_AUTHORITY_FORBIDDEN(managed_clone)` 拒绝 ——
即 **observe 本身在生产中不成立**。ADR-0455 方案 A（v2 上的 publication-scoped allow）
在 authority 侧实现完备、测试覆盖，但**测试夹具是手工塞入 `publication_scope` 的**，
生产从未走通该分支。

连带影响：ADR-0461 第 1 步从回执读出的 `publication_scope.paths_digest`
在生产中**恒为空字符串**。因此 ADR-0461 的第 2–4 步即便全部完成，
`path_digest` 仍为空，legacy publish fence 依旧无法满足。

### 一个尚未解释的细节

生产与测试夹具的 `paths_digest` 算法**不一致**：

- 生产（`lifecycle.py:486`）：`_authority_digest({"paths": sorted(...), "surfaces": sorted(...)})`
- 测试夹具（`_publication_scope`）：`canonical_digest(paths)`（扁平列表）

而 authority 要求 `scope["paths_digest"] == request["requested_paths_digest"]`。
夹具通过 `request["requested_paths_digest"] = scope["paths_digest"]` 直接覆盖生产
公式来绕开这一差异 —— 这正是「测试绿、生产死」的典型成因。

## 待裁定项（需 principal 决定，不由实现侧代决）

1. **生产的 `observe-claim` 应不应该带 `publication_scope`？**
   - **应带** → `lifecycle.py` 是真实缺陷，需为本 ADR 定「何时允许构造、scope 如何收窄、
     `effect_ceiling` 如何取值」的生产规则；且要先解释生产/夹具的 `paths_digest` 算法差异。
   - **不应带**（shadow 态下 observe 本就应 deny）→ ADR-0455 方案 A 在当前设计下
     从未被使用，fence 链路是**设计上不可达**的，ADR-0461 的第 2–4 步应作废。
2. 若裁定为「不应带」：`describe-claim`（omo#206）与 ledger 绑定（omo#207）是否保留？
   它们本身无害（只读 + 追加 ledger），但会让「fence 即将可用」的错误印象持续存在。

## 建议的根治方向（若裁定为「应带」）

引入一条**常设检查**：对 authority 每个必填/校验字段，断言**生产侧存在生产者**。
本会话三次都是靠人工排查发现的，成本极高；而这类缺口天然适合 lint —— 字段在
`claims_authority.py` 的校验清单里出现、却在 `lifecycle.py` 的请求构造中从不出现，
即可机械检出。

## 非目标

- 不在本 ADR 内实现 `publication_scope` 的生产构造（授权语义需先裁定）
- 不改动 authority 侧任何校验逻辑
- 不因「测试是绿的」而认定相关分支有效

## 证据

- `projects/omo/src/omo/workflow/claims_authority.py:440` `_validate_publication_scoped_allow`
- `projects/omo/src/omo/workflow/lifecycle.py:486` 生产 `requested_paths_digest`
- `projects/omo/tests/test_workflow_claims_authority_bridge.py:1177` 夹具 `_publication_scope`
- `bin/gac/clone-lifecycle.py:1296` fence context 唯一读取方
- 父仓 #4596（`gh_json`）、omo#206（`describe-claim`）、omo#207（ledger 绑定）

## 2026-10-05 裁定与实施结果

**principal 裁定**：生产的 `observe-claim` **不应**带 `publication_scope`。
即上列第 2 支成立 —— shadow 态下 observe 本就应 deny，ADR-0455 方案 A
（v2 上的 publication-scoped allow）**从未在生产被使用过**，
`_validate_publication_scoped_allow` 是一条**从未被走通**的分支。

**据此**：

1. **ADR-0461 第 2–4 步作废**（已回写该 ADR）。若继续接线，等于照着一份
   从未在生产运行过的契约施工。
2. **第 1 例（`gh_json`）与第 2 例（`claims_authority_fence_context`）的修复予以保留**。
   `describe-claim`（omo#206）与 ledger 绑定（omo#207）本身无害 —— 只读 + 追加
   ledger，不改任何既有语义；它们只是**不构成完整链路**，须与本 ADR 一并阅读，
   避免产生「fence 即将可用」的错误印象。
3. **机器态不变**：`integrate --apply` 仍走常规 PR 流程（ADR-0459 既有结论）。

### 关于「根治方向」的可行性（实测后收窄）

原建议是「对 authority 每个校验字段断言生产侧存在生产者」。实测该判据**可用但不够**：

- 以 `request.get("...")` / `request["..."]` 从 `claims_authority.py` 提取到 56 个字段，
  在 `lifecycle.py` + `clone-lifecycle.py` + `agent-clone.py` 三个生产调用方中
  查找「完全无人构造」的 —— 命中 7 项。
- 但 **`publication_scope` 落在漏网里**：omo#207 新增的 `receipt.get("publication_scope")`
  让该字符串出现在 `lifecycle.py` 中，尽管那是**读取回执**而非**构造请求**。

**结论**：检查必须限定到**请求构造点**（如「`request = {` 字面量内的键」），
全文件字符串搜索会产生假阴性。留待后续专项。

## 决策记录

- **2026-10-05**：提案。记录三例同构缺口；第 1、2 例已修，第 3 例（`publication_scope`）
  未解并阻塞 ADR-0461 第 2–4 步。待 principal 裁定。
- **2026-10-05（裁定）**：取「不应带」一支。ADR-0455 方案 A 判定为**从未在生产使用**；
  ADR-0461 第 2–4 步作废；omo#206 / omo#207 保留但须与本 ADR 一并阅读。
  根治方向经实测后收窄为「限定到请求构造点」。
