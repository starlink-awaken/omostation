"""命令: formal — 形式化推理(Phase1-4管线)"""

from ontoderive.core.derive import OntoDerive


def cmd_formal(text: str = "", project: str = ".") -> None:
    """形式化推理(Phase1-4管线)"""
    od = OntoDerive(project)
    result = od.derive_formal(text=text)
    print(result.get("report", "推理完成")[:3000])
