#!/usr/bin/env python3
"""
概念孤岛编织 — concept-weave（2026-10-09 按 MAINTENANCE-概念孤岛编织.md 规格重建）
================================================================================
原工具丢失后依据运维手册重建。四子命令 + report，全部幂等（段名判重）：

  detect      扫描零入链概念（[[标题]] + @path 入链统计），列出孤儿清单（只读）
  mesh        同域全互链（双向 clique 刷新）——零误链风险
  bridge      应用人工策展的 bridge-map.json，跨域桥接（先编辑 map 再跑）
  exec-bridge 应用 exec-bridge-map.json，30-execution 笔记 ↔ 概念双向并网
  report      汇总连通率（概念总数 / 已连通 / 孤儿 / 连通率%）

段名约定（幂等判重依据，勿改）：
  ## 同域相关概念（编织回流）        同域每个概念
  ## 相关概念（回流编织）            孤岛概念 → 中枢 hub
  ## 关联孤岛概念（回流编织）        中枢 hub → 孤岛
  ## 相关概念（KEMS 知识网络）       30-execution 笔记 → 概念（@path）
  ## 实操延伸（来自 30-execution）   概念 → 30-execution 笔记（@path）
"""

import json
import os
import re
import sys
from pathlib import Path

# 2026-10-10 自 _control/scripts/ 迁入 Workspace（L4-CONTENT-008：实现代码归 Workspace，
# Documents 只存声明）。vault 路径显式锚定，支持 VAULT_ROOT 环境变量覆盖。
VAULT = Path(os.environ.get("VAULT_ROOT", Path.home() / "Documents" / "@学习进化"))
CONCEPTS = VAULT / "_knowledge" / "50-concepts"
EXECUTION = VAULT / "_knowledge" / "30-execution"
SCRIPTS = VAULT / "_control" / "scripts"
BRIDGE_MAP = SCRIPTS / "bridge-map.json"
EXEC_BRIDGE_MAP = SCRIPTS / "exec-bridge-map.json"

SEC_MESH = "## 同域相关概念（编织回流）"
SEC_BRIDGE_ORPHAN = "## 相关概念（回流编织）"
SEC_BRIDGE_HUB = "## 关联孤岛概念（回流编织）"
SEC_EXEC_NOTE = "## 相关概念（KEMS 知识网络）"
SEC_EXEC_CONCEPT = "## 实操延伸（来自 30-execution）"


# ── 概念发现 ────────────────────────────────────────────────────────────

def _fm_title(text: str, fallback: str) -> str:
    m = re.search(r"^title:\s*(.+)$", text[:2000], re.M)
    if not m:
        return fallback
    return m.group(1).strip().strip("'\"")


def load_concepts() -> list[dict]:
    """发现 50-concepts 下全部概念。域 = 一级子目录名；根散落文件域为 ''（单文件域，不 mesh）。"""
    out = []
    for f in sorted(CONCEPTS.rglob("*.md")):
        rel = f.relative_to(CONCEPTS)
        domain = rel.parts[0] if len(rel.parts) > 1 else ""
        text = f.read_text()
        out.append({
            "path": f,
            "rel": f"_knowledge/50-concepts/{rel}",
            "domain": domain,
            "title": _fm_title(text, f.stem),
            "text": text,
        })
    return out


def load_vault_texts() -> list[tuple[Path, str]]:
    """全 vault md 文本（供入链统计），跳过隐藏目录。"""
    out = []
    for f in sorted(VAULT.rglob("*.md")):
        if any(p.startswith(".") for p in f.relative_to(VAULT).parts):
            continue
        if not f.is_file():
            continue  # 非常规条目（名为 .md 的目录等，kems scan 已标记为 L4-CONTENT 违规）
        try:
            out.append((f, f.read_text()))
        except (UnicodeDecodeError, OSError):
            continue
    return out


# ── 入链统计 ────────────────────────────────────────────────────────────

