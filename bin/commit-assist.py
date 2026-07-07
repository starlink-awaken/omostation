#!/usr/bin/env python3
"""commit-assist.py — P76 Phase 7.1 LLM-assisted commit (aetherforge-first)

按 Conventional Commits 规范: type(scope): subject

LLM provider 优先级:
  1. aetherforge 网关 (100.96.126.35:4000, OpenAI compatible) — prefer
  2. ollama 本地 (env OLLAMA_MODEL, fallback) — sub-zero latency
  3. heuristic (--no-llm 硬门) — last resort

工作流 (硬门 — LLM 永远不自己 commit):
  1. 收集 git diff --staged
  2. 压缩: 文件级 summary + -4000 字符 diff
  3. LLM 给 1-line subject + 3-5 line body (Conventional Commits)
  4. **只写侧车** `.commit-suggestion` (gitignored)
  5. 用户必须 `git commit -F .commit-suggestion` 显式应用 (硬门)

约束 (P76-7.1 原则):
  - LLM output 是 advisory, 不替代 developer
  - 必须有 --dry-run / --apply / --no-llm modes
  - 网关不可达 → fallback ollama → fallback heuristic (3-tier graceful)
  - 不发任何 commit (硬门)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]

CONVENTIONAL_TYPES = {
    "feat": "新功能",
    "fix": "Bug 修复",
    "refactor": "重构 (不改行为)",
    "perf": "性能优化",
    "docs": "文档",
    "test": "测试",
    "build": "构建/CI",
    "ci": "CI 守门",
    "chore": "杂项",
    "style": "格式",
    "revert": "回退",
}

AETHERFORGE_GATEWAY = os.environ.get("AETHERFORGE_URL", "http://100.96.126.35:4000")
AETHERFORGE_MODEL = os.environ.get("AETHERFORGE_MODEL", "mid")  # 紧凑小模型, mini-9b 把 budget 耗光返空
AETHERFORGE_TIMEOUT = int(os.environ.get("AETHERFORGE_TIMEOUT", "60"))  # 实测 ~32s 但留 buffer
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:31b-mlx")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "60"))  # ollama gemma4:e4b 已知慢


def git(*args: str, cwd: Path | None = None) -> str:
    cwd = cwd or WORKSPACE
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def get_staged_diff(short: bool = True, limit: int = 500) -> tuple[str, str]:
    """aetherforge 'mid' 处理 ~500 字符 prompt 最稳. 压缩策略:
       stat (必给) + diff file-by-file summary (500 chars max).
       Never 发送完整 diff — LLM 不读代码, 读 summary 就够.
    """
    stat = git("diff", "--staged", "--stat")
    raw = git("diff", "--staged")
    if len(raw) > limit:
        raw = raw[: limit] + f"\n\n[truncated to {limit} chars]"
    return stat, raw


def heuristic_subject(stat: str) -> tuple[str, str]:
    """无 LLM 时 fallback."""
    files = [line.split()[0] for line in stat.splitlines() if "|" in line]
    if not files:
        return "chore", "misc"
    paths = [f.lower() for f in files]
    if any(".omo/_truth/registry/" in p for p in paths):
        ctype, scope = "feat", "gac"
    elif any(".omo/_knowledge/decisions/" in p for p in paths):
        ctype, scope = "docs", "adr"
    elif any("docs/" in p for p in paths):
        ctype, scope = "docs", "docs"
    elif any("bin/" in p for p in paths):
        ctype, scope = "feat", "tools"
    elif any(".omo/" in p for p in paths):
        ctype, scope = "chore", "governance"
    elif any("projects/" in p for p in paths):
        ctype, scope = "refactor", "submodule"
    else:
        ctype, scope = "chore", "misc"
    return f"{ctype}({scope})", f"update {len(files)} files"


def query_aetherforge(model: str, prompt: str, timeout: int) -> str | None:
    """aetherforge 网关 (OpenAI /v1/chat/completions compatible)."""
    url = f"{AETHERFORGE_GATEWAY}/v1/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "你是 commit message 生成器. 输出必须是 Conventional Commits: <type>(<scope>): <subject> + 3-5 行 body. Chinese OK. 不要 preamble / markdown fence."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 600,  # 紧凑 — mid 在 500-1000 之间最稳
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, KeyError, json.JSONDecodeError, OSError) as e:
        print(f"⚠️ aetherforge gateway unreachable: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
        return None


def query_ollama(model: str, prompt: str, timeout: int) -> str | None:
    try:
        result = subprocess.run(
            ["ollama", "run", model, prompt],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"⚠️ ollama: {e}", file=sys.stderr)
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def query_llm(stat: str, diff: str) -> tuple[str, str]:
    """3-tier LLM query: aetherforge → ollama → heuristic."""
    types_list = ", ".join(CONVENTIONAL_TYPES.keys())
    prompt = f"""按 Conventional Commits 规范生成 1 个 commit message.
