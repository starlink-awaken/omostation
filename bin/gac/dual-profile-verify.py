#!/usr/bin/env python3
"""双 profile verify 腿 —— 把声明的写面生成器在两个 state 根上各跑一遍。

契约: `docs/superpowers/specs/2026-10-13-dual-profile-verify-leg.md`
BET:  BET-Y2Q4-T10-248 (方案 `§风险与检测`:「dev 能跑」退化成 dev/prod 漂移)

三条判据形状, 缺任一条本门禁就退化成按构造就绿的假门禁:

- **正向落点**: 每条腿报告它实际写出的绝对路径; 落在本 profile 声明的 root 之外即 FAIL。
  「检出没被写」只是隔离副判据 —— 单独用它, 「writer 根本没跑」与「writer 正确改道」同绿。
- **仪表必须是被真消费的旋钮**: 腿只注入 `OMOSTATION_STATE_ROOT`。`OMOSTATION_PROFILE`
  实测零消费者, 以它为开关不改变任何解析结果。
- **探不到的面记 `deferred`, 不得记 `pass`** (CI 干净检出既没有 install_root 也没有 launchd)。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
from repo_root import code_root, install_root  # noqa: E402

SCHEMA = "dual-profile-verify/v1"
STATE_ROOT_ENV = "OMOSTATION_STATE_ROOT"
# 父 env 里这两条优先级高于 STATE_ROOT, 不剥掉就测不到 profile。
PARENT_OVERRIDE_ENV = ("OMOSTATION_ROOT", "OMO_EVENT_LEDGER_DB")
MATERIALIZE_REL = Path("bin") / "gac" / "materialize-system-state.py"
SYSTEM_YAML_REL = Path(".omo") / "state" / "system.yaml"
XDG_STATE_REL = Path(".local") / "state" / "omostation"
SCRATCH_PREFIX = "dual-profile-"
LEG_TIMEOUT_SECONDS = 120
GIT_TIMEOUT_SECONDS = 30

PASS = "pass"
WARN = "warn"
FAIL = "fail"
DEFERRED = "deferred"

HOST_ONLY_LEGS = (
    ("service_registry_reality", "E2 launchd 实测: 声明 vs 已装载 label, 需要本机 launchd 面"),
    ("hardcoded_ports_host", "本机端口占用实测, 需要真实服务在跑"),
)


def _under(path: Path | str, base: Path | str) -> bool:
    """path 是否在 base 之内 (含 base 本身)。"""
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except (ValueError, OSError):
        return False


def forbidden_root_bases() -> dict[str, Path]:
    """腿的 root 不得落在这两个面之下: 检出 (会写进 git 工作树) 与 XDG 状态根 (住着
    B4b 批次 1 的在线备份快照与 provenance, 写进去就是污染机器级状态面)。"""
    return {"checkout": code_root(), "xdg_state": Path.home() / XDG_STATE_REL}


def resolve_root(
    label: str,
    overrides: dict[str, str],
    env: dict[str, str],
    mkdtemp: Callable[[str], str] = tempfile.mkdtemp,
) -> tuple[Path, str]:
    """一条腿的 state 根, 返回 (root, origin)。

    解析顺序: `--root <label>=<绝对路径>` → 已声明 `OMOSTATION_STATE_ROOT` 时的
    `<state_root>/<label>` 子目录 → 每次新建的 scratch 目录。
    """
    if label in overrides:
        return Path(overrides[label]).expanduser().absolute(), "--root"
    declared = env.get(STATE_ROOT_ENV)
    if declared:
        return Path(declared).expanduser().absolute() / label, "declared"
    return Path(mkdtemp(prefix=f"{SCRATCH_PREFIX}{label}-")), "scratch"


def leg_env(root: Path, parent_env: dict[str, str]) -> dict[str, str]:
    env = dict(parent_env)
    for name in PARENT_OVERRIDE_ENV:
        env.pop(name, None)
    env.pop("OMOSTATION_PROFILE", None)
    env[STATE_ROOT_ENV] = str(Path(root).resolve())
    return env


def _fail(reason: str) -> dict[str, str]:
    return {"status": FAIL, "reason": reason}


def system_state_leg(
    label: str,
    root: Path,
    *,
    workspace: Path,
    generator: Path | str = MATERIALIZE_REL,
    parent_env: dict[str, str] | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    executable: str | None = None,
) -> dict[str, object]:
    """L2 —— 在声明 root 下跑一次物化器, 然后做正向落点断言。"""
    env = leg_env(root, dict(os.environ) if parent_env is None else parent_env)
    script = Path(generator)
    if not script.is_absolute():
        script = workspace / script
    cmd = [executable or sys.executable, str(script), "--json"]
    try:
        proc = runner(cmd, capture_output=True, text=True, timeout=LEG_TIMEOUT_SECONDS, env=env, cwd=str(workspace))
    except subprocess.TimeoutExpired:
        return {"profile": label, "root": str(root), **_fail(f"generator timed out after {LEG_TIMEOUT_SECONDS}s")}
    except OSError as exc:
        return {"profile": label, "root": str(root), **_fail(f"generator could not start: {exc}")}

    base = {"profile": label, "root": str(Path(root).resolve()), "generator": str(script)}
    try:
        payload = json.loads(proc.stdout)
    except (json.JSONDecodeError, TypeError):
        lines = [line for line in (proc.stderr or proc.stdout or "").strip().splitlines() if line]
        return {**base, **_fail(f"generator emitted no JSON (rc={proc.returncode}): {lines[0] if lines else 'no output'}")}
    if not isinstance(payload, dict):
        return {**base, **_fail("generator JSON is not an object")}

    reported = payload.get("target")
    landing = Path(reported) if isinstance(reported, str) and reported else None
    base = {**base, "generator_status": payload.get("status"), "landing": str(landing) if landing else None}
    if landing is None:
        return {**base, **_fail("generator reported no landing path")}
    if not landing.is_absolute():
        return {**base, **_fail(f"landing is not an absolute path: {landing}")}
    if not _under(landing, root):
        return {**base, **_fail(f"landing {landing} is outside the declared root {base['root']}")}
    if not landing.is_file():
        return {**base, **_fail(f"landing {landing} does not exist under the declared root")}
    if payload.get("status") not in ("materialized", "skipped"):
        return {**base, **_fail(f"generator status is {payload.get('status')!r}, which is not a write")}
    return {**base, "status": PASS, "reason": ""}


def checkout_isolation(workspace: Path) -> dict[str, object]:
    """I4 的副判据 —— 检出侧的声明写目标未被触碰。绝不可单独构成通过证据。"""
    try:
        proc = subprocess.run(
            ["git", "-C", str(workspace), "status", "--short", "--", str(SYSTEM_YAML_REL)],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"checkout_clean": None, "reason": f"git probe unavailable: {exc}"}
    dirty = proc.stdout.strip()
    return {
        "checkout_clean": proc.returncode == 0 and not dirty,
        "checkout_dirty": dirty,
        "checkout_target_present": (workspace / SYSTEM_YAML_REL).is_file(),
    }


def _git(root: Path, *args: str, runner: Callable[..., subprocess.CompletedProcess]) -> tuple[int, str]:
    try:
        proc = runner(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 125, f"probe unavailable: {exc}"
    return proc.returncode, (proc.stdout or "").strip()


def install_root_drift(
    root: Path | None = None,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    locator: Callable[[], Path | None] = install_root,
) -> dict[str, object]:
    """L3 —— 「dev 钉在同一发布面」的同义仪表: git 祖先关系 + 落后计数。

    本仓没有 release tag 序列, `git describe` 两侧今天就不一致 (spec §0 前提修正),
    按字面接 describe 只会永久噪声。`behind > 0` 或非祖先 → warn (检测语义是告警不是中止);
    探不到 install root → deferred, 不得记 pass。
    """
    base: dict[str, object] = {"target": None, "head": None, "is_ancestor": None, "behind": None}
    if root is None:
        root = locator()
    if root is None:
        return {
            **base,
            "status": DEFERRED,
            "reason": "no runtime install root on this machine (CI clean checkout / fresh clone)",
        }
    base["target"] = str(root)
    rc, head = _git(root, "rev-parse", "HEAD", runner=runner)
    if rc != 0:
        return {**base, **_fail(f"install root has no readable HEAD (git rc={rc})")}
    base["head"] = head
    rc, _ = _git(root, "rev-parse", "--verify", "--quiet", "origin/main", runner=runner)
    if rc != 0:
        return {**base, "status": DEFERRED, "reason": "install root has no origin/main ref, ancestry cannot be measured"}
    ancestor_rc, _ = _git(root, "merge-base", "--is-ancestor", "HEAD", "origin/main", runner=runner)
    is_ancestor = ancestor_rc == 0
    rc, count = _git(root, "rev-list", "--count", "HEAD..origin/main", runner=runner)
    if rc != 0 or not count.isdigit():
        return {**base, "status": DEFERRED, "is_ancestor": is_ancestor, "reason": f"behind count unavailable (git rc={rc})"}
    behind = int(count)
    verdict = {**base, "is_ancestor": is_ancestor, "behind": behind}
    if not is_ancestor:
        return {**verdict, "status": WARN, "reason": "install root HEAD is not an ancestor of origin/main"}
    if behind > 0:
        return {**verdict, "status": WARN, "reason": f"install root is {behind} commits behind origin/main"}
    return {**verdict, "status": PASS, "reason": ""}


def host_legs(which: Callable[[str], str | None] = shutil.which) -> list[dict[str, object]]:
    """L4 —— 需要 launchd / 真实服务 / 本机端口的判据一律 deferred, 不计入通过数。

    探针本身是实测: `launchctl` 在不在本机。不在 → 环境无该面 (CI); 在 → 跑它会写机器级
    状态面 (`~/Library/LaunchAgents`), 属 B4b 批次 2+ 的授权范围, 不由本腿越权。
    """
    has_launchd = bool(which("launchctl"))
    reason = (
        "host has launchd, but running it writes machine-level state; needs explicit authorization"
        if has_launchd
        else "no launchd surface on this environment (CI clean checkout)"
    )
    return [{"leg": name, "scope": scope, "status": DEFERRED, "reason": reason} for name, scope in HOST_ONLY_LEGS]


def summarize(
    legs: list[dict[str, object]], install: dict[str, object], hosts: list[dict[str, object]]
) -> dict[str, int]:
    counts = {PASS: 0, WARN: 0, FAIL: 0, DEFERRED: 0}
    for item in [*legs, install, *hosts]:
        status = item.get("status")
        if isinstance(status, str) and status in counts:
            counts[status] += 1
    return counts


def parse_overrides(raw: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in raw:
        label, sep, value = item.partition("=")
        if not sep or not label or not value:
            raise ValueError(f"--root expects <label>=<absolute path>, got: {item}")
        if not Path(value).is_absolute():
            raise ValueError(f"--root value must be absolute: {item}")
        if label in overrides:
            raise ValueError(f"--root given twice for label {label}")
        overrides[label] = value
    return overrides


def _root_plan(
    labels: list[str], overrides: dict[str, str], parent_env: dict[str, str]
) -> tuple[dict[str, str], dict[str, str], list[str], list[str]]:
    roots: dict[str, str] = {}
    origins: dict[str, str] = {}
    scratch: list[str] = []
    problems: list[str] = []
    for label in labels:
        root, origin = resolve_root(label, overrides, parent_env)
        roots[label] = str(Path(root).resolve())
        origins[label] = origin
        if origin == "scratch":
            scratch.append(label)
    if len(labels) < 2:
        problems.append(f"need at least two profiles, got {labels}")
    if len(set(roots.values())) != len(labels):
        shared = sorted({path for path in roots.values() if list(roots.values()).count(path) > 1})
        problems.append(f"profiles resolve to the same state root: {shared}")
    bases = forbidden_root_bases()
    for label, path in roots.items():
        for name, base in bases.items():
            if _under(path, base):
                problems.append(f"{label} root {path} is under the {name} root {base}")
    return roots, origins, scratch, problems


def build_report(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    parent_env = dict(os.environ)
    labels = [item.strip() for item in args.profiles.split(",") if item.strip()]
    roots, origins, scratch, problems = _root_plan(labels, parse_overrides(args.root), parent_env)

    if problems:
        legs = [{"profile": label, "root": roots.get(label), **_fail("; ".join(problems))} for label in labels]
    else:
        legs = [
            system_state_leg(
                label,
                Path(path),
                workspace=args.workspace,
                generator=args.generator,
                parent_env=parent_env,
            )
            for label, path in roots.items()
        ]
    install = install_root_drift()
    hosts = host_legs()
    counts = summarize(legs, install, hosts)
    ok = not problems and not any(leg.get("status") == FAIL for leg in legs)

    report: dict[str, object] = {
        "schema": SCHEMA,
        "ok": ok,
        "profiles": labels,
        "roots": roots,
        "root_origins": origins,
        "legs": legs,
        "install_root": install,
        "host_legs": hosts,
        "isolation": checkout_isolation(args.workspace),
        "summary": {key: counts[key] for key in (PASS, WARN, FAIL, DEFERRED)},
        "state_root_env": STATE_ROOT_ENV,
        "parent_state_root": parent_env.get(STATE_ROOT_ENV),
        "cleaned_scratch": [],
    }
    scratch_paths = [roots[label] for label in scratch]
    if args.keep_roots or not ok:
        report["kept_scratch"] = scratch_paths
    else:
        report["cleaned_scratch"] = [path for path in scratch_paths if _cleanup(Path(path))]
    return (0 if ok else 1), report


def _cleanup(path: Path) -> bool:
    """只清理本脚本自建、目录名带 scratch 前缀的 root; 绝不对别的形状动手。"""
    if SCRATCH_PREFIX not in path.name or not path.is_dir():
        return False
    shutil.rmtree(path, ignore_errors=True)
    return not path.exists()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the declared write-plane generators on two state roots")
    parser.add_argument("--profiles", default="prod,dev", help="逗号分隔的 profile 标签 (标签, 不是新的 env 面)")
    parser.add_argument("--root", action="append", default=[], metavar="LABEL=ABS_PATH", help="显式覆盖某标签的 state 根")
    parser.add_argument("--workspace", type=Path, default=code_root(), help="检出根 (默认 code_root())")
    parser.add_argument("--generator", type=Path, default=MATERIALIZE_REL, help="写面生成器 (相对检出根或绝对路径)")
    parser.add_argument("--keep-roots", action="store_true", help="保留脚本自建的 scratch root")
    parser.add_argument("--json", action="store_true", dest="as_json")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        raise SystemExit(2 if exc.code not in (0, None) else exc.code) from exc
    args.workspace = args.workspace.resolve()
    return args


def render(report: dict[str, object]) -> str:
    lines: list[str] = []
    for leg in report["legs"]:
        detail = leg.get("reason") or leg.get("landing")
        lines.append(f"[{leg['status']:>8}] {leg.get('profile')}: {detail}")
    install = report["install_root"]
    if install.get("reason"):
        detail = install["reason"]
    else:
        detail = "head={} behind={}".format(install.get("head"), install.get("behind"))
    lines.append(f"[{install['status']:>8}] install_root: {detail}")
    for host in report["host_legs"]:
        lines.append(f"[{host['status']:>8}] {host['leg']}: {host['reason']}")
    lines.append(f"summary: {report['summary']} ok={report['ok']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rc, report = build_report(args)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
