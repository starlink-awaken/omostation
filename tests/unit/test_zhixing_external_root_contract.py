"""ADR-0456 决策 5 / BET-Y2Q4-T10-267 — 外部依赖契约的可执行判据。

三件事各自要钉住:

1. `repo_root.external_root()` 的解析序与三种失败形状 (env / 登记表 path / 未落位 /
   未登记 / 登记了没 path);
2. `ops check-signals` 的 `/health` 观测轴 —— 缺省 observe-only, 且 `pinned_sha`
   一个读取点都不许有;
3. 登记表自身的一致性: `health.env` 必须是 `protocols/port-registry.yaml` 里登记过的
   env 名 (反向核对是集合判据, 不是手抄名单 —— AGENTS.md §7「契约名单单一来源」条)。

全部用例 hermetic: 探针一律 monkeypatch `urllib.request.urlopen`, 既不打真服务, 也不要求
本机装了 zhixing-dashboard (AGENTS.md §7「hermetic 测试泄漏 host 状态」条: 本机在跑的服务
一旦停掉, 直接联网的用例就变成环境类假红)。
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bin" / "lib"))

import repo_root  # noqa: E402

REGISTRY_REL = Path(".omo") / "_truth" / "registry" / "external-write-roots.yaml"
ZHIXING_ID = "zhixing-dashboard"
PORT_REGISTRY_REL = Path("protocols") / "port-registry.yaml"


def _load_ops_cli() -> Any:
    path = REPO / "bin" / "ops" / "cli.py"
    spec = importlib.util.spec_from_file_location("ops_cli_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ops_cli = _load_ops_cli()


def _materialize_registry(root: Path, entries: str) -> Path:
    """在一棵假根下写出登记表, 使 root 可同时喂给 repo_root 与 ops 探针。"""
    target = root / REGISTRY_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "schema: external-write-root-registry/v1\nroots:\n" + entries.rstrip() + "\n",
        encoding="utf-8",
    )
    return root


class _FakeResponse:
    def __init__(self, body: str, status: int = 200) -> None:
        self._body = body.encode("utf-8")
        self.status = status

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


@pytest.fixture
def fake_urlopen(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """替换 urlopen 并记录调用, 返回可改写的响应袋 —— 全程不碰网络。"""
    box: dict[str, Any] = {"url": None, "response": _FakeResponse('{"code_drift": false}'), "raise": None}

    def _urlopen(url: str, timeout: float | None = None, *a: object, **kw: object):
        box["url"] = url
        box["timeout"] = timeout
        if box["raise"] is not None:
            raise box["raise"]
        return box["response"]

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    return box


# ── 1. 解析器: 优先级与失败形状 ─────────────────────────


def test_external_root_prefers_env_named_by_the_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_dir = tmp_path / "env-placed"
    env_dir.mkdir()
    root = _materialize_registry(
        tmp_path / "checkout",
        """  - id: fake-dep
    path: /definitely/not/this/one
    root_env: FAKE_DEP_ROOT
    kind: local_git""",
    )
    monkeypatch.setenv("FAKE_DEP_ROOT", str(env_dir))
    assert repo_root.external_root("fake-dep", registry_root=root) == env_dir


def test_env_override_worthless_when_target_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """env 指向不存在的目录 ⇒ None, 不得悄悄退回登记表 path (定位器不说谎)。"""
    placed = tmp_path / "real"
    placed.mkdir()
    root = _materialize_registry(
        tmp_path,
        """  - id: fake-dep
    path: %s
    root_env: FAKE_DEP_ROOT""" % placed,
    )
    monkeypatch.setenv("FAKE_DEP_ROOT", str(tmp_path / "gone"))
    assert repo_root.external_root("fake-dep", registry_root=root) is None


def test_external_root_expands_tilde_from_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    (home / ".local/share/fake").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("FAKE_DEP_ROOT", raising=False)
    root = _materialize_registry(
        tmp_path / "checkout",
        """  - id: fake-dep
    path: ~/.local/share/fake
    root_env: FAKE_DEP_ROOT""",
    )
    assert repo_root.external_root("fake-dep", registry_root=root) == home / ".local/share/fake"


def test_external_root_returns_none_when_not_placed(tmp_path: Path) -> None:
    root = _materialize_registry(tmp_path, """  - id: fake-dep
    path: %s""" % (tmp_path / "absent"))
    assert repo_root.external_root("fake-dep", registry_root=root) is None


def test_external_root_undeclared_id_raises_keyerror(tmp_path: Path) -> None:
    root = _materialize_registry(tmp_path, """  - id: fake-dep
    path: %s""" % tmp_path)
    with pytest.raises(KeyError, match="not declared"):
        repo_root.external_root("typo-in-id", registry_root=root)


def test_external_root_declared_without_path_raises_valueerror(tmp_path: Path) -> None:
    root = _materialize_registry(tmp_path, """  - id: fake-dep
    kind: local_git""")
    with pytest.raises(ValueError, match="without path"):
        repo_root.external_root("fake-dep", registry_root=root)


def test_entry_without_root_env_has_no_env_channel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`root_env` 缺席 ⇒ 没有任何 env 能移动它 —— env 名来自登记表而不是代码里的名单。"""
    declared = tmp_path / "declared"
    declared.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    root = _materialize_registry(
        tmp_path,
        """  - id: fake-dep
    path: %s""" % declared,
    )
    monkeypatch.setenv("FAKE_DEP_ROOT", str(other))
    assert repo_root.external_root("fake-dep", registry_root=root) == declared


