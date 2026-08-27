#!/usr/bin/env python3
"""post-commit 派生同步检查 — agora 等子模块指针变更后自动 sync-all-docs.

背景: agora 迭代频繁 (新增 MCP 工具/BOS 服务), bump 指针后派生文档
(capability-registry.yaml / CAPABILITY-MAP / CLI-REFERENCE / INDEX-MCP)
需要重新生成, 否则 CI check-docs-drift 失败. 用户每次需手动提醒.

本脚本: post-commit hook 调用, 检测本次 commit 是否:
  1. 变更子模块 gitlink → 自动 sync-all-docs (既有)
  2. 触碰 SSOT 源 (agent-workflows/profiles, mof-capabilities 等) →
     自动 projection-sync / 对应投影生成器 (PROJ-FORCE, 差距治理 S1)

生成到工作区 (不自动 commit — 由 agent/开发者随下次 commit 提交).

用法 (post-commit hook):
    python3 bin/ssot/post-commit-sync-check.py

返回: 0 = 无需同步 / 已同步; 1 = 同步后产生 diff (提示提交).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 迭代敏感的 PASW 子模块 (bump 后需派生文档同步)
SYNC_SUBMODULES = ("projects/agora",)

# SSOT 源 → 投影生成器映射 (PROJ-FORCE)
# commit 触碰 SSOT 源 → 自动跑对应生成器, 消除"改 SSOT 忘投影"漂移
SSOT_GENERATORS: list[tuple[tuple[str, ...], list[str]]] = [
    # agent-workflows SSOT (_base.yaml 等 profiles) → projection-sync
    (
        (".omo/_truth/registry/agent-workflows/profiles/",),
        ["uv", "run", "--with", "pyyaml", "python", "bin/agent-workflow.py", "projection-sync"],
    ),
    # mof-capabilities SSOT → capability-registry 重生成
    (
        (".omo/_truth/registry/mof-capabilities.yaml",),
        ["uv", "run", "--with", "pyyaml", "python", "bin/ssot/gen-capability-registry.py"],
    ),
]


def _changed_gitlinks() -> list[str]:
    """检测本次 commit (HEAD) 相对上一 commit (HEAD~1) 的 gitlink 变更."""
    try:
        r = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--name-only"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        changed = r.stdout.splitlines()
        return [s for s in SYNC_SUBMODULES if s in changed]
    except Exception:
        return []


def _changed_ssot_sources() -> list[list[str]]:
    """检测本次 commit 触碰的 SSOT 源, 返回需运行的生成器命令列表."""
    try:
        r = subprocess.run(
            ["git", "diff", "HEAD~1", "HEAD", "--name-only"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        changed = r.stdout.splitlines()
    except Exception:
        return []
    triggered: list[list[str]] = []
    for prefixes, cmd in SSOT_GENERATORS:
        if any(c.startswith(prefix) for prefix in prefixes for c in changed):
            if cmd not in triggered:
                triggered.append(cmd)
    return triggered


def _run_sync_all_docs() -> tuple[bool, str]:
    """跑 make sync-all-docs, 返回 (success, output tail)."""
    try:
        r = subprocess.run(
            ["make", "sync-all-docs"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        return r.returncode == 0, (r.stdout or r.stderr)[-400:]
    except Exception as exc:
        return False, str(exc)


def _has_doc_drift() -> bool:
    """检查派生文档是否产生 git diff (待提交)."""
    targets = [
        "docs/generated/",
        "projects/cockpit/CAPABILITY-MAP.md",
        "docs/CLI-REFERENCE.md",
        "docs/INDEX-MCP.md",
    ]
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "--", *targets],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return bool(r.stdout.strip())
    except Exception:
        return False


def _validate_generation() -> bool:
    """校验派生文档生成完整性 (防残缺生成被提交).

    本地子模块不全时生成器产出残缺 (mcp_tools=0/bos_services=0),
    提交会污染 main 致 CI check-docs-drift/能力注册表 fail.
    校验 capability-registry totals 3 键全 > 0.
    """
    try:
        import yaml

        reg_path = ROOT / "docs" / "generated" / "capability-registry.yaml"
        if not reg_path.exists():
            return False
        data = yaml.safe_load(reg_path.read_text(encoding="utf-8"))
        totals = data.get("totals", {}) if isinstance(data, dict) else {}
        keys = ("mcp_servers", "mcp_tools", "bos_services")
        return all(int(totals.get(k, 0)) > 0 for k in keys)
    except Exception:
        return False


def main() -> int:
    rc = 0
    # 1. SSOT-touch → 自动投影生成 (PROJ-FORCE)
    triggered = _changed_ssot_sources()
    for cmd in triggered:
        gen = " ".join(cmd[3:]) if cmd[:2] == ["uv", "run"] else " ".join(cmd)
        print(f"[sync-check] SSOT 源变更 → 自动运行 {gen} ...")
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=180, check=False)
            if r.returncode == 0:
                print(f"[sync-check] ✅ {gen} 完成")
            else:
                print(f"[sync-check] ⚠️ {gen} 失败 (exit {r.returncode}):\n{(r.stdout or r.stderr)[-300:]}")
        except Exception as exc:
            print(f"[sync-check] ⚠️ {gen} 执行异常: {exc}")
        # 残缺防护: capability-registry 生成若本地 submodule 不全产出残缺 (totals=0),
        # 自动 revert, 避免残缺生成物被提交污染 main (CI 完整环境会重新生成).
        if not _validate_generation():
            print("[sync-check] ⚠️ 生成不完整 (本地 submodule 不全?) — 已自动 revert 残缺生成物")
            _revert_incomplete_generation()
            return 0
        # 投影生成可能产生派生文档 diff, 并入下方 drift 提示
        rc = 1 if _has_doc_drift() else rc

    # 2. 子模块指针变更 → sync-all-docs (既有)
    changed = _changed_gitlinks()
    if not changed:
        return rc  # 无子模块指针变更; SSOT-touch 产生的 drift 已提示

    print(f"[sync-check] 检测到子模块指针变更: {', '.join(changed)}")
    print("[sync-check] 自动运行 make sync-all-docs ...")
    ok, out = _run_sync_all_docs()
    if not ok:
        print(f"[sync-check] ⚠️ sync-all-docs 执行失败 (可能子模块不全):\n{out}")
        return 0  # 失败不阻塞 commit

    # 完整性校验 (防残缺生成污染 main)
    if not _validate_generation():
        print("[sync-check] ⚠️ 派生文档生成不完整 (本地子模块不全?) — 跳过提交提示")
        print("[sync-check] 请勿提交残缺派生文档 (CI 完整环境会重新生成)")
        return 0

    if _has_doc_drift():
        print("[sync-check] ⚠️ 派生文档已更新 (capability-registry/CLI-REFERENCE/INDEX-MCP)")
        print("[sync-check] 请随下次 commit 提交这些派生文档 (CI check-docs-drift 依赖)")
        return 1
    print("[sync-check] ✅ 派生文档无漂移")
    return 0


def _revert_incomplete_generation() -> None:
    """revert 残缺生成的 capability-registry 到 HEAD (保持工作树干净)."""
    target = "docs/generated/capability-registry.yaml"
    try:
        subprocess.run(
            ["git", "checkout", "HEAD", "--", target],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
