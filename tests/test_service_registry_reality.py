"""BET-Y2Q4-T10-206 —— launchd 现实双向门禁 E1–E4 的可失败性证明。

契约: docs/superpowers/specs/2026-09-27-service-registry-reality-closure.md

门禁的现实侧输入是 ~/Library/LaunchAgents —— 那既不是 CI 上存在的东西, 也不该被单元测试
读写。所以这里全部用构造出来的 plist + 注入的枚举器: 测 reality_check() 的判定逻辑,
不碰本机现实。plutil 枚举本身(契约 C1)只能在 macOS 手工核对, 见 spec §8。

反例条款(spec §8)是这些测试存在的理由: 给门禁一条注册表里没说的 owned label 必须红。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

MODULE_PATH = Path(__file__).parents[1] / "bin" / "mof" / "gen-service-configs.py"
TEST_ROOT = "/Users/tester/Workspace"
FRONT_MATTER = """---
status: ssot
lifecycle: registry
owner: governance-team
last-reviewed: 2026-09-27
---
"""
E1_OK = {"status": "ok", "drift_count": 0, "drifts": []}
PREFIXES = ["com.omostation"]


def _module():
    spec = importlib.util.spec_from_file_location("service_reality_under_test", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mark_disabled(registry: Path, label: str) -> None:
    """在该 label 的 service 条目里补 `enabled: false`。

    `_write_registry` 用 yaml.safe_dump 展开成多行, 所以只能在 label 行之后
    定位其 `generate:` 行并续写 —— 不能靠单行字符串替换。
    """
    lines = registry.read_text(encoding="utf-8").split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip() == f"label: {label}")
    for i in range(start, min(start + 6, len(lines))):
        if lines[i].strip() == "generate: false":
            indent = " " * (len(lines[i]) - len(lines[i].lstrip()))
            lines.insert(i + 1, f"{indent}enabled: false")
            break
    else:
        raise AssertionError(f"未在 {label} 条目里找到 generate: false 行")
    registry.write_text("\n".join(lines), encoding="utf-8")


def _write_registry(tmp_path: Path, labels: list[str], policy: dict, *, split_docs: bool = False) -> Path:
    """services 与 launchd_namespace 同文档 —— load_services() 取 docs[-1] 的硬约束。

    split_docs=True 造的是错误形状(namespace 单独成第三文档), 用来证明门禁不会因此假绿。
    """
    services = [{"id": f"svc.{label}", "label": label, "scheduler": "launchd", "generate": False} for label in labels]
    if split_docs:
        text = f"{FRONT_MATTER}---\n{yaml.safe_dump({'services': services}, sort_keys=False)}"
        text += f"---\n{yaml.safe_dump({'launchd_namespace': policy}, sort_keys=False)}\n"
    else:
        body = {"services": services, "launchd_namespace": policy}
        text = f"{FRONT_MATTER}---\n{yaml.safe_dump(body, sort_keys=False)}"
    path = tmp_path / "services.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _install(dir_: Path, labels: list[str], *, malformed: tuple[str, ...] = ()) -> list[dict]:
    """落真 plist 文件(E3 读字节), 返回注入给 reality_check 的"本机现实"。"""
    dir_.mkdir(parents=True, exist_ok=True)
    rows = []
    for label in labels:
        path = dir_ / f"{label}.plist"
        comment = "    <!-- audit --strict, mode drwx------ -->\n" if label in malformed else ""
        path.write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            f'<plist version="1.0">\n{comment}<dict>\n'
            f"    <key>Label</key>\n    <string>{label}</string>\n"
            f"    <key>ProgramArguments</key>\n    <array>\n"
            f"        <string>{TEST_ROOT}/bin/{label}.py</string>\n"
            "    </array>\n</dict>\n</plist>\n",
            encoding="utf-8",
        )
        payload = {"Label": label, "ProgramArguments": [f"{TEST_ROOT}/bin/{label}.py"]}
        rows.append(
            {
                "file": path.name,
                "path": path,
                "label": label,
                "plutil_ok": True,
                "blob": json.dumps(payload),
                "program_arguments": payload["ProgramArguments"],
            }
        )
    return rows


@pytest.fixture
def run(tmp_path, monkeypatch):
    """reality_check() 的可注入版本: 本机现实由测试给出, 不读 ~/Library/LaunchAgents。"""
    module = _module()

    def _run(rows: list[dict], registry: Path, **kwargs) -> dict:
        monkeypatch.setattr(module, "enumerate_launchd_plists", lambda _dir: rows)
        e1 = kwargs.pop("e1", E1_OK)
        root = kwargs.pop("workspace_root", TEST_ROOT)
        return module.reality_check(registry, registry.parent, e1=e1, workspace_root=root, **kwargs)

    _run.module = module
    return _run


def test_import_does_not_eagerly_resolve_the_root(tmp_path, monkeypatch) -> None:
    """C5 的惰性面: 无规范检出时 import 仍要成功。

    canonical_root() 定位不到就 raise 是规定行为(不许退回 __file__), 但解析必须发生在
    真要落笔机器级配置的那一刻 —— bin/ops/cli.py 只要本模块的纯函数, 单元测试更是完全不碰根。
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OMOSTATION_ROOT", raising=False)

    module = _module()
    with pytest.raises(RuntimeError):
        module.workspace()