# ── 2. 嵌套段的 path 不得被当成根 path ─────────────────


ENTRY_WITH_HEALTH = """  - id: fake-dep
    path: %s
    health:
      env: FAKE_DEP_PORT
      path: /health"""


def test_health_path_is_not_parsed_as_root_path(tmp_path: Path) -> None:
    placed = tmp_path / "dep-code"
    placed.mkdir()
    root = _materialize_registry(tmp_path, ENTRY_WITH_HEALTH % placed)
    decls = repo_root._external_root_decls(root)
    assert decls["fake-dep"]["path"] == str(placed)
    assert repo_root.external_root("fake-dep", registry_root=root) == placed


def test_indent_parser_is_not_a_no_op(tmp_path: Path) -> None:
    """反证: 把根 path 挪进 health 块 ⇒ 解析结果必须是空串并当场 ValueError, 不是 /health。

    没有这一条, 上一条的「== placed」可能只是因为解析器根本没看任何 path。
    """
    root = _materialize_registry(
        tmp_path,
        """  - id: fake-dep
    kind: local_git
    health:
      env: FAKE_DEP_PORT
      path: /health""",
    )
    assert repo_root._external_root_decls(root)["fake-dep"]["path"] == ""
    with pytest.raises(ValueError, match="without path"):
        repo_root.external_root("fake-dep", registry_root=root)


def test_real_registry_zhixing_entry_carries_the_three_contract_keys() -> None:
    decls = repo_root._external_root_decls(REPO)
    assert ZHIXING_ID in decls
    assert decls[ZHIXING_ID]["root_env"] == "ZHIXING_DASHBOARD_ROOT"
    assert decls[ZHIXING_ID]["path"] == "~/.local/share/zhixing-dashboard"
    doc = yaml.safe_load((REPO / REGISTRY_REL).read_text(encoding="utf-8"))
    entry = next(item for item in doc["roots"] if item["id"] == ZHIXING_ID)
    assert entry["repo"] == "git@github.com:starlink-awaken/zhixing-dashboard.git"
    assert len(entry["pinned_sha"]) == 40
    assert entry["health"] == {"env": "ZHIXING_OBSERVATORY_PORT", "path": "/health"}
    assert "require_health" not in entry  # 缺省 observe-only 是这一轮的交付状态


def test_healthy_env_names_are_registered_in_port_registry() -> None:
    doc = yaml.safe_load((REPO / REGISTRY_REL).read_text(encoding="utf-8"))
    ports = yaml.safe_load((REPO / PORT_REGISTRY_REL).read_text(encoding="utf-8"))
    declared_envs = {str(value) for value in (ports.get("env_vars") or {}).values()}
    used = {
        str(item["health"]["env"])
        for item in doc.get("roots") or []
        if isinstance(item.get("health"), dict) and item["health"].get("env")
    }
    assert used  # 空集合也能通过 ⊆, 那正是空绿形状
    assert used <= declared_envs, f"未登记端口的 env: {sorted(used - declared_envs)}"


# ── 3. 探针分类: 四种状态 + 升级条件 ──────────────────


def _probe_root(tmp_path: Path, *, port_env: str = "FAKE_DEP_PORT") -> Path:
    return _materialize_registry(
        tmp_path,
        """  - id: fake-dep
    path: %s
    health:
      env: %s
      path: /health""" % (tmp_path, port_env),
    )


