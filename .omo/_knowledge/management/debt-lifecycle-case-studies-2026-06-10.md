---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-22
archived-since: 2026-06-22
note: "P45 审计: 历史决策/phase closeout, 标记 archived"
---

# §16 §15 流程实践案例集 — 债循环自然扩 (Round 36 起步)

> **状态**: 起步 (Round 36 P0)
> **作者**: 老王
> **定位**: §15 5 阶段流程 (发现/登记/治理/验收/归档) 的**实战案例集**
> **目的**: 把"债循环"自然扩, 每发现新债 → 5 阶段走一遍 → 归档案例
> **链接**: §15 (流程) + §11.6 (债列表) + §13 (omo_lint 工具) + §16 (案例)

---

## §16.0 一句话总结

§16 是 §15 5 阶段流程的**实战案例库**——每发现新债, 5 阶段走一遍, 归到 §16 子节"案例 N". 当前**案例 1 (R34-R35 sort_keys_default)** 已 100% 闭合, 案例 2+ 留 §16.5+.

## §16.1 §15 5 阶段流程回顾

```
[发现]  →  [登记]  →  [治理]  →  [验收]  →  [归档]
守门告警  §11.6 段标   治本/治标   测试+lint+baseline  §16 案例 N
```

详见 §15.1.

## §16.2 案例 1: R34-R35 sort_keys_default 完整循环

### §16.2.1 发现 (R34 P0)

**触发**: omo_lint 加新规则 7 (`sort-keys-default`) 实施时, 跑 7 consumer 触发 4 处违规.

**输出**:
```
❌ sort_keys default (§12.1.4): 4 处 .append() 未传 sort_keys=True
   - omo_bos_metrics.py [missing-sort-keys]
   - omo_sync.py [missing-sort-keys]
   - omo_sync.py [missing-sort-keys]
   - omo_trail.py [missing-sort-keys]
```

### §16.2.2 登记 (R34 P1 文档)

**动作**: 在 `append-only-log-pattern-2026-06-09.md` §11.6 段加新债:
```markdown
- [ ] **P3-X** 🆕 Round 34 P0 重开: sort_keys_default (§12.1.4 跨仓 4 不变量) — 4 处 .append() 待治 (omo_bos_metrics/sync×2/trail)
```

§15.1 流程: 债编号 `P3-X` (X = 第 N 项重开债, §11.6 已有 P0-1/0-2/1-1/1-2/1-3/1-4/P2/P3, P3-X 是首次重开).

### §16.2.3 治理 (R35 P0 治本)

**动作**: 修 4 处 .append() 调用都加 `sort_keys=True`:
- `omo_bos_metrics.py:78` — `schema=OmoBosMetricsRecord, sort_keys=True`
- `omo_sync.py:73-84` (ok record) — `sort_keys=True,` 关键字
- `omo_sync.py:98-106` (error record) — `sort_keys=True,` 关键字
- `omo_trail.py:91` — `schema=OmoTrailRecord, sort_keys=True`

### §16.2.4 验收 (R35 P0 lint 验证)

**输出**:
```
✅ sort_keys default (§12.1.4): 7/7 consumer 字节级兼容
✅ omo lint schemas pass: 7/7 + 4 完整性 + SRP + 0 dead code + sort_keys 守
```

§15.1 流程: 测试+lint+baseline 三重守门, sort_keys 7/7 PASS, X2 baseline 不退化.

### §16.2.5 归档 (R35 P1 文档)

**动作**: 在 `append-only-log-pattern-2026-06-09.md` §11.6 段标 done:
```markdown
- [x] **P3-X** ✅ Round 35 P0: sort_keys_default 治本 — 4 处 .append() 加 sort_keys=True, §12.1.4 跨仓 4 不变量 100% 守
```

**案例 1 时间线总结**:
- R34 P0: 发现 (4 处违规) + 登记 (§11.6 P3-X)
- R34 P1: 文档收口
- R35 P0: 治理 (修 4 处)
- R35 P1: 验收 (lint 7/7) + 归档 (本段)

**总耗时**: 2 Round (R34 + R35) = 2 commit + 4 文件.

