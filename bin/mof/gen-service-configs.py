#!/usr/bin/env python3
"""gen-service-configs — 从 services.yaml 生成调度配置 (launchd plist).

理想态调度契约 (P73 + governance-ssot-edit skill): plist 由注册生成, 不手写.
稳定锚点 (interpreter=stable-python3 → shutil.which) 杜绝 uv 临时路径炸弹.

用法:
  python3 bin/mof/gen-service-configs.py              # dry-run 打印 plist
  python3 bin/mof/gen-service-configs.py --write      # 生成写盘
  python3 bin/mof/gen-service-configs.py --check      # drift 检测 (plist vs services.yaml)
  python3 bin/mof/gen-service-configs.py --reality-check  # 注册表 vs 本机 launchd 现实 (E1-E4, 只读)
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from repo_root import canonical_root

_WORKSPACE_CACHE: Path | None = None


def workspace() -> Path:
    """本工具写的是机器级配置(~/Library/LaunchAgents), 必须锚定规范检出。

    2026-08-08 事故: 原实现用 parents[2], 于是在哪个 worktree 里跑就把 plist
    里的路径写成那个 worktree 的。多个 agent 在各自 worktree 触发后, omlx 网关 /
    autopilot / agora / cockpit 七个 plist 的程序路径先后被改写成
    ws-mass-deletion-gate、ws-observability-impl…… 全部失效。
    worktree 是临时的, 机器级配置不能指向它。

    解析规则只有一份, 在 bin/lib/repo_root.py:canonical_root() —— 它定位不到规范检出时
    raise, 而不是退回 __file__。原实现在环境变量与 ~/Workspace 都不命中时恰恰退回了
    __file__, 也就是把上面那类事故重新打开。

    惰性: 无规范检出时 raise 是规定行为, 但 `bin/ops/cli.py` 与单元测试只要本文件的
    纯函数(路径展开/plist 生成), 不该被 import 副作用判死。只有真要落笔机器级配置
    的那条调用路径才付这个解析。
    """
    global _WORKSPACE_CACHE
    if _WORKSPACE_CACHE is None:
        _WORKSPACE_CACHE = canonical_root()
    return _WORKSPACE_CACHE


def services_yaml_path() -> Path:
    return workspace() / ".omo" / "_truth" / "registry" / "services.yaml"


def _stable_python3() -> str:
    # Prefer machine-stable installations before scanning PATH.  `uv run`
    # prepends temporary/venv directories and, after those are skipped, can
    # make `/usr/bin/python3` win even when the installed plist was generated
    # with Homebrew Python.  A generator/check pair must choose one identity
    # independent of the caller's environment.
    for candidate in ("/opt/homebrew/bin/python3", "/usr/local/bin/python3"):
        if Path(candidate).is_file():
            return candidate

    for path in os.environ.get("PATH", "").split(os.pathsep):
        # 跳过 uv 临时目录、uv 管理的 .venv 入口 (uv run 会把 .venv/bin 提到 PATH 最前),
        # 这些都是 uv 拥有生命周期的 Python, GC 后会失效或切版本 — 不属于 "stable" 锚点.
        if ".cache/uv" in path or "/.tmp" in path or "/.venv/bin" in path or "/.venv/" in path:
            continue
        p = shutil.which("python3", path=path)
        if p and not (".cache/uv" in p or "/.tmp" in p or "/.venv/bin" in p):
            return p
    return "/opt/homebrew/bin/python3"


INTERPRETERS = {"stable-python3": _stable_python3}


def _cron_tokens(svc: dict) -> set[str]:
    """Entry 的可匹配 token 集: id 尾段 (含连字符变体) + 显式 crontab_token。"""
    service_id = str(svc.get("id") or "")
    tail = service_id.rsplit(".", 1)[-1]
    tokens = {tail, tail.replace("_", "-")}
    token = svc.get("crontab_token")
    if isinstance(token, str) and token.strip():
        tokens.add(token.strip())
    return {t for t in tokens if len(t) >= 4}


def _cron_admission_violation(svc: dict) -> str | None:
    """Cron 准入 (BET-Y1Q4-T16): enabled cron 条目必须携带至少一个能与 crontab
    行匹配的 token — entrypoint basename 词边界命中 id 尾段, 或显式 crontab_token
    (显式声明即放行, 现实性由 ops check-signals 对本机 crontab 核验)。
    拒绝 `projects/omo` 类占位 entrypoint 无 token 混进注册表 (批次 18 误判根因)。
    仅校验 enabled=true (存量 disabled 占位 grandfather)。"""
    if not svc.get("enabled", True):
        return None
    service_id = str(svc.get("id") or "?")
    program = svc.get("program") or {}
    entrypoint = program.get("entrypoint") if isinstance(program, dict) else None
    if not isinstance(entrypoint, str) or not entrypoint.strip():
        return f"{service_id}: cron generator requires program.entrypoint"
    declared = svc.get("crontab_token")
    if isinstance(declared, str) and declared.strip():
        return None
    text = entrypoint.rsplit("/", 1)[-1]
    for token in _cron_tokens(svc):
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(token)}(?![A-Za-z0-9_-])", text):
            return None
    return (
        f"{service_id}: cron 准入失败 — entrypoint basename 与 id 尾段词边界不匹配且无 crontab_token"
        f" (entrypoint={entrypoint!r})"
    )


def validate_service_declaration(svc: dict) -> list[str]:
    """Validate fields required before a launchd plist or crontab line can be generated."""
    service_id = str(svc.get("id") or "?")
    violations: list[str] = []
    if not svc.get("id"):
        violations.append("service 缺必填 id")
    scheduler = svc.get("scheduler")
    if not scheduler:
        violations.append("service 缺必填 scheduler")
    if scheduler == "cron":
        violation = _cron_admission_violation(svc)
        if violation:
            violations.append(violation)
        return violations
    if scheduler != "launchd" or not svc.get("enabled", True) or not svc.get("generate", True):
        return violations
    if not isinstance(svc.get("label"), str) or not svc["label"].strip():
        violations.append(f"{service_id}: launchd generator requires label")
    program = svc.get("program")
    if not isinstance(program, dict) or not isinstance(program.get("interpreter"), str) or not program["interpreter"].strip():
        violations.append(f"{service_id}: launchd generator requires program.interpreter")
    if not isinstance(program, dict) or not isinstance(program.get("entrypoint"), str) or not program["entrypoint"].strip():
        violations.append(f"{service_id}: launchd generator requires program.entrypoint")
    return violations


def load_services(path: Path | None = None) -> list[dict]:
    reg = path or services_yaml_path()
    docs = [d for d in yaml.safe_load_all(reg.read_text(encoding="utf-8")) if d]
    return (docs[-1] if docs else {}).get("services", []) or []


def _launchd_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _resolve_path(p: str) -> str:
    """~ 展开、绝对路径原样、其余相对规范检出根。

    原实现无条件 `WORKSPACE / p`, 于是 "~/.local/bin/x" 变成
    "<workspace>/~/.local/bin/x" —— 带字面量 ~ 的死路径。
    """
    p = str(p)
    if p.startswith("~"):
        return str(Path(p).expanduser())
    if p.startswith("/"):
        return p
    return str(workspace() / p)


def resolve_interpreter(spec: str) -> str:
    if spec in INTERPRETERS:
        interp = INTERPRETERS[spec]()
    elif spec.startswith("/") or spec.startswith("~"):
        interp = str(Path(spec).expanduser())
    else:
        # 未知别名原样落进 ProgramArguments[0] 会生成 "shell"、"uv" 这种
        # 不存在的程序名, launchd 静默起不来。宁可在生成期炸, 不要写坏 plist。
        resolved = shutil.which(spec)
        if not resolved:
            raise ValueError(
                f"未知 interpreter {spec!r} — 请用 {sorted(INTERPRETERS)} "
                f"或绝对路径 (services.yaml 里写 shell/uv 这类别名不受支持)"
            )
        interp = resolved
    # 校验禁 uv 临时路径 (治 P2 + uv run 时 shutil.which 返回 .tmp 的坑 — PR#77 不彻底)
    if ".cache/uv/builds" in interp or "/.tmp" in interp or "/.venv/bin" in interp:
        raise ValueError(f"interpreter 含 uv 临时路径 (禁, uv GC 后失效): {interp}")
    return interp


def _plist_program_args(plist_xml: str) -> list[str]:
    """从生成的 plist XML 里取 ProgramArguments 的字符串项(用于写盘前自检)。"""
    import re

    m = re.search(r"<key>ProgramArguments</key>\s*<array>(.*?)</array>", plist_xml, re.DOTALL)
    if not m:
        return []
    return re.findall(r"<string>(.*?)</string>", m.group(1), re.DOTALL)


def gen_launchd_plist(svc: dict) -> str:
    label = svc["label"]
    interp = resolve_interpreter(svc["program"]["interpreter"])
    entry = _resolve_path(svc["program"]["entrypoint"])
    args = [interp, entry, *svc["program"].get("args", [])]
    prog_xml = "".join(f"        <string>{a}</string>\n" for a in args)
    watch = svc.get("watch_paths", [])
    watch_xml = "".join(f"        <string>{workspace() / w}</string>\n" for w in watch)
    env = svc.get("environment", {})
    env_xml = ""
    if env:
        items = "".join(f"        <key>{k}</key>\n        <string>{v}</string>\n" for k, v in env.items())
        env_xml = f"    <key>EnvironmentVariables</key>\n    <dict>\n{items}    </dict>\n"
    res = svc.get("resilience", {})
    keepalive_xml = ""
    # always = 无条件常驻(退出即拉起); crashed = 仅崩溃后拉起。
    # 此前只认 crashed, 声明 always 的服务会静默失去常驻语义 ——
    # plist 看着生成成功, 但服务退出后不会被拉起, 且当场看不出来。
    if res.get("keepalive") == "always":
        keepalive_xml = "    <key>KeepAlive</key>\n    <true/>\n"
    elif res.get("keepalive") == "crashed":
        keepalive_xml = (
            "    <key>KeepAlive</key>\n    <dict>\n        <key>Crashed</key>\n        <true/>\n    </dict>\n"
        )
    throttle = res.get("throttle_interval")
    throttle_xml = f"    <key>ThrottleInterval</key>\n    <integer>{throttle}</integer>\n" if throttle else ""
    # trigger: interval → StartInterval (此前静默丢弃: interval 型服务退化成
    # RunAtLoad 一次性, load 后永不再调度 —— 角色 jobs 40min 水位 stale 的根因)
    trigger = svc.get("trigger", "")
    interval_sec = svc.get("interval_sec")
    start_interval_xml = (
        f"    <key>StartInterval</key>\n    <integer>{int(interval_sec)}</integer>\n"
        if trigger == "interval" and interval_sec else ""
    )
    run_at_load_xml = "    <key>RunAtLoad</key>\n    <true/>\n" if svc.get("run_at_load") else ""
    out = svc.get("outputs", {})
    # 与 entrypoint 同样要过 _resolve_path —— 否则 "~/Library/Logs/x.log" 会被
    # 拼成 "<workspace>/~/Library/Logs/x.log"(带字面量 ~ 的死路径)。
    # 2026-08-08 修 entrypoint 时漏了这里, 同一个 bug 换了个字段。
    stdout_xml = (
        f"    <key>StandardOutPath</key>\n    <string>{_resolve_path(out['stdout'])}</string>\n"
        if out.get("stdout")
        else ""
    )
    stderr_xml = (
        f"    <key>StandardErrorPath</key>\n    <string>{_resolve_path(out['stderr'])}</string>\n"
        if out.get("stderr")
        else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n<dict>\n'
        f"    <key>Label</key>\n    <string>{label}</string>\n"
        "    <key>ProgramArguments</key>\n    <array>\n"
        f"{prog_xml}    </array>\n"
        + (f"    <key>WatchPaths</key>\n    <array>\n{watch_xml}    </array>\n" if watch else "")
        + env_xml
        + keepalive_xml
        + throttle_xml
        + run_at_load_xml
        + start_interval_xml
        + stdout_xml
        + stderr_xml
        + "</dict>\n</plist>\n"
    )


NAMESPACE_KEY = "launchd_namespace"
EXEMPT_CLASSES = {"external", "unclassified"}


def _registry_docs(path: Path) -> list[dict]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def load_namespace_policy(path: Path) -> dict:
    """读取 launchd 命名空间分区 (与 services 同文档, 不是独立文档)。

    分区必须是**注册表数据**而非代码常量: "哪些 label 归本仓管"是会随
    新服务增长的判断, 写在代码里就等于每次判断都要改生成器。

    放置位置是硬约束: `load_services()` 取 docs[-1]["services"], 若把本块
    做成第三个 YAML 文档, docs[-1] 就变成只有 namespace 的文档 → services
    解析为空列表 → --check 在零服务上"漂移 0"通过。门禁自己变成假绿。
    """
    for doc in reversed(_registry_docs(path)):
        if NAMESPACE_KEY in doc:
            policy = doc[NAMESPACE_KEY] or {}
            return {
                "workspace_prefixes": list(policy.get("workspace_prefixes") or []),
                "exempt_labels": list(policy.get("exempt_labels") or []),
                "dev_label_prefix": str(policy.get("dev_label_prefix") or ""),
            }
    return {}


def match_workspace_prefix(label: str, prefixes: list[str]) -> str | None:
    """点段边界匹配, 不是字符串前缀。

    `com.omo` 是 `com.omostation` 的字符串前缀, 但不是它的点段前缀 ——
    用 startswith 会把 23 条 com.omostation.* 划进 com.omo, 分区看着完整,
    实际把两个命名空间的归属混成一份。
    """
    for prefix in prefixes:
        if label == prefix or label.startswith(prefix + "."):
            return prefix
    return None


def classify_label(label: str, policy: dict) -> str:
    """workspace / external / unclassified / unmanaged_unknown。

    classification 拼错时落到 unmanaged_unknown(分区外), 而不是默认当成 external:
    后者会让一条本仓服务静默退出等式。E4 的非法分类断言在同一份数据上另行报出。
    """
    if match_workspace_prefix(label, policy.get("workspace_prefixes", [])):
        return "workspace"
    for item in policy.get("exempt_labels", []):
        if item.get("label") == label:
            classification = str(item.get("classification") or "")
            return classification if classification in EXEMPT_CLASSES else "unmanaged_unknown"
    return "unmanaged_unknown"


def enumerate_launchd_plists(launchd_dir: Path) -> list[dict]:
    """本机 LaunchAgents 现实。用 plutil 解析, 不用 plistlib。

    实测 56 条 plist 全部可被 plutil 解析, 但其中 2 条
    (com.omostation.expiry-radar / com.omostation.zhixing-host-drift) 的注释里
    含 `--`, plistlib/expat 因此拒绝 —— 而 launchd 照跑。用 plistlib 枚举本机现实
    会静默丢掉这两条正在跑的常驻 (bin/gac/meta-doctor.py:364 就是 try/except continue)。
    所以枚举走 plutil, plistlib 的拒绝单独作为 E3 的 lint 债报告。
    """
    rows: list[dict] = []
    for path in sorted(launchd_dir.glob("*.plist")):
        result = subprocess.run(
            ["/usr/bin/plutil", "-convert", "json", "-o", "-", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = {}
        if result.returncode == 0:
            try:
                payload = json.loads(result.stdout)
            except ValueError:
                payload = {}
        args = payload.get("ProgramArguments") or []
        if isinstance(args, str):
            args = [args]
        rows.append(
            {
                "file": path.name,
                "path": path,
                "label": str(payload.get("Label") or path.stem),
                "plutil_ok": result.returncode == 0 and bool(payload),
                "blob": json.dumps(payload, ensure_ascii=False),
                "program_arguments": [str(a) for a in args],
            }
        )
    return rows


def plist_strict_well_formed(path: Path) -> bool:
    try:
        plistlib.loads(path.read_bytes())
        return True
    except Exception:
        return False


def declared_labels(services: list[dict]) -> set[str]:
    return {str(svc["label"]) for svc in services if isinstance(svc.get("label"), str) and svc["label"].strip()}


def run_e1_drift() -> dict:
    """E1 = 现有 --check 逐字节原样调用 (不改环境、不改注册表解析)。

    不传 OMOSTATION_ROOT: --check 的根解析维持 canonical, 生成文本里的相对
    entrypoint 才会与已安装 plist 一致。若在 worktree 里改根, 16 条相对路径服务
    会全部报 drift —— 那是测量方法造假, 不是现实。
    """
    cmd = [sys.executable, str(Path(__file__).resolve()), "--check", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        payload = json.loads(result.stdout)
    except ValueError:
        return {"status": "error", "drift_count": None, "detail": (result.stderr or result.stdout)[:200]}
    if payload.get("skipped"):
        return {"status": "skipped", "drift_count": None, "reason": payload.get("reason", "")}
    return {
        "status": "ok" if payload.get("ok") else "drift",
        "drift_count": int(payload.get("drift_count", 0)),
        "drifts": list(payload.get("drifts") or [])[:20],
    }


def reality_check(
    registry_path: Path,
    launchd_dir: Path,
    e1: dict | None = None,
    workspace_root: Path | str | None = None,
) -> dict:
    """注册表 vs 本机 launchd 现实的双向门禁 (只读)。"""
    services = load_services(registry_path)
    policy = load_namespace_policy(registry_path)
    rows = enumerate_launchd_plists(launchd_dir) if launchd_dir.is_dir() else []
    declared = declared_labels(services)
    e1 = e1 if e1 is not None else run_e1_drift()
    root_str = str(workspace_root or workspace())

    buckets: dict[str, list[str]] = {"workspace": [], "external": [], "unclassified": [], "unmanaged_unknown": []}
    for row in rows:
        buckets[classify_label(row["label"], policy)].append(row["label"])
    scoped = [row for row in rows if root_str in row["blob"]]

    e2_gap = sorted(set(buckets["workspace"]) - declared)
    e3_debt = sorted(row["label"] for row in rows if not plist_strict_well_formed(row["path"]))

    findings: list[str] = []
    unparseable = sorted(row["file"] for row in rows if not row["plutil_ok"])
    if unparseable:
        findings.append(f"E4 plutil 无法解析的 plist (连 Label 都取不到): {unparseable}")
    prefixes = list(policy.get("workspace_prefixes") or [])
    if not prefixes:
        findings.append(f"E4 {NAMESPACE_KEY}.workspace_prefixes 缺失 → 分区不可证, 门禁 fail-closed")
    if len(prefixes) != len(set(prefixes)):
        findings.append("E4 workspace_prefixes 有重复项")
    exempt_items = [str(i.get("label") or "") for i in policy.get("exempt_labels", [])]
    if len(exempt_items) != len(set(exempt_items)):
        findings.append("E4 exempt_labels 有重复项")
    shadowed = [i for i in exempt_items if match_workspace_prefix(i, prefixes)]
    if shadowed:
        findings.append(f"E4 exempt 项被 workspace 前缀遮蔽 (死数据): {shadowed}")
    if buckets["unmanaged_unknown"]:
        findings.append(
            f"E4 未分区 label {len(buckets['unmanaged_unknown'])} 条: {sorted(buckets['unmanaged_unknown'])}"
        )
    bad_class = [str(i.get("label")) for i in policy.get("exempt_labels", []) if i.get("classification") not in EXEMPT_CLASSES]
    if bad_class:
        findings.append(f"E4 exempt classification 非法: {bad_class}")
    installed = {row["label"] for row in rows}
    if len(installed) != len(rows):
        findings.append("E4 同一 Label 出现在多个 plist 文件 (Label 与文件名不一致)")
    mismatched = sorted(row["file"] for row in rows if row["label"] != Path(row["file"]).stem)
    if mismatched:
        findings.append(f"E4 Label 与文件名不一致 (launchd 按内容注册, 工具按文件名核对): {mismatched}")
    if sum(len(v) for v in buckets.values()) != len(rows):
        findings.append(f"E4 分区不闭合: 分类 {sum(len(v) for v in buckets.values())} != 本机 {len(rows)}")
    dangling_exempt = sorted({i for i in exempt_items} - installed)
    if dangling_exempt:
        findings.append(f"E4 exempt 项已不在本机 (登记陈旧, 需删): {dangling_exempt}")
    if e2_gap:
        findings.append(f"E2 本机已装但注册表未声明 {len(e2_gap)} 条: {e2_gap}")
    if e1["status"] == "drift":
        findings.append(f"E1 plist 与注册表漂移 {e1['drift_count']} 条: {e1.get('drifts', [])}")
    if e1["status"] == "error":
        findings.append(f"E1 --check 无法解析: {e1.get('detail', '')}")

    return {
        "ok": not findings,
        "findings": findings,
        "e1_status": e1["status"],
        "e1_drift": e1["drift_count"] if e1["drift_count"] is not None else -1,
        "e2_undeclared": len(e2_gap),
        "e2_undeclared_labels": e2_gap,
        "e3_lint_debt": len(e3_debt),
        "e3_malformed_labels": e3_debt,
        "e4_prefix_ok": not any(f.startswith("E4") for f in findings),
        "installed_total": len(rows),
        "workspace_scoped": len(scoped),
        "workspace_scoped_labels": sorted(row["label"] for row in scoped),
        "owned_installed": len(buckets["workspace"]),
        "owned_declared": len(buckets["workspace"]) - len(e2_gap),
        "unclassified": len(buckets["unclassified"]),
        "external": len(buckets["external"]),
        "registry_declared_total": len(declared),
        "dev_label_prefix": policy.get("dev_label_prefix", ""),
    }


def reality_check_main(local_root: Path, registry: Path | None, as_json: bool) -> int:
    report = reality_check(
        registry or (local_root / ".omo" / "_truth" / "registry" / "services.yaml"),
        _launchd_dir(),
    )
    if as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(
            f"E1 drift={report['e1_drift']} ({report['e1_status']})  "
            f"E2 undeclared={report['e2_undeclared']}  E3 lint_debt={report['e3_lint_debt']}  "
            f"E4 prefix_ok={report['e4_prefix_ok']}"
        )
        print(
            f"本机 {report['installed_total']} = workspace {report['owned_installed']} + "
            f"unclassified {report['unclassified']} + external {report['external']}  |  "
            f"Workspace 作用域 {report['workspace_scoped']}"
        )
        for f in report["findings"]:
            print(f"❌ {f}")
        if report["ok"]:
            print("✅ 注册表与本机 launchd 现实闭合")
    return 0 if report["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n")[0])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true", help="JSON 输出 (--check/--validate)")
    parser.add_argument("--validate", action="store_true", help="验注册自洽 (CI, 不依赖本机 plist)")
    parser.add_argument(
        "--reality-check",
        action="store_true",
        help="双向门禁 E1-E4 (注册表 vs 本机 ~/Library/LaunchAgents; 只读, 不写盘)",
    )
    parser.add_argument(
        "--registry",
        default="",
        help="--reality-check 用: 指定 services.yaml (默认取当前检出的那份)",
    )
    args = parser.parse_args()
    local_root = Path(__file__).resolve().parents[2]
    if args.reality_check:
        return reality_check_main(local_root, Path(args.registry) if args.registry else None, args.json)
    registry_path = (
        local_root / ".omo" / "_truth" / "registry" / "services.yaml"
        if args.validate
        else services_yaml_path()
    )
    if not registry_path.exists():
        print(f"❌ 注册不存在: {registry_path}", file=sys.stderr)
        return 1
    services = load_services(registry_path)
    if args.validate:
        # 验注册自洽 (CI 可验, 不依赖本机 plist). 治 service-config-drift gate 在 CI 无本机 plist 的设计问题.
        violations: list[str] = []
        for svc in services:
            if not svc.get("enabled", True):
                continue
            violations.extend(validate_service_declaration(svc))
            if svc.get("scheduler") == "launchd" and not svc.get("generate", True):
                continue
            try:
                resolve_interpreter(svc.get("program", {}).get("interpreter", ""))
            except ValueError as e:
                violations.append(f"{svc.get('id', '?')}: {e}")
            # GHA 调度验 schedule_ref 存在 (治 P4 元递归全覆盖 — 引导扇区 GHA 声明可证, CI 可验仓库内)
            if svc.get("scheduler") == "gha":
                sched_ref = svc.get("schedule_ref")
                if not sched_ref:
                    violations.append(f"{svc.get('id', '?')}: gha 调度缺 schedule_ref")
                elif not (local_root / sched_ref).is_file():
                    violations.append(f"{svc.get('id', '?')}: schedule_ref 不存在 {sched_ref}")
        report = {
            "ok": not violations,
            "violation_count": len(violations),
            "violations": violations,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 1
    launchd_dir = _launchd_dir()
    launchd_observer_available = launchd_dir.is_dir()
    drifts: list[str] = []
    bad_services: list[str] = []
    for svc in services:
        if not svc.get("enabled", True) or svc.get("scheduler") != "launchd":
            continue
        # generate: false —— 注册表只"记录"这个服务的生命周期(供 wsvc 观测),
        # plist 的源头在别处(如 ~/omlx-orchestration/launchd/)。不声明这一点,
        # 生成器会拿注册表里的简化描述去覆盖手写 plist —— 2026-08-08 就是这样
        # 把 omlx 网关等 7 个 plist 写成了死路径。
        if not svc.get("generate", True):
            continue
        declaration_errors = validate_service_declaration(svc)
        if declaration_errors:
            for error in declaration_errors:
                print(f"❌ {error}", file=sys.stderr)
            bad_services.extend(declaration_errors)
            continue
        if args.check and not launchd_observer_available:
            continue
        try:
            plist = gen_launchd_plist(svc)
        except ValueError as exc:
            print(f"❌ {svc.get('label', svc.get('id', '?'))}: {exc}", file=sys.stderr)
            bad_services.append(str(exc))
            continue
        target = launchd_dir / f"{svc['label']}.plist"

        # 生成期最后一道: 程序路径不存在就不写。写进去的是"看着已登记、
        # 实际起不来"的 plist, 比不写更糟 —— 出事时没人会去核对路径。
        missing = [a for a in _plist_program_args(plist) if a.startswith("/") and not Path(a).exists()]
        if missing:
            print(
                f"❌ {svc['label']}: 程序路径不存在 {missing} — 拒绝写入",
                file=sys.stderr,
            )
            bad_services.append(f"{svc['label']}: {missing}")
            continue

        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                plist, encoding="utf-8"
            )  # audit-exempt: non-atomic-write (plist 写 ~/Library/LaunchAgents, 非 .omo state plane)
            print(f"✅ 生成 {target}")
        elif args.check:
            existing = target.read_text(encoding="utf-8") if target.exists() else ""
            if existing.strip() != plist.strip():
                drifts.append(f"{svc['label']}: plist 与 services.yaml 不一致 (drift)")
        else:
            print(f"--- {svc['label']} ---")
            print(plist)
    if args.check:
        if not launchd_observer_available:
            report = {
                "ok": not bad_services,
                "skipped": True,
                "reason": "launchd_observer_unavailable",
                "validation_errors": bad_services,
            }
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print("⏭ launchd observer unavailable; plist byte comparison skipped")
            return 0 if report["ok"] else 1
        if args.json:
            report = {"ok": not drifts, "drift_count": len(drifts), "drifts": drifts}
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if report["ok"] else 1
        if drifts:
            print(f"❌ {len(drifts)} drift:")
            for d in drifts:
                print(f"  - {d}")
            return 1
        launchd_count = sum(1 for s in services if s.get("scheduler") == "launchd")
        print(f"✅ 0 drift ({launchd_count} launchd services)")
    if bad_services:
        print(
            f"\n❌ {len(bad_services)} 个服务未生成(路径/interpreter 有问题):",
            file=sys.stderr,
        )
        for b in bad_services:
            print(f"  - {b}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
