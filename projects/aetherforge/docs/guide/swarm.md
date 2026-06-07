# 多 Agent 协作 (Swarm)

Swarm 提供了多 Agent 协作的三种模式。

## GroupChat (对话式)

多个 Agent 轮流发言，适合头脑风暴：

```python
from swarm_engine.group_chat import GroupChat, GroupChatAgent

chat = GroupChat(agents=[
    GroupChatAgent(name="研究员", system_prompt="你擅长收集信息"),
    GroupChatAgent(name="写作者", system_prompt="你擅长撰写内容"),
], max_turns=4)

result = chat.run("写一篇关于 AI 的短文")
for msg in result.history:
    print(f"[{msg.sender}]: {msg.content[:100]}")
```

## HierarchicalProcess (层级式)

Manager 分解任务 → Worker 执行 → Manager 汇总：

```python
from swarm_engine.hierarchical_process import HierarchicalProcess

hp = HierarchicalProcess()
result = hp.run("分析竞争对手产品", worker_roles=["researcher", "analyst"])
print(result.final_output)
```

## GraphWorkflow (图工作流)

有向无环图，支持条件分支：

```python
from swarm_engine.graph_workflow import GraphWorkflow

wf = GraphWorkflow()

@wf.node("analyze")
def analyze(state):
    return {"result": f"分析: {state['input']}"}

@wf.node("output")
def output(state):
    return {"final": f"输出: {state['result']}"}

wf.add_edge("analyze", "output")
wf.set_entry("analyze")
state = wf.run({"input": "数据"})
```