def test_dot_segment_prefix_does_not_collapse_namespaces(run) -> None:
    """com.omo 是 com.omostation 的字符串前缀, 但不是它的点段前缀。"""
    module = run.module

    assert module.match_workspace_prefix("com.omostation.autopilot", ["com.omo"]) is None
    assert module.match_workspace_prefix("com.omo.model-scheduler", ["com.omo"]) == "com.omo"
    assert module.match_workspace_prefix("com.omo", ["com.omo"]) == "com.omo"


def test_e2_zero_when_every_owned_installed_label_is_declared(tmp_path, run) -> None:
    labels = ["com.omostation.autopilot", "com.omostation.sig-poller"]
    registry = _write_registry(tmp_path, labels, {"workspace_prefixes": PREFIXES, "exempt_labels": []})

    report = run(_install(tmp_path / "launchd", labels), registry)

    assert report["ok"], report["findings"]
    assert report["e2_undeclared"] == 0
    assert report["e4_prefix_ok"] is True
    assert report["installed_total"] == 2 == report["owned_installed"] == report["owned_declared"]


def test_gate_goes_red_when_an_owned_label_is_missing_from_registry(tmp_path, run) -> None:
    """spec §8 的反例: 本机在跑、注册表没说出来 ⇒ 必须红, 否则门禁是第二个"零检查的绿"。"""
    registry = _write_registry(
        tmp_path, ["com.omostation.autopilot"], {"workspace_prefixes": PREFIXES, "exempt_labels": []}
    )
    rows = _install(tmp_path / "launchd", ["com.omostation.autopilot", "com.omostation.new-daemon"])

    report = run(rows, registry)

    assert report["ok"] is False
    assert report["e2_undeclared"] == 1
    assert report["e2_undeclared_labels"] == ["com.omostation.new-daemon"]
    assert any(f.startswith("E2") for f in report["findings"])


def test_exempt_bucket_is_outside_the_equality(tmp_path, run) -> None:
    """未登记的第三方 job 不触发 E2 —— 要求登记它是范畴错误(契约 C2)。"""
    registry = _write_registry(
        tmp_path,
        ["com.omostation.autopilot"],
        {
            "workspace_prefixes": PREFIXES,
            "exempt_labels": [{"label": "com.macpaw.CleanMyMac5.Updater", "classification": "external"}],
        },
    )
    rows = _install(tmp_path / "launchd", ["com.omostation.autopilot", "com.macpaw.CleanMyMac5.Updater"])

    report = run(rows, registry)

    assert report["ok"], report["findings"]
    assert report["external"] == 1
    assert report["e2_undeclared"] == 0


