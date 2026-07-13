#!/usr/bin/env python3
"""A1 · BOS 声明/执行鸿沟静态审计.

对每条 BOS 服务声明，判定其 `uv run ... python -m <module>` 目标模块
是否能在对应项目的 venv site-packages 或 src 树中被解析。
纯文件系统检查，不 spawn 子进程。输出 CSV + 分类汇总。
"""
from __future__ import annotations
import csv
import glob
import os
import re
import sys

WS = "/sessions/inspiring-determined-edison/mnt/Workspace"


def load_services():
    """从 agora fallback 定义直接 import POC_SERVICES 结构 (纯解析, 不执行 resolve)."""
    # 直接解析 services.py 的 BosService 声明 (避免依赖 agora 环境)
    src = open(os.path.join(WS, "projects/agora/src/agora/mcp/resolver/services.py")).read()
    # 也尝试 YAML (真实运行时优先 YAML)
    yaml_path = os.path.join(WS, "projects/agora/etc/bos-services.yaml")
    services = []
    if os.path.exists(yaml_path):
        try:
            import yaml
            docs = list(yaml.safe_load_all(open(yaml_path)))
            for d in docs:
                if not isinstance(d, dict):
                    continue
                svc = d.get("services") or d.get("bos_services") or []
                if isinstance(svc, list) and svc:
                    for s in svc:
                        if isinstance(s, dict):
                            services.append(s)
        except Exception as e:
            print(f"[warn] YAML parse failed: {e}", file=sys.stderr)
    return services, src


def parse_fallback(src):
    """从 services.py 正则抽取每个 BosService 块的关键字段."""
    out = []
    for m in re.finditer(r"BosService\((.*?)\n    \),", src, re.S):
        blk = m.group(1)
        def g(field):
            mm = re.search(rf'{field}="([^"]*)"', blk)
            return mm.group(1) if mm else ""
        uri = g("uri")
        if not uri:
            continue
        transport = g("transport")
        package = g("package")
        desc = g("description")
        module_path = g("module_path")  # internal only
        # command list
        cmd = re.findall(r'"([^"]+)"', blk[blk.find("command="):]) if "command=" in blk else []
        out.append(dict(uri=uri, transport=transport, package=package,
                        description=desc, module_path=module_path, command=cmd))
    return out


def resolve_dir(cmd):
    for i, tok in enumerate(cmd):
        if tok == "--directory" and i + 1 < len(cmd):
            return cmd[i + 1]
        if tok == "--package" and i + 1 < len(cmd):
            return ("pkg", cmd[i + 1])
    return None


def module_target(cmd):
    for i, tok in enumerate(cmd):
        if tok == "-m" and i + 1 < len(cmd):
            return cmd[i + 1]
    # e.g. "python projects/family-hub/mcp_server.py"
    for tok in cmd:
        if tok.endswith(".py"):
            return tok
    return None


def top_module(mod):
    return mod.split(".")[0] if mod else ""


def find_module(project_dir, mod):
    """在项目 venv site-packages 或 src 树里找 top module 是否存在."""
    if not mod:
        return False, "no-module-target"
    if mod.endswith(".py"):
        p = os.path.join(WS, mod)
        return os.path.exists(p), ("file-found" if os.path.exists(p) else "file-missing")
    top = top_module(mod)
    # 目标文件路径 (module_path -> path)
    modpath = mod.replace(".", "/")
    roots = []
    if isinstance(project_dir, tuple):  # --package
        # 搜索所有 projects 下匹配 package 的 src
        roots += glob.glob(os.path.join(WS, "projects", "*", "src"))
        roots += glob.glob(os.path.join(WS, "projects", "*", "packages", "*", "src"))
        venvs = glob.glob(os.path.join(WS, "projects", "*", ".venv", "lib", "python*", "site-packages"))
        roots += venvs
    else:
        proj = os.path.join(WS, project_dir)
        # venv site-packages
        roots += glob.glob(os.path.join(proj, ".venv", "lib", "python*", "site-packages"))
        # src trees (kairon 有 packages/*/src)
        roots += glob.glob(os.path.join(proj, "src"))
        roots += glob.glob(os.path.join(proj, "packages", "*", "src"))
    # 判定: top module 目录/文件存在, 且具体 module 文件(若给全路径)存在
    top_found = False
    exact_found = False
    for r in roots:
        if os.path.isdir(os.path.join(r, top)) or os.path.exists(os.path.join(r, top + ".py")):
            top_found = True
        # exact: kos/cli.py or kos/cli/__init__.py
        exact = os.path.join(r, modpath)
        if os.path.exists(exact + ".py") or os.path.isdir(exact):
            exact_found = True
    if exact_found:
        return True, "module-resolved"
    if top_found:
        return False, "submodule-missing(top-ok)"
    return False, "top-module-missing"


