#!/usr/bin/env python3
"""P1a: bidirectional alias cross-check (opencode.json provider.omlxc ↔ omlx gateway litellm-config.yaml).

Catch config drift between the model aliases opencode exposes and the routes
the omlx LiteLLM gateway actually serves. This drift is the root cause of the
subagent delegation failure: an alias registered in opencode.json but absent
from the gateway's model_list has no route, so requests return empty content
("narrate but never edit").

Matching rule (normalization):
  - opencode aliases are the plain keys of provider.omlxc.models, e.g. "coder".
  - litellm model_name may carry a routing prefix, e.g. "lmstudio/<name>".
  - Both sides are compared on their LAST path segment after splitting on "/",
    trimmed of whitespace. "lmstudio/coder" and "coder" therefore match.
  - Comparison is exact after that normalization — no fuzzy matching.

Output categories:
  - IN_OPENCODE_ONLY: alias in opencode.json but no gateway route (routing gap).
  - IN_LITELLM_ONLY: gateway route not exposed as an opencode alias (unused capacity).
  - IN_BOTH: synced pairs.

Exit codes (semantic):
  0  route-safe — no OpenCode alias is missing a gateway route; unused gateway capacity is diagnostic
  1  routing gap detected (IN_OPENCODE_ONLY non-empty)
  2  configuration / IO error (missing file, missing provider block, parse error)

Usage:
  python3 bin/delegation-alias-check.py            # human text
  python3 bin/delegation-alias-check.py --json     # machine-readable JSON
  python3 bin/delegation-alias-check.py --opencode-config <path> --litellm-config <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def find_workspace_root() -> Path:
    """从当前脚本位置回溯找到 workspace 根 (含 .omo/ 目录)."""
    current = Path(__file__).resolve().parent
    for _ in range(5):  # 最多向上 5 层
        if (current / ".omo" / "_truth").exists():
            return current
        current = current.parent
    # fallback: 假设 PWD 是 workspace
    return Path.cwd()


def resolve_path(raw: str, workspace_root: Path) -> Path:
    """解析配置路径; 相对路径锚定在 workspace 根."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = workspace_root / p
    return p


