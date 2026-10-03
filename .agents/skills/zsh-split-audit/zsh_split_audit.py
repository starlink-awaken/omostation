#!/usr/bin/env python3
"""zsh_split_audit.py — 事后审计会话转写: Agent 是否违反 zsh 分词纪律。

背景
----
zsh 对**参数展开不做 word splitting**（只有**命令替换**会）⇒
    VAR="a b c"; for x in $VAR     # 只迭代 1 次, $x 是整串 "a b c"
危险之处: **不报错**、输出看着还正常。最致命的形态是「批量删除前的逐项安全检查」
塌缩 —— 四列全有值、格式完全正常, 却在描述一个**不存在的路径** ⇒
据此会得出「都干净、可删」并真去删(安全检查的塌缩 = 安全网本身失效)。

这条纪律只发生在 Agent **临时写的一次性 Bash 命令**里(不进仓、不过 hook)
⇒ 事前无法拦截; 但每条命令都落在会话转写里 ⇒ **事后可审计**。本脚本即该审计器。

用法
----
    zsh_split_audit.py [transcript.jsonl ...] [--projects-dir DIR] [--json]

不带路径时, 自动取「当前工作目录对应的 codebuddy 项目目录」下最新的 *.jsonl。

退出码
------
    0  审计完成(命中数见输出)
    3  **假零警报** —— 一条命令都没扫到, 说明结构/键名变了, 本次结果无效
       (没有这个断言的话, 「扫错键名 ⇒ 0 命中 ⇒ 看着完全合规」无法察觉)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sys

# `for <var> in $<VAR>` —— 注意 $( ) 与 ${=VAR} 天然不匹配, 无需额外排除。
SCAN = re.compile(r"\bfor\s+(\w+)\s+in\s+\$\{?(\w+)\}?(?=[\s;|&)\]])")
# 同命令内存在 `VAR=(` ⇒ 数组形式(zsh 安全)。
ARRAY_ASSIGN = r"\b{}\s*=\s*\("
# 同命令内存在 `VAR=` ⇒ 该变量在本命令内确有赋值(否则不是本模式)。
SCALAR_ASSIGN = r"\b{}\s*="
# heredoc 写入 .sh ⇒ 产物由 bash 执行, `for x in $VAR` 在 bash 下是对的 ⇒ 免责。
BASH_DESTINED = re.compile(r"(cat\s*>\s*[^\s]+\.sh|>\s*[^\s]+\.sh\s*<<|<<\s*'?(BASH|SH|SHELL)\b)")
SELF_TEST = ("expect=5 got=", "四种写法实测", "zsh_split_audit")

CATEGORY_ORDER = ("真候选", "bash-destined(免)", "python 内嵌 bash(免)", "self-test(免)")


def collect_commands(obj, out: set) -> None:
    """递归收集命令字符串。

    ⚠️ 命令**不在**顶层 `"command"` 键: 真实路径是
       .providerData.arguments  —— 一个**二次编码的 JSON 字符串** {"command": "…"}
       .providerData.argumentsDisplayText —— 同内容的展示副本
    只找 '"command"' 会得到**假零**。用 set 去重, 避免上述两份副本重复计数。
    """
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "command" and isinstance(val, str):
                out.add(val)
            elif key == "arguments" and isinstance(val, str):
                try:
                    collect_commands(json.loads(val), out)
                except Exception:
                    out.add(val)
            elif key == "argumentsDisplayText" and isinstance(val, str):
                out.add(val)
            else:
                collect_commands(val, out)
    elif isinstance(obj, list):
        for val in obj:
            collect_commands(val, out)


def classify(cmd: str) -> str:
    if BASH_DESTINED.search(cmd):
        return "bash-destined(免)"
    if "PYEOF" in cmd or "<<'PY" in cmd:
        return "python 内嵌 bash(免)"
    if any(tok in cmd for tok in SELF_TEST):
        return "self-test(免)"
    return "真候选"


def scan_file(path: pathlib.Path) -> tuple[int, dict[tuple, str]]:
    """返回 (扫描到的命令串总数, {(md5, 变量名): 命令} 去重命中)。"""
    total = 0
    hits: dict[tuple, str] = {}
    with path.open("r", errors="replace") as fh:
        for line in fh:
            if "for " not in line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            cmds: set = set()
            collect_commands(obj, cmds)
            for cmd in cmds:
                total += 1
                # 归一化**字面** `\n`(转义换行) ⇒ 真换行。否则形如 `…\nfor s in $VAR`
                # 的片段里, `for` 前面是 `n`(词字符) ⇒ `\bfor` 失配 ⇒ **漏报**。
                # (2026-10-03 自证时发现: python 内嵌 bash 片段常以转义换行形式存储)
                scan_text = cmd.replace("\\n", "\n")
                for _loop_var, var in SCAN.findall(scan_text):
                    if re.search(ARRAY_ASSIGN.format(re.escape(var)), scan_text):
                        continue  # 数组 ⇒ 安全
                    if not re.search(SCALAR_ASSIGN.format(re.escape(var)), scan_text):
                        continue  # 本命令内无该变量赋值 ⇒ 不是本模式
                    digest = hashlib.md5(cmd.encode()).hexdigest()[:10]
                    hits.setdefault((digest, var), cmd)
    return total, hits


def _slug(path: pathlib.Path) -> str:
    return str(path).strip("/").replace("/", "-")


def _newest(files) -> pathlib.Path | None:
    cands = [p for p in files if p.is_file() and p.stat().st_size > 4096]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def default_transcript(projects_dir: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """探测转写。返回 (路径, 说明)。

    注意: 项目目录是按**workspace 根**路径 slug 的(不是 cwd) ⇒
    在 worktree(`~/ws-<session>`)里跑时, cwd 的 slug 不存在。故按「cwd 逐级祖先
    找匹配的项目目录」→「全部项目目录里取最新」两级回退。
    (2026-10-03 实测: 只按 cwd 一级会直接报「未找到转写」)
    """
    cwd = pathlib.Path.cwd()
    for anc in (cwd, *cwd.parents):
        d = projects_dir / _slug(anc)
        if d.is_dir():
            hit = _newest(d.glob("*.jsonl"))
            if hit:
                return hit, f"cwd 祖先匹配 ({anc})"
    hit = _newest(projects_dir.glob("*/*.jsonl"))
    if hit:
        return hit, "回退: 全部项目目录里最新 (未能按 cwd 定位)"
    return None, "未找到"


def main() -> int:
    ap = argparse.ArgumentParser(description="审计会话转写中的 zsh 分词违规")
    ap.add_argument("transcripts", nargs="*", help="转写 .jsonl 路径(缺省=自动探测)")
    ap.add_argument("--projects-dir", default=str(pathlib.Path.home() / ".codebuddy" / "projects"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    paths = [pathlib.Path(p) for p in args.transcripts]
    if not paths:
        auto, how = default_transcript(pathlib.Path(args.projects_dir))
        if auto is None:
            print("❌ 未找到转写; 请显式传路径, 或用 --projects-dir 指定", file=sys.stderr)
            return 2
        print(f"ℹ️  自动探测: {how} ⇒ {auto.name}", file=sys.stderr)
        paths = [auto]

    grand_total = 0
    all_hits: dict[tuple, str] = {}
    for path in paths:
        if not path.is_file():
            print(f"❌ 不是文件: {path}", file=sys.stderr)
            return 2
        total, hits = scan_file(path)
        grand_total += total
        all_hits.update(hits)

    buckets: dict[str, list[tuple[str, str]]] = {}
    for (_digest, var), cmd in all_hits.items():
        buckets.setdefault(classify(cmd), []).append((var, cmd.strip().replace("\n", " ")[:110]))

    if args.json:
        print(json.dumps({
            "transcripts": [str(p) for p in paths],
            "commands_scanned": grand_total,
            "unique_suspects": len(all_hits),
            "buckets": {k: [{"var": v, "cmd": c} for v, c in vs] for k, vs in buckets.items()},
            "false_zero": grand_total == 0,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"转写: {', '.join(str(p) for p in paths)}")
        print(f"扫描到命令/参数串: {grand_total}")
        print(f"去重后唯一「可疑命令×变量」组合: {len(all_hits)}")
        for cat in CATEGORY_ORDER:
            items = buckets.get(cat, [])
            print(f"\n── {cat}: {len(items)} ──")
            for var, snippet in items[:15]:
                print(f"   ${var}  ::  {snippet}")

    if grand_total == 0:
        print("\n❌ 假零警报: 一条命令都没扫到 —— 检查器可能扫错了键名/结构, 本次结果无效", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