types: {types_list}

Changed files (stat):
{stat}

Diff (truncated):
{diff}

Output ONLY:
- 1 line subject: <type>(<scope>): <subject, ≤72 chars>
- blank line
- 3-5 line body: WHY/WHAT/NEXT (Chinese OK)

NO preamble, NO closing remark."""

    # Tier 1: aetherforge
    out = query_aetherforge(AETHERFORGE_MODEL, prompt, AETHERFORGE_TIMEOUT)
    if out:
        return "aetherforge", out

    # Tier 2: ollama
    out = query_ollama(OLLAMA_MODEL, prompt, OLLAMA_TIMEOUT)
    if out:
        return "ollama", out

    # Tier 3: heuristic
    scope, subject = heuristic_subject(stat)
    body = f"\n\nWHY: omostation 治理态按现有策略更新\nWHAT: {len(stat.splitlines())} 文件改动\nNEXT: cross-feature on PR"
    return "heuristic", f"{scope}: {subject}{body}\n"


def clean_suggestion(text: str) -> str:
    """清理 LLM 输出: 去 fence, normalize newlines."""
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", text, flags=re.M)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned, flags=re.M)
    return cleaned.strip() + "\n"


def apply_suggestion(suggestion_path: Path) -> int:
    if not suggestion_path.exists():
        print(f"❌ 无 suggestion: {suggestion_path}", file=sys.stderr)
        return 1
    result = subprocess.run(
        ["git", "commit", "-F", str(suggestion_path)],
        cwd=WORKSPACE, capture_output=True, text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true",
                   help="应用 .commit-suggestion 为 commit message (硬门)")
    p.add_argument("--no-llm", action="store_true",
                   help="跳过 LLM 调用, 用启发式 fallback")
    p.add_argument("--dry-run", action="store_true", help="只打印, 不写")
    p.add_argument("--model", default=None, help="override 模型名")
    args = p.parse_args()

    if args.apply:
        return apply_suggestion(WORKSPACE / ".commit-suggestion")

    stat, diff = get_staged_diff()
    if not stat:
        print("⚠️ 无 staged 改动. 提示: `git add` 你的改动.")
        return 1

    print("=== commit-assist.py ===")
    print(f"Files changed:\n{stat}\n")

    if args.no_llm:
        print("(--no-llm 模式, 用启发式)")
        scope, subject = heuristic_subject(stat)
        body = f"\n\nWHY: omostation 治理态按现有策略更新\nWHAT: {len(stat.splitlines())} 文件改动\nNEXT: cross-feature on PR"
        provider = "heuristic"
        suggestion = f"{scope}: {subject}{body}\n"
    else:
        provider, raw = query_llm(stat, diff)
        suggestion = clean_suggestion(raw)
        print(f"(provider: {provider})")

    # Hard gate: subject ≤72 chars
    first_line = suggestion.split("\n", 1)[0]
    if len(first_line) > 72:
        truncated = first_line[:69] + "..."
        suggestion = truncated + suggestion[len(first_line):]

    print(f"\n--- suggested commit message ---\n{suggestion}\n---")

    if args.dry_run:
        return 0

    suggestion_path = WORKSPACE / ".commit-suggestion"
    suggestion_path.write_text(suggestion)
    print(f"✅ 已写: {suggestion_path.relative_to(WORKSPACE)} (provider={provider})")
    print()
    print("下一步 (任选其一):")
    print(f"  1. python bin/commit-assist.py --apply  # 应用 suggestion")
    print(f"  2. git commit -F .commit-suggestion      # 等价")
    print(f"  3. 手动 git commit -m '<your message>'    # 不用 LLM 建议")
    return 0


if __name__ == "__main__":
    sys.exit(main())
