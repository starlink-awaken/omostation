"""三处「契约已定义并测试，但生产侧无生产者」的绊线 (ADR-0463).

不是通用检查框架 —— 实测通用版不可行: authority 校验的 56 个字段中, 大量经由
`**splat` 展开加入请求(如 `**_authority_envelope_identity(...)`), 纯 AST 字面量键
提取会产出 36 个假阳性; 跨过程解析成本过高。

故本文件只对**三个已知缺口**各写一条精准谓词: 若日后有人补上生产者, 断言即失败,
提示把该条目从 ADR-0463 移除。

1. ``gh_json``                     bin/lib 有定义, clone-lifecycle 用而不 import  (#4596 已修)
2. ``claims_authority_fence_context``  只有读取方, 无写入方                   (omo#206 补了读动词)
3. ``publication_scope``            只有校验方, **生产 lifecycle.py 从不构造**  (未解)
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
OMO = WORKSPACE / "projects" / "omo" / "src" / "omo" / "workflow"
CLAIMS = OMO / "claims_authority.py"
LIFECYCLE = OMO / "lifecycle.py"
CLONE_LIFECYCLE = WORKSPACE / "bin" / "gac" / "clone-lifecycle.py"


def _request_dict_keys(src: str) -> set[str]:
    """AST: 名字以 request 开头的字典字面量的字符串键。"""
    tree = ast.parse(src)
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        assigned = any(
            isinstance(parent, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id.startswith("request") for t in parent.targets)
            and parent.value is node
            for parent in ast.walk(tree)
        )
        if assigned:
            keys.update(
                k.value for k in node.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            )
    return keys


def test_gh_json_is_imported_not_just_called() -> None:
    """`gh_json` 定义在 bin/lib/gh_query.py; clone-lifecycle 必须真的 import 它。"""
    src = CLONE_LIFECYCLE.read_text(encoding="utf-8")
    imported = any(
        isinstance(n, (ast.Import, ast.ImportFrom))
        and any(a.name.endswith("gh_query") or a.name == "gh_json" for a in n.names)
        for n in ast.walk(ast.parse(src))
    )
    assert imported, "gh_json 被调用却未 import —— #4596 的修复已回退?"
    assert "gh_json(" in src, "gh_json 已无调用点, 该缺口条目应从 ADR-0463 移除"


def test_fence_context_still_has_no_producer() -> None:
    """`claims_authority_fence_context` 只被读; 生产侧仍无写入方。

    若有人补上写入方, 本断言失败 -> 提示从 ADR-0463 移除并重估 ADR-0461 第 2-4 步。
    """
    producers = [
        WORKSPACE / "bin" / "gac" / "agent-clone.py",
        WORKSPACE / "bin" / "gac" / "clone-lifecycle.py",
        LIFECYCLE,
    ]
    needle = '"claims_authority_fence_context"'
    written = [
        p.name for p in producers
        if re.search(rf'["\']\w+["\']\s*:\s*{re.escape(needle)}', p.read_text(encoding="utf-8"))
    ]
    assert not written, (
        f"fence context 已出现生产侧写入方 {written} —— 该缺口已闭合, "
        "请从 ADR-0463 移除并重估 ADR-0461 第 2-4 步"
    )


def test_publication_scope_still_absent_from_production_requests() -> None:
    """**当前唯一的未解缺口**。

    authority 侧 `_validate_publication_scoped_allow` 在缺 `publication_scope` 时直接
    `V1_AUTHORITY_FORBIDDEN(managed_clone)`; 而生产 observe-claim 从不构造它, 故该分支
    从未在生产被走通 (ADR-0463 裁定: 观察不应带; ADR-0461 第 2-4 步作废)。

    谓词只认「请求字面量里的键」, 刻意**不**认全文出现 —— omo#207 的
    `receipt.get("publication_scope")` 是**读取回执**, 不是构造请求。
    """
    src = LIFECYCLE.read_text(encoding="utf-8")
    assert "publication_scope" not in _request_dict_keys(src), (
        "生产 observe-claim 开始构造 publication_scope —— ADR-0463 的裁定已失效, "
        "需重开 ADR-0461 第 2-4 步"
    )
    assert 'request.get("publication_scope")' in CLAIMS.read_text(encoding="utf-8"), (
        "authority 侧已不再校验 publication_scope —— ADR-0463 的缺口描述需更新"
    )
