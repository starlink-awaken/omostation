"""Agora enforce CLI — 查看/设置/清除强制授权范围 (R5).

集成: agora enforce list/set/clear
"""

import sys


def cmd_enforce(args):
    """Enforce 子命令分发：list / set / clear。"""
    from agora.auth.authorizer import ENFORCE_TOOLS, is_enforced, set_enforce_tools  # type: ignore[import-not-found]

    if args.enforce_cmd == "list":
        current = ENFORCE_TOOLS
        if not current:
            print("Enforce: disabled (all pass-through)")
        else:
            print(f"Enforce tools: {current}")
        # 显示当前通过率
        print(f"  Sample: collab.create_task → {'ENFORCED' if is_enforced('collab.create_task') else 'PASS-THROUGH'}")
        print(f"  Sample: minerva.research → {'ENFORCED' if is_enforced('minerva.research') else 'PASS-THROUGH'}")
    elif args.enforce_cmd == "set":
        tools = sys.argv[3:] if len(sys.argv) > 3 else [getattr(args, "tool", "")]
        # Filter out empty strings from parsing
        tools = [t for t in tools if t]
        set_enforce_tools(tools)
        print(f"Enforce set to: {tools}")
    elif args.enforce_cmd == "clear":
        set_enforce_tools([])
        print("Enforce cleared (all pass-through)")
