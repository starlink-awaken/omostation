---
schema: md/v1
status: accepted
lifecycle: contract
owner: governance-team
last-reviewed: 2026-09-26
type: ephemeral
schema_version: specification/v1
spec_version: 1.0.0
title: Scene-Map Fallback Gap — workflow-scene-map/v1 声明的 default 无人实现
bet_id: BET-Y2Q4-SH-5.3
---

# BET-Y2Q4-SH-5.3 — Scene-Map Fallback Gap

## 1. 问题（先测量，后判断）

`bin/ssot/workflow-scene-map.yaml` 是 closeout→scene 桥的解析表（`schema: workflow-scene-map/v1`）。
它声明了三条解析规则，其中第 3 条写在文件自身的注释里：

> 3. Otherwise fall back to `default` (covers new workflows added before this map is updated).

并且顶层确实有两个键承载这条规则：

```yaml
default: scenes/agent-workflow-closeout.yaml
fallback_resolution: default
```

实测（2026-09-26，`origin/main@a3b4852a5`）：

| 量 | 值 |
|---|---|
| `.omo/_truth/registry/agent-workflows/workflows/*.yaml` 注册的 workflow | 26 |
| `map:` 段条目 | 19 |
| **未入 map 的 workflow** | **7** |
| `map:` 中指向不存在 scene card 的条目 | 0 |
| `map:` 中无对应 registry 文件的孤儿条目 | 0 |

未映射的 7 条：`agent-onboarding`、`round-type-router`、`scene-execution`、`scene-lifecycle`、
`state-sync`、`submodule-pointer-bump`、`submodule-pointer-close`。

消费端 `bin/agent-workflow.py:_bridge_closeout_to_scene` 只做一次查找：

```python
scene_card_rel = str((scene_map.get("map") or {}).get(workflow_id) or "").strip()
if not scene_card_rel:
    _bail(f"workflow_id '{workflow_id}' not in scene map 'map:' section")
    return
```

`default:` 与 `fallback_resolution:` **从未被读取**。因此这 7 个 workflow 的每一次 closeout
都会走进 `_bail`：episode 不落账。BET-Y2Q4-SH-5.2 已经把这条路径变成**可观测**（stderr 上会打印
理由），但它按设计不改变**结果**——桥仍然不发 episode。

所以这不是「声明未实现所以无害」，而是「声明的覆盖率承诺是假的」：SSOT 说未映射的 workflow 会被
`default` 兜住，真实行为是丢掉。`submodule-pointer-bump` / `submodule-pointer-close` 是本仓日常
高频流程，它们正是那 7 条里的成员。

## 2. 契约

桥的场景卡解析必须与 `workflow-scene-map/v1` 的声明一致，即完整实现三条规则：

1. 以 closeout run 的 `workflow_id` 查 `map:`；命中即使用该 scene card 路径。
2. 未命中时读取 `fallback_resolution`；**仅当其值为 `default`** 时取顶层 `default:` 的路径。
3. 兜底路径为空、或 `fallback_resolution` 缺失/取值非 `default` 时，判为未解析，桥不发 episode。

两条不可退让的性质：

- **兜底必须可发现**。命中规则 2 时在 stderr 打印一行信息级提示，说明该 workflow 未入 `map:`
  且使用了兜底卡。沉默兜底会把「映射漂移」变成新的假绿——这正是 SH-5 的病根。
- **兜底不得比直查更宽松**。兜底解析出的卡片若不存在，同样判为未解析，不得回退到任何硬编码路径。

## 3. 边界与非目标

- 不改 `workflow-scene-map.yaml` 的任何内容（`map:` 条目、`default:`、schema、version）。
  本 bet 修的是消费端与声明的不一致，不是补数据；给那 7 条补显式条目属于场景卡归属决策，
  留给 owner。
- 不改 `scene-outcome-recorder.py` 的 producer 语义（`omo-personal-episode` 是刻意的，见 SH-5.2）。
- 不新增 `bin/` 脚本：`bin/` 有净增配额闸门（`check-bin-quota-diff.py`），回归用例落在既有
  pytest 文件 `tests/test_scene_outcome_episode_bridge.py`。
- 不改 `governance-checks.yaml` registry 规则，不改 `.gitignore`。
- 不为历史 closeout 回填 episode。

## 4. 验证

解析逻辑以纯函数形式落地的理由：`_bridge_closeout_to_scene` 的 `workspace_root` 取模块常量
`WORKSPACE`，且要 `import omo.workflow`、要读 run 记录、要 spawn 子进程，任何端到端用例都会把
host 状态带进测试（hermetic 泄漏，AGENTS.md 已记一类事故）。纯函数只需构造 dict 即可覆盖三条规则。

- 规则 1：`workflow_id` 在 `map:` 中 → 返回该条目路径。
- 规则 2：`workflow_id` 不在 `map:` 且 `fallback_resolution: default` → 返回 `default:` 路径。
- 规则 3a：`workflow_id` 不在 `map:` 且无 `fallback_resolution` → 未解析。
- 规则 3b：`fallback_resolution: default` 但 `default:` 为空 → 未解析。
- 回归护栏：兜底命中必须与未解析可区分（前者带可发现提示，后者不带 episode），断言两者返回不同。
