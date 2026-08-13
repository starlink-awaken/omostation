"""Generate and verify the human Documents domain index from L4 manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
L4_SRC = ROOT / "projects" / "l4-kernel" / "src"
if str(L4_SRC) not in sys.path:
    sys.path.insert(0, str(L4_SRC))

from l4_kernel.manifest_registry import ManifestRegistry

BEGIN = "<!-- AUTOGEN:L4-DOMAIN-MANIFESTS BEGIN -->"
END = "<!-- AUTOGEN:L4-DOMAIN-MANIFESTS END -->"
LEGACY_BEGIN = "<!-- AUTOGEN:DOMAIN-TABLES BEGIN (domain-sync.py --write · 勿手改) -->"
LEGACY_END = "<!-- AUTOGEN:DOMAIN-TABLES END -->"
MIGRATED_HEADER = """# DOMAIN-INDEX — Documents 域注册表

> **SSOT**: 域身份、根路径、生命周期与权限策略只来自
> `@公共/_control/L4-DOMAIN-REGISTRY.yaml` 及其由 L4 Manifest Registry
> 校验的 `DOMAIN.yaml`。
> 本文件是人类导航投影，不可反向修改 Registry 或 Manifest。

"""
MIGRATED_FOOTER = """
> 历史说明：2026-08-13 前本文件投影过 legacy `registry.py` 的全局路径清单；
> 该清单不再是 Documents 域注册的来源。
"""


def render(registry: ManifestRegistry) -> str:
    """Render only validated domain identity fields for the human index."""

    domains = registry.list_all()
    lines = [
        BEGIN,
        "",
        f"> 由 `{registry.index_path.name}` 及其已校验的 `DOMAIN.yaml` 生成；勿手改。",
        "",
        f"## {len(domains)} 个已验证 Documents 域",
        "",
        "| ID | 名称 | Archetype | Authority | 路径 |",
        "|---|---|---|---|---|",
    ]
    lines.extend(
        (
            f"| {manifest.id} | {manifest.display_name} | {manifest.archetype} | "
            f"{manifest.authority_policy} | {manifest.root} |"
        )
        for manifest in domains
    )
    lines.extend(["", END])
    return "\n".join(lines) + "\n"


def replace_projection(index_path: Path, projection: str) -> None:
    """Replace one explicit generated block without touching surrounding notes."""

    text = index_path.read_text(encoding="utf-8")
    if BEGIN in text and END in text:
        begin, end = BEGIN, END
    elif LEGACY_BEGIN in text and LEGACY_END in text:
        begin, end = LEGACY_BEGIN, LEGACY_END
    else:
        raise ValueError(f"index requires {BEGIN} and {END}")
    before, remainder = text.split(begin, 1)
    _existing, after = remainder.split(end, 1)
    if begin == LEGACY_BEGIN:
        index_path.write_text(
            MIGRATED_HEADER + projection + MIGRATED_FOOTER, encoding="utf-8"
        )
        return
    index_path.write_text(before + projection + after, encoding="utf-8")


def current_projection(index_path: Path) -> str:
    """Return exactly the existing generated block for byte-for-byte drift checks."""

    text = index_path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise ValueError(f"index requires {BEGIN} and {END}")
    _before, remainder = text.split(BEGIN, 1)
    existing, _after = remainder.split(END, 1)
    return BEGIN + existing + END + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "write"))
    parser.add_argument("--domain-registry", type=Path, required=True)
    parser.add_argument("--index-path", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        registry = ManifestRegistry.load(args.domain_registry)
        projection = render(registry)
        if args.command == "write":
            replace_projection(args.index_path, projection)
            return 0
        if current_projection(args.index_path) != projection:
            print("DOMAIN-INDEX projection drift", file=sys.stderr)
            return 1
    except (OSError, UnicodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
