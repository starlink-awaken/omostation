"""BET-Y2Q4-T10-206 —— launchd 现实双向门禁 E1–E4 的可失败性证明。

契约: docs/superpowers/specs/2026-09-27-service-registry-reality-closure.md

门禁的现实侧输入是 ~/Library/LaunchAgents —— 那既不是 CI 上存在的东西, 也不该被单元测试
读写。所以这里全部用构造出来的 plist + 注入的枚举器: 测 reality_check() 的判定逻辑,
不碰本机现实。plutil 枚举本身(契约 C1)只能在 macOS 手工核对, 见 spec §8。

反例条款(spec §8)是这些测试存在的理由: 给门禁一条注册表里没说的 owned label 必须红。
"""

from __future__ import annotations

import importlib.util
import json
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
