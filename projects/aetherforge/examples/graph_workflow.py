"""Example 5: 图工作流 — 函数节点 + LLM 节点 + 条件分支。"""

from swarm_engine.graph_workflow import GraphWorkflow

# 1. 创建工作流
wf = GraphWorkflow()

# 2. 定义工作流节点
@wf.node("分析需求", description="分析用户需求的关键要素")
def analyze(state):
    text = state.get("input", "")
    return {"requirements": f"需求: {text[:50]}...", "complexity": len(text) / 100}

@wf.node("简单方案", description="为简单需求生成方案")
def simple_solution(state):
    return {"solution": f"快速方案: 基于 {state['requirements']}"}

@wf.node("复杂方案", description="为复杂需求生成详细方案")
def complex_solution(state):
    return {"solution": f"详细方案: 基于 {state['requirements']}，需要多步骤处理"}

@wf.node("输出报告", description="格式化最终输出")
def output(state):
    return {"output": f"## 最终方案\n\n{state['solution']}\n\n复杂度: {state['complexity']:.1f}"}

# 3. 连接节点
wf.add_edge("分析需求", "简单方案",
    condition=lambda s: "简单方案" if s.get("complexity", 0) < 1 else None)
wf.add_edge("分析需求", "复杂方案",
    condition=lambda s: "复杂方案" if s.get("complexity", 0) >= 1 else None)
wf.add_edge("简单方案", "输出报告")
wf.add_edge("复杂方案", "输出报告")

# 4. 执行工作流
for input_text in ["写一首诗", "分析这个 500 页的文档并提取关键信息、生成摘要、翻译成三种语言"]:
    wf.set_entry("分析需求")
    state = wf.run({"input": input_text})
    print(f"\n📝 输入: {input_text[:40]}...")
    print(f"   复杂度: {state.get('complexity', 0):.1f}")
    print(f"   {state.get('output', '')}")
