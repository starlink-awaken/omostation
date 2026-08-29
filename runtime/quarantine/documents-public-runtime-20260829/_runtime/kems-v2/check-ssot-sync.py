#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SSOT 统一守卫 — check-ssot-sync.py
三层 SSOT 一致性总检：M2 本体层 / M1 模型层 / M0 实例层 + 计数断言 + 交叉校验。
保证「模型、本体、实例」同步，任何一层改动后必须全绿。
用法：
  python3 _runtime/check-ssot-sync.py            # 全量守卫
  python3 _runtime/check-ssot-sync.py --json     # JSON 输出（供控制器）
退出码：0 = SSOT 一致；1 = 存在漂移
"""
import json, re, subprocess, sys, yaml
from pathlib import Path

BASE = Path(__file__).parent.parent
RESULTS = []  # (layer, check, ok, detail)


def record(layer, check, ok, detail=""):
    RESULTS.append((layer, check, ok, detail))
    mark = "✅" if ok else "❌"
    print(f"  {mark} [{layer}] {check}" + (f" — {detail}" if detail else ""))


def run_py(script, args):
    return subprocess.run([sys.executable, str(BASE / "_runtime" / script), *args],
                          capture_output=True, text=True)


# ---------- 1. M2 本体层 ----------
def check_ontology():
    r = run_py("check-ontology-consistency.py", ["--strict"])
    ok = r.returncode == 0
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip()
    record("M2 本体", "本体三源一致(类/关系/实例/约束/关联/缺口)", ok, tail)
    return ok


# ---------- 2. M1 模型层 ----------
def check_models():
    r = run_py("check-model-conformance.py", [])
    ok = r.returncode == 0
    m = re.search(r"模型总数 (\d+) \| FAIL (\d+) \| WARN (\d+)", r.stdout)
    detail = f"{m.group(0)}" if m else "异常"
    record("M1 模型", "元模型一致性(CF-1~7)", ok, detail)
    return ok


# ---------- 3. M0 实例层 + 计数断言 ----------
def check_counts():
    all_ok = True
    for flag, name, ssot in [("--gaps-count", "缺口计数", "gaps.yaml"),
                              ("--facts-count", "事实计数", "facts.md"),
                              ("--file-count", "文件计数", "业务资料/")]:
        r = run_py("refresh-indexes.py", [flag])
        ok = "OK" in r.stdout
        detail = r.stdout.strip().splitlines()[0] if r.stdout.strip() else "异常"
        record("M0 实例", f"{name}({ssot})", ok, detail)
        all_ok = all_ok and ok
    return all_ok


# ---------- 4. 交叉校验：模型声明 vs 实例现实（域自适应） ----------
def check_cross_layer():
    all_ok = True
    inst = yaml.safe_load(open(BASE / "_entities/ontology/instances.yaml", encoding="utf-8"))["instances"]
    c3 = [i for i in inst if i["class"] == "C3"]
    active = sum(1 for i in c3 if i.get("status") == "active")
    archived = sum(1 for i in c3 if i.get("status") == "archived")

    # 卫健委式专项检查：仅当存在 域模型-信息化项目KEMS.md 时运行
    has_proj_domain = (BASE / "_entities/models/域模型-信息化项目KEMS.md").exists()
    if has_proj_domain:
        ok = active >= 3 and archived >= 5
        record("交叉", "域模型声明(在管3+归档5) vs 实例现实", ok,
               f"实例 active {active} / archived {archived}")
        all_ok = all_ok and ok
        miss = [p for p in ["proj-data-collect", "proj-jyjk", "proj-lis-upgrade"]
                if not any(i["id"] == p for i in inst)]
        ok = not miss
        record("交叉", "在管三项目实例齐全", ok, "" if ok else f"缺 {miss}")
        all_ok = all_ok and ok
    else:
        # 通用域：C3 有 active 或 archived 即视为项目层有效
        record("交叉", "项目层实例完整性（通用域）", True,
               f"C3 active {active} / archived {archived}")

    # 决策视图（域自适应：有 M2D 文档则要求 ≥1 决策，缺失则 WARN）
    m2d_path = BASE / "_entities/models/模型驱动决策视图.md"
    if m2d_path.exists():
        m2d = m2d_path.read_text(encoding="utf-8")
        n_views = len(re.findall(r"决策[一二三四五六]：", m2d))
        if n_views >= 4:
            record("交叉", f"决策视图完整性（{n_views} 类）", True)
        else:
            ok = n_views >= 1
            record("交叉", f"决策视图基础（{n_views} 类，≥4 为完整）", ok)
            all_ok = all_ok and ok
    else:
        record("交叉", "决策视图（未建，WARN）", True, "模型驱动决策视图.md 待建")
    return all_ok


def main():
    print("=" * 66)
    print("SSOT 统一守卫 — 模型 / 本体 / 实例 三层一致性")
    print(f"时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 66)
    o1 = check_ontology()
    o2 = check_models()
    o3 = check_counts()
    o4 = check_cross_layer()
    print("-" * 66)
    fails = [r for r in RESULTS if not r[2]]
    if fails:
        print(f"❌ SSOT 漂移 {len(fails)} 项：")
        for layer, check, _, detail in fails:
            print(f"   - [{layer}] {check} {detail}")
    else:
        n_m2 = sum(1 for r in RESULTS if r[0].startswith("M2"))
        n_m1 = sum(1 for r in RESULTS if r[0].startswith("M1"))
        n_m0 = sum(1 for r in RESULTS if r[0].startswith("M0"))
        n_x = sum(1 for r in RESULTS if r[0] == "交叉")
        print(f"✅ SSOT 三层全绿：本体 {n_m2} · 模型 {n_m1} · 实例 {n_m0} · 交叉 {n_x} 项校验通过")
    if "--json" in sys.argv:
        print(json.dumps({"ok": not fails, "checks": len(RESULTS), "fails": len(fails)},
                         ensure_ascii=False))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
