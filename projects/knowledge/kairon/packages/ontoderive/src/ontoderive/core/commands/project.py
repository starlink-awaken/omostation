"""命令: init — 初始化新项目"""

from pathlib import Path
from typing import Any

from ontoderive.foundation.templates import TEMPLATES


def cmd_init(project_name: str, template: str = "default") -> None:
    """初始化 OntoDerive 项目目录结构"""
    tmpl: Any = TEMPLATES.get(template, TEMPLATES["default"])

    root = Path(project_name)

    for d in ["facts", "entities", "inferences", "protocols", "scheme", "_logs"]:
        (root / d).mkdir(parents=True, exist_ok=True)

    # 事实
    facts_lines = "| 编号 | 数据 | 数值 | 来源 |\n|------|------|------|------|\n"
    for fid, desc, val, src in tmpl["facts"]:
        facts_lines += f"| {fid} | {desc} | {val} | {src} |\n"
    (root / "facts" / "data.md").write_text(facts_lines)

    # 政策
    policy_lines = "| 编号 | 政策 | 发布主体 | 日期 |\n|------|------|---------|------|\n"
    for pid, desc, subj, date in tmpl["policy"]:
        policy_lines += f"| {pid} | {desc} | {subj} | {date} |\n"
    (root / "facts" / "policy.md").write_text(policy_lines)

    # 实体
    entity_lines = "| 实体 | 类型 | 角色 |\n|------|------|------|\n"
    for eid, etype, role in tmpl["entities"]:
        entity_lines += f"| {eid} | {etype} | {role} |\n"
    (root / "entities" / "actors.md").write_text(entity_lines)

    # 推论
    inf_lines = ""
    for inf in tmpl["inferences"]:
        df = ", ".join(inf["derives_from"])
        inf_lines += f"## {inf['id']}：{inf['title']}\n\n{inf['content']}\n\n- derives_from: [{df}]\n\n"
    (root / "inferences" / "analysis.md").write_text(inf_lines.strip())

    # 方案
    (root / "scheme" / "report.md").write_text(tmpl["scheme"])

    (root / "README.md").write_text(
        f"# {project_name}\n\n> OntoDerive v3.6.1\n\n"
        "```bash\nontoderive derive --project .\n"
        "ontoderive check --project .\n```\n"
    )
    print(f"项目 {project_name} 已初始化 (模板: {template})")
