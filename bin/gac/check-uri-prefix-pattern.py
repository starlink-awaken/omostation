#!/usr/bin/env python3
"""CR-P77-URI-PREFIX: 检查 URI 末尾 / 前缀模式一致性.

P77-3-2: URI 末尾 / 表 routing prefix, 不需具体服务注册.
检查 projects/agora/etc/bos-services.yaml 中 URI 是否遵循前缀模式.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BOS_PATH = REPO / "projects" / "agora" / "etc" / "bos-services.yaml"


def main() -> int:
    if not BOS_PATH.exists():
        print("OK 未发现 BOS 服务注册表")
        return 0

    try:
        import yaml
        data = yaml.safe_load(BOS_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"WARN 无法读取 BOS 注册表: {e}")
        return 0

    violations = []
    services = data if isinstance(data, list) else data.get("services", data.get("bos_services", []))

    for svc in services:
        uri = svc.get("uri", svc.get("route", ""))
        if not uri:
            continue
        # 检查 routing prefix 以 / 结尾
        is_routing = svc.get("type") == "routing" or "routing" in str(svc.get("tags", ""))
        if is_routing and not uri.endswith("/"):
            violations.append(f"  {uri} — routing prefix 应 / 结尾 (P77-3-2)")

    if violations:
        print(f"WARN 发现 {len(violations)} 个 URI 前缀格式问题:")
        for v in violations:
            print(v)
        return 0  # advisory

    print("OK 所有 URI 格式符合前缀模式")
    return 0


if __name__ == "__main__":
    sys.exit(main())
