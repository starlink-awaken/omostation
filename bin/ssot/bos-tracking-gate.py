#!/usr/bin/env python3
"""BOS 追踪门禁 — GaC 预提交检查

验证:
  1. et/bos-unimplemented.yaml 中的服务在 bos-services.yaml 中标记为 [UNIMPLEMENTED]
  2. bos-services.yaml 中所有 [UNIMPLEMENTED] 服务都在 unimplemented 追踪文件中

违反任一条件 → exit 1（阻止 commit）
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[BOS-TRACKING] ⚠️  pyyaml 未安装, 跳过")
    sys.exit(0)

WORKSPACE = Path(__file__).resolve().parents[2]
BOS_SERVICES = WORKSPACE / "projects" / "agora" / "etc" / "bos-services.yaml"
BOS_UNIMPLEMENTED = WORKSPACE / "projects" / "agora" / "etc" / "bos-unimplemented.yaml"


def main() -> int:
    errors: list[str] = []

    if not BOS_SERVICES.is_file():
        print(f"[BOS-TRACKING] ⚠️  bos-services.yaml 不存在: {BOS_SERVICES}")
        return 0  # 开发环境可能没有子模块 checkout
    if not BOS_UNIMPLEMENTED.is_file():
        print(f"[BOS-TRACKING] ⚠️  bos-unimplemented.yaml 不存在: {BOS_UNIMPLEMENTED}")
        return 0

    services = yaml.safe_load(BOS_SERVICES.read_text(encoding="utf-8")) or {}
    unimplemented = yaml.safe_load(BOS_UNIMPLEMENTED.read_text(encoding="utf-8")) or {}

    # 收集实际标记为 [UNIMPLEMENTED] 的服务
    unimplemented_uris: set[str] = set()
    for svc in services.get("services", []):
        desc = svc.get("description", "")
        if desc.startswith("[UNIMPLEMENTED]"):
            unimplemented_uris.add(svc["uri"])

    # 收集追踪文件中的条目
    tracked_uris = {e["uri"] for e in unimplemented.get("unimplemented", [])}

    # 检查 1: 追踪文件中有但 bos-services.yaml 未标记 [UNIMPLEMENTED]
    unknown = tracked_uris - unimplemented_uris
    if unknown:
        for uri in sorted(unknown):
            errors.append(
                f"  ⚠️  '{uri}' 在 bos-unimplemented.yaml 中但 bos-services.yaml 未标记 [UNIMPLEMENTED]"
            )

    # 检查 2: bos-services.yaml 标记了 [UNIMPLEMENTED] 但追踪文件未登记
    missing = unimplemented_uris - tracked_uris
    if missing:
        for uri in sorted(missing):
            errors.append(
                f"  ⚠️  '{uri}' 标记 [UNIMPLEMENTED] 但未在 bos-unimplemented.yaml 登记"
            )

    if errors:
        print(f"[BOS-TRACKING] ❌ {len(errors)} 个 BOS 追踪问题:")
        for err in errors:
            print(err)
        print("[BOS-TRACKING] 提示: 新增实现后从 bos-unimplemented.yaml 删除对应条目")
        return 1

    count = len(unimplemented_uris)
    print(
        f"[BOS-TRACKING] ✅ BOS 追踪一致 — {len(tracked_uris)} 未实现, "
        f"{len(services.get('services', []))} 活动"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
