#!/usr/bin/env python3
"""omo baseline write — dependency-baseline.yaml 合规写入 broker CLI (C2 方案 C).

gen-dependency-baseline --write 算 mismatched patch (业务), subprocess 调本 CLI,
本 CLI 调 apply_baseline_patches (broker, src/omo/ 路径豁免 direct_omo_io).
跟 omo_readiness (P63) 先例同构: gen 算 payload → omo broker CLI 写.

用法:
  omo baseline write --patches '{"apscheduler": ">=3.11.2"}' [--actor <name>] [--source-ref <ref>]
"""
from __future__ import annotations

import argparse
import json
import sys

from omo.omo_ingress_registry_writes import apply_baseline_patches
from omo.omo_paths import find_omo_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="omo baseline write — dependency-baseline patch broker (C2 方案 C)",
    )
    parser.add_argument("action", choices=["write"], help="动作 (目前仅 write, 跟 omo readiness snapshot 同构)")
    parser.add_argument(
        "--patches",
        required=True,
        help='JSON object {dep_name: new_baseline}, e.g. \'{"apscheduler": ">=3.11.2"}\'',
    )
    parser.add_argument("--actor", default="gen-dependency-baseline", help="actor (谁触发 patch)")
    parser.add_argument("--source-ref", default="", help="source ref (commit sha / agent id)")
    args = parser.parse_args(argv)

    try:
        patches = json.loads(args.patches)
    except json.JSONDecodeError as exc:
        print(f"❌ --patches JSON 无效: {exc}", file=sys.stderr)
        return 2
    if not isinstance(patches, dict) or not patches:
        print("❌ --patches 必须是非空 JSON object {name: baseline}", file=sys.stderr)
        return 2

    omo_dir = find_omo_dir()
    if omo_dir is None:
        print("❌ 找不到 .omo 目录 (不在 workspace?)", file=sys.stderr)
        return 1

    try:
        result = apply_baseline_patches(
            omo_dir,
            patches=patches,
            actor=args.actor,
            source_ref=args.source_ref,
        )
    except FileNotFoundError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