**§15 治理史新增** (R12-R32 11 项 + R34-R35 1 项 = 12 项):
| Round | 债编号 | 动作 | commit |
|-------|--------|------|--------|
| ... | (前 11 项见 §15.2) | ... | ... |
| R34 | P3-X 重开 | 发现+登记 | `9c7ed6f4` `f78002f2` |
| R35 | P3-X 治本 | 治理+验收+归档 | `4f200152` `7558b8a1` |

## §16.3 案例 2: 扩规则 7 检测覆盖临时变量 (§15 流程下一债)

**债编号 (待登记)**: `P3-Y` 🆕

**动机**: R34 实施规则 7 时, 规则只检测"AppendOnlyLog(...).append(...)" immediate chain 模式. 但 consumer 多用临时变量模式 `log = AppendOnlyLog(...); log.append(...)` —— R34 漏了 omo_audit/omo_alert/omo_event 等真违规.

**探查 (R36 起步)**:
```bash
$ rg "log\s*=\s*AppendOnlyLog" projects/omo/src/omo/*.py
omo_audit.py:84-85:  log = AppendOnlyLog(path)  # 临时变量
omo_alert.py:50-?:   log = AppendOnlyLog(path)  # 临时变量
omo_event.py:?:      log = AppendOnlyLog(path)  # 临时变量
# 这些 log.append() 都没传 sort_keys=True
```

**实施** (R36+ 治本, 留待 §16.3 实质化):
- 改 `_check_sort_keys_default()` 函数
- 扫模块所有 `Name` 节点, 找 `log = AppendOnlyLog(...)` 赋值
- 找 `log.append(...)` 调用 (log 是临时变量)
- 检查 kwargs 缺 `sort_keys=True` → 违规

**预期违规数** (R34 探查): 3 处 (omo_audit/alert/event 各 1).

### §16.4 案例 3+: §13.3 候选规则 8 (sort-keys-default) 收尾 + 新规则

**待办** (留 §16.4+ 实质化):
- 实施规则 8 扩检测 (案例 2 实质化)
- §13.3 候选规则 9-12 (新规则探索, 例如跨仓 import 边界 / sort_keys 默认值 / 等)
- §12.8 候选 4 实质化 (跨仓债 E1-E4 落地, 需各仓 owner 配合)

## §16.5 §15 vs §16 vs §11.6 关系

| 维度 | §15 (流程) | §16 (案例) | §11.6 (债列表) |
|------|-----------|-----------|-----------------|
| 范围 | 5 阶段流程 (抽象) | 实战案例 (具体) | 当前债状态 (todo/done) |
| 形式 | 5 阶段 + 治理史 | 案例 N (时间线) | 列表 + commit hash |
| 价值 | 让"债管理"有节奏可循 | 让"债循环"可复用 | 让"债现状"可查询 |
| 关系 | 流程 (怎么管) | 案例 (管过哪些) | 列表 (当前哪些) |

## §16.6 Round 36+ 候选

- [x] §16.0 起步 (本 commit)
- [x] §16.1 §15 5 阶段流程回顾
- [x] §16.2 案例 1: R34-R35 sort_keys_default 完整循环
- [x] §16.3 案例 2: 扩规则 7 检测覆盖临时变量 (R36 起步)
- [x] §16.4 案例 3+: §13.3 候选规则 8 收尾 + 新规则
- [x] §16.5 §15 vs §16 vs §11.6 关系
- [x] §16.6 Round 36+ 候选
- [ ] §16.7+ 实施案例 2 (R36 起步)

---

**§16 章节总览** (Round 36 起步):

| 子节 | 主题 | 状态 |
|------|------|------|
| §16.0 | 一句话总结 | ✅ Round 36 |
| §16.1 | §15 5 阶段流程回顾 | ✅ Round 36 |
| §16.2 | 案例 1: R34-R35 sort_keys_default 完整循环 | ✅ Round 36 |
| §16.3 | 案例 2: 扩规则 7 检测覆盖临时变量 | ✅ Round 36 (设计稿) |
| §16.4 | 案例 3+: §13.3 候选规则 8 收尾 + 新规则 | ✅ Round 36 |
| §16.5 | §15 vs §16 vs §11.6 关系 | ✅ Round 36 |
| §16.6 | Round 36+ 候选 | ✅ Round 36 |
| **总** | **§16 7 子节** | ✅ 起步 |