def test_illegal_classification_is_red(tmp_path, run) -> None:
    """分类拼错不能默认当成 external —— 那会把 owned 分区悄悄缩小。"""
    registry = _write_registry(
        tmp_path,
        ["com.omostation.autopilot"],
        {"workspace_prefixes": PREFIXES, "exempt_labels": [{"label": "com.local.thing", "classification": "maybe"}]},
    )
    rows = _install(tmp_path / "launchd", ["com.omostation.autopilot", "com.local.thing"])

    report = run(rows, registry)

    assert report["ok"] is False
    assert any("classification 非法" in f for f in report["findings"])
    assert any("未分区 label" in f for f in report["findings"]), "非法分类要落到分区外, 不能崩也不能被当成豁免"


def test_unpartitioned_label_is_red_not_silently_dropped(tmp_path, run) -> None:
    """没进任何一张表的 label ⇒ unmanaged_unknown ⇒ 红。默认归属等于盲区重来。"""
    registry = _write_registry(tmp_path, ["com.omostation.autopilot"], {"workspace_prefixes": PREFIXES, "exempt_labels": []})
    rows = _install(tmp_path / "launchd", ["com.omostation.autopilot", "com.unknown.thing"])

    report = run(rows, registry)

    assert report["ok"] is False
    assert report["e4_prefix_ok"] is False
    assert any("未分区 label" in f and "com.unknown.thing" in f for f in report["findings"])
    assert report["e2_undeclared"] == 0, "未分区不等于已声明: 既不能过 E2, 也不能静默消失"


def test_missing_prefix_table_fails_closed(tmp_path, run) -> None:
    """分区数据缺失时门禁必须红, 不能报"本机 0 条 owned、E2 天然满足"。"""
    registry = _write_registry(tmp_path, [], {"workspace_prefixes": [], "exempt_labels": []})
    rows = _install(tmp_path / "launchd", ["com.omostation.autopilot"])

    report = run(rows, registry)

    assert report["ok"] is False
    assert any("workspace_prefixes 缺失" in f for f in report["findings"])


def test_exempt_entry_shadowed_by_prefix_is_red(tmp_path, run) -> None:
    """豁免项同时命中 owned 前缀 = 死数据, 说明两张表自相矛盾。"""
    registry = _write_registry(
        tmp_path,
        [],
        {"workspace_prefixes": PREFIXES, "exempt_labels": [{"label": "com.omostation.legacy", "classification": "external"}]},
    )
    rows = _install(tmp_path / "launchd", ["com.omostation.legacy"])

    report = run(rows, registry)

    assert report["ok"] is False
    assert any("遮蔽" in f for f in report["findings"])


def test_exempt_entry_no_longer_installed_is_red(tmp_path, run) -> None:
    """卸载了的第三方 job 留在豁免表里 = 登记陈旧, 否则分区表慢慢变成垃圾桶。"""
    registry = _write_registry(
        tmp_path,
        [],
        {"workspace_prefixes": PREFIXES, "exempt_labels": [{"label": "com.gone.away", "classification": "external"}]},
    )
    rows = _install(tmp_path / "launchd", ["com.omostation.autopilot"])

    report = run(rows, registry)

    assert report["ok"] is False
    assert any("登记陈旧" in f and "com.gone.away" in f for f in report["findings"])


def test_label_filename_mismatch_is_red(tmp_path, run) -> None:
    """launchd 按内容注册、工具按文件名核对 —— 两者不一致时门禁口径自相矛盾。"""
    registry = _write_registry(tmp_path, ["com.omostation.b"], {"workspace_prefixes": PREFIXES, "exempt_labels": []})
    rows = _install(tmp_path / "launchd", ["com.omostation.a"])
    rows[0]["label"] = "com.omostation.b"

    report = run(rows, registry)

    assert report["ok"] is False
    assert any("Label 与文件名不一致" in f for f in report["findings"])


