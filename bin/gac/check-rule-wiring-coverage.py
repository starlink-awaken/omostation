#!/usr/bin/env python3
"""规则接线覆盖率清单 (rule wiring inventory) — 让"声明了规则但没人执行"可见.

背景 (2026-09-21 实证, 今天主题的最大规模实例):
  追查 17 项 debt item 的 `gate_level` 用了契约外的 `P0/P1/P2` (契约与 omo
  `GATE_ORDER` 都是 {gate,watchlist,none}, 非法值 → rank=99 → **severity 最高
  的债务在 review queue 里反而最后被看到**) 时发现:

    - 契约文档 `.omo/standards/debt-gate-level-enum.md` 声明了值域 ✓
    - `projects/omo/src/omo/omo_debt_review_queue.py:13` 实现了 `GATE_ORDER` ✓
    - L0 注册表声明了 `CR-DEBT-GATE-ENUM-01` ✓
    - 但**没有任何执行器引用它** —— 文档 §4 自己写着"实现位置: 待补" ✗

  ⇒ 违规数据能存在 3 个月 (06-18 定契约 → 09-21 才发现), 根因是**唯一该执行
  它的守卫从未接线**。

本工具做**清单**而非门禁 —— 并且必须说清它的**已知假阳边界**:

  三个规则注册表使用**互不相同的 id 词汇**:
    - `.omo/_truth/registry/governance-checks.yaml`  → `CR-X4-HEALTH-SSOT` 等 86 条
    - `projects/ecos/.../L0-constraints.yaml`        → `CR-SFOP-05` 等 77 条 (子模块)
    - `bin/gac/check-l0-constraints.py` 实际实现      → `X2-C05` / `CR-OMO-SURFACE-01` 等
  实测: `check-l0-constraints.py` 对 governance-checks 的 86 个 id **零引用** ——
  它用自己的命名。所以"某 id 在可执行语料里查不到"**有两种可能**:
    (a) 真未接线 (如 CR-DEBT-GATE-ENUM-01)
    (b) 已实现但**换了名字** (别名)
  在没有 id 映射表之前, 本工具**无法区分** (a) 与 (b), 因此:
    - 只输出**候选清单**, 不判 fail
    - 退出码恒 0 (除非 --strict 用于巡检提醒)

  要把它变成真门禁, 前置工作是**建立 id 别名映射** (逐条人工确认), 那是
  owner 的语义决策, 不是本工具能自动做的。

用法:
    python3 bin/gac/check-rule-wiring-coverage.py [--json] [--strict]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
GOV_CHECKS = _ROOT / ".omo" / "_truth" / "registry" / "governance-checks.yaml"
L0_SUBMODULE = _ROOT / "projects" / "ecos" / "src" / "ecos" / "ssot" / "registry" / "L0-constraints.yaml"
ALIAS_MAP = _ROOT / "bin" / "gac" / "registry-alias-map.yaml"

# 可执行语料: 真正的执行体所在处 (不含注册表自身, 否则自引用会全绿)
EXEC_CORPUS_GLOBS = [
    "bin/**/*.py",
    "bin/**/*.sh",
    # F4: 子模块源码树也是执行面 (ecos 的 L0 registry 与自身执行栈、agora/omo/runtime/cockpit
    # 等全部落在这里)。此前只扫根仓 bin/, 使 submodule 里实现的规则 id 结构性不可见。
    "projects/*/src/**/*.py",
    "projects/*/src/**/*.sh",
    ".githooks/*",
    ".github/workflows/*.yml",
]
# F4: bin/ 下无扩展名的可执行体 (e.g. bin/ssot/mypy-baseline-gate 实现的 mypy-truth 规则)。
# bin/**/*.py + bin/**/*.sh 结构性抓不到它们; 这里按 "无扩展名 + (可执行位 || shebang)" 收录。
EXTENSIONLESS_EXEC_GLOBS = ["bin/**"]
EXEC_MANIFEST = _ROOT / ".omo" / "_truth" / "registry" / "hook-manifest.yaml"

# F3: 豁免/遗留清单数据 (exemption DATA) — 不是执行面。
# LEGACY_CR_IDS (governance-convergence-lint.py:65) 是 R-GOV-1 准入豁免白名单;
# 规则 id 出现在其中 ≠ 被执行。接线判定必须把这些块剥掉, 否则"豁免数据"会被
# 当成"接线证据"。
EXEMPTION_BLOCKS: list[tuple[str, re.Pattern]] = [
    (
        "bin/gac/governance-convergence-lint.py",
        re.compile(r"LEGACY_CR_IDS\s*=\s*\{(?:[^}]|\n)*?\n\}", re.S),
    ),
]

# F5: 检测器自身的文件不得进入"执行语料" — 本文件的 docstring 会以示例形式
# 提到真实规则 id (如 CR-X4-HEALTH-SSOT), 若把自己算进语料, "自引用" 会让
# 只出现在文档示例里的规则看起来已接线 (与 _archive/_registry 排除同一原则:
# 注册表/文档 ≠ 执行面)。
SELF_MODULE = Path(__file__).resolve()

_ID_RE = re.compile(r"^CR-[A-Z0-9-]+$|^X[1-4]-C\d{2}$|^CS-\d+$")

# governance-checks has 4 entries using lowercase hyphen form (x1-audit-chain etc.)
# while 86 use CR-* form. The regex above matches only CR-*, so we add
# lowercase xN-name as a valid id form for both _rule_ids extraction AND
# _implemented_ids corpus scan.
_ID_RE_LOWER = re.compile(r"^[xX][1-4]-[a-z][a-z0-9-]+$")


def _load_alias_map() -> dict[str, set[str]]:
    """Load alias map → {canonical_id: {aliases including self}}.

    Used by inventory() to detect "implemented but renamed" IDs.
    """
    if not ALIAS_MAP.is_file():
        return {}
    try:
        import yaml
        with ALIAS_MAP.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return {}
    out: dict[str, set[str]] = {}
    for entry in data.get("aliases", []) or []:
        canon = str(entry.get("canonical", "")).strip()
        if not canon:
            continue
        aliases = {canon}
        for a in entry.get("aliases", []) or []:
            aliases.add(str(a).strip())
        out[canon] = aliases
    return out


def _resolve_via_alias(rule_id: str, alias_map: dict[str, set[str]]) -> str | None:
    """Return canonical id if rule_id matches any alias (case-insensitive)."""
    rule_lower = rule_id.lower()
    for canon, aliases in alias_map.items():
        if rule_id in aliases or canon == rule_id:
            return canon
        lowered = {a.lower() for a in aliases}
        if rule_lower in lowered:
            return canon
    return None



def _load_retired() -> set[str]:
    """retired: 清单 — 弃用/收窄/并入决策条目, 从接线候选统计分离 (T10-07 批次四)."""
    if not ALIAS_MAP.is_file():
        return set()
    try:
        import yaml
        with ALIAS_MAP.open(encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return set()
    return {str(x).strip() for x in (data.get("retired") or []) if str(x).strip()}


def _is_extensionless_exec(f: Path) -> bool:
    """bin/ 下无扩展名的可执行体: (可执行位 || shebang 头) 且非目录."""
    if not f.is_file():
        return False
    if f.suffix:
        return False
    try:
        mode = f.stat().st_mode
        if mode & 0o111:
            return True
    except OSError:
        pass
    try:
        with f.open("r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(2).startswith("#!")
    except OSError:
        return False


def _exemption_block_pattern(path: Path) -> re.Pattern | None:
    """若该文件是豁免数据来源, 返回需要剥离的块正则; 否则 None."""
    rel = path.relative_to(_ROOT).as_posix()
    for rel_path, pat in EXEMPTION_BLOCKS:
        if rel == rel_path:
            return pat
    return None


def _read_cleaned(f: Path) -> str:
    """读取文件文本; 若是豁免数据来源, 剥离其中的豁免块 (F3)."""
    text = f.read_text(encoding="utf-8", errors="ignore")
    pat = _exemption_block_pattern(f)
    if pat is not None:
        text = pat.sub("", text)
    return text


def _exec_corpus() -> str:
    parts = []
    for pat in EXEC_CORPUS_GLOBS:
        for f in _ROOT.glob(pat):
            if not f.is_file():
                continue
            # F5: 检测器自证排除 — 本文件自己 (或其任何 glob 命中形态) 不是执行面
            if f.resolve() == SELF_MODULE.resolve():
                continue
            if "_archive" in f.parts or "_registry" in f.parts:
                continue
            try:
                parts.append(_read_cleaned(f))
            except OSError:
                continue
    for pat in EXTENSIONLESS_EXEC_GLOBS:
        for f in _ROOT.glob(pat):
            if "_archive" in f.parts or "_registry" in f.parts:
                continue
            if not _is_extensionless_exec(f):
                continue
            # F5: 同上 — 本文件不进语料 (本文件是 .py, .suffix 非空, 此处为保险)
            if f.resolve() == SELF_MODULE.resolve():
                continue
            try:
                parts.append(_read_cleaned(f))
            except OSError:
                continue
    if EXEC_MANIFEST.is_file():
        parts.append(EXEC_MANIFEST.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _rule_ids(path: Path) -> list[str]:
    if not path.is_file():
        return []
    try:
        import yaml
        docs = [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8", errors="ignore"))
                if isinstance(d, dict)]
    except Exception:
        return []
    ids: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            v = o.get("id")
            if isinstance(v, str) and (_ID_RE.match(v) or _ID_RE_LOWER.match(v)):
                ids.append(v)
            for x in o.values():
                walk(x)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    for d in docs:
        walk(d)
    return ids


def _implemented_ids(corpus: str) -> list[str]:
    """执行体里出现的规则 id (含别名形态 X2-C05 等)."""
    found = sorted({m.group(0) for m in re.finditer(
        r"\b(?:CR-[A-Z0-9][A-Z0-9-]{2,}|X[1-4]-C\d{2}|CS-\d{2})\b", corpus)})
    return found


def inventory() -> dict:
    corpus = _exec_corpus()
    gov = _rule_ids(GOV_CHECKS)
    l0 = _rule_ids(L0_SUBMODULE)
    l0_available = bool(l0)
    alias_map = _load_alias_map()
    retired = _load_retired()

    # An ID is "wired" if:
    #   (a) its string form appears literally in the corpus, OR
    #   (b) any alias of it appears in the corpus (alias map cross-walk)
    def is_wired(rule_id: str) -> bool:
        if rule_id in corpus:
            return True
        canon = _resolve_via_alias(rule_id, alias_map)
        if not canon:
            return False
        aliases = alias_map[canon]
        return any(a in corpus for a in aliases)

    # F3: exemption-only 判定 — id 出现在豁免清单 (LEGACY_CR_IDS 等) 但不在
    # 执行面语料里。我们把"接线"分成两桶: wired (执行面) vs exemption-only
    # (豁免数据引用)。豁免数据 ≠ 执行面, 不计入 wired。
    def exemption_only(rule_id: str) -> bool:
        # 先按执行面判定; 命中执行面则不是 exemption-only
        if is_wired(rule_id):
            return False
        # 只在其 id 出现于豁免块/清单数据, 且执行面语料里查不到时才算
        # 豁免-only 引用 (输出层将归入 unreferenced 候选, 但带豁免标记)
        # 实现: 无法从已剥离语料反查豁免块 — 直接看原始全局豁免清单 id。
        for rel_path, pat in EXEMPTION_BLOCKS:
            f = _ROOT / rel_path
            if not f.is_file():
                continue
            try:
                raw = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            block = pat.search(raw)
            if block and rule_id in block.group(0):
                return True
        return False

    def unreferenced(ids):
        return [i for i in ids if not is_wired(i)]

    gov_un = [i for i in unreferenced(gov) if i not in retired]
    l0_un = [i for i in unreferenced(l0) if i not in retired]
    impl = _implemented_ids(corpus)

    # government exemption-only ids (declared but only in exemption lists)
    gov_exempt_only = sorted({i for i in gov if exemption_only(i)})
    l0_exempt_only = sorted({i for i in l0 if exemption_only(i)})

    # also: IDs implemented but not declared (alias-resolved count)
    declared_all = set(gov) | set(l0)
    impl_resolved = []
    for iid in impl:
        if iid in declared_all:
            continue
        canon = _resolve_via_alias(iid, alias_map)
        if canon and canon in declared_all:
            impl_resolved.append({"id": iid, "canonical": canon})

    return {
        "sources": {
            "governance-checks": {
                "declared": len(gov),
                "unreferenced": len(gov_un),
                "wired": len(gov) - len(gov_un) - len(retired & set(gov)),
                "exemption_only_referenced": len(gov_exempt_only),
                "retired": sorted(retired & set(gov)),
                "retired_count": len(retired & set(gov)),
                "alias_map_loaded": bool(alias_map),
                "alias_map_size": len(alias_map),
            },
            "L0-constraints(submodule)": {
                "declared": len(l0), "unreferenced": len(l0_un),
                "wired": len(l0) - len(l0_un) - len(retired & set(l0)),
                "exemption_only_referenced": len(l0_exempt_only),
                "available": l0_available,
                "note": None if l0_available else
                "子模块未初始化 → 该源跳过 (CI 里有); 本地不得据此判全貌",
            },
        },
        "executed_ids_in_corpus": len(impl),
        "candidates_unwired": {
            "governance-checks": gov_un,
            "L0-constraints": l0_un,
        },
        "exemption_only_ids": {
            "governance-checks": gov_exempt_only,
            "L0-constraints": l0_exempt_only,
        },
        "implemented_via_alias": impl_resolved,
        "caveat": (
            "无法区分『真未接线』与『已实现但换了名字』—— 三个注册表 id 词汇互异, "
            "且 check-l0-constraints.py 对 governance-checks 的 id 零引用 (用自己的 "
            "X2-C05 等命名)。建立 id 别名映射是前置的人工工作, 在此之前本清单"
            "**不作为门禁**。\n"
            "F3 (2026-10-07): 接线判定已把豁免/遗留清单数据 (LEGACY_CR_IDS 等) 从"
            "执行面语料中剥离 —— exception data ≠ execution surface。exemption_only_referenced "
            "列出仅被豁免清单引用的 id, 它们计入 unreferenced 候选。\n"
            "F4 (2026-10-07): 语料扩展到子模块源码树 (projects/*/src) 与 bin/ 无扩展名"
            "可执行体 (如 bin/ssot/mypy-baseline-gate)。submodule 里实现的规则 id 不再"
            "结构性不可见; 相应地, 之前靠 'wired via same id' 误判的 id 会重新计为 wired。\n"
            "F5 (2026-10-07): 检测器自身的文件 (check-rule-wiring-coverage.py) 不再计入"
            "执行语料 —— 本文件 docstring 以示例形式提到的规则 id (如 CR-X4-HEALTH-SSOT)"
            "此前会因自引用被判为 wired, 而它实际上没有任何执行器引用。自证排除后, "
            "这类只存在于检测器文档里的 id 会如实进入 unreferenced 候选。\n"
            "F6 (2026-10-09): retired 清单 (registry-alias-map.yaml::retired) 现在同时"
            "过滤 L0-constraints 的接线候选 —— 前提不再成立且已在注册表标注 "
            "lifecycle: removed 的规则不再被当作『待接线新人』。L0 debt closeout 把 20 条"
            "(OPC 7 + eCOS-v6 3 + AGT 10) 标为 removed (superseded_by 逐条可查), 并为 27 条"
            "『实现但换了名字』的 L0 规则补 alias 映射 (evidence 指向真实宿主文件)。\n"
            "F7 (2026-10-10, adversarial audit): 明确本清单数字的含义边界 —— "
            "『wired』= 规则 id 字符串/别名 token 出现在执行语料里, 是**文本接线覆盖**"
            "(text coverage)，**不是**强制力证明 (enforcement)。每条 alias 的强制力必须"
            "逐条人工核验: (a) 宿主是否真实执行该谓词, (b) 规则是否可红 (合成违规能触发"
            "非零退出)。audit F2/F3 已把 7 条『伪接线』取下 (CR-TRIGGER-01..06, "
            "CR-STRATEGY-02 退回候选集), 并为 CR-OMO-DIRECT-IO-01 / CR-OMNIBUS-01 / "
            "CR-KOS-CONSENSUS-RAG-01 强化宿主。因此: 数字下降 ≠ 规则已强制执行; "
            "未接线候选数只说明『还没有任何文本引用』, 接线数只说明『有宿主引用』。\n"
            "注意: registry-alias-map.yaml 的 evidence.* 块 (如 evidence.bin_executor) 是"
            "人工填写的说明性字段, **本清单不读它们**; 接线判定只依据 alias 字符串在"
            "执行语料中的出现。alias-map 里指向 bin/_archive/ 的 evidence 引用是历史"
            "说明, 不代表当前接线。"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--top", type=int, default=20, help="最多列出多少候选 (默认 20)")
    ap.add_argument("--strict", action="store_true",
                    help="存在未接线候选 → exit 1 (仅巡检提醒; 因含假阳, 勿接入门禁)")
    args = ap.parse_args(argv)

    inv = inventory()
    if args.json:
        print(json.dumps(inv, ensure_ascii=False, indent=1))
        total_un = (inv["sources"]["governance-checks"]["unreferenced"]
                    + inv["sources"]["L0-constraints(submodule)"]["unreferenced"])
        return 1 if (args.strict and total_un) else 0

    s = inv["sources"]
    print("规则接线覆盖率清单 (报告型, **非门禁**)")
    print(f"  执行体语料里出现的规则 id: {inv['executed_ids_in_corpus']} 个")
    print(f"  governance-checks:  声明 {s['governance-checks']['declared']} / "
          f"未引用候选 {s['governance-checks']['unreferenced']}"
          f" (wired {s['governance-checks']['wired']}, 仅豁免清单引用 "
          f"{s['governance-checks']['exemption_only_referenced']})")
    l0s = s["L0-constraints(submodule)"]
    if l0s["available"]:
        print(f"  L0-constraints(子仓): 声明 {l0s['declared']} / 未引用候选 {l0s['unreferenced']}"
              f" (wired {l0s['wired']}, 仅豁免清单引用 {l0s['exemption_only_referenced']})")
    else:
        print(f"  L0-constraints(子仓): {l0s['note']}")
    ex = inv["exemption_only_ids"]
    if ex["L0-constraints"] or ex["governance-checks"]:
        print("\n  仅被豁免/遗留清单引用 (F3: 不再计为 wired):")
        for i in ex["L0-constraints"]:
            print(f"    ! {i} (L0, 豁免-only)")
        for i in ex["governance-checks"]:
            print(f"    ! {i} (governance-checks, 豁免-only)")
    cand = inv["candidates_unwired"]["governance-checks"]
    if cand:
        print(f"\n  候选 (governance-checks, 前 {args.top}):")
        for i in cand[:args.top]:
            print(f"    ? {i}")
        if len(cand) > args.top:
            print(f"    … 另 {len(cand) - args.top} 个")
    l0_cand = inv["candidates_unwired"]["L0-constraints"]
    if l0s["available"] and l0_cand:
        print(f"\n  候选 (L0-constraints, 前 {args.top}):")
        for i in l0_cand[:args.top]:
            print(f"    ? {i}")
        if len(l0_cand) > args.top:
            print(f"    … 另 {len(l0_cand) - args.top} 个")
    print(f"\n  ⚠️ 已知假阳边界: {inv['caveat']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