def inbound_counts(concepts: list[dict], texts: list[tuple[Path, str]]) -> dict[str, int]:
    """每概念入链数：[[标题]]（含 [[标题|别名]]）或 @vault 相对路径（按文件名匹配）。"""
    counts = dict.fromkeys((c["title"] for c in concepts), 0)
    path_pattern = re.compile(r"@" + re.escape(str(VAULT)) + r"/_knowledge/50-concepts/(\S+?\.md)")
    for p, text in texts:
        # vault 约定：[[标题]] 或 [[文件名|标题]]（别名形式，Obsidian 按文件名解析）
        links = {(t, a) for t, a in re.findall(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]", text)}
        path_refs = set(path_pattern.findall(text))
        for c in concepts:
            if c["path"] == p:
                continue
            stem = c["path"].stem
            hit_link = any(t == c["title"] or t == stem or a == c["title"] for t, a in links)
            if hit_link or c["rel"].endswith(tuple(path_refs)) or c["path"].name in path_refs:
                counts[c["title"]] += 1
    return counts


def orphans(concepts: list[dict], counts: dict[str, int]) -> list[dict]:
    return [c for c in concepts if counts[c["title"]] == 0]


# ── 写操作（幂等：段名判重）─────────────────────────────────────────────

def append_section(path: Path, text: str, section: str, bullets: list[str]) -> bool:
    """段已存在则跳过；否则在文末追加段 + bullet（bullet 级判重跳过已有行）。"""
    if f"\n{section}\n" in text or text.lstrip().startswith(section):
        return False
    body = text.rstrip("\n") + "\n"
    new_bullets = [b for b in bullets if b not in text]
    if not new_bullets:
        return False
    body += f"\n{section}\n\n" + "\n".join(f"- {b}" for b in new_bullets) + "\n"
    path.write_text(body)
    return True


def cmd_mesh(concepts: list[dict]) -> int:
    """同域全互链（双向 clique 刷新）：段已存在则整体重写为当前全互链集合；
    单文件散落域跳过（交给 bridge）。刷新语义见运行记录 2026-07-07。"""
    changed = 0
    domains: dict[str, list[dict]] = {}
    for c in concepts:
        domains.setdefault(c["domain"], []).append(c)
    for domain, members in sorted(domains.items()):
        if not domain or len(members) < 2:
            continue
        for c in members:
            bullets = [f"- [[{m['title']}]]" for m in members if m is not c]
            text = c["path"].read_text()
            block = f"{SEC_MESH}\n\n" + "\n".join(bullets) + "\n"
            marker = f"\n{SEC_MESH}\n"
            if marker in text:
                head, rest = text.split(marker, 1)
                nxt = rest.find("\n## ")
                old_bullets = {l for l in (rest if nxt == -1 else rest[:nxt]).splitlines() if l.startswith("- ")}
                tail = "" if nxt == -1 else rest[nxt:]  # 以 "\n## " 开头，保持原有空行结构
                if old_bullets != set(bullets):
                    new_text = head + marker + "\n" + "\n".join(bullets) + "\n" + tail
                    c["path"].write_text(new_text.rstrip("\n") + "\n")
                    changed += 1
                    print(f"  🔄 mesh 刷新 {domain}/{c['path'].name} (={len(bullets)})")
            else:
                c["path"].write_text(text.rstrip("\n") + f"\n\n{block}")
                changed += 1
                print(f"  🔗 mesh {domain}/{c['path'].name} (+{len(bullets)})")
    print(f"mesh 完成：{changed} 个文件更新")
    return 0


def cmd_bridge(concepts: list[dict]) -> int:
    """应用人工策展 bridge-map.json：孤儿 → hub 双向补链。"""
    if not BRIDGE_MAP.exists():
        print(f"❌ 缺少 {BRIDGE_MAP}")
        return 2
    mapping = json.loads(BRIDGE_MAP.read_text())
    by_title = {c["title"]: c for c in concepts}
    changed = 0
    for orphan_title, hubs in mapping.items():
        orphan = by_title.get(orphan_title)
        if orphan is None:
            print(f"  ⚠️ 孤儿标题不存在: {orphan_title}")
            continue
        valid_hubs = [h for h in hubs if h in by_title]
        for h in hubs:
            if h not in by_title:
                print(f"  ⚠️ hub 标题不存在: {h}")
        orphan_bullets = [f"[[{h}]]" for h in valid_hubs]
        if append_section(orphan["path"], orphan["path"].read_text(), SEC_BRIDGE_ORPHAN, orphan_bullets):
            changed += 1
            print(f"  🌉 bridge 孤儿 {orphan_title} → {len(valid_hubs)} hub")
        for h in valid_hubs:
            # vault 约定：回链用 [[文件名|标题]] 别名形式（Obsidian 按文件名可解析）
            hub = by_title[h]
            link = f"[[{orphan['path'].stem}|{orphan_title}]]" if orphan["path"].stem != orphan_title else f"[[{orphan_title}]]"
            if append_section(hub["path"], hub["path"].read_text(), SEC_BRIDGE_HUB, [link]):
                changed += 1
    print(f"bridge 完成：{changed} 个文件更新")
    return 0


def cmd_exec_bridge(concepts: list[dict]) -> int:
    """应用 exec-bridge-map.json：30-execution 笔记 ↔ 概念双向并网（bullet 级判重）。"""
    if not EXEC_BRIDGE_MAP.exists():
        print(f"❌ 缺少 {EXEC_BRIDGE_MAP}")
        return 2
    mapping = json.loads(EXEC_BRIDGE_MAP.read_text())
    # map 值约定：相对 50-concepts/ 的路径（如 认知科学/元认知.md 或 根散落文件.md）
    by_rel = {str(c["path"].relative_to(CONCEPTS)): c for c in concepts}
    changed = 0
    for note, concept_rels in mapping.items():
        note_path = EXECUTION / note
        if not note_path.exists():
            print(f"  ⚠️ 笔记不存在: {note}")
            continue
        note_bullets = [f"@{VAULT}/_knowledge/50-concepts/{r}" for r in concept_rels if r in by_rel]
        for r in concept_rels:
            if r not in by_rel:
                print(f"  ⚠️ 概念路径不存在: {r}")
        if append_section(note_path, note_path.read_text(), SEC_EXEC_NOTE, note_bullets):
            changed += 1
        for r in concept_rels:
            c = by_rel.get(r)
            if c is None:
                continue
            back = f"@{VAULT}/_knowledge/30-execution/{note}"
            if append_section(c["path"], c["path"].read_text(), SEC_EXEC_CONCEPT, [back]):
                changed += 1
    print(f"exec-bridge 完成：{changed} 个文件更新")
    return 0


# ── 只读命令 ────────────────────────────────────────────────────────────

def cmd_report(concepts: list[dict]) -> int:
    counts = inbound_counts(concepts, load_vault_texts())
    linked = sum(1 for c in concepts if counts[c["title"]] > 0)
    total = len(concepts)
    rate = (linked / total * 100) if total else 0.0
    print(f"概念总数: {total}")
    print(f"已连通: {linked}")
    print(f"孤儿: {total - linked}")
    print(f"连通率: {rate:.1f}%")
    return 0


def cmd_detect(concepts: list[dict]) -> int:
    counts = inbound_counts(concepts, load_vault_texts())
    op = orphans(concepts, counts)
    print(f"孤儿清单（{len(op)} 个）：")
    for c in op:
        loc = c["domain"] or "（根散落）"
        print(f"  - {c['title']}  [{loc}]")
    return 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    concepts = load_concepts()
    if cmd == "detect":
        return cmd_detect(concepts)
    if cmd == "mesh":
        return cmd_mesh(concepts)
    if cmd == "bridge":
        return cmd_bridge(concepts)
    if cmd == "exec-bridge":
        return cmd_exec_bridge(concepts)
    if cmd == "report":
        return cmd_report(concepts)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