def test_plutil_unparseable_plist_is_red(tmp_path, run) -> None:
    """枚举口径自身失败时不能报"本机 0 条"蒙混过关。"""
    registry = _write_registry(tmp_path, ["com.omostation.a"], {"workspace_prefixes": PREFIXES, "exempt_labels": []})
    rows = _install(tmp_path / "launchd", ["com.omostation.a"])
    rows[0]["plutil_ok"] = False

    report = run(rows, registry)

    assert report["ok"] is False
    assert any("plutil 无法解析" in f for f in report["findings"])


def test_e3_reports_strict_xml_debt_without_dropping_the_job(tmp_path, run) -> None:
    """契约 C1 的根: 注释含 `--` 时 plistlib 拒绝、plutil 照收、launchd 照跑。

    E3 把它记成债(报告项), 但它仍出现在 installed_total / E2 里 —— 不能因为解析器挑文件
    就让一条在跑的常驻从门禁的视野里消失。
    """
    module = run.module
    registry = _write_registry(
        tmp_path, ["com.omostation.a", "com.omostation.expiry-radar"], {"workspace_prefixes": PREFIXES, "exempt_labels": []}
    )
    rows = _install(tmp_path / "launchd", ["com.omostation.a", "com.omostation.expiry-radar"], malformed=("com.omostation.expiry-radar",))

    assert module.plist_strict_well_formed(rows[0]["path"]) is True
    assert module.plist_strict_well_formed(rows[1]["path"]) is False

    report = run(rows, registry)

    assert report["e3_lint_debt"] == 1
    assert report["e3_malformed_labels"] == ["com.omostation.expiry-radar"]
    assert report["installed_total"] == 2
    assert report["ok"], report["findings"]  # E3 是报告项, 不阻塞


def test_e1_drift_surfaces_as_finding(tmp_path, run) -> None:
    registry = _write_registry(tmp_path, ["com.omostation.a"], {"workspace_prefixes": PREFIXES, "exempt_labels": []})
    rows = _install(tmp_path / "launchd", ["com.omostation.a"])

    report = run(rows, registry, e1={"status": "drift", "drift_count": 1, "drifts": ["com.omostation.a"]})

    assert report["ok"] is False
    assert report["e1_status"] == "drift"
    assert any(f.startswith("E1") for f in report["findings"])


def test_namespace_as_a_separate_document_does_not_go_green(tmp_path, run) -> None:
    """load_services() 取 docs[-1]: namespace 单独成文档会把 services 清空。

    危险的不是解析失败, 而是 --check 在零服务上"漂移 0"通过。这里证明 E2 不受这个假绿保护:
    本机现实仍在, owned 分区无声明可比 ⇒ 红。
    """
    module = run.module
    registry = _write_registry(
        tmp_path, ["com.omostation.a"], {"workspace_prefixes": PREFIXES, "exempt_labels": []}, split_docs=True
    )

    assert module.load_services(registry) == []
    report = run(_install(tmp_path / "launchd", ["com.omostation.a"]), registry)

    assert report["ok"] is False
    assert report["e2_undeclared"] == 1


def test_workspace_scoped_is_report_only(tmp_path, run) -> None:
    """不引用本仓路径的 owned job 照样受 E2 约束 —— ws 字面量不是归属谓词(B4 爆炸半径另算)。"""
    registry = _write_registry(
        tmp_path, ["com.omostation.a", "com.omostation.outside"], {"workspace_prefixes": PREFIXES, "exempt_labels": []}
    )
    rows = _install(tmp_path / "launchd", ["com.omostation.a", "com.omostation.outside"])
    rows[1]["blob"] = json.dumps({"Label": rows[1]["label"], "ProgramArguments": ["/Users/tester/.local/share/elsewhere/run.py"]})

    report = run(rows, registry)

    assert report["ok"], report["findings"]
    assert report["installed_total"] == report["owned_installed"] == 2
    assert report["workspace_scoped"] == 1


# ---------------------------------------------------------------------------
# E5: E2 的反方向 —— 「声明了但没装」
# ---------------------------------------------------------------------------