def test_probe_classifies_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]) -> None:
    monkeypatch.setenv("FAKE_DEP_PORT", "43199")
    fake_urlopen["response"] = _FakeResponse('{"code_drift": false, "projection_status": "fresh"}')
    checks = ops_cli._external_health_checks(_probe_root(tmp_path))
    assert checks == [{"id": "fake-dep", "state": "ok", "required": False, "detail": "200"}]
    assert fake_urlopen["url"] == "http://127.0.0.1:43199/health"
    assert fake_urlopen["timeout"] == 2
    assert ops_cli._health_drifts(checks) == []


def test_probe_self_reported_code_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]) -> None:
    monkeypatch.setenv("FAKE_DEP_PORT", "43199")
    fake_urlopen["response"] = _FakeResponse('{"code_drift": true}')
    checks = ops_cli._external_health_checks(_probe_root(tmp_path))
    assert checks[0]["state"] == "code_drift"
    assert ops_cli._health_drifts(checks) == []  # 未声明 require_health ⇒ 纯观测
    required = _materialize_registry(
        tmp_path / "req",
        """  - id: fake-dep
    path: %s
    require_health: true
    health:
      env: FAKE_DEP_PORT
      path: /health""" % tmp_path,
    )
    promoted = ops_cli._external_health_checks(required)
    assert promoted[0]["required"] is True
    drifts = ops_cli._health_drifts(promoted)
    assert len(drifts) == 1 and drifts[0]["id"] == "fake-dep"
    assert drifts[0]["scheduler"] == "external"


def test_probe_connection_failure_is_unreachable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]) -> None:
    monkeypatch.setenv("FAKE_DEP_PORT", "43199")
    fake_urlopen["raise"] = urllib.error.URLError("connection refused")
    checks = ops_cli._external_health_checks(_probe_root(tmp_path))
    assert checks[0]["state"] == "unreachable"


def test_probe_http_error_is_undetermined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]) -> None:
    monkeypatch.setenv("FAKE_DEP_PORT", "43199")
    fake_urlopen["raise"] = urllib.error.HTTPError(
        "http://127.0.0.1:43199/health", 500, "boom", None, None  # type: ignore[arg-type]
    )
    checks = ops_cli._external_health_checks(_probe_root(tmp_path))
    assert checks[0]["state"] == "undetermined"
    assert "HTTP 500" in checks[0]["detail"]


def test_probe_non_object_body_is_undetermined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]) -> None:
    monkeypatch.setenv("FAKE_DEP_PORT", "43199")
    fake_urlopen["response"] = _FakeResponse("[1, 2, 3]")
    checks = ops_cli._external_health_checks(_probe_root(tmp_path))
    assert checks[0]["state"] == "undetermined"


def test_probe_absent_port_env_is_undetermined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]) -> None:
    monkeypatch.delenv("FAKE_DEP_PORT", raising=False)
    checks = ops_cli._external_health_checks(_probe_root(tmp_path))
    assert checks[0]["state"] == "undetermined"
    assert fake_urlopen["url"] is None  # 没有 env 就根本没有发起请求


def test_probe_non_numeric_port_env_is_undetermined(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]) -> None:
    monkeypatch.setenv("FAKE_DEP_PORT", "http://example.invalid")
    checks = ops_cli._external_health_checks(_probe_root(tmp_path))
    assert checks[0]["state"] == "undetermined"
    assert fake_urlopen["url"] is None


def test_probe_unparsable_registry_is_empty_not_failure(tmp_path: Path) -> None:
    """§7⑨ 的形状: 读坏的 registry 不得折叠成「没有条目」再报错, 也不得向上抛。"""
    root = tmp_path
    target = root / REGISTRY_REL
    target.parent.mkdir(parents=True)
    target.write_text("schema: x\nroots: [\n  broken: : :\n", encoding="utf-8")
    assert ops_cli._external_health_checks(root) == []


def test_probe_require_health_validation_shapes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]) -> None:
    monkeypatch.setenv("FAKE_DEP_PORT", "43199")
    # true 但没有 health 块
    no_health = _materialize_registry(
        tmp_path / "a", """  - id: fake-dep
    path: %s
    require_health: true""" % tmp_path
    )
    checks = ops_cli._external_health_checks(no_health)
    assert checks[0]["required"] is True and checks[0]["state"] == "undetermined"
    assert len(ops_cli._health_drifts(checks)) == 1
    # 非布尔取值一律拒, 且按 required 处理 (含糊声明不能静默降级成 observe-only)
    for literal in ("'true'", '"yes"', "1", "[]" , "null"):
        odd = _materialize_registry(
            tmp_path / f"b-{literal}",
            """  - id: fake-dep
    path: %s
    require_health: %s
    health:
      env: FAKE_DEP_PORT
      path: /health""" % (tmp_path, literal),
        )
        got = ops_cli._external_health_checks(odd)
        assert got[0]["required"] is True, literal
        assert got[0]["state"] == "undetermined", literal
        assert "只接受 true" in got[0]["detail"], literal


