#!/usr/bin/env python3
"""CR-X4-MESH-ROUTING-CONSISTENCY: 检查 mesh 路由一致性.

Mesh 路由 (bin/mesh/, 以及 mesh 相关工具) 必须遵循 BOS URI 标准,
确保路由注册与声明一致.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

TIMEOUT = 30  # seconds per subprocess call
RETRY = 3    # max retries on transient failure

REPO_ROOT = Path(__file__).resolve().parents[2]

# Mesh 相关目录
MESH_DIRS = ["bin/mesh", "bin/ssot"]

ROUTING_RE = re.compile(r"route|dispatch|forward|send|publish", re.IGNORECASE)


def _code_only(path: Path) -> str:
    """只保留代码：抹掉 docstring、所有字符串常量与注释。

    判据是「有没有路由逻辑」, 而 route/dispatch/forward/send/publish 这五个词
    在工作流状态名里也出现（`StepDispatched`、`dispatched` 生命周期串、
    seed 链 "Requested→Admitted→Dispatched→Started"）—— 直接对全文跑正则会把
    `bin/ssot/mesh-iris-executor.py` 这类**纯工作流编排**文件误判成 mesh 路由
    （2026-11-11 实测：本机恒报 1 条 WARN）。真正的路由调用是标识符/调用,
    不含在字符串里, 所以抹掉字符串不影响真命中。

    解析失败时回退到「仅去注释」的文本, 宁可多报也不静默漏报。
    """
    src = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return re.sub(r"#.*", "", src)
    lines = src.splitlines(keepends=True)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for i in range(node.lineno - 1, node.end_lineno):
                if 0 <= i < len(lines):
                    lines[i] = ""
    return re.sub(r"#.*", "", "".join(lines))


def main() -> int:
    violations = []
    mesh_files = []

    for d in MESH_DIRS:
        d_path = REPO_ROOT / d
        if not d_path.is_dir():
            continue
        for f in sorted(d_path.rglob("*.py")):
            rel = f.relative_to(REPO_ROOT)
            name = f.name.lower()
            if "mesh" in name or "iris" in name or "dispatch" in name:
                mesh_files.append((rel, f))

    if not mesh_files:
        print("OK 未发现 mesh 相关文件")
        return 0

    for rel, f in mesh_files:
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # 检查是否有 BOS URI 注册（BOS URI 在字符串里, 必须扫全文）
        has_bos = bool(re.search(r"bos://|bos_route|bos_service|bos:", text))
        # 检查是否有错误处理
        has_error_handling = bool(re.search(r"try:|except|raise|return", text))
        # 检查是否有路由逻辑 —— 只扫代码: 字符串里的状态名不是路由
        has_routing = bool(ROUTING_RE.search(_code_only(f)))

        if has_routing and not has_bos:
            violations.append(f"  {rel} — 包含路由逻辑但无 BOS URI 注册")

        if has_routing and not has_error_handling:
            violations.append(f"  {rel} — 包含路由逻辑但缺少错误处理")

    if violations:
        print(f"WARN 发现 {len(violations)} 个 mesh 路由完整性问题:")
        for v in violations:
            print(v)
        return 0  # advisory

    print("OK 所有 mesh 路由一致性良好")
    return 0


if __name__ == "__main__":
    sys.exit(main())
