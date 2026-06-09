"""
SSOT Kernel — sync.py
=======================
YAML → Markdown 同步器。

解决双写一致性问题：YAML 版引擎数据和 Markdown 版知识本体
之间的双向同步。

用法:
    ssot-kernel sync --yaml-dir path/to/domains/guozhuan --md-dir path/to/domain
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

from .config_loader import load_domain
from .meta_model import Entity, Fact, Inference

# ── Markdown 条目解析 ─────────────────────────────────


def _parse_markdown_entities(text: str) -> set[str]:
    """从 Markdown 文本中提取已有实体 ID"""
    ids = set()
    for m in re.finditer(r"##\s+[✅📋⚠️]?\s*([\w-]+)", text):
        ids.add(m.group(1))
    return ids


def _parse_markdown_facts(text: str) -> set[str]:
    """从 Markdown 文本中提取已有事实 ID（DAT-/POL- 编号）"""
    ids = set()
    for m in re.finditer(r"(DAT-[\w-]+|POL-[\w-]+)", text):
        ids.add(m.group(1))
    return ids


def _parse_markdown_inferences(text: str) -> set[str]:
    """从 Markdown 文本中提取已有推论 ID"""
    ids = set()
    for m in re.finditer(r"(INF-[\w-]+)", text):
        ids.add(m.group(1))
    return ids


# ── 条目生成 ───────────────────────────────────────────


def _entity_to_md(e) -> str:
    """将 YAML 实体转换为 Markdown 条目"""
    icon = "✅" if e.status == "active" else "📋"
    lines = [f"## {icon} {e.id}（{e.name}）"]
    for k, v in e.attributes.items():
        lines.append(f"- **{k}**：{v}")
    if e.source:
        lines.append(f"- **来源**：{e.source}")
    # 如果 metadata 中有 policies/facts，加上标注行
    if e.metadata.get("facts") or e.metadata.get("policies"):
        refs = []
        if e.metadata.get("facts"):
            refs.extend(e.metadata["facts"])
        if e.metadata.get("policies"):
            refs.extend(e.metadata["policies"])
        lines.append(f"- **关联**：{', '.join(refs)}")
    lines.append("")
    return "\n".join(lines)


def _fact_to_md(f) -> str:
    """将 YAML 事实转换为 Markdown 条目"""
    if f.id.startswith("POL-"):
        lines = [f"- **{f.id}**：{f.title}"]
        if f.value:
            lines.append(f"  - 内容：{f.value}")
    else:
        lines = [f"- **{f.id}**：{f.title} = {f.value or ''} {f.unit or ''}"]
    if f.source:
        lines.append(f"  - 来源：{f.source}")
    if f.date:
        lines.append(f"  - 日期：{f.date}")
    if f.warnings:
        for w in f.warnings:
            lines.append(f"  - ⚠️ {w}")
    lines.append("")
    return "\n".join(lines)


def _inference_to_md(i) -> str:
    """将 YAML 推论转换为 Markdown 条目"""
    lines = [f"- **{i.id}**：{i.title}"]
    lines.append(f"  - 结论：{i.conclusion}")
    if i.logic:
        lines.append(f"  - 推导：{i.logic}")
    if i.derives_from:
        lines.append(f"  - 依赖：{', '.join(i.derives_from)}")
    if i.theory:
        lines.append(f"  - 理论：{i.theory}")
    lines.append("")
    return "\n".join(lines)


# ── 文件映射 ───────────────────────────────────────────

FILE_MAP = [
    (
        "entities",
        "entity",
        "01-实体本体/01-组织实体.md",
        lambda e: e.entity_type == "Organization",
        _entity_to_md,
    ),
    (
        "entities",
        "entity",
        "01-实体本体/02-角色实体.md",
        lambda e: e.entity_type == "Role",
        _entity_to_md,
    ),
    (
        "entities",
        "entity",
        "01-实体本体/03-项目实体.md",
        lambda e: e.entity_type == "Project",
        _entity_to_md,
    ),
    (
        "facts",
        "fact",
        "02-事实基座/01-政策事实.md",
        lambda f: f.id.startswith("POL-"),
        _fact_to_md,
    ),
    (
        "facts",
        "fact",
        "02-事实基座/02-数据事实.md",
        lambda f: f.id.startswith("DAT-"),
        _fact_to_md,
    ),
    ("inferences", "inference", "03-推论体系/01-矛盾诊断.md", None, _inference_to_md),
]


# ── 主同步逻辑 ────────────────────────────────────────


class SyncReport:
    """同步操作的差异报告"""

    def __init__(self):
        self.items_added: list[tuple[str, str]] = []  # (file, id)
        self.items_skipped: list[tuple[str, str]] = []  # (file, id)
        self.items_conflict: list[tuple[str, str, str]] = []  # (file, id, detail)
        self.errors: list[str] = []

    def print(self):
        print("\n## 同步报告")
        print(f"  新增: {len(self.items_added)}")
        print(f"  跳过: {len(self.items_skipped)}")
        print(f"  冲突: {len(self.items_conflict)}")
        print(f"  错误: {len(self.errors)}")

        if self.items_added:
            print("\n### 新增条目")
            for fname, eid in self.items_added:
                print(f"  ✅ {fname}: {eid}")

        if self.items_conflict:
            print("\n### 冲突")
            for fname, eid, detail in self.items_conflict:
                print(f"  ❌ {fname}: {eid} — {detail}")

        if self.errors:
            print("\n### 错误")
            for e in self.errors:
                print(f"  🔴 {e}")

    @property
    def has_changes(self) -> bool:
        return bool(self.items_added or self.items_conflict)


def sync_yaml_to_markdown(
    yaml_dir: str,
    md_dir: str,
    dry_run: bool = True,
) -> SyncReport:
    """执行 YAML → Markdown 同步。

    Args:
        yaml_dir: YAML 领域目录路径
        md_dir: Markdown 知识本体根目录路径
        dry_run: 仅输出差异，不实际写入

    Returns:
        SyncReport: 差异报告
    """
    report = SyncReport()
    md_root = Path(md_dir)

    if not md_root.exists():
        report.errors.append(f"Markdown 目录不存在: {md_dir}")
        return report

    # 1. 加载 YAML 数据
    try:
        config = load_domain(yaml_dir, use_cache=True)
    except Exception as e:
        report.errors.append(f"YAML 加载失败: {e}")
        return report

    # 2. 遍历文件映射
    for yaml_key, item_type, md_rel_path, filter_fn, to_md_fn in FILE_MAP:
        md_path = md_root / md_rel_path
        if not md_path.exists():
            report.errors.append(f"Markdown 文件不存在: {md_path}")
            continue

        # 读取已有 Markdown 内容
        md_text = md_path.read_text("utf-8")

        # 获取 YAML 数据源
        if yaml_key == "entities":
            items: list[Entity] | list[Fact] | list[Inference] = [
                e for e in config.entities if not filter_fn or filter_fn(e)
            ]
            parser = _parse_markdown_entities
        elif yaml_key == "facts":
            items = [f for f in config.facts if not filter_fn or filter_fn(f)]
            parser = _parse_markdown_facts
        elif yaml_key == "inferences":
            items = config.inferences
            parser = _parse_markdown_inferences
        else:
            continue

        existing_ids = parser(md_text)
        new_entries: list[str] = []

        for item in items:
            item_id = item.id
            if item_id in existing_ids:
                report.items_skipped.append((md_rel_path, item_id))
                continue

            # 新增条目
            entry = to_md_fn(item)
            new_entries.append(entry)
            report.items_added.append((md_rel_path, item_id))

        if not new_entries:
            continue

        # 追加到文件
        if not dry_run:
            sync_note = (
                f"\n<!-- 同步自 ssot-kernel {datetime.date.today().isoformat()} -->\n"
            )
            new_section = sync_note + "\n".join(new_entries)
            md_path.write_text(md_text.rstrip() + "\n" + new_section, encoding="utf-8")
        else:
            # dry-run 模式下展示预览
            print(f"\n📄 {md_rel_path} (+{len(new_entries)} 条)")
            for entry in new_entries[:3]:
                first_line = entry.split("\n")[0]
                print(f"  {first_line[:80]}")
            if len(new_entries) > 3:
                print(f"  ... 还有 {len(new_entries) - 3} 条")

    return report


# ── CLI 接口 ───────────────────────────────────────────


def add_subcommand(subparsers, common_parent):
    """向 argparse 注册 sync 子命令"""
    p = subparsers.add_parser(
        "sync",
        parents=[common_parent],
        help="同步 YAML 引擎数据到 Markdown 知识库",
    )
    p.add_argument(
        "--yaml-dir",
        required=True,
        help="YAML 领域目录（如 tool/ssot-kernel/domains/guozhuan）",
    )
    p.add_argument(
        "--md-dir", required=True, help="Markdown 知识本体根目录（如 domain/）"
    )
    p.add_argument(
        "--write", action="store_true", help="实际写入（默认 dry-run 仅预览）"
    )
    return p


def cmd_sync(args):
    """执行 YAML → Markdown 同步"""
    report = sync_yaml_to_markdown(
        yaml_dir=args.yaml_dir,
        md_dir=args.md_dir,
        dry_run=not args.write,
    )
    report.print()
    return 0 if not report.errors else 1
