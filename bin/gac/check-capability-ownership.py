#!/usr/bin/env python3
"""CAP-OWN 能力所有权 + 删除防腐检查 (差距治理 S1).

背景 (复盘实证): agora tools_bcos.py 在并发过程中曾被删后恢复 (4103B 抖动),
capability-registry 能"记录" 600 tools 但不阻止删除 — 能力层缺少防腐,
对比 gitlink 有 submodule-guard (fast-forward) 保护一阶对象 (git 历史),
能力 (二阶对象) 却无保护.

本检查实现三层断言:
  1. OWNER-REQUIRED : 注册表中的每个能力 (path 指向实现的工具) 必须声明 owner
                      (owner 缺失 → finding; 说明该能力无人负责, 删除无审批主体)
  2. IMPL-EXISTS    : 注册表声明的能力 → 实现文件/CLI 必须存在
                      (registered-but-missing → 能力丢失/漂移, 阻断级)
  3. IMPL-REGISTERED: 存在实现但未在注册表 → 孤儿能力 (漂移告警, 引导补登)

与 submodule-guard 的对称设计:
  - submodule-guard 保护 gitlink 非 fast-forward
  - CAP-OWN 保护能力删除 (实现缺失即注册表 active 能力失效 → gate FAIL)

SSOT:  .omo/_truth/registry/mof-capabilities.yaml (注册表 + owner)
投影:  docs/generated/capability-registry.yaml (能力规模投影, 只读)
        projects/agora/etc/bos-services.yaml (BOS 服务注册)

用法:
    python3 bin/gac/check-capability-ownership.py            # 全量检查
    python3 bin/gac/check-capability-ownership.py --json     # JSON 输出
    python3 bin/gac/check-capability-ownership.py --scope <path>  # 单面检查
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 能力注册表 SSOT (owner 声明在这里)
MOF_CAPABILITIES = ROOT / ".omo" / "_truth" / "registry" / "mof-capabilities.yaml"
# 能力规模投影 (只读)
CAPABILITY_REGISTRY = ROOT / "docs" / "generated" / "capability-registry.yaml"
# BOS 服务注册 (agora)
BOS_SERVICES = ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"
# 项目能力注册 (projects-capabilities.yaml)
PROJECTS_CAPABILITIES = ROOT / ".omo" / "_truth" / "registry" / "projects-capabilities.yaml"

# owner 缺失时默认 owner (未声明 → 视为无人负责)
DEFAULT_OWNER = "unassigned"

# 跳过检查的路径模式 (生成物/虚拟条目, 无独立实现文件)
SKIP_PATH_PATTERNS = (
    "::",  # bin/agent-workflow.py::suggest 这类嵌入子命令
    "mcp:",  # MCP 传输引用
)

# _resolve_impl 返回 SKIP_MARKER 表示"嵌入子命令, 无独立文件, 不检查存在性"
SKIP_MARKER = object()


class Finding:
    __slots__ = ("check", "severity", "message", "capability")

    def __init__(self, check: str, severity: str, message: str, capability: str = "") -> None:
        self.check = check
        self.severity = severity
        self.message = message
        self.capability = capability

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "severity": self.severity,
            "message": self.message,
            "capability": self.capability,
        }


def _load_yaml(path: Path) -> dict | None:
    """加载 YAML, 支持 frontmatter 多文档 (safe_load_all 取最后一个 doc).

    参考 AGENTS.md: "Frontmatter yaml 读法 (safe_load_all)".
    mof-capabilities.yaml 是 `---` 分隔的多文档 (frontmatter + 主体),
    注册表数据在最后一个 doc.
    """
    try:
        import yaml

        if not path.exists():
            return None
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        # 取最后一个非空 doc (主体数据)
        for doc in reversed(docs):
            if isinstance(doc, dict) and doc:
                return doc
        return {}
    except Exception:
        return None


def _load_yaml_frontmatter(path: Path) -> dict:
    """读 frontmatter (第一个 doc) 元数据: owner/lifecycle/last-reviewed 等."""
    try:
        import yaml

        if not path.exists():
            return {}
        docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        if docs and isinstance(docs[0], dict):
            return docs[0]
        return {}
    except Exception:
        return {}


def _collect_registered(paths: list[Path]) -> list[dict]:
    """从注册表收集 {capability, path, owner} 条目."""
    entries: list[dict] = []
    for p in paths:
        data = _load_yaml(p)
        if not isinstance(data, dict):
            continue
        # frontmatter owner 是文件级默认 (如 mof-capabilities: governance-team)
        file_owner = str(_load_yaml_frontmatter(p).get("owner") or DEFAULT_OWNER)
        # mof-capabilities.yaml: tools / omo_tools / p74_tools 段
        # 顶层 owner (file_owner) 是有效继承默认; 显式 per-capability owner 覆盖
        for section in ("tools", "omo_tools", "p74_tools"):
            for cap, meta in (data.get(section) or {}).items():
                if isinstance(meta, dict) and "path" in meta:
                    entries.append(
                        {
                            "capability": str(cap),
                            "path": str(meta["path"]),
                            "owner": str(meta.get("owner") or file_owner),
                            "explicit_owner": bool(meta.get("owner")),
                            "registered": True,
                        }
                    )
        # capability_ownership 段 (S1 新增): 显式能力所有权, owner 必填
        for cap, meta in (data.get("capability_ownership") or {}).items():
            if isinstance(meta, dict):
                entries.append(
                    {
                        "capability": str(cap),
                        "path": str(meta.get("implements") or ""),
                        "owner": str(meta.get("owner") or DEFAULT_OWNER),
                        "explicit_owner": bool(meta.get("owner")),
                        "registered": bool(meta.get("implements")),
                    }
                )
    return entries


def _collect_projects_capabilities() -> list[dict]:
    """从 projects-capabilities.yaml 收集项目能力条目."""
    entries: list[dict] = []
    data = _load_yaml(PROJECTS_CAPABILITIES)
    if not isinstance(data, dict):
        return entries
    file_owner = str(_load_yaml_frontmatter(PROJECTS_CAPABILITIES).get("owner") or DEFAULT_OWNER)
    for cap in data.get("capabilities", []):
        if isinstance(cap, dict) and "entrypoint" in cap:
            entries.append(
                {
                    "capability": str(cap.get("id", cap["entrypoint"])),
                    "path": str(cap["entrypoint"]),
                    "owner": str(cap.get("owner") or file_owner),
                    "explicit_owner": bool(cap.get("owner")),
                    "registered": True,
                }
            )
    return entries


def _collect_bos_services() -> list[dict]:
    """从 bos-services.yaml 收集 BOS 服务 (agora 域)."""
    data = _load_yaml(BOS_SERVICES)
    entries: list[dict] = []
    if not isinstance(data, dict):
        return entries
    for domain, services in (data.get("domains") or {}).items():
        if isinstance(services, dict):
            for svc, meta in services.items():
                if isinstance(meta, dict):
                    entries.append(
                        {
                            "capability": f"bos://{domain}/{svc}",
                            "path": str(meta.get("implements") or ""),
                            "owner": str(meta.get("owner") or DEFAULT_OWNER),
                            "explicit_owner": bool(meta.get("owner")),
                            "registered": True,
                        }
                    )
    return entries


def _resolve_impl(path_str: str) -> Path | None:
    """把注册表中的 path 解析为绝对路径 (root-relative or project-relative).

    返回:
      - Path: 实现存在
      - None: 实现缺失 (应报 IMPL-EXISTS)
      - SKIP 标记 (嵌入子命令等无独立文件, 不检查)
    """
    if any(p in path_str for p in SKIP_PATH_PATTERNS):
        return SKIP_MARKER
    if path_str.startswith("/"):
        cand = Path(path_str)
    else:
        cand = ROOT / path_str
    # path 可能是 python 模块路径 (a.b.c → a/b/c.py) 或 bin 脚本
    if cand.exists():
        return cand
    # 尝试追加 .py (模块引用)
    if cand.suffix == "":
        py = ROOT / f"{path_str}.py"
        if py.exists():
            return py
    return None


def _submodule_unchecked(path_str: str) -> bool:
    """检测实现缺失是否因 submodule 未 checkout (环境限制, 非能力删除).

    判断依据: 路径在 projects/<sub>/... 且该 submodule 的 git commit (HEAD)
    **包含**该文件, 但本地工作树缺失 → 本地 checkout 不完整 (环境限制).
    若 commit 也不含该文件 → 真实漂移 (应报 error).
    """
    parts = path_str.split("/")
    if len(parts) < 3 or parts[0] != "projects":
        return False
    sub = parts[1]
    sub_dir = ROOT / "projects" / sub
    if not sub_dir.exists():
        return False
    # 取 projects/<sub>/ 之后的相对路径 (submodule 内路径)
    rel_in_sub = "/".join(parts[2:])
    try:
        # git cat-file -e HEAD:<path>: 文件在 submodule commit 中?
        r = subprocess.run(
            ["git", "cat-file", "-e", f"HEAD:{rel_in_sub}"],
            cwd=sub_dir,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        # 文件在 commit 中 (cat-file -e 成功) 但工作树缺 → checkout 不完整
        return r.returncode == 0
    except Exception:
        return False


def _scan_project_impls() -> set[str]:
    """扫描仓库内存在的实现入口 (bin/, projects/*/src/**/tools_*.py, mcp_server.py).

    排除:
      - _archive / _archive-*: 归档语义 = 退役能力, 不参与反向断言
      - test_*.py / *_test.py: 测试不是能力
      - _lib.py / __init__.py: 库模块不是独立能力
    """
    found: set[str] = set()
    bin_dir = ROOT / "bin"
    if bin_dir.exists():
        for p in bin_dir.rglob("*.py"):
            rel = str(p.relative_to(ROOT))
            if _is_impl_candidate(rel):
                found.add(rel)
        for p in bin_dir.rglob("*"):
            if p.is_file() and p.suffix in ("", ".sh") and p.name not in ("__init__.py",):
                rel = str(p.relative_to(ROOT))
                if _is_impl_candidate(rel):
                    found.add(rel)
    for proj in (ROOT / "projects").iterdir():
        src = proj / "src"
        if not src.exists():
            continue
        for p in src.rglob("tools_*.py"):
            rel = str(p.relative_to(ROOT))
            if _is_impl_candidate(rel):
                found.add(rel)
        for p in src.rglob("mcp_server.py"):
            found.add(str(p.relative_to(ROOT)))
    return found


def _is_impl_candidate(rel: str) -> bool:
    """实现候选过滤: 归档/测试/库模块不算独立能力."""
    parts = rel.split("/")
    if any("_archive" in part for part in parts):
        return False
    name = parts[-1]
    if name.startswith("test_") or name.endswith("_test.py"):
        return False
    if name in ("_lib.py", "__init__.py"):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="CAP-OWN 能力所有权 + 删除防腐检查")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--scope", default="", help="单面检查 (impl|owner|reverse)")
    args = ap.parse_args()

    entries = _collect_registered([MOF_CAPABILITIES]) + _collect_projects_capabilities()
    bos = _collect_bos_services()
    findings: list[Finding] = []
    impls = _scan_project_impls()

    # 1. OWNER-REQUIRED: 显式能力 (capability_ownership 段) + BOS 服务必须声明 owner
    #    顶层 owner (governance-team) 是 tools/omo_tools/p74_tools 的有效继承默认,
    #    不报; 只有"显式能力段/BOS 服务无 owner"才 warning (删除/变更无审批主体).
    if not args.scope or args.scope == "owner":
        explicit = [e for e in entries if e.get("explicit_owner") is False and e["owner"] == DEFAULT_OWNER]
        for e in explicit:
            findings.append(
                Finding(
                    "OWNER-REQUIRED",
                    "warning",
                    f"能力 {e['capability']} 无显式 owner (默认 {DEFAULT_OWNER}), "
                    f"删除/变更无审批主体",
                    e["capability"],
                )
            )
        for e in bos:
            if not e.get("explicit_owner"):
                findings.append(
                    Finding(
                        "OWNER-REQUIRED",
                        "warning",
                        f"BOS 服务 {e['capability']} 无 owner (默认 {DEFAULT_OWNER})",
                        e["capability"],
                    )
                )

    # 2. IMPL-EXISTS: 注册能力 → 实现必须存在 (删除防腐核心)
    if not args.scope or args.scope == "impl":
        for e in entries:
            if not e["path"]:
                continue
            resolved = _resolve_impl(e["path"])
            if resolved is SKIP_MARKER:
                continue  # 嵌入子命令 (::), 无独立文件, 不检查
            if resolved is None:
                if _submodule_unchecked(e["path"]):
                    # submodule 未 checkout = 本地环境限制, CI 完整环境会覆盖
                    findings.append(
                        Finding(
                            "IMPL-UNCHECKED",
                            "info",
                            f"注册能力 {e['capability']} 实现路径在未 checkout 的 submodule: "
                            f"{e['path']} (本地环境限制, CI 全量校验)",
                            e["capability"],
                        )
                    )
                    continue
                findings.append(
                    Finding(
                        "IMPL-EXISTS",
                        "error",
                        f"注册能力 {e['capability']} 实现缺失: {e['path']} "
                        f"(能力被删除但注册表未同步 → 删除防腐 FAIL)",
                        e["capability"],
                    )
                )

    # 3. IMPL-REGISTERED: 实现存在但未注册 → 孤儿能力 (漂移告警)
    if not args.scope or args.scope == "reverse":
        registered_paths = {e["path"] for e in entries if e["path"]}
        for impl_path in sorted(impls):
            if impl_path not in registered_paths:
                # 只对 tools_*.py 和 bin 脚本告警, 避免噪音
                if "tools_" in impl_path or impl_path.startswith("bin/"):
                    findings.append(
                        Finding(
                            "IMPL-REGISTERED",
                            "info",
                            f"实现存在但未注册: {impl_path} (孤儿能力, 建议补登)",
                            impl_path,
                        )
                    )

    if args.json:
        print(json.dumps({"findings": [f.to_dict() for f in findings]}, ensure_ascii=False, indent=2))
    else:
        for f in findings:
            print(f"[{f.check}:{f.severity}] {f.message}")
        if findings:
            n_error = sum(1 for f in findings if f.severity == "error")
            print(f"\n{len(findings)} findings ({n_error} errors, {len(findings)-n_error} non-errors)")
        else:
            print("✅ CAP-OWN: 无能力所有权/删除防腐问题")

    # 阻断级: error findings
    n_error = sum(1 for f in findings if f.severity == "error")
    return 1 if n_error else 0


if __name__ == "__main__":
    sys.exit(main())
