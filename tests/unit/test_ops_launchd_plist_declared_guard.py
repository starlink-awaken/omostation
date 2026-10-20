"""仓内 plist ⇒ `.omo/_truth/registry/services.yaml` 必须声明它的 label（BET-Y2Q4-T10-258 ISC-4）。

结构性根因是「commit 了 plist 却没同时 commit 注册表条目」这一形，而
`com.omostation.omo-state-sync` 是它的第一例：#4816 把 plist 入了库、本机装上并在排程，
注册表里却没有它。当时的门禁只看得见这缺口 —— `gen-service-configs.py --reality-check`
的 E2 是「本机已装 ∖ 注册表声明」，要一台装过机的机器才出得来。

本守卫故意不看机器：它只比对本检出里的两个仓内表面（`bin/ops/launchd/*.plist` 的
`Label` 与 services.yaml 的 `label`），所以 CI 干净检出可复现，而且在 plist 提交的那一步
就能点名缺口，不必等某个 profile 的 launchd 状态。

根用 `__file__` 反推而不是 `repo_root.code_root()`：被检的两个对象都是与本用例同一次
检出的仓内文件，而 `code_root()` 在未声明 profile 时兜底到 canonical 检出 —— 那是一棵
可能与本 PR 交付内容无关的陈旧树（PITFALL-COO-006）。
"""

from pathlib import Path
import plistlib
import re

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLIST_DIR = ROOT / "bin" / "ops" / "launchd"
SERVICES = ROOT / ".omo" / "_truth" / "registry" / "services.yaml"

# 已知的仓内未声明债 —— 必须是「实测集合 == 本清单」，不是「实测 ⊆ 本清单」：
# 补齐一条却不从这里的删掉就应当红，否则豁免面会变成只增不减的暗账。
# · com.omostation.arch-health-weekly —— 本机从未安装，属 #97 / BET-Y2Q4-T10-237 那条
#   「注册在案但未装机」的裁定面，归署名决定，不在本轮。
# · com.omostation.panorama-refresh-guard —— 曾因其 plist 注释含 `--` 而整份不可解析，
#   该缺陷已由 BET-Y2Q4-T10-260 消除（argv 移到脚本模块文档）。缺口本身不变：它未声明、
#   且本机未装机 —— 登记与否属署名面（task #124），不因文件变合法而自动放行。
ALLOWLIST = frozenset(
    {
        "com.omostation.arch-health-weekly",
        "com.omostation.panorama-refresh-guard",
    }
)

_ALLOWLIST_REASON = {
    "com.omostation.arch-health-weekly": "本机从未安装，装机与否属署名裁定（#97）",
    "com.omostation.panorama-refresh-guard": "本机未装机，登记与否属署名裁定（#124）",
}


def labels_from_plists(paths: list[Path]) -> dict[str, str | None]:
    """plist 文件名 → 其 `Label`；解析不出 Label 记 None（由 test 单独判罪，不得静默放过）。"""
    out: dict[str, str | None] = {}
    for path in sorted(paths):
        label: str | None = None
        try:
            label = plistlib.loads(path.read_bytes()).get("Label")
        except Exception:
            # 非法 XML 也不许逃过守卫：退回文本抽取，仍能认出它是谁的 plist。
            match = re.search(
                r"<key>Label</key>\s*<string>(.*?)</string>",
                path.read_text(encoding="utf-8", errors="replace"),
                re.S,
            )
            label = match.group(1) if match else None
        out[path.name] = label
    return out


def declared_labels(services_text: str) -> set[str]:
    """services.yaml 是两份文档（frontmatter + 主体），主体文档才含 services。"""
    body = list(yaml.safe_load_all(services_text))[-1]
    return {s["label"] for s in body["services"] if s.get("label")}


def find_undeclared(plist_labels: dict[str, str | None], declared: set[str]) -> set[str]:
    """纯函数检测器：仓内 plist 的 label 缺席于注册表声明集合的那些。"""
    return {label for label in plist_labels.values() if label and label not in declared}


SERVICES_TEXT = SERVICES.read_text(encoding="utf-8")
PLIST_LABELS = labels_from_plists(list(PLIST_DIR.glob("*.plist")))
DECLARED = declared_labels(SERVICES_TEXT)
UNDECLARED = find_undeclared(PLIST_LABELS, DECLARED)


def test_guard_surface_is_not_empty_and_names_this_bets_label() -> None:
    """反空转的正向对照：plist 面非空，且本轮新登记的那条 label 两侧都在。

    没有这一条，「glob 零命中」或「services 取了错文档而空集」都会让下面所有断言
    以「违规 0」的形态通过（AGENTS.md §7「扫源码的门禁必须自证」的假绿面）。
    """
    assert PLIST_LABELS, "bin/ops/launchd 下必须扫到 plist"
    assert "com.omostation.omo-state-sync.plist" in PLIST_LABELS
    assert PLIST_LABELS["com.omostation.omo-state-sync.plist"] == "com.omostation.omo-state-sync"
    assert "com.omostation.omo-state-sync" in DECLARED