def main():
    yaml_svc, src = load_services()
    fb = parse_fallback(src)
    # 用 fallback (硬编码) 作为审计源 — 与 resolver 一致的可执行声明
    services = fb
    source = "services.py fallback"
    print(f"[info] audit source: {source}, N={len(services)}", file=sys.stderr)

    rows = []
    counts = {}
    for s in services:
        cmd = s["command"]
        uri = s["uri"]
        transport = s["transport"]
        desc = s["description"]
        if transport == "internal":
            # internal: module_path 在 agora src
            mp = s.get("module_path", "")
            ok, reason = find_module("projects/agora", mp) if mp else (True, "internal-inproc")
            verdict = "OK" if ok else "FAIL"
            root = "internal"
        elif desc.startswith("[UNIMPLEMENTED]"):
            verdict = "UNIMPLEMENTED"
            reason = "declared-unimplemented"
            root = "unimplemented"
        else:
            pdir = resolve_dir(cmd)
            mod = module_target(cmd)
            ok, reason = find_module(pdir, mod)
            verdict = "OK" if ok else "FAIL"
            root = reason
        counts[verdict] = counts.get(verdict, 0) + 1
        rows.append(dict(uri=uri, transport=transport, verdict=verdict,
                         reason=reason, package=s["package"]))

    out_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bos_resolve_audit.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["uri", "transport", "verdict", "reason", "package"])
        w.writeheader()
        w.writerows(rows)

    total = len(rows)
    ok = counts.get("OK", 0)
    unimpl = counts.get("UNIMPLEMENTED", 0)
    fail = counts.get("FAIL", 0)
    print("=" * 60)
    print(f"BOS 声明/执行鸿沟审计 (静态可解析性)")
    print("=" * 60)
    print(f"总声明数:        {total}")
    print(f"  OK (可解析):    {ok}  ({100*ok//total if total else 0}%)")
    print(f"  UNIMPLEMENTED:  {unimpl}  (声明即标注未实现)")
    print(f"  FAIL (断层):    {fail}")
    print()
    # 失败根因分布
    fail_reasons = {}
    for r in rows:
        if r["verdict"] == "FAIL":
            fail_reasons[r["reason"]] = fail_reasons.get(r["reason"], 0) + 1
    if fail_reasons:
        print("FAIL 根因分布:")
        for k, v in sorted(fail_reasons.items(), key=lambda x: -x[1]):
            print(f"  {v:3d}  {k}")
    print()
    print("按 transport:")
    tcount = {}
    for r in rows:
        key = (r["transport"], r["verdict"])
        tcount[key] = tcount.get(key, 0) + 1
    for (t, v), c in sorted(tcount.items()):
        print(f"  {t:12s} {v:14s} {c}")
    print()
    print(f"CSV: {out_csv}")
    # 打印 FAIL 明细
    print("\nFAIL 明细:")
    for r in rows:
        if r["verdict"] == "FAIL":
            print(f"  [{r['transport']:10s}] {r['uri']:52s} {r['reason']}")


if __name__ == "__main__":
    main()
