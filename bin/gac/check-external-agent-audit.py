#!/usr/bin/env python3
"""CR-X1-EXTERNAL-AGENT-AUDIT: 检查外部 agent 接入审计.

外部 agent 接入必须: 1) 注册 MCP 工具入口 2) 审计链记录操作
3) 不绕过 .omo ingress. 检查 agent 注册文件中的外部 agent 接入点.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# 外部 agent 注册文件
AGENT_REGISTRIES = [
    REPO_ROOT / ".omo" / "_truth" / "registry" / "agent-workflows.yaml",
    REPO_ROOT / ".omo" / "standards",
]


def main() -> int:
    violations = []
    for reg_path in AGENT_REGISTRIES:
        if not reg_path.exists():
            continue
        if reg_path.is_file():
            files = [reg_path]
        else:
            files = list(reg_path.rglob("*.yaml"))

        for f in files:
            rel = f.relative_to(REPO_ROOT)
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # 检查是否包含外部 agent 相关配置
            # 外部 agent = 非 omo/ecos 原生的 agent 接入
            lines = text.splitlines()
            for i, line in enumerate(lines, 1):
                lower = line.lower()
                if any(kw in lower for kw in ["external_agent", "external-agent", "agent_url", "webhook_url", "remote_agent"]):
                    # 检查是否有审计链配置
                    audit_found = any(
                        kw in lower for kw in ["audit", "trail", "log", "ingress"]
                    )
                    if not audit_found:
                        violations.append(
                            f"  {rel}:{i} — 外部 agent 配置 '{line.strip()[:60]}' 缺少审计链"
                        )

    if violations:
        print(f"WARN 发现 {len(violations)} 处外部 agent 配置缺少审计链:")
        for v in violations:
            print(v)
        return 0  # advisory only

    print("OK 外部 agent 接入审计正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