def test_e5_red_when_enabled_service_is_not_installed(tmp_path, run) -> None:
    """注册表声明 enabled=true(在跑)而本机没装 ⇒ 必须红。

    这是 E2 的反方向。E2 只查「装了但没声明」(孤儿); 没有 E5 时, 一次批量误删
    可以完全静默 —— 2026-09-30 按 `generate: false` 误删 27 个 enabled 服务时,
    E2 一声未响, 因为它只看多出来的, 不看少掉的。
    """
    declared = ["com.omostation.autopilot", "com.omostation.sig-poller"]
    registry = _write_registry(
        tmp_path, declared, {"workspace_prefixes": PREFIXES, "exempt_labels": []}
    )

    # 只装其中一个 —— 另一个「声明在跑却没装」
    report = run(_install(tmp_path / "launchd", declared[:1]), registry)

    assert report["ok"] is False, report["findings"]
    assert report["e5_enabled_missing"] == 1
    assert report["e5_enabled_missing_labels"] == ["com.omostation.sig-poller"]
    assert any("E5" in f and "sig-poller" in f for f in report["findings"])


def test_e5_red_when_disabled_service_is_still_installed(tmp_path, run) -> None:
    """注册表声明 enabled=false(已退役)而本机仍装着 ⇒ 必须红(应移入 archived/)。

    2026-10-02: E5 首次运行即抓到本会话自己留下的一处残留
    (com.omo.model-scheduler 声明 disabled 却仍装着)。
    """
    label = "com.omostation.autopilot"
    registry = _write_registry(
        tmp_path, [label], {"workspace_prefixes": PREFIXES, "exempt_labels": []}
    )
    _mark_disabled(registry, label)

    report = run(_install(tmp_path / "launchd", [label]), registry)

    assert report["ok"] is False, report["findings"]
    assert report["e5_disabled_residual"] == 1
    assert report["e5_disabled_residual_labels"] == [label]


def test_e5_zero_when_registry_and_host_agree(tmp_path, run) -> None:
    """enabled=true 全装、enabled=false 全不装 ⇒ E5 必须静默, 不得制造假阳性。"""
    live = ["com.omostation.autopilot"]
    dead = "com.omostation.retired"
    registry = _write_registry(
        tmp_path, live + [dead], {"workspace_prefixes": PREFIXES, "exempt_labels": []}
    )
    _mark_disabled(registry, dead)

    report = run(_install(tmp_path / "launchd", live), registry)

    assert report["e5_enabled_missing"] == 0
    assert report["e5_disabled_residual"] == 0
    assert not any(f.startswith("E5") for f in report["findings"]), report["findings"]


# ---------------------------------------------------------------------------
# T262 · measured_base —— 这份读数是在哪棵树上量出来的
# 契约: docs/superpowers/specs/2026-10-20-launchd-reality-check-base-provenance.md
# ---------------------------------------------------------------------------

BASE_FIELDS = ("registry_file", "registry_sha256", "head", "origin_main", "base_state", "behind_count")
BASE_STATES = ("equal", "behind", "diverged", "unknown")


