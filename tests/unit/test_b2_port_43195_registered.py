"""BET-Y2Q4-T10-283 —— ADR-0456 B2「未注册端口 0」判据的可复算钉子。

钉三件事，全部是**不变量**，不把任何 host 运行态（实盘 plist、监听 socket）读进用例：

1. 端口声明必须按 YAML **结构**解析（数字 mapping 键），计数口径而非字串命中 ——
   写成注释、标量值或非数字键名都不算声明。
2. 反证口径 —— 同一份内容把 43195 挪成非数字键或注释时，声明集必须读不到它。
   若这条不成立，第 1 条就只是「文件里有这串字」。
3. 声明了 ``runtime_root: install`` 的 launchd 条目，其 ``program`` 里不得残留检出根字面量
   —— 记录与自己声明的根必须同侧（这是 resident-web 此前错着的形状）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

PORT = 43195
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def repo_file(rel: str) -> Path:
    """按调用时刻解析仓库根，不在 import 期冻结常量。"""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / rel).exists():
            return parent / rel
    raise AssertionError(f"{rel} not found from {here}")


def services_registry() -> list[dict]:
    """读 ``.omo/_truth/registry/services.yaml`` 的 services 清单。

    该文件是**两文档** YAML（首文档为 frontmatter 元数据，次文档为
    ``launchd_namespace`` + ``services``），``yaml.safe_load`` 会抛 ComposerError，
    所以必须 ``safe_load_all`` 后按内容选文档。
    """
    docs = list(yaml.safe_load_all(repo_file(".omo/_truth/registry/services.yaml").read_text(encoding="utf-8")))
    for doc in docs:
        if isinstance(doc, dict) and isinstance(doc.get("services"), list):
            return doc["services"]
    raise AssertionError(f"services 文档缺失，读到 {len(docs)} 个文档: {[type(d).__name__ for d in docs]}")


def checkout_root() -> Path | None:
    """规范检出根（``~/Workspace``），不是当前 worktree 根。

    检出根字面量必须按 canonical 根判定：用 ``__file__`` 反推的 code_root 在 worktree
    里等于 worktree 路径，services.yaml 里本来就不会出现它，第 3 条钉子会**真空通过**。
    """
    sys.path.insert(0, str(repo_file("bin/lib/repo_root.py").parent))
    try:
        import repo_root
    except ImportError:
        return None
    try:
        return repo_root.canonical_root()
    except RuntimeError:
        return None


def numeric_port_keys(node: object, cluster: str) -> list[int]:
    """结构解析：某簇下**整数键**才算声明端口。

    ``yaml.safe_load`` 会把 ``43195:`` 解析成 int 键、把 ``'43195x':`` 或注释解析成
    非键内容 —— 所以这个口径对「字串命中但不是声明」天然免疫。
    """
    out: list[int] = []
    if not isinstance(node, dict):
        return out
    sub = node.get(cluster)
    if not isinstance(sub, dict):
        return []
    for key in sub:
        if isinstance(key, int):
            out.append(key)
    return out


def test_43195_is_a_declared_port_by_structure() -> None:
    doc = yaml.safe_load(repo_file("protocols/port-registry.yaml").read_text(encoding="utf-8"))
    declared = numeric_port_keys(doc, "ports")
    assert PORT in declared, "43195 未成为 /ports 的数字键声明"
    # 计数口径：声明数等于数字键数（重复键会被 YAML 合并，所以这里同时钉「无重复塌缩」）
    ports_block = doc["ports"]
    assert len(ports_block) == len(declared), (
        f"/ports 有 {len(ports_block)} 键但仅 {len(declared)} 个数字键 —— 存在非数字键混入，"
        "计数不再可作为「未注册端口 0」的分母"
    )
    # 只追加不重排：既有锚点仍在原位
    text = repo_file("protocols/port-registry.yaml").read_text(encoding="utf-8")
    for anchor in ("  4000:", "  5173:", "  43191:", "  43910:"):
        assert anchor in text, f"既有声明 {anchor} 被动过 —— 违反「分配即固定, 只追加不重排」"


def test_counter_proof_non_numeric_or_comment_is_not_a_declaration() -> None:
    """反证 —— 声明必须落在数字键上，注释与字符串键都不算。"""
    commented = f"""
ports:
  8000:
    name: kept
    status: active
  # {PORT}: resident-web
"""
    doc = yaml.safe_load(commented)
    declared = numeric_port_keys(doc, "ports")
    assert PORT not in declared, "注释里的端口被当成声明 —— 口径退化成了字串命中"
    assert declared == [8000], f"意外读数 {declared}"

    stringy = f"""
ports:
  8000:
    name: kept
    status: active
  '{PORT} ':
    name: resident-web
"""
    doc2 = yaml.safe_load(stringy)
    assert PORT not in numeric_port_keys(doc2, "ports"), "近似字符串键被当成数字声明"


def test_launchd_entries_declaring_install_root_carry_no_checkout_literal() -> None:
    checkout = checkout_root()
    if checkout is None:
        pytest.skip("定位不到规范检出根 —— 该钉子在本机无从判定，不降级为 code_root")
    services = services_registry()
    offenders: list[str] = []
    install_entries = 0
    for svc in services:
        if not isinstance(svc, dict) or svc.get("scheduler") != "launchd":
            continue
        if svc.get("runtime_root") != "install":
            continue
        install_entries += 1
        blob = yaml.dump(svc.get("program"), allow_unicode=True)
        if str(checkout) in blob:
            offenders.append(str(svc.get("id")))
    assert install_entries, "没有任何条目声明 runtime_root: install —— 钉子已与被检对象脱钩"
    assert not offenders, f"声明 install 却记录检出根 {checkout}: {offenders}"


def test_resident_web_record_is_schema_valid_and_self_consistent() -> None:
    services = services_registry()
    svc = next(s for s in services if isinstance(s, dict) and s.get("id") == "omostation.resident-web")
    assert svc["runtime_root"] == "install"
    assert svc["generate"] is False, "改 generate: true 会立即产生 E1 漂移（plist 含 WorkingDirectory）"
    # 两个准入开关缺省即不声明 —— 本 BET 不越权推进（#143 的授权项）
    for pin in ("require_kernel_root_match", "require_state_root_partitioned"):
        assert pin not in svc, f"{pin} 不该由注册腿挂上"
    assert SHA256_RE.match(str(svc["content_digest"])), "content_digest 形状不合法"
    args = svc["program"]["args"]
    joined = " ".join(a if isinstance(a, str) else str(a) for a in args)
    tokens = re.split(r"[\s,']+", joined)
    assert "--port" in tokens, f"argv 里没有 --port 旗标: {joined[:200]}"
    flag = tokens.index("--port")
    assert tokens[flag + 1] == str(PORT), f"--port 的取值不是 {PORT}: {tokens[flag:flag + 2]}"
    assert "/.local/opt/omostation/projects/omo/src" in joined, "载荷里的根未订正到安装位"
