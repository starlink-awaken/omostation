"""scheduler-compile 的 launchd 平面 shadow 段 (T16-01) 与 label 解析契约."""

from __future__ import annotations

import importlib.util
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "scheduler_compile", WORKSPACE / "bin" / "scheduler-compile.py"
)
assert _spec and _spec.loader
sc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sc)


def _reg():
    import yaml

    m = {}
    for doc in yaml.safe_load_all((WORKSPACE / ".omo" / "cron" / "registry.yaml").read_text(encoding="utf-8")):
        if isinstance(doc, dict):
            m.update(doc)
    return m


def test_every_active_launchd_entry_resolves_to_an_installed_label() -> None:
    """全部 active launchd 登记必须能解析到一个真实已安装的 label。

    这是 T16-01 升 warning 的前置条件: 命中率不到 100% 时判据不成立, 会立刻产生
    假阳性。2026-09-29 前仅 7/17 —— 9 条 resident-launchd-* 的真实前缀是 com.l4. 而非
    com.omostation., 另 1 条 zhixing-host-drift-hourly-active 的 label 丢了后缀。
    """
    import plistlib

    la = Path.home() / "Library" / "LaunchAgents"
    controlled = WORKSPACE / "runtime" / "cron"
    installed = set()
    corrupt: dict[str, str] = {}

    def _scan(directory: Path) -> None:
        for p in directory.glob("com.*.plist"):
            try:
                installed.add(plistlib.loads(p.read_bytes()).get("Label", p.stem))
            except Exception as exc:  # noqa: BLE001
                # 2026-09-30: 原实现是 `continue` —— 于是**损坏的 plist 被当成「不存在」**,
                # 与「确实没装」混为一谈。本机 57 个 plist 里有 47 个被覆写成裸 JSON
                # ProgramArguments, launchd 根本无法加载, 而这个测试当时只把它们算作
                # "missing"。损坏是另一种状态, 必须显式报出, 否则一次批量覆写事故
                # 在断言里长得跟「还没部署」一模一样。
                corrupt[p.stem] = f"{type(exc).__name__}: {exc}"

    # launchd 平面的登记由两种形态满足:
    #   1. 已安装 agent  ~/Library/LaunchAgents/<label>.plist
    #   2. 受控观测产物  runtime/cron/<label>.plist (仓内跟踪, 不安装)
    # 原实现只看 (1), 于是 5 个「受控观测」被误判为缺失。
    _scan(la)
    _scan(controlled)

    # 期望存在的 label 对应的文件若是损坏的, 直接判失败 —— 不允许降级成 "missing"
    expected = {
        (j.get("label") or f"com.omostation.{j['name']}")
        for j in _reg()["jobs"]
        if "launchd" in (j.get("planes") or []) and j.get("status", "active") == "active"
    }
    broken_expected = sorted(expected & set(corrupt))
    assert not broken_expected, "以下 label 的 plist 文件存在但无法解析(损坏, 非缺失):\n" + "\n".join(
        f"  {label}: {corrupt[label]}" for label in broken_expected
    )

    jobs = _reg()["jobs"]
    entries = [j for j in jobs if "launchd" in (j.get("planes") or []) and j.get("status", "active") == "active"]
    assert entries, "未找到 active launchd 登记 —— 测试前提不成立"

    missing = []
    for j in entries:
        label = j.get("label") or f"com.omostation.{j['name']}"
        if label not in installed:
            missing.append(f"{j['name']} -> {label}")
    assert not missing, "以下 launchd 登记既无已安装 agent 也无 runtime/cron 受控产物:\n" + "\n".join(
        missing
    )


def _controlled_plists() -> set[str]:
    return {p.stem for p in (WORKSPACE / "runtime" / "cron").glob("com.*.plist")}


def test_active_launchd_entries_are_authorized_by_services_registry() -> None:
    """每条 active+launchd 登记必须有授权: services.yaml 放行, 或存在受控观测产物。

    2026-09-30 事故的根因是**登记与现实脱节**:
      - `.omo/cron/registry.yaml` 把 17 个服务标为 `status: active` + `planes: [launchd]`,
        隐含「应该已就位」;
      - 其中 6 个在 `.omo/_truth/registry/services.yaml`(launchd 服务 SSOT) 里是
        `enabled: false` / `generate: false` / 无此条目, 即**本就不该存在**;
      - 另有 5 个是「受控观测」, 形态是仓内 `runtime/cron/<label>.plist` 而非已安装 agent。

    原测试只查已安装 agent, 于是受控观测被误判, 真正的 6 个未授权项则一直失败。
    本测试锁死判据, 避免「降级」只成为一次性数据修改。
    """
    import yaml

    services: dict[str, dict] = {}
    text = (WORKSPACE / ".omo" / "_truth" / "registry" / "services.yaml").read_text(
        encoding="utf-8"
    )
    for doc in yaml.safe_load_all(text):
        if not isinstance(doc, dict):
            continue
        for svc in doc.get("services") or []:
            if isinstance(svc, dict) and svc.get("label"):
                services[svc["label"]] = svc

    controlled = _controlled_plists()
    unauthorized = []
    for job in _reg()["jobs"]:
        if "launchd" not in (job.get("planes") or []):
            continue
        if job.get("status", "active") != "active":
            continue
        label = job.get("label") or f"com.omostation.{job['name']}"
        if label in controlled:
            continue  # 受控观测形态
        svc = services.get(label)
        if svc is None:
            unauthorized.append(f"{job['name']} -> {label} (services.yaml 无此 label, 且无受控产物)")
        elif not svc.get("enabled", True):
            unauthorized.append(f"{job['name']} -> {label} (enabled=false, 且无受控产物)")
        elif not svc.get("generate", True):
            unauthorized.append(f"{job['name']} -> {label} (generate=false, 且无受控产物)")
    assert not unauthorized, (
        "以下 active launchd 登记缺少 services.yaml 授权也无受控产物 —— 以 services.yaml "
        "为准, 应降级为 proposed:\n" + "\n".join("  " + u for u in unauthorized)
    )


def test_downgraded_entries_carry_ssot_conflict_trace() -> None:
    """降级过的条目必须留痕, 否则事后无从判断它为何不是 active。"""
    conflicted = [j for j in _reg()["jobs"] if j.get("ssot_conflict")]
    assert conflicted, "预期存在被 services.yaml 否决而降级的条目"
    for job in conflicted:
        assert job.get("status") != "active", f"{job['name']} 带 ssot_conflict 却仍是 active"
        assert "services.yaml" in job["ssot_conflict"], f"{job['name']} 的 ssot_conflict 未指明依据"


def test_explicit_label_field_overrides_synthesis() -> None:
    """显式 label 字段优先于合成 —— 合成只是缺省值, 不是判据。"""
    d = _reg()
    explicit = {j["name"]: j["label"] for j in d["jobs"] if j.get("label")}
    assert explicit, "登记源中应存在显式 label 字段"
    for name, label in explicit.items():
        assert label != f"com.omostation.{name}", f"{name} 的显式 label 与合成值相同, 该字段无必要"


def test_shadow_segment_never_blocks_the_gate() -> None:
    """shadow 阶段 launchd 段不得影响 crontab 的 ok 判定 (ADR-0457 三段式)。"""
    res = sc.check_drift()
    assert res["ok"] is True, f"crontab 口径应保持通过: {res}"
    ld = res["launchd"]
    assert ld["mode"] == "shadow"
    assert ld["blocks_gate"] is False
