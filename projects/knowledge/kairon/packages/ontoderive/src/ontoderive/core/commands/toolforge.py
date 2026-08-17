"""命令: toolforge — 思维工具匹配"""

import json

from ontoderive.toolforge import ToolForge


def cmd_toolforge(
    goal: str,
    context: str = "",
    inference_guide: bool = False,
    json_output: bool = False,
) -> None:
    """思维工具匹配"""
    tf = ToolForge()
    if inference_guide:
        print(tf.to_inference_guide(goal, context))
    elif json_output:
        print(
            json.dumps(
                tf.select(goal, context, 5),
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        tf.report(goal, context)
