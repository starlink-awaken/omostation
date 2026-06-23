---
status: archived
lifecycle: history
owner: governance-team
last-reviewed: 2026-06-23
archived-since: 2026-06-23
note: "P56 R2: 全量兜底批量归档, 当前活跃以各面 INDEX/SSOT/PANORAMA.md 为准"
---
# Task Prompt: T100 — Hermes集成TaskObject

> 类型: P8 Task | 预估: 5天 | 前置: T099 (self_inject就绪)
> Wave: 7.1 | Phase: 7

## 一、目标

Hermes在遇到复杂任务时自动创建TaskObject、拆解subtasks、按进度跟踪。

## 二、设计

### 判断逻辑 (`should_create_task`)

创建一个判断函数，接收用户输入，返回是否创建TaskObject：

```python
# ~/.hermes/plugins/task_plugin.py

COMPLEX_PATTERNS = [
    r"(先.+再.+然后)",       # "先调研再设计然后编码"
    r"(让|叫|找)\w+(来|做)",  # "让Claude Desktop来设计"
    r"(分解|拆分|分步骤)",    # "帮我分解这个任务"
    r"(审计|分析|评估).+(报告|文档)",  # "审计XX并输出报告"
    r"需要(.+和.+){2,}",     # "需要调研和设计和编码"
]

SIMPLE_PATTERNS = [
    r"(是什么|在哪里|谁)",
    r"(搜一下|查一下|找一下)",
    r"(翻译|解释|总结)",
    r"(打开|运行|执行)\w+$",
]

def should_create_task(user_input: str) -> bool:
    for pat in COMPLEX_PATTERNS:
        if re.search(pat, user_input):
            return True
    for pat in SIMPLE_PATTERNS:
        if re.search(pat, user_input):
            return False
    # LLM兜底判断
    return llm_judge_complexity(user_input) in ("L2", "L3")
```

### 拆解逻辑 (`decompose_to_task`)

```python
def decompose_to_task(user_input: str) -> dict:
    """用LLM分析用户输入，输出TaskObject结构"""
    prompt = f"""分析以下用户请求，拆分为TaskObject格式:
用户: {user_input}

输出JSON:
{{
  "title": "任务标题",
  "goal": "任务目标",
  "subtasks": [
    {{"id": "step-1", "title": "步骤1描述", "depends_on": []}},
    {{"id": "step-2", "title": "步骤2描述", "depends_on": ["step-1"]}}
  ]
}}
"""
    result = llm_call(prompt)
    return json.loads(result)
```

### 集成到Hermes流程

在Hermes的`handle_message`中增加：

```python
def handle_message(user_input: str):
    # 1. 判断是否要创建Task
    if should_create_task(user_input):
        task_data = decompose_to_task(user_input)
        task = mcp_call("collab.create_task", **task_data, creator_id="user:老王")
        task_id = task["task_id"]
        # 2. 自动认领第一个subtask
        for st in task_data["subtasks"]:
            mcp_call("collab.claim_subtask",
                task_id=task_id,
                subtask_id=st["id"],
                assignee="agent:hermes")
        # 3. 在回复中包含Task ID
        return f"我已将任务分解，可随时查看进度。Task ID: {task_id}\n子任务: {', '.join(s['title'] for s in task_data['subtasks'])}"
    
    # 原有逻辑
    return normal_handle(user_input)
```

## 三、执行步骤

### Step 1: 创建插件文件

```bash
touch ~/.hermes/plugins/task_plugin.py
```

写入上述代码。

### Step 2: 修改Hermes main loop

找到Hermes处理用户消息的入口函数，增加Task创建判断。

### Step 3: 单元测试

```bash
python3 -c "
from task_plugin import should_create_task

# 应该创建Task
assert should_create_task('先调研mac监控方案，再设计UI，最后编码实现')
assert should_create_task('让Claude Desktop来设计这个UI')
assert should_create_task('帮我分解这个架构审计任务')

# 不应该创建Task
assert not should_create_task('KOS地址是什么')
assert not should_create_task('搜一下mac监控方案')
assert not should_create_task('翻译这段话')

print('all tests passed')
"
```

### Step 4: 集成测试

```bash
# 验证TaskObject创建
hermes chat "审计Forge的代码质量" --debug 2>&1 | grep "Task ID:"
```

## 四、验收标准

```
☐ should_create_task 能区分简单/复杂任务
☐ 复杂任务自动创建TaskObject（含多个subtasks）
☐ 创建后第一个subtask自动被Hermes认领
☐ 回复中包含Task ID，可用collab.get_task查询
☐ 简单任务不创建TaskObject（0额外开销）
☐ 单元测试全部通过
```
