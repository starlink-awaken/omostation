#!/usr/bin/env python3
"""timeout-audit: 审计治理脚本中的无界网络调用 (repo-wide timeout audit)。

治本: #3934 给 claim fetch / submodule init / post-checkout 加了有界超时,
      #3937 给 agent-clone 的 git/uv 调用加了超时 — 但没有全仓审计,
      新增脚本仍可引入无界 `git fetch / ls-remote / clone / submodule update`
      或无超时的 `curl / wget`, CI 高峰时 hung 住整个 gate。
本 gate 把"无界网络调用"收敛到标准有界习语, 先 advisory (warn-only)。

扫描范围 (默认 / --all):
  - bin/gac/、bin/ssot/、.githooks/ 下 tracked 的 .py / .sh / 无扩展名 hook 脚本

有界习语 (命中即放行):
  - shell:  `gac_run_with_timeout` / `run_with_stage_timeout` / `timeout `
            同行包装; `*_TIMEOUT` / `TIMEOUT` 同行引用 (如
            `gac_run_with_timeout "$_fetch_timeout" git ... fetch`);
            `git submodule update ... --no-fetch` (纯本地, 无网络)
  - python: `subprocess.*(..., timeout=...)` 同调用窗口 (±12 行) 内含
            `timeout=`; 经文件内有界 helper 中转 (函数体向 subprocess 透传
            timeout=, 如 agent-clone `_run_git`、check-pitfall-gat006 `_git`、
            check-submodule-hygiene `_run`)
  - curl/wget: 同行含 `--max-time` / `-m ` / `--connect-timeout` / `--timeout`,
            或同行有上述 shell 超时包装

Output (advisory first landing, 仿 check-pitfall-gat006 SOFT 语义):
  exit 0 = 恒不阻断; findings 非空时人类可读 warn + --json 输出 ok=false。
  --strict 提升为 exit 1 (供未来 enforcement 升级, 当前默认不用)。

用法:
  python3 bin/gac/timeout-audit.py           # 人类可读报告
  python3 bin/gac/timeout-audit.py --json    # JSON (ok=false 即有 findings)
  python3 bin/gac/timeout-audit.py --strict  # findings 非空时 exit 1
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

SCAN_DIRS = ("bin/gac", "bin/ssot", ".githooks")

# 网络型 git 动词 — 位置敏感: git [flags] <动词>, 防变量名/文案误报
# (如 run(["git", "-C", str(clone), "remote", ...]) 的 clone 是变量名,
#  "git common dir is not clone-local" 的 clone 在文案里)
GIT_NET = re.compile(
    r"\bgit\b(?:\s+(?:-C\s+\S+|-c\s+\S+|--git-dir=\S+))*\s+"
    r"(fetch|ls-remote|clone|submodule\s+update)\b"
)
NO_FETCH = re.compile(r"submodule\s+update\b.{0,120}?--no-fetch")

# shell 有界包装习语 (同行)
SHELL_BOUND = re.compile(
    r"gac_run_with_timeout|run_with_stage_timeout|(?<!\w)timeout\s+(-[a-z]+\s+)*\d|_TIMEOUT\b|\bTIMEOUT\b"
)
SHELL_SKIP_LINE = re.compile(r"^\s*(#|echo\b|printf\b|cat\b|log_[a-z_]+\b)")

# curl/wget 有界 flag (同行)
CURL_NET = re.compile(r"(?<!\w)(curl|wget)\b")
CURL_BOUND = re.compile(
    r"--max-time\b|(?<!\w)-m\s|(?<!\w)-m\d|--connect-timeout\b|--timeout\b"
    r"|gac_run_with_timeout|run_with_stage_timeout"
)

# python 有界: 调用窗口内 timeout= / helper 中转
PY_TIMEOUT_KW = re.compile(r"\btimeout\s*=")
# (helper 有界判定见 _bounded_helpers: 函数体含 timeout= + subprocess 调用)
PY_SUBPROCESS = re.compile(r"subprocess\.(run|Popen|call|check_output|check_call)\b")
PY_HELPER_CALL = re.compile(r"(?<!\w)(\w+)\s*\(\s*\[")
# 纯描述行 (报错文案/标记/注释, 非真实调用) — 跳过防误报
PY_SKIP_LINE = re.compile(
    r"^\s*#|print\s*\(|logger?\.|raise\b|return\b[^:]*f['\"]|_MARKERS|MARKERS\s*=|"
    r"assert\b|\"\"\"|NOTE\b|hint|message|msg\s*=|Error|error_msg|"
    r"failed|Failed|FAILED|ToolError|reject\s*\(|"
    r'"fix":|\'fix\':|"remediation":|remediation\s*='
)
# shell heredoc (cat << 'EOF' 用法文案块) — 块内逐行跳过
SHELL_HEREDOC_OPEN = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
WINDOW = 12


def _tracked_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--", *SCAN_DIRS],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f for f in out.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        return []
    wanted: list[str] = []
    for f in files:
        p = WORKSPACE / f
        suffix = p.suffix
        if suffix in (".py", ".sh") or (suffix == "" and ".githooks/" in f):
            wanted.append(f)
    return sorted(wanted)


def _staged_files() -> list[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "--", *SCAN_DIRS],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=True,
        )
        files = [f for f in out.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        return []
    return sorted(f for f in files if f.endswith(".py") or f.endswith(".sh") or ".githooks/" in f)


def _disk_lines(path: str) -> list[str] | None:
    p = WORKSPACE / path
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def _window_has(lines: list[str], idx: int, pat: re.Pattern[str]) -> bool:
    lo = max(0, idx - WINDOW)
    hi = min(len(lines), idx + WINDOW + 1)
    return any(pat.search(lines[j]) for j in range(lo, hi))


def _bounded_helpers(text: str) -> set[str]:
    """文件内定义且函数体向 subprocess 透传 timeout= 的 helper 名.

    如 check-submodule-hygiene `_run` (timeout=30 写死体内)、
    agent-clone `_run_git` / check-pitfall-gat006 `_git` (timeout 参数透传)。
    纯 **kwargs 透传 (clone-lifecycle `run`) 体内无 timeout= 字面量 → 不算有界,
    调用点仍需各自传 timeout= (窗口检查覆盖)。
    """
    bounded: set[str] = set()
    for m in re.finditer(r"^\s*def\s+(\w+)\s*\(", text, re.MULTILINE):
        name = m.group(1)
        body = re.search(
            rf"^\s*def\s+{re.escape(name)}\b.*?(?=^\s*def\s+|\Z)",
            text[m.start() :],
            re.MULTILINE | re.DOTALL,
        )
        if body and PY_TIMEOUT_KW.search(body.group(0)) and PY_SUBPROCESS.search(body.group(0)):
            bounded.add(name)
    return bounded


def _scan_shell(path: str, lines: list[str]) -> list[dict]:
    findings: list[dict] = []
    heredoc_end: str | None = None
    for i, line in enumerate(lines, 1):
        if heredoc_end is not None:
            if line.strip() == heredoc_end:
                heredoc_end = None
            continue
        m_hd = SHELL_HEREDOC_OPEN.search(line)
        if m_hd:
            heredoc_end = m_hd.group(1)
            continue
        if SHELL_SKIP_LINE.match(line):
            continue
        if CURL_NET.search(line) and not CURL_BOUND.search(line):
            findings.append({"file": path, "line": i, "kind": "curl-unbounded", "text": line.strip()[:160]})
            continue
        m = GIT_NET.search(line)
        if not m:
            continue
        if NO_FETCH.search(line):
            continue  # --no-fetch 纯本地, 无网络
        if SHELL_BOUND.search(line):
            continue  # 同行已有超时包装
        findings.append(
            {
                "file": path,
                "line": i,
                "kind": f"git-{m.group(1).replace(' ', '-')}-unbounded",
                "text": line.strip()[:160],
            }
        )
    return findings


def _scan_python(path: str, lines: list[str]) -> list[dict]:
    findings: list[dict] = []
    text = "\n".join(lines)
    bounded_helpers = _bounded_helpers(text)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or PY_SKIP_LINE.search(line):
            continue
        if re.match(r"""^['"][^'"]+['"],?\s*$""", stripped):
            continue  # 纯字符串字面量行 (UNINIT_MARKERS 成员/文案, 非调用)
        # 数组形式 ["git", "fetch", ...] 归一化后再匹配动词位置
        norm = re.sub(r"""["'],\s*["']""", " ", line)
        is_curl = CURL_NET.search(norm) is not None
        m = GIT_NET.search(norm)
        if not is_curl and not m:
            continue
        # 真实调用证据: 数组构造 ["git", ...] / shell 串 / helper 调用 / subprocess 窗口
        invocation = (
            '["git"' in line
            or "['git'" in line
            or '"git ' in line
            or "'git " in line
            or PY_HELPER_CALL.search(line) is not None
            or _window_has(lines, i - 1, PY_SUBPROCESS)
        )
        if not invocation:
            continue
        if CURL_BOUND.search(line) or _window_has(lines, i - 1, PY_TIMEOUT_KW):
            continue  # 同行/同窗口已有 timeout
        if m:
            hm = PY_HELPER_CALL.search(line)
            if hm and hm.group(1) in bounded_helpers:
                continue  # 经有界 helper 中转 (agent-clone / pitfall-gat006 习语)
        kind = (
            "curl-unbounded"
            if (is_curl and not m)
            else (f"git-{m.group(1).replace(' ', '-')}-unbounded" if m else "curl-unbounded")
        )
        findings.append({"file": path, "line": i, "kind": kind, "text": stripped[:160]})
    return findings


def scan(files: list[str]) -> list[dict]:
    findings: list[dict] = []
    for f in files:
        lines = _disk_lines(f)
        if lines is None:
            continue
        if f.endswith(".py"):
            findings.extend(_scan_python(f, lines))
        else:
            findings.extend(_scan_shell(f, lines))
    return sorted(findings, key=lambda d: (d["file"], d["line"]))


def main() -> int:
    ap = argparse.ArgumentParser(description="审计治理脚本中的无界网络调用 (advisory)")
    ap.add_argument("--staged", action="store_true", help="扫 staged (pre-commit 场景)")
    ap.add_argument("--all", action="store_true", help="扫全部 tracked (CI / gate 场景)")
    ap.add_argument("--file", action="append", default=[], help="限定文件 (可多次)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--strict", action="store_true", help="findings 非空时 exit 1 (供未来 enforcement 升级)")
    args = ap.parse_args()

    if args.file:
        files = args.file
    elif args.staged and not args.all:
        files = _staged_files()
    else:
        files = _tracked_files()

    findings = scan(files)

    if args.json:
        print(json.dumps({"ok": not findings, "findings": findings}, ensure_ascii=False))
    elif findings:
        print(f"⚠️ timeout-audit: {len(findings)} 处无界网络调用 (advisory, 不阻断)", file=sys.stderr)
        for fnd in findings:
            print(f"  {fnd['file']}:{fnd['line']} [{fnd['kind']}] {fnd['text']}", file=sys.stderr)
        print("  修复习语: shell 用 gac_run_with_timeout / GAC_*_TIMEOUT;", file=sys.stderr)
        print("            python subprocess 传 timeout= / 经有界 helper 中转;", file=sys.stderr)
        print("            curl 加 --max-time, wget 加 --timeout (详见 #3934/#3937)", file=sys.stderr)
    else:
        print("✅ timeout-audit: 无无界网络调用")

    if args.strict and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
