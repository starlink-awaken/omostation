"""Example 4: 多 Agent GroupChat 对话式协作。"""

from swarm_engine.group_chat import GroupChat, GroupChatAgent

# 1. 定义 Agent
agents = [
    GroupChatAgent(
        name="研究员",
        system_prompt="你是一名研究员，擅长收集和分析信息。回答简洁。",
        role="researcher",
    ),
    GroupChatAgent(
        name="写作者",
        system_prompt="你是一名技术写作者，擅长把复杂概念讲清楚。回答简洁。",
        role="writer",
    ),
]

# 2. 启动 GroupChat
chat = GroupChat(agents=agents, max_turns=4)
result = chat.run("告诉我 AI Agent 是什么，用通俗的语言")

# 3. 输出对话历史
print(f"💬 GroupChat 完成 ({result.total_turns} 轮)")
print("=" * 50)
for msg in result.history:
    role_tag = f"[{msg.agent_role}]" if msg.agent_role else ""
    print(f"\n  {msg.sender} {role_tag} (第 {msg.turn} 轮):")
    print(f"  {msg.content[:200]}")
print("\n" + "=" * 50)