def test_yaml_truthy_words_fold_to_required_before_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]
) -> None:
    """`require_health: yes` 经 PyYAML 1.1 折叠成 True ⇒ 同样升级为 required, 不是静默失效。

    §7①「YAML 的静默折叠」一族: 写 `yes` 的人以为在声明, 值却是别的形状就更危险; 这里钉住
    「无论写 true/yes/on 都算声明」, 并把「非布尔」与「没声明」区分开。
    """
    monkeypatch.setenv("FAKE_DEP_PORT", "43199")
    fake_urlopen["response"] = _FakeResponse('{"code_drift": false}')
    for word in ("yes", "on", "True"):
        assert yaml.safe_load(f"v: {word}")["v"] is True, word
        root = _materialize_registry(
            tmp_path / word,
            """  - id: fake-dep
    path: %s
    require_health: %s
    health:
      env: FAKE_DEP_PORT
      path: /health""" % (tmp_path, word),
        )
        got = ops_cli._external_health_checks(root)
        assert got[0]["required"] is True, word
        assert got[0]["state"] == "ok", word
        assert len(ops_cli._health_drifts(got)) == 0, word


def test_entries_without_health_block_stay_out_of_the_probe(tmp_path: Path) -> None:
    root = _materialize_registry(
        tmp_path, """  - id: fake-dep
    path: %s
    kind: local_git""" % tmp_path
    )
    assert ops_cli._external_health_checks(root) == []


# ── 4. 缺省不改变 check-signals 的判定 (done_when-4) ───


def test_default_readings_keep_drift_plane_empty(
    monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]
) -> None:
    """真实登记表 + ok / 不可达 两种读数: 升级后的 drift 都必须是 0 条。"""
    doc = yaml.safe_load((REPO / REGISTRY_REL).read_text(encoding="utf-8"))
    assert not any("require_health" in item for item in doc["roots"])

    monkeypatch.setenv("ZHIXING_OBSERVATORY_PORT", "43199")
    fake_urlopen["response"] = _FakeResponse('{"code_drift": false}')
    assert ops_cli._health_drifts(ops_cli._external_health_checks(REPO)) == []

    fake_urlopen["raise"] = urllib.error.URLError("service down")
    checks = ops_cli._external_health_checks(REPO)
    assert [item["state"] for item in checks] == ["unreachable"]
    assert ops_cli._health_drifts(checks) == []

    monkeypatch.delenv("ZHIXING_OBSERVATORY_PORT", raising=False)
    assert ops_cli._health_drifts(ops_cli._external_health_checks(REPO)) == []


def test_probe_folds_any_exception_into_undetermined(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """探测器坏掉不得影响调用方: urlopen 抛任何异常 (含 AssertionError) 都折叠成 undetermined。

    这也是 hermetic 的一半 —— 另一半是每个用例都用 fake_urlopen 钉住请求 URL, 见
    test_probe_classifies_ok。
    """

    def _boom(*a: object, **kw: object) -> None:
        raise AssertionError("探测装置自身炸了")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    monkeypatch.setenv("ZHIXING_OBSERVATORY_PORT", "43199")
    checks = ops_cli._external_health_checks(REPO)
    assert checks[0]["state"] == "undetermined"
    assert "AssertionError" in checks[0]["detail"]
    assert ops_cli._health_drifts(checks) == []


# ── 5. pinned_sha 不得参与任何判定 (§2) ────────────────


def _pinned_sha_reads(path: Path) -> list[int]:
    """代码里出现 `pinned_sha` 这个词的行号 (AST 常量/属性, 注释与 docstring 看不见)。"""
    hits: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Constant) and node.value == "pinned_sha":
            hits.append(node.lineno)
        elif isinstance(node, ast.Attribute) and node.attr == "pinned_sha":
            hits.append(node.lineno)
    return hits


def _registry_consumer_sources() -> list[Path]:
    """读过这份登记表的 .py —— 扫描面由登记表自己的文件名导出, 不手写名单。

    范围不能是「整个 bin/」: `bin/gac/agent-clone.py` 里 `pinned_sha` 是 submodule gitlink
    pin 的既有概念 (实测 11 处, 且那里拿它跟 live HEAD 比较是正确行为), 与本契约无关。
    过宽的 detector 只能靠豁免清单通过, 而豁免清单正是 §7 里被点名的失效形状。
    """
    found: list[Path] = []
    for base in (REPO / "bin", REPO / "projects" / "omo" / "src"):
        if not base.is_dir():  # 子模块未 init 时这一面不存在, 不构成假绿 (下面另有非空断言)
            continue
        found.extend(
            p
            for p in base.rglob("*.py")
            if "external-write-roots" in p.read_text(encoding="utf-8", errors="replace")
        )
    return sorted(found)


