# Task Prompt: Wave 5.4.B — 保鲜Cron + E2E验证

> 类型: P9 → P8 Task Prompt | 状态: backlog | 预估: 120min
> Phase: 5 → 5.4.B | 负责人: prometheus | 日期: Day 6-8
> 前置: Wave 5.4.A (Consensus Domain) 已完成

## 一、目标

创建保鲜Cron脚本 + 在Agora验证所有13个新工具 + 端到端验证+归档文档。

## 二、文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `~/.hermes/scripts/freshness_check.sh` | 新建 | 保鲜Cron—扫描过期实体+L1自动续签 |
| `.hermes/cron` | 注册 | 每周一早8点Cron Job |
| `phase5_e2e_test.py` | 新建 | E2E全链路测试 |
| `~/.kos/self/profile.json` | 验证 | L4数据完整性 |
| `.omo/INVENTORY.md` | 更新 | 新增项目/模块状态 |
| `.omo/TASK_POOL.md` | 更新 | T080-T083 → done |
| `.omo/STATE.md` | 更新 | Phase 5进度100% |

## 三、验收标准

```
☐ freshness_check.sh 可运行, 无异常时静默
☐ Agora验证: agora tool list | grep -E "self|collab|consensus" 显示13个工具
☐ python3 phase5_e2e_test.py → ALL PASSED
☐ .omo/TASK_POOL.md Phase5全部done
☐ .omo/STATE.md Phase5进度 100%
```

## 四、E2E测试脚本核心逻辑

```python
def test_l4_self():
    r = mcp_call("self.get_profile")
    assert r["person"] == "老王"
    r = mcp_call("self.get_current_role")
    assert "role_id" in r

def test_l3_collab():
    r = mcp_call("collab.create_task", title="E2E测试", goal="验证", creator_id="user:E2E")
    task_id = r["id"]
    r = mcp_call("collab.claim_subtask", task_id=task_id, subtask_id="auto-test-1", agent_id="agent:e2e")
    assert r["status"] == "claimed"
    r = mcp_call("collab.get_task", task_id=task_id)
    assert r["status"] == "active"

def test_x3_consensus():
    r = mcp_call("consensus.create", entity_id="e2e:test",
                 agreed_by=["user:老王", "agent:e2e"], agreement="E2E验证通过")
    assert r["status"] == "active"

print("Phase5 E2E: ALL PASSED")
```

## 五、→ 下一个阶段

完成后进入 **Phase 6 (验证·复盘·迭代·纠偏)**。