def load_opencode_aliases(path: Path) -> list[str]:
    """返回 opencode.json provider.omlxc.models 的别名键 (排序).

    Raises:
      FileNotFoundError — opencode.json 不存在
      ValueError       — opencode.json JSON 解析失败
      KeyError         — 缺少 provider.omlxc 配置块 (或 provider 非 JSON 对象)
      TypeError        — 结构异常: 顶层 / provider.omlxc / provider.omlxc.models 不是 JSON 对象
    """
    if not path.exists():
        raise FileNotFoundError(f"opencode.json 不存在: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"opencode.json 解析失败 ({path}): {e}") from e
    if not isinstance(data, dict):
        raise TypeError(f"opencode.json 顶层不是 JSON 对象 ({path})")
    provider = data.get("provider")
    if not isinstance(provider, dict) or "omlxc" not in provider:
        raise KeyError(f"opencode.json 缺少 provider.omlxc 配置块 ({path}) — 无法提取 omlxc 模型别名")
    omlxc = provider["omlxc"]
    if not isinstance(omlxc, dict):
        raise TypeError(f"opencode.json provider.omlxc 不是 JSON 对象 ({path})")
    models = omlxc.get("models")
    if not isinstance(models, dict):
        raise TypeError(f"opencode.json provider.omlxc.models 不是 JSON 对象 ({path})")
    return sorted(models.keys())


def load_litellm_model_names(path: Path) -> list[str]:
    """返回 litellm-config.yaml model_list[*].model_name 值 (排序).

    Raises FileNotFoundError / RuntimeError (缺 pyyaml) / ValueError (yaml 解析失败).
    """
    if not path.exists():
        raise FileNotFoundError(f"litellm-config.yaml 不存在: {path}")
    if yaml is None:
        raise RuntimeError("缺少 pyyaml 依赖 — 请用 `uv run --with pyyaml python bin/delegation-alias-check.py` 运行")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ValueError(f"litellm-config.yaml 解析失败 ({path}): {e}") from e
    model_list = (data or {}).get("model_list") or []
    names = []
    for entry in model_list:
        if not isinstance(entry, dict):
            continue
        name = entry.get("model_name")
        if isinstance(name, str) and name.strip():
            names.append(name)
    return sorted(names)


def normalize(name: str) -> str:
    """归一化模型别名/名称用于比较: 取最后一段路径并去除首尾空白."""
    return name.strip().split("/")[-1].strip()


def compare(aliases: list[str], model_names: list[str]) -> dict[str, list[str]]:
    """返回 IN_OPENCODE_ONLY / IN_LITELLM_ONLY / IN_BOTH 三个桶."""
    alias_set = {normalized for alias in aliases if (normalized := normalize(alias))}
    gateway_set = {normalized for model in model_names if (normalized := normalize(model))}
    return {
        "IN_OPENCODE_ONLY": sorted(alias_set - gateway_set),
        "IN_LITELLM_ONLY": sorted(gateway_set - alias_set),
        "IN_BOTH": sorted(alias_set & gateway_set),
    }


def drift_detected(result: dict[str, list[str]]) -> bool:
    """Return whether an exposed OpenCode alias has no executable gateway route."""
    return bool(result["IN_OPENCODE_ONLY"])


def any_drift_detected(result: dict[str, list[str]]) -> bool:
    """Return whether the two inventories differ in either direction."""
    return bool(result["IN_OPENCODE_ONLY"] or result["IN_LITELLM_ONLY"])


def render_text(
    result: dict[str, list[str]],
    opencode_path: Path,
    litellm_path: Path,
    workspace_root: Path,
) -> str:
    """渲染人类可读文本报告."""
    lines = [
        "omlxc 别名 ↔ 网关路由 双向交叉检查",
        f"  opencode.json : {opencode_path}",
        f"  litellm       : {litellm_path}",
        f"  workspace root: {workspace_root}",
        "",
    ]
    if result["IN_OPENCODE_ONLY"]:
        lines.append("ROUTING GAP — opencode 暴露的别名缺少网关路由")
    elif result["IN_LITELLM_ONLY"]:
        lines.append("ROUTE SAFE — 仅存在未暴露的网关容量 (diagnostic)")
    else:
        lines.append("SYNCED — opencode 与网关模型别名一致")
    lines.append("")
    for key, title in (
        (
            "IN_OPENCODE_ONLY",
            "IN_OPENCODE_ONLY — opencode 有别名但网关无路由 (routing gap, 请求无处可去)",
        ),
        (
            "IN_LITELLM_ONLY",
            "IN_LITELLM_ONLY — 网关有路由但 opencode 未暴露 (未使用容量)",
        ),
        ("IN_BOTH", "IN_BOTH — 已同步"),
    ):
        items = result[key]
        lines.append(f"{title}:")
        if items:
            lines.extend(f"  - {item}" for item in items)
        else:
            lines.append("  (none)")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P1a: 双向别名交叉检查 — opencode.json provider.omlxc.models ↔ omlx 网关 litellm-config.yaml model_list"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 machine-readable JSON (默认人类可读文本)",
    )
    parser.add_argument(
        "--opencode-config",
        default="~/.config/opencode/opencode.json",
        help="opencode.json 路径 (默认 ~/.config/opencode/opencode.json)",
    )
    parser.add_argument(
        "--litellm-config",
        default="/Volumes/Model/omlx/gateway/litellm-config.yaml",
        help="litellm-config.yaml 路径 (默认 /Volumes/Model/omlx/gateway/litellm-config.yaml)",
    )
    args = parser.parse_args()

    workspace_root = find_workspace_root()
    opencode_path = resolve_path(args.opencode_config, workspace_root)
    litellm_path = resolve_path(args.litellm_config, workspace_root)

    try:
        aliases = load_opencode_aliases(opencode_path)
        model_names = load_litellm_model_names(litellm_path)
    except (FileNotFoundError, KeyError, RuntimeError, TypeError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    result = compare(aliases, model_names)

    if args.json:
        payload = {
            "synced": not any_drift_detected(result),
            "route_safe": not drift_detected(result),
            "opencode_config": str(opencode_path),
            "litellm_config": str(litellm_path),
            "opencode_aliases": aliases,
            "litellm_model_names": model_names,
            **result,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text(result, opencode_path, litellm_path, workspace_root))

    return 1 if drift_detected(result) else 0


if __name__ == "__main__":
    sys.exit(main())