def test_no_registry_consumer_reads_pinned_sha() -> None:
    sources = _registry_consumer_sources()
    names = {str(p.relative_to(REPO)) for p in sources}
    assert {"bin/lib/repo_root.py", "bin/ops/cli.py"} <= names, names  # 扫描面非空
    offenders = {str(p.relative_to(REPO)): _pinned_sha_reads(p) for p in sources}
    assert {k: v for k, v in offenders.items() if v} == {}


UNRELATED_PINNED_SHA_SITES = frozenset(
    {
        "bin/gac/agent-clone.py",
        "bin/gac/clone-lifecycle.py",
        "bin/gac/test_agent_clone.py",
        "bin/_archive/obsolete_tests/test_agent_clone.py",  # 上一行的归档副本
    }
)


def test_repo_wide_pinned_sha_sites_are_the_reviewed_gitlink_list() -> None:
    """全 bin/ 读数钉成集合相等 (§7③): 那三处是 submodule gitlink pin 的既有同名词。

    保留这条是因为「只扫消费者」会漏掉未来某人在别的 bin/ 脚本里新建一份 registry
    读取路径。判据不是「bin/ 里没有这个词」(实测 13 处 / 4 个文件, 全与本契约无关), 而是
    「出现这个词的文件 == 已评审名单」且「名单里的文件都不引用这份登记表」。
    """
    hits = {
        str(p.relative_to(REPO))
        for p in (REPO / "bin").rglob("*.py")
        if _pinned_sha_reads(p)
    }
    assert hits == set(UNRELATED_PINNED_SHA_SITES)
    for rel in hits:
        assert "external-write-roots" not in (REPO / rel).read_text(encoding="utf-8")


def test_pinned_sha_detector_is_not_a_no_op(tmp_path: Path) -> None:
    """合成违规自证 (§7②): 消费者里注入一条真比较, 判据必须点名它; 只写在注释里不得命中。"""
    consumer = tmp_path / "bin" / "bad-consumer.py"
    consumer.parent.mkdir(parents=True)
    consumer.write_text(
        'REG = ".omo/_truth/registry/external-write-roots.yaml"\n'
        "def gate(entry, observed):\n"
        "    return entry[\"pinned_sha\"] == observed\n",
        encoding="utf-8",
    )
    bystander = tmp_path / "bin" / "unrelated.py"
    bystander.write_text("def gate():\n    return 1  # pinned_sha 在这里是 gitlink 概念\n", encoding="utf-8")
    ok_only = tmp_path / "bin" / "honest.py"
    ok_only.write_text(
        'REG = ".omo/_truth/registry/external-write-roots.yaml"\n'
        '"""pinned_sha 只做溯源, 不参与判定。"""\n',
        encoding="utf-8",
    )
    scanned = [
        p
        for p in (consumer, bystander, ok_only)
        if "external-write-roots" in p.read_text(encoding="utf-8")
    ]
    assert scanned == [consumer, ok_only]  # 扫描面按登记表引用筛, 与 bystander 无关
    hits = {p.name: _pinned_sha_reads(p) for p in scanned}
    assert hits["bad-consumer.py"] == [3]
    assert hits["honest.py"] == []  # 只在 docstring 里出现 ⇒ AST 看不见


def test_pinned_sha_mutation_leaves_classification_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_urlopen: dict[str, Any]
) -> None:
    """部署仓 HEAD ≠ registry pinned_sha 是**常态** (§2): 分类必须与 pinned_sha 取值无关。"""
    monkeypatch.setenv("FAKE_DEP_PORT", "43199")
    fake_urlopen["response"] = _FakeResponse('{"code_drift": false, "dashboard_code_oid": "e021642b"}')
    readings = []
    for sha in ("c2a8471b4a222ecc2eef38eecf66e2e2ebe7eb07", "0" * 40):
        root = _materialize_registry(
            tmp_path / sha[:7],
            """  - id: fake-dep
    path: %s
    pinned_sha: %s
    health:
      env: FAKE_DEP_PORT
      path: /health""" % (tmp_path, sha),
        )
        readings.append(ops_cli._external_health_checks(root))
    assert readings[0] == readings[1] == [
        {"id": "fake-dep", "state": "ok", "required": False, "detail": "200"}
    ]
