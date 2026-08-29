#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""模型一致性核验 — 25 个知识模型 × KEMS 元模型（metamodel.yaml）CF 规则
对齐 OMG MOF：M1 模型必须遵循 M2 元模型契约。
用法：
  python3 _runtime/check-model-conformance.py            # 全量核验
  python3 _runtime/check-model-conformance.py --strict   # WARN 也计失败
退出码：0 = 无 FAIL；1 = 有 FAIL
"""
import os, re, sys, datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
MODELS_DIR = BASE / "_entities" / "models"
TODAY = datetime.date(2026, 8, 5)
STRICT = "--strict" in sys.argv

REQUIRED = ["title", "status", "owner", "created"]  # review-date 单独判（last-reviewed 或 date）
FRESHNESS = 90

def infer_model_type(fname):
    """按文件名语义推断 model_type（现行 type 字段过粗，见元模型 taxonomy）"""
    if "域模型" in fname: return "domain"
    if "数据字典" in fname or "底座" in fname or "目录" in fname or "台账" in fname or "政务云" in fname: return "data"
    if "决策视图" in fname: return "view"
    if "宏观" in fname and "战略" in fname: return "strategy"
    if "治理机制" in fname: return "governance"
    if "知识全量抽象" in fname or "本体模型" in fname: return "ontology"
    if "影响评估" in fname or "接入率" in fname: return "analysis"
    return "model"

def parse_fm(text):
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m: return {}
    fm = {}
    for k, v in re.findall(r"^([\w-]+):\s*(.*)$", m.group(1), re.M):
        fm[k] = v.strip().strip('"')
    return fm

fails, warns = [], []
rows = []
models = sorted(f for f in os.listdir(MODELS_DIR) if f.endswith(".md") and f != "README.md")

for m in models:
    text = (MODELS_DIR / m).read_text(encoding="utf-8")
    fm = parse_fm(text)
    mtype = infer_model_type(m)
    issues = []

    # CF-1 必填
    miss = [k for k in REQUIRED if k not in fm or not fm[k]]
    rdate = fm.get("last-reviewed") or fm.get("date") or ""
    if "last-reviewed" not in fm and "date" not in fm:
        miss.append("review-date(last-reviewed|date)")
    if miss:
        issues.append(f"CF-1 缺字段:{'/'.join(miss)}")

    # CF-2 类型
    issues.append(f"type={fm.get('type','?')}→{mtype}")

    # CF-3 状态
    if fm.get("status") not in ("active", "archived", "draft", ""):
        issues.append(f"CF-3 status={fm['status']} 非法")

    # CF-4 新鲜度
    if rdate:
        try:
            days = (TODAY - datetime.date.fromisoformat(rdate[:10])).days
            if days > FRESHNESS:
                issues.append(f"CF-4 过期{days}天")
        except ValueError:
            issues.append(f"CF-4 日期格式异常:{rdate}")
    else:
        issues.append("CF-4 无审查日期")

    # CF-5 data-sources 存在性
    for src in re.findall(r"^  - (.+)$", fm.get("data-sources", ""), re.M):
        p = src.split("（")[0].strip().rstrip("/")
        if not (BASE / "_entities" / "models" / p).exists() and not (BASE / p).exists() and not (BASE / "_entities" / p).exists():
            issues.append(f"CF-5 数据源不存在:{p}")

    is_fail = any(x.startswith(("CF-1", "CF-3", "CF-4")) for x in issues if not x.startswith("CF-4 无审查日期") and "CF-2" not in x[:4])
    no_rdate = "CF-4 无审查日期" in issues
    has_cf1 = any(x.startswith("CF-1") for x in issues)
    rows.append((m, mtype, fm.get("status", ""), rdate[:10] if rdate else "无", issues, has_cf1 or no_rdate))

print(f"{'模型':<40}{'类型':<10}{'状态':<8}{'审查':<12}一致性")
print("-" * 90)
n_fail = 0
for m, mt, st, rd, issues, bad in rows:
    # 判定：CF-1/CF-3/CF-4(有日期但过期) 为 FAIL；CF-4无日期 为 WARN(新约定用date但缺last-reviewed)；其余 WARN
    cf1 = any(x.startswith("CF-1") for x in issues)
    cf3 = any(x.startswith("CF-3") for x in issues)
    cf4_over = any(x.startswith("CF-4 过期") or x.startswith("CF-4 日期") for x in issues)
    no_rd = "CF-4 无审查日期" in issues
    status_mark = "❌" if (cf1 or cf3 or cf4_over) else ("⚠️" if (no_rd or cf1) else "✅")
    if cf1 or cf3 or cf4_over:
        n_fail += 1
    print(f"{status_mark} {m:<38}{mt:<10}{st:<8}{rd:<12}{';'.join(issues[:3])}")
print("-" * 90)
print(f"模型总数 {len(models)} | FAIL {n_fail} | WARN {len(rows)-n_fail-sum(1 for _,_,_,_,_,b in rows if not b)}")
# 简单汇总
warns_n = sum(1 for _,_,_,_,i,b in rows if b and not any(x.startswith(('CF-1','CF-3')) for x in i) and not any(x.startswith('CF-4 过期') or x.startswith('CF-4 日期') for x in i))
print(f"WARN（缺审查日期/数据源）: {warns_n}")
return_code = 1 if n_fail else 0
if STRICT:
    return_code = 1 if (n_fail or warns_n) else 0
sys.exit(return_code)
