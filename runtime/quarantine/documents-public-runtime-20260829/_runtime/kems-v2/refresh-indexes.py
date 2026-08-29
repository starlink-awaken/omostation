#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KEMS 机器索引统一刷新脚本
用途：
  1. 为业务资料各子目录批量生成/刷新 JSON 索引（KEMS 迭代机制·每半年）。
  2. --gaps-count / --facts-count：KEMS 计数断言（缺口/事实条数唯一真源）。
     ——治理机制 v1.0 执行纪律 6「数字由机器生成」：派生文档引用计数必须来自本命令输出，禁止手抄。
运行：
  python3 _runtime/refresh-indexes.py [--dry-run]
  python3 _runtime/refresh-indexes.py --gaps-count
  python3 _runtime/refresh-indexes.py --facts-count
  python3 _runtime/refresh-indexes.py --file-count
"""
import os, sys, json, datetime

ROOT = "_knowledge/业务资料"
DATE = datetime.date.today().strftime("%Y-%m-%d")

# 索引目标：子目录 → 索引文件名前缀
INDEX_TARGETS = [
    ("01-业务核心/信息化项目/01-项目全生命周期/S1-立项申报", "项目申报索引"),
    ("01-业务核心/信息化项目/01-项目全生命周期/S8-项目审计", "项目审计索引"),
    ("01-业务核心/信息化项目/02-专项工作/工作督导", "工作督导索引"),
    ("01-业务核心/信息化项目/03-支撑资料/数据上报", "数据上报索引"),
    ("01-业务核心/网络安全", "网络安全文件索引"),
    ("01-业务核心/评价考核", "评价考核索引"),
    ("01-业务核心/政策与规划", "政策与规划索引"),
    ("01-业务核心/卫生统计", "卫生统计索引"),
    ("00-体系制度/制度规范", "制度规范索引"),
    ("00-体系制度/软件正版化", "软件正版化索引"),
]

GAPS_SSOT = "_entities/ontology/gaps.yaml"
FACTS_SSOT = "_entities/facts.md"


def gaps_count():
    """缺口计数断言：解析 gaps.yaml，输出三态计数（resolved/in_progress/open）。
    派生文档（KEMS治理机制/宏观战略/DASHBOARD）中的缺口数字必须引用本输出。"""
    try:
        import yaml
        data = yaml.safe_load(open(GAPS_SSOT, encoding="utf-8"))
    except ImportError:
        print("[WARN] PyYAML 不可用，跳过 gaps 计数断言（pip install pyyaml）")
        return 1
    gaps = data["gaps"]
    ids = [g["id"] for g in gaps]
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup:
        print(f"[FAIL] gaps.yaml 存在重复缺口 id: {dup}")
        return 1
    n_resolved = sum(1 for g in gaps if g.get("status") == "resolved")
    n_progress = sum(1 for g in gaps if g.get("status") == "in_progress")
    n_open = sum(1 for g in gaps if g.get("status") == "open")
    derived = sum(1 for g in gaps if g.get("derived_from"))
    print(f"[OK] 缺口计数断言（SSOT: {GAPS_SSOT}）："
          f"resolved {n_resolved} / in_progress {n_progress} / open {n_open} / 合计 {len(gaps)}")
    print(f"[OK] 缺口衍生关系：{derived} 项标注 derived_from（存量清零带出的新知识边界）")
    print(f"引用格式：resolved={n_resolved}, in_progress={n_progress}, open={n_open}")
    return 0


def facts_count():
    """事实计数断言：解析 facts.md 表格行，输出事实条数（格式自适应：≥4 列即算，
    兼容卫健委 9 列与国转中心 5 列；排除表头/模板/段分隔/可信度图例行）。"""
    LEGEND = {"事实陈述", "可信度", "confirmed", "single_source", "rumor", "类型", "📄信息"}
    n = 0
    for ln in open(FACTS_SSOT, encoding="utf-8"):
        if not ln.startswith("| "):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        c0 = cells[0] if cells else ""
        if len(cells) >= 4 and c0 and c0 not in LEGEND \
                and not c0.startswith("==") \
                and "[可验证" not in c0 and "YYYY-MM-DD" not in c0:
            n += 1
    print(f"[OK] 事实计数断言（SSOT: {FACTS_SSOT}）：{n} 条")
    return 0


def file_count():
    """业务资料各子目录文件计数（排除 . 开头的隐藏文件）。
    域模型/业务资料模型中的文件数是快照，刷新以本命令输出为准。"""
    def count_files(path):
        return sum(1 for _, _, fns in os.walk(path) for fn in fns if not fn.startswith("."))

    # 顶层二级子目录（模型 §二 对应层级）
    subdirs = []
    for dp, dns, _ in os.walk(ROOT):
        for d in dns:
            if d.startswith("."):
                continue
            rel = os.path.relpath(os.path.join(dp, d), ROOT)
            if rel.count(os.sep) == 1:  # 二级子目录（如 00-体系制度/制度规范）
                subdirs.append(rel)
    subdirs = sorted(set(subdirs))

    total = count_files(ROOT)
    print(f"[OK] 业务资料文件计数（SSOT 扫描，二级子目录 {len(subdirs)} 个，全库合计 {total}）：")
    for rel in sorted(subdirs, key=lambda x: -count_files(os.path.join(ROOT, x))):
        print(f"  {count_files(os.path.join(ROOT, rel)):5d}  {rel}")
    return 0


def build_index(base, name):
    """扫描 base 下全部文件，生成 JSON 索引"""
    entries = []
    for dp, dn, fns in os.walk(base):
        for fn in fns:
            if fn.startswith("."): continue
            fp = os.path.join(dp, fn)
            rel = os.path.relpath(fp, base)
            entries.append({
                "文件": rel,
                "大小KB": round(os.path.getsize(fp) / 1024, 1),
            })
    entries.sort(key=lambda x: x["文件"])
    return entries

def main():
    if "--gaps-count" in sys.argv:
        return gaps_count()
    if "--facts-count" in sys.argv:
        return facts_count()
    if "--file-count" in sys.argv:
        return file_count()
    dry = "--dry-run" in sys.argv
    generated = []
    for rel, name in INDEX_TARGETS:
        base = os.path.join(ROOT, rel)
        if not os.path.isdir(base):
            print(f"[SKIP] 目录不存在: {rel}")
            continue
        entries = build_index(base, name)
        out = os.path.join(base, f"{DATE}-{name}.json")
        if dry:
            print(f"[DRY] {rel}: {len(entries)} 条 → {os.path.basename(out)}")
        else:
            json.dump(entries, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[OK] {rel}: {len(entries)} 条")
        generated.append((rel, name, len(entries)))
    print(f"\n{'DRY-RUN ' if dry else ''}索引刷新完成: {len(generated)} 个子目录")
    return 0

if __name__ == "__main__":
    sys.exit(main())
