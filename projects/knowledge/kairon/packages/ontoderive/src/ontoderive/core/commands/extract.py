"""命令: extract — 从文本/URL提取事实"""

from pathlib import Path

from ontoderive.reasoners.formalize import Formalizer


def cmd_extract(source: str, to_path: str = "facts/data.md", project: str = ".") -> None:
    """从文本/URL提取事实"""
    fz = Formalizer()
    kb = fz.extract_from_text(source)
    md = fz.to_markdown(kb)
    output = Path(project) / to_path if project != "." else Path(to_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(md)
    print(f"[extract] ✅ {len(kb.facts)}事实/{len(kb.entities)}实体 → {output}")
