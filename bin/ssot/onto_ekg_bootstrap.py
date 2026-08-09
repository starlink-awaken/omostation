#!/usr/bin/env python3
"""onto_ekg_bootstrap.py — OntoEKG 自举（LLM 知识工程 Wave 2 MVP）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 2:
从文档 + 治理规则提取候选概念 → 补 ontology 要素缺口。

MVP 采用规则式概念提取（确定性可测），LLM 增强层预留 aetherforge 接入点。

用法:
    python3 bin/ssot/onto_ekg_bootstrap.py --dry-run     # 扫描输出候选概念
    python3 bin/ssot/onto_ekg_bootstrap.py --emit        # 写出派生面报告
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DERIVED_OUT = ROOT / "projects" / "ecos" / ".omo" / "_derived" / "onto-bootstrap-candidates.yaml"
ONTOLOGY = ROOT / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "ontology.yaml"

DOC_GLOBS = ("docs/**/*.md", ".omo/_knowledge/**/*.md", ".omo/standards/**/*.md")
# 高频治理概念关键词（规则式提取的种子词典，从 16 抽象族映射推导）
SEED_CONCEPTS = (
    "layer-contract", "bos-uri", "mcp-tool", "agent-workflow", "governance-check",
    "derived-artifact", "frontmatter", "ssot-registry", "submodule-pointer",
    "debt-item", "adr", "service-registry", "runtime-projection", "approval-flow",
)


def extract_candidate_concepts(docs: list[dict]) -> list[dict]:
    """从文档内容提取候选概念：标题 h2 命中种子词 + frontmatter 上下文。

    返回 [{"name", "count", "source", "dimension", "surface"}]，按 count 降序去重。
    """
    counter: Counter = Counter()
    sources: dict[str, str] = {}
    metas: dict[str, dict] = {}
    for doc in docs:
        content = doc.get("content", "")
        path = doc.get("path", "")
        meta = {}
        fm = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if fm:
            for line in fm.group(1).splitlines():
                m = re.match(r"^(\w+):\s*(.+)$", line.strip())
                if m:
                    meta[m.group(1)] = m.group(2).strip()
        for concept in SEED_CONCEPTS:
            if concept.lower() in content.lower():
                counter[concept] += 1
                sources.setdefault(concept, path)
                metas.setdefault(concept, meta)
    concepts = []
    for name, count in counter.most_common():
        meta = metas.get(name, {})
        concepts.append({"name": name, "count": count, "source": sources.get(name, ""),
                         "dimension": meta.get("dimension", "?"),
                         "surface": meta.get("surface", "?")})
    return concepts


def build_bootstrap_report(concepts: list[dict]) -> str:
    """构建自举报告（Markdown 文本）。"""
    lines = ["# OntoEKG Bootstrap 候选概念", ""]
    for c in concepts:
        lines.append(f"- {c['name']} (×{c['count']}) — dim={c['dimension']} "
                     f"surface={c['surface']} src={c['source']}")
    lines.append("")
    lines.append(f"共 {len(concepts)} 个候选概念（规则式提取，LLM 增强待接入 aetherforge）")
    return "\n".join(lines)


def llm_enhance(concepts: list[dict], llm_fn=None) -> list[dict]:
    """LLM 增强层：对候选概念做语义分类/合并建议。

    llm_fn 可注入（如 aetherforge 调用）；缺省时返回原样（规则式基线）。
    增强输出追加字段: semantic_note（LLM 给出的分类或合并建议）。
    """
    if not llm_fn:
        return concepts
    enhanced = []
    for c in concepts:
        note = llm_fn(c)
        if isinstance(note, str) and note:
            c = dict(c)
            c["semantic_note"] = note
        enhanced.append(c)
    return enhanced


def scan_docs() -> list[dict]:
    """扫描 DOC_GLOBS 返回文档列表。"""
    docs = []
    for pattern in DOC_GLOBS:
        for p in ROOT.glob(pattern):
            if "node_modules" in str(p) or "generated" in str(p):
                continue
            try:
                docs.append({"path": str(p.relative_to(ROOT)),
                             "content": p.read_text(encoding="utf-8", errors="ignore")[:4000]})
            except OSError:
                continue
    return docs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="只打印候选概念")
    ap.add_argument("--emit", action="store_true", help="写出派生面报告")
    args = ap.parse_args()
    docs = scan_docs()
    concepts = extract_candidate_concepts(docs)
    if not concepts:
        print("[WARN] 未提取到候选概念（种子词典未命中）", file=sys.stderr)
        return 1
    if args.dry_run:
        print(build_bootstrap_report(concepts))
        return 0
    if args.emit:
        DERIVED_OUT.parent.mkdir(parents=True, exist_ok=True)
        DERIVED_OUT.write_text(yaml.safe_dump(concepts, allow_unicode=True, sort_keys=False))
        print(f"[OK] 候选概念已写出 → {DERIVED_OUT}（{len(concepts)} 个）")
        return 0
    print(build_bootstrap_report(concepts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
