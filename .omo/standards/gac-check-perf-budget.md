---
lifecycle: contract
owner: governance-team
last_updated: "2026-07-28"
---

# GAC Check Performance Budget Standard

> Status: MANDATORY | Applied: N1 (2026-07-28) | ⚠️ 2026-08-08: gate 工具已退役（bin/_archive/check-perf-budget.py，ecos/sgf-policy 零引用）— 本文档为历史决策，执行面以 gate runner 实测层为准
> Authority: `projects/ecos/.../sgf-policy.yaml` gate.`perf_budget_s` + `bin/_archive/check-perf-budget.py`（已退役）
> 照搬 baseline 模式: 标准化 > 逐个打补丁 (第三次"门超时"后立的规矩)

## 1. 核心目的

进 pre-commit 的 GAC check 必须 **<2s**。慢 check 会拖垮每次 commit,
逼开发者 `--no-verify` 绕过, 治理形同虚设。本标准把"快"从口头约定
变成 schema 声明 + 可验证红线。

历史教训 (三个超时的门):
  - layer-call: 40s (全量扫描无增量)
  - severity-registry: 30s (--full 模式 timeout=120 掩盖)
  - check-work-landed: 112s (N×M `git log` subprocess + Python yaml)

## 2. 预算规则

| 场景 | 规则 |
|------|------|
| pre-commit gate | `perf_budget_s ≤ 2` (实测, 含 python 启动) |
| 实测 >2s 的 check | 必须 `ci_only: true` + 注释说明理由 |
| 新增 gate | 必须声明 `perf_budget_s`, 否则 `check-perf-budget` fail |
| 存量 gate | baseline grace (不追溯), 逐步补声明 |
| 调大超时消警 | **禁止** (红线: 不调大超时/不吞异常/不跳过检查) |

## 3. gate schema 字段

```yaml
- id: "check-xxx"
  command: ["bin/gac/check-xxx.py"]
  perf_budget_s: 2        # 必填, int 秒, pre-commit 预算
  ci_only: true           # 可选, >2s 的 check 走 CI
  ci_skip: true           # 可选, CI 环境无依赖也跳
```

`perf_budget_s` 语义: 该 check 在 pre-commit 场景的实测耗时上限 (秒)。
非 ci_only gate 此值必须 ≤2; ci_only gate 声明实测值即可 (无上限约束)。

## 4. 新 check 模板 (含性能声明)

```yaml
- id: "check-new-feature"
  command: ["bin/gac/check-new-feature.py", "--json"]
  perf_budget_s: 2  # 实测 X.XX s (静态 schema / --files 快路径 / CSafeLoader)
```

无 `perf_budget_s` 的新 gate **默认不得进 pre-commit** — `check-perf-budget`
会在 pre-commit 阶段报 warn (baseline grace 期) / fail (grace 期满后)。

## 5. 优化手法 (照搬已验证的成功做法)

按优先级 (先 KISS, 再复杂):

1. **批量预取** — N×M 次 subprocess 合并成 1 次。例: check-work-landed
   把每个 ref 的 `git log --grep` 换成一次 `git log --format` 全量预取 +
   内存 grep (112s → 5.6s)。
2. **CSafeLoader** — yaml 解析用 C 实现 (`yaml.load(text, Loader=yaml.CSafeLoader)`),
   比 `yaml.safe_load` 快 ~10x (87 files: 2.43s → 0.25s)。check-work-landed
   靠这一招 5.6s → 1.75s。
3. **`--files` 快路径** — pre-commit 增量, 只查 staged 触及的文件; CI 全量。
   参考 layer-call 的 `--baseline` + `--files` 双路径。
4. **static vs full 双模式** — 默认 static (schema 校验, <2s); `--full` opt-in
   跑 subprocess (慢, 走 CI)。参考 check-severity-registry。
5. **缓存** — HEAD sha + 输入 mtime 做 key, 命中返回缓存。最后手段 (复杂)。

## 6. 验证

| 层 | 工具 | 场景 | 状态 |
|----|------|------|------|
| 声明层 (静态) | `bin/_archive/check-perf-budget.py`（已退役） | pre-commit | ✅ N1 交付 |
| 实测层 (回归) | gate runner timing | CI | ⬜ Q4 gate runner overhaul (见 redlines `gate-cost-budget` gap) |

声明层只验"gate 声明了 perf_budget_s 且非 ci_only 的 ≤2"。实测层验"实际
耗时不超声明值"——这需要 gate runner 计时基建, 目前是已知 gap。

## 7. 反模式 (红线)

❌ **调大 timeout 消警** — `timeout=120` 掩盖慢 check, 治标不治本。
❌ **`|| true` 了事** — pipe-mask-failure-pattern 同族, 吃 exit code。
❌ **except 吞异常** — 静默失败比慢更危险。
❌ **跳过检查** — `--no-verify` 只能用于 reachability 这类冗余验证 (CI 兜底),
   不能用于消性能警。
❌ **无 perf 声明进 pre-commit** — 新 gate 必须先测耗时再上线。

## 8. References

- N1 goal (本标准的触发源, 2026-07-28)
- baseline 模式: `.omo/_truth/registry/baseline-work-landed.txt` (M2)
- pipe-mask-failure-pattern: `.omo/_knowledge/patterns/pipe-mask-failure-pattern.md`
- redlines: `.omo/_truth/registry/redlines.yaml` (`perf-budget-declared`)
- ADR-0249 (governance ratio 40%, N1 计入治理桶)