def test_no_repo_plist_lacks_a_label_key() -> None:
    assert sorted(name for name, label in PLIST_LABELS.items() if label is None) == []


def test_every_repo_plist_is_declared_or_allowlisted() -> None:
    offenders = UNDECLARED - ALLOWLIST
    assert offenders == set(), f"仓内 plist 未登记进 services.yaml 的 label: {offenders}"


def test_allowlist_is_exactly_the_measured_undebt() -> None:
    """集合相等（不是子集）：债还一条就必须从豁免里摘一条。"""
    assert UNDECLARED == ALLOWLIST, (
        f"实测未声明集合与豁免清单不再相等: 实测={sorted(UNDECLARED)} 清单={sorted(ALLOWLIST)}"
    )


def test_allowlist_reasons_point_at_real_files() -> None:
    assert set(_ALLOWLIST_REASON) == ALLOWLIST
    for name, label in PLIST_LABELS.items():
        if label in ALLOWLIST:
            assert (PLIST_DIR / name).is_file()


def test_detector_fires_on_a_synthetic_missing_declaration() -> None:
    """自证：把本轮那条声明从 declared 里摘掉，检测器必须当场点名它。

    「改后为 0」与「改前为 N」由同一对断言产出 —— 少了这一条，一个结构性看不见
    缺口的检测器也能让前面所有用例绿。
    """
    crippled = set(DECLARED) - {"com.omostation.omo-state-sync"}
    fired = find_undeclared(PLIST_LABELS, crippled)
    assert fired == ALLOWLIST | {"com.omostation.omo-state-sync"}, fired


def test_detector_does_not_fire_on_the_current_tree() -> None:
    assert UNDECLARED - ALLOWLIST == set()


def test_services_body_doc_carries_the_namespace_partition_too() -> None:
    """services 与 launchd_namespace 必须同文档：拆开会令 load_services() 取到空 services,
    于是 --check 在零服务上「漂移 0」通过 —— 门禁自己变假绿（该文件 6279 行的注释）。"""
    body = list(yaml.safe_load_all(SERVICES_TEXT))[-1]
    assert body["services"], "主体文档必须含非空 services"
    assert "launchd_namespace" in body, "launchd_namespace 不得另起一份文档"


def test_text_fallback_reports_label_of_an_unparseable_plist(tmp_path: Path) -> None:
    """非法 XML 不许从守卫视野里消失 —— 用合成样本钉，不钉某个真实缺陷还活着。

    本用例原先直接拿真实那份 plist 断言「解析必须失败」，于是它把自己钉在一次性的缺陷上：
    BET-Y2Q4-T10-260 修好文件本体后该前提按构造消失（AGENTS.md §7②「时钟炸弹」的反面：
    fixture 写死一个会被授权修掉的真实状态）。换成合成样本之后，回退分支的覆盖与
    那份 plist 修没修**解耦**，而「不许静默放过」这条不变式仍然有牙齿。
    """
    synthetic = tmp_path / "com.example.synthetic-malformed.plist"
    synthetic.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<!-- 手动触发: python3 bin/gac/x.py --json --dry-run —— XML 注释体内禁止连续两个半角连字符 -->\n"
        '<plist version="1.0"><dict>\n'
        "<key>Label</key><string>com.example.synthetic-malformed</string>\n"
        "</dict></plist>\n",
        encoding="utf-8",
    )
    try:
        plistlib.loads(synthetic.read_bytes())
    except Exception:
        pass
    else:
        raise AssertionError("合成样本必须不可解析，否则本用例没有验到文本抽取回退分支")
    assert labels_from_plists([synthetic]) == {
        "com.example.synthetic-malformed.plist": "com.example.synthetic-malformed"
    }


def test_the_xml_fixed_plist_parses_and_stays_an_open_admission() -> None:
    """文件本体已合法（BET-Y2Q4-T10-260），但登记与否仍是署名面 —— 两条都得钉住。

    把该 label 登记进 services.yaml 而无人署名 ⇒ `test_allowlist_is_exactly_the_measured_undebt`
    当场红（UNDECLARED 少一条而清单没少）；豁免理由若还写着「XML 非法」⇒ 本用例红（陈旧指针，
    AGENTS.md §7⑥）。
    """
    name = "com.omostation.panorama-refresh-guard.plist"
    label = PLIST_LABELS[name]
    assert label == "com.omostation.panorama-refresh-guard"
    parsed = plistlib.loads((PLIST_DIR / name).read_bytes())
    assert parsed["Label"] == label
    assert label in UNDECLARED, "该机未装且未登记，缺口必须仍然可见"
    assert label in ALLOWLIST
    assert "XML 非法" not in _ALLOWLIST_REASON[label], "豁免理由陈旧：该缺陷已由 BET-Y2Q4-T10-260 消除"
