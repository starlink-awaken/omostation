---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: Wave 6.3 — 迭代修正

> 类型: P9 → P8 Task Prompt | 状态: ready | 预估: 30min
> Phase: 6 → 6.3 | 前置: Phase 5 实现已完成 + 复盘门禁通过

## Task T093: Subtask API int→string ID 兼容

### 问题
`kos/collab/api.py` 的 `claim_subtask()` 使用整数下标(`subtask_index: int`)而非字符串ID。与Eidos Schema的 `task-object.schema.json` 中 subtasks[].id 设计不一致。

### 修正要求

在 `kos/collab/api.py` 中给 `claim_subtask()` 增加 `subtask_id: str | None = None` 可选参数:

```python
def claim_subtask(task_id: str, subtask_index: int = 0, subtask_id: str | None = None, assignee: str = "") -> dict[str, Any]:
    """认领子任务。支持整数下标(subtask_index)或字符串ID(subtask_id)。"""
```

实现逻辑:
- 如果传了 `subtask_id`，遍历 subtasks 列表按 `st.get("id")` 匹配
- 找到匹配项后用其下标继续原有逻辑
- 如果 `subtask_id` 未匹配任何项 → 返回 `{"error": "...", "code": "SUBTASK_NOT_FOUND"}`
- 原有 `subtask_index` 行为不变（向后兼容）

### 验证
```bash
cd ~/Workspace/kos && .venv/bin/python3 -c "
from kos.collab.api import create_task, claim_subtask
t = create_task('修正测试','验证string id','user:老王', subtasks=[
    {'id':'step-1','title':'Step1','status':'pending'}
])
tid = t['task_id']
# 用string id
r = claim_subtask(tid, subtask_id='step-1', assignee='agent:test')
assert r.get('status') == 'claimed', f'Failed: {r}'
# 不存在的id
r = claim_subtask(tid, subtask_id='nonexist', assignee='agent:test')
assert r.get('code') == 'SUBTASK_NOT_FOUND', f'Should fail: {r}'
print('T093: PASSED')
"
```

## Task T094: Consensus API 签名统一

### 问题
`kos/consensus/api.py` 的 `create_consensus()` 参数顺序与Eidos Schema设计不一致。

### 修正要求

调整函数签名，确保参数顺序与Eidos Schema对齐:

```python
def create_consensus(
    entity_id: str,
    agreed_by: list[str],
    agreement: str,
    source_session: str = "",
    level: int = 1,       # 自动判断: 含user:→L2, 否则L1
) -> dict[str, Any]:
```

实现逻辑:
- `level` 默认为1
- 如果 `agreed_by` 中有 `user:` 前缀且 `level < 2` → 自动升为2
- 如果传了 `level=3` 则保持3

### 验证
```bash
cd ~/Workspace/kos && .venv/bin/python3 -c "
from kos.consensus.api import create_consensus, get_consensus
# Agent单方 → L1
c1 = create_consensus('test:e1', ['agent:hermes'], '自动验证')
assert c1['level'] == 1, f'Expected L1, got L{c1[\"level\"]}'
# 含用户 → L2
c2 = create_consensus('test:e1', ['user:老王','agent:hermes'], '用户确认')
assert c2['level'] == 2, f'Expected L2, got L{c2[\"level\"]}'
# 查询
g = get_consensus('test:e1')
assert g['count'] >= 2
print('T094: PASSED')
"
```

## 完成后

更新 `.omo/TASK_POOL.md` → T093-T094 → done