def _git(root: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


@pytest.fixture
def git_root(tmp_path) -> Path:
    """一个有 origin/main 的最小真仓库 —— 测 base_state 三态, 不碰任何真实检出。

    初始分支名必须钉死, 不能交给 `git init` 决定：`init.defaultBranch` 是 host 配置
    —— macOS 的 Xcode 系统 gitconfig 给 main, 干净 CI runner 给 master —— 而分叉用例
    按名字 `checkout main`。本机 `HOME=<空>` 也照不出这条(Xcode 那份系统配置不受 HOME 影响),
    必须在 `HOME/.gitconfig` 写 master 才复刻得出来。
    """
    root = tmp_path / "wt"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    (root / "seed").write_text("1\n", encoding="utf-8")
    _git(root, "add", "seed")
    _git(root, "commit", "-q", "-m", "one")
    return root


def test_measured_base_has_exactly_the_six_contract_fields(tmp_path, run) -> None:
    """C1 · 六字段齐, 且 base_state 只在四值里取。"""
    registry = _write_registry(tmp_path, ["com.omostation.a"], {"workspace_prefixes": PREFIXES})
    report = run(_install(tmp_path / "launchd", ["com.omostation.a"]), registry)

    base = report["measured_base"]
    assert set(base) == set(BASE_FIELDS), sorted(base)
    assert base["base_state"] in BASE_STATES


def test_measured_base_is_purely_observational(tmp_path, run) -> None:
    """C2 · 零判定效应: 同一现实 + 同一注册表, 只有注入的 base 不同 ⇒ ok/findings 逐字相等。

    判据与被验对象不共享失效模式: 这里让两个 base 在 head/origin_main/base_state/behind_count
    上全不同(behind 12 vs unknown), 若哪天有人把「基座落后」接成一条 finding, 本用例当场红。
    """
    registry = _write_registry(tmp_path, ["com.omostation.a"], {"workspace_prefixes": PREFIXES})
    rows = _install(tmp_path / "launchd", ["com.omostation.a"])

    stale = {
        "registry_file": "stale.yaml", "registry_sha256": "a" * 12, "head": "1111111",
        "origin_main": "2222222", "base_state": "behind", "behind_count": 12,
    }
    clean = {
        "registry_file": "clean.yaml", "registry_sha256": "b" * 12, "head": None,
        "origin_main": None, "base_state": "unknown", "behind_count": None,
    }
    assert stale != clean

    r1 = run(rows, registry, base=stale)
    r2 = run(rows, registry, base=clean)
    assert r1["ok"] == r2["ok"]
    assert r1["findings"] == r2["findings"]
    assert r1["measured_base"] == stale and r2["measured_base"] == clean


def test_stale_base_and_full_base_are_distinguishable_from_output_alone(tmp_path, run) -> None:
    """C3 · 本 BET 的牙齿: 同一份本机现实, 旧基座读数 E2=1 / 新基座读数 E2=0,
    而两个读数仅凭 measured_base 就能分开 —— 因为 registry_sha256 也不同。

    复现的是 2026-10-20 那次假债: 落后 29 个 commit 的检出声称「装了但没登记」5 条,
    而 origin/main 上 E2=0。差别不在机器, 在测量基座。
    """
    full = ["com.omostation.a", "com.omostation.b"]
    rows = _install(tmp_path / "launchd", full)
    policy = {"workspace_prefixes": PREFIXES}

    old_base = _write_registry(tmp_path, ["com.omostation.a"], policy)          # 少了 b 的旧注册表
    (tmp_path / "n").mkdir()
    new_base = _write_registry(tmp_path / "n", full, policy)                    # 登记齐了的注册表

    r_old = run(rows, old_base)
    r_new = run(rows, new_base)

    assert r_old["e2_undeclared"] == 1 and r_new["e2_undeclared"] == 0
    b_old, b_new = r_old["measured_base"], r_new["measured_base"]
    assert b_old["registry_sha256"] != b_new["registry_sha256"]
    assert b_old["base_state"] == b_new["base_state"] == "unknown"  # 同一棵树, 差的只是内容


def test_equal_content_registries_produce_identical_provenance(tmp_path, run) -> None:
    """C3 的变异对照反面: 两份内容逐字节相同的注册表 ⇒ 判别式两侧都必须相等。

    若这条也「不同」, 说明 sha 不跟文件内容走(而是跟路径/时间走), 那 C3 就是假绿。
    """
    policy = {"workspace_prefixes": PREFIXES}
    full = ["com.omostation.a", "com.omostation.b"]
    rows = _install(tmp_path / "launchd", full)

    one = _write_registry(tmp_path / "one", full, policy)
    two = _write_registry(tmp_path / "two", full, policy)
    assert one.read_bytes() == two.read_bytes()

    r1, r2 = run(rows, one), run(rows, two)
    assert r1["measured_base"]["registry_sha256"] == r2["measured_base"]["registry_sha256"]
    assert r1["e2_undeclared"] == r2["e2_undeclared"]


def test_registry_sha256_follows_a_single_byte_change(tmp_path, run) -> None:
    """C5 · 摘要钉的是那份文件本身: 加一个换行, 摘要必须变, 且仍可复算。"""
    labels = ["com.omostation.a"]
    registry = _write_registry(tmp_path, labels, {"workspace_prefixes": PREFIXES})
    rows = _install(tmp_path / "launchd", labels)

    before = run(rows, registry)["measured_base"]["registry_sha256"]
    registry.write_bytes(registry.read_bytes() + b"\n")
    after = run(rows, registry)["measured_base"]["registry_sha256"]

    assert before != after
    assert re.fullmatch(r"[0-9a-f]{12}", after)
    assert hashlib.sha256(registry.read_bytes()).hexdigest().startswith(after)


def test_non_git_root_reports_nulls_not_an_error(tmp_path, run) -> None:
    """C4 · 测量根不是 git 仓库(git archive 对照树、CI 干净检出两类装置面) ⇒ 空值 + unknown, 不炸。

    根用真实存在的目录 —— 测的是「没有 git」而不是「没有这个目录」, 后者已被 TEST_ROOT 用例覆盖。
    """
    registry = _write_registry(tmp_path, ["com.omostation.a"], {"workspace_prefixes": PREFIXES})
    report = run(_install(tmp_path / "launchd", ["com.omostation.a"]), registry,
                 workspace_root=str(tmp_path))

    base = report["measured_base"]
    assert base["base_state"] == "unknown"
    assert base["head"] is None and base["origin_main"] is None and base["behind_count"] is None
    assert base["registry_sha256"] is not None  # 摘要与 git 无关, 装置面缺 git 也不能缺摘要


def test_registry_file_is_reported_relative_to_the_root(tmp_path, run) -> None:
    """C6 · 呈现不含 host 字面量: 注册表在根内时给相对路径。"""
    root = tmp_path / "tree"
    reg_dir = root / ".omo" / "_truth" / "registry"
    reg_dir.mkdir(parents=True)
    registry = _write_registry(reg_dir, ["com.omostation.a"], {"workspace_prefixes": PREFIXES})

    base = run(_install(tmp_path / "launchd", ["com.omostation.a"]), registry,
               workspace_root=str(root))["measured_base"]
    assert base["registry_file"] == ".omo/_truth/registry/services.yaml"
    assert "/Users/" not in base["registry_file"]


def test_equal_when_head_is_origin_main(git_root, tmp_path, run) -> None:
    """equal: HEAD == origin/main ⇒ behind_count=0, 无假债可归因于基座。"""
    _git(git_root, "update-ref", "refs/remotes/origin/main", _git(git_root, "rev-parse", "HEAD"))
    registry = _write_registry(git_root / ".omo" / "_truth" / "registry", [], {"workspace_prefixes": PREFIXES})

    base = run([], registry, workspace_root=str(git_root))["measured_base"]
    assert (base["base_state"], base["behind_count"]) == ("equal", 0)
    assert base["registry_file"] == ".omo/_truth/registry/services.yaml"


def test_behind_counts_commits_ahead_of_the_checkout(git_root, tmp_path, run) -> None:
    """behind: origin/main 前进 2 个 commit ⇒ behind_count=2 且基座可见(head != origin_main)。"""
    head = _git(git_root, "rev-parse", "HEAD")
    _git(git_root, "update-ref", "refs/remotes/origin/main", head)
    for n in (2, 3):
        (git_root / "seed").write_text(f"{n}\n", encoding="utf-8")
        _git(git_root, "add", "seed")
        _git(git_root, "commit", "-q", "-m", f"step{n}")
    tip = _git(git_root, "rev-parse", "HEAD")
    _git(git_root, "update-ref", "refs/remotes/origin/main", tip)
    _git(git_root, "reset", "--soft", head)

    registry = _write_registry(git_root / ".omo" / "_truth" / "registry", [], {"workspace_prefixes": PREFIXES})
    base = run([], registry, workspace_root=str(git_root))["measured_base"]
    assert (base["base_state"], base["behind_count"]) == ("behind", 2)
    assert base["head"] != base["origin_main"]


def test_diverged_when_the_also_has_local_commits(git_root, tmp_path, run) -> None:
    """diverged: 本地有未提交到 main 的 commit 且 origin/main 也前进 ⇒ 不谎报 behind。"""
    base_sha = _git(git_root, "rev-parse", "HEAD")
    (git_root / "seed").write_text("2\n", encoding="utf-8")
    _git(git_root, "add", "seed")
    _git(git_root, "commit", "-q", "-m", "local")
    _git(git_root, "update-ref", "refs/remotes/origin/main", base_sha)

    registry = _write_registry(git_root / ".omo" / "_truth" / "registry", [], {"workspace_prefixes": PREFIXES})
    base = run([], registry, workspace_root=str(git_root))["measured_base"]
    assert (base["base_state"], base["behind_count"]) == ("diverged", 0)


def test_diverged_with_both_sides_moved_is_not_reported_as_behind(git_root, tmp_path, run) -> None:
    """behind>0 且 ahead>0 的真分叉必须是 diverged, 不能被折叠成「只是落后」。

    这是 `behind and not ahead` 里 `not ahead` 那半的唯一覆盖: 上一条用例 behind=0,
    去掉 `not ahead` 也照样绿 —— 判别式的两侧都要有能命中它的输入。
    """
    seed = git_root / "seed"
    _git(git_root, "checkout", "-q", "-b", "side")
    seed.write_text("side\n", encoding="utf-8")
    _git(git_root, "add", "seed")
    _git(git_root, "commit", "-q", "-m", "remote-side")
    _git(git_root, "update-ref", "refs/remotes/origin/main", _git(git_root, "rev-parse", "HEAD"))
    _git(git_root, "checkout", "-q", "main")
    seed.write_text("local\n", encoding="utf-8")
    _git(git_root, "add", "seed")
    _git(git_root, "commit", "-q", "-m", "local-side")

    registry = _write_registry(git_root / ".omo" / "_truth" / "registry", [], {"workspace_prefixes": PREFIXES})
    base = run([], registry, workspace_root=str(git_root))["measured_base"]
    assert (base["base_state"], base["behind_count"]) == ("diverged", 1)
    assert base["head"] != base["origin_main"]


def test_git_facts_follow_the_registry_tree_not_the_passed_root(git_root, tmp_path, run) -> None:
    """证词必须指向被量的那棵树: root 参数指向另一棵树时, head 仍是注册表所在检出的 head。

    实现前的真实错法: CLI 在 worktree 里跑, `workspace()` 解析到 canonical 检出,
    于是拿 canonical 的 HEAD 去标注 worktree 的注册表 —— 自报的基座本身就是假的。
    """
    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    _git(other, "config", "user.email", "t@t")
    _git(other, "config", "user.name", "t")
    (other / "seed").write_text("9\n", encoding="utf-8")
    _git(other, "add", "seed")
    _git(other, "commit", "-q", "-m", "other-tree")

    registry = _write_registry(git_root / ".omo" / "_truth" / "registry", [], {"workspace_prefixes": PREFIXES})
    base = run([], registry, workspace_root=str(other))["measured_base"]

    assert base["head"] == _git(git_root, "rev-parse", "--short", "HEAD")
    assert base["head"] != _git(other, "rev-parse", "--short", "HEAD")
    assert base["registry_file"] == ".omo/_truth/registry/services.yaml"


def test_unprovable_registry_tree_is_unknown_not_the_callers_root(git_root, tmp_path, run) -> None:
    """注册表落在任何仓库之外(`--registry /tmp/x.yaml`)⇒ unknown, 不拿调用方的根凑一个基座。

    与上一条合起来才封住两种假证词: 报错树(M8 退回 root)和报猜测树。宁缺毋假。
    """
    outside = tmp_path / "loose"
    registry = _write_registry(outside, [], {"workspace_prefixes": PREFIXES})
    base = run([], registry, workspace_root=str(git_root))["measured_base"]

    assert base["base_state"] == "unknown"
    assert base["head"] is None and base["behind_count"] is None
    assert base["registry_sha256"] is not None
