#!/usr/bin/env python3
"""
discover_ecosystem — 包管理器生态嗅探

探测 npm global / brew / docker / uv / pipx / cargo / go 已安装工具，
与注册表对比，输出/写入 candidate 条目。

用法:
  python3 src/discover_ecosystem.py [--dry-run] [--eco npm,brew,docker]
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from forge.forge_config import REGISTRY  # type: ignore[import-not-found]

# ─── 跳过的基础设施包 ─────────────────────────────

SKIP_NPM = {
    "npm",
    "yarn",
    "pnpm",
    "corepack",
    "node",
    "typescript",
    "ts-node",
    "tsx",
    "eslint",
    "prettier",
    "stylelint",
    "webpack",
    "vite",
    "rollup",
    "parcel",
    "babel-cli",
    "postcss-cli",
    "create-react-app",
    "create-next-app",
    "create-vite",
    "nodemon",
    "concurrently",
    "cross-env",
    "http-server",
    "serve",
    "rimraf",
    "mkdirp",
    "husky",
    "lint-staged",
    "commitizen",
    "jest",
    "mocha",
    "cypress",
    "vitest",
    "playwright",
    "aws-cli",
    "azure-cli",
    "gcloud",
}

SKIP_BREW = {
    "python",
    "python3",
    "node",
    "nodejs",
    "npm",
    "yarn",
    "git",
    "git-lfs",
    "wget",
    "curl",
    "cmake",
    "make",
    "autoconf",
    "automake",
    "libtool",
    "pkg-config",
    "openssl",
    "readline",
    "sqlite",
    "xz",
    "zlib",
    "vim",
    "neovim",
    "emacs",
    "nano",
    "bash",
    "zsh",
    "fish",
    "tmux",
    "htop",
    "jq",
    "tree",
    "bat",
    "ripgrep",
    "fd",
    "fzf",
    "coreutils",
    "findutils",
    "gnu-sed",
    "gnu-tar",
    "gh",
    "gist",
    "docker",
    "docker-compose",
    "docker-buildx",
    "kubectl",
    "helm",
    "minikube",
    "kind",
    "terraform",
    "packer",
    "vagrant",
    "mysql",
    "postgresql",
    "redis",
    "mongodb",
    "nginx",
    "httpd",
    "ffmpeg",
    "imagemagick",
    "rust",
    "rustup",
    "cargo",
    "go",
    "llvm",
    "gcc",
}

SKIP_DOCKER = {
    "hello-world",
    "alpine",
    "ubuntu",
    "debian",
    "centos",
    "fedora",
    "busybox",
    "scratch",
    "node",
    "python",
    "golang",
    "openjdk",
    "nginx",
    "httpd",
    "caddy",
    "redis",
    "postgres",
    "mysql",
    "mariadb",
    "mongo",
    "rabbitmq",
    "nats",
    "traefik",
    "haproxy",
    "prometheus",
    "grafana",
    "portainer",
}


def _now_ts() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _has_cmd(cmd: str) -> bool:
    try:
        subprocess.run(["which", cmd], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _load_registry() -> dict:
    return json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {"tools": [], "event_log": []}


def _save_registry(reg: dict) -> None:
    import fcntl

    tmp = REGISTRY.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    with REGISTRY.open("rb") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        tmp.rename(REGISTRY)


def _get_registered_ids(reg: dict) -> set:
    return {t["id"] for t in reg.get("tools", []) if "id" in t}


def _build_candidate(
    id_str: str,
    name: str,
    cmd_type: str = "cli",
    provider: str = "",
    location: str = "",
    notes: str = "",
    install_method: str = "manual",
    install_cmd: str = "",
    confidence: float = 0.5,
    version: str = "",
) -> dict:
    return {
        "id": id_str,
        "name": name,
        "type": cmd_type,
        "status": "candidate",
        "category": [],
        "capabilities": [],
        "access": {"method": "cli", "location": location},
        "source": {"type": "github", "provider": provider, "version_tracking": True},
        "cost_model": "free",
        "health": "unknown",
        "notes": notes,
        "added": "",
        "updated": "",
        "_discovery": {"source": "package_manager", "first_seen": "", "confidence": confidence},
        "install": {"method": install_method, "command": install_cmd, "auto_installable": True},
    }


def probe_npm() -> list[dict]:
    if not _has_cmd("npm"):
        return []
    try:
        r = subprocess.run(
            ["npm", "list", "-g", "--json", "--depth=0"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(r.stdout)
    except Exception:
        return []
    deps = data.get("dependencies", {})
    candidates = []
    for name, info in deps.items():
        if name in SKIP_NPM:
            continue
        ver = info.get("version", "")
        candidates.append(
            _build_candidate(
                id_str=f"npm-{name}",
                name=f"{name} (npm)",
                provider="npm",
                location="npm global",
                notes=f"npm global package v{ver}",
                install_method="npm",
                install_cmd=f"npm install -g {name}",
                confidence=0.5,
                version=ver,
            )
        )
    return candidates


def probe_brew() -> list[dict]:
    if not _has_cmd("brew"):
        return []
    try:
        r = subprocess.run(
            ["brew", "list", "--formula", "-1"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        formulae = [f for f in r.stdout.strip().split("\n") if f]
    except Exception:
        return []
    candidates = []
    for name in formulae:
        if name in SKIP_BREW:
            continue
        try:
            r2 = subprocess.run(
                ["brew", "info", name, "--json=v2"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            info = json.loads(r2.stdout)
            formulae_data = info.get("formulae", [{}])[0]
            ver = formulae_data.get("versions", {}).get("stable", "")
            desc = formulae_data.get("desc", "") or ""
        except Exception:
            ver, desc = "", ""
        notes = f"{desc} (brew)" if desc else "brew formula"
        if ver:
            notes += f" v{ver}"
        candidates.append(
            _build_candidate(
                id_str=name,
                name=f"{name} (brew)",
                provider="Homebrew",
                location="brew",
                notes=notes,
                install_method="brew",
                install_cmd=f"brew install {name}",
                confidence=0.6,
                version=ver,
            )
        )
    return candidates


def probe_docker() -> list[dict]:
    if not _has_cmd("docker"):
        return []
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=10)
    except Exception:
        return []
    try:
        r = subprocess.run(
            ["docker", "image", "ls", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        lines = [l for l in r.stdout.strip().split("\n") if l]  # noqa: E741
    except Exception:
        return []
    candidates = []
    seen = set()
    for line in lines:
        try:
            img = json.loads(line)
            repo = img.get("Repository", "")
            tag = img.get("Tag", "")
            if not repo:
                continue
            short = Path(repo).name.lower()
            if short in SKIP_DOCKER or short in seen:
                continue
            seen.add(short)
            candidates.append(
                _build_candidate(
                    id_str=f"docker-{short}",
                    name=f"{short} (Docker)",
                    cmd_type="service",
                    provider="Docker Hub",
                    location=f"docker: {repo}:{tag}",
                    notes=f"Docker image: {repo}:{tag}",
                    install_method="manual",
                    install_cmd=f"docker pull {repo}:{tag}",
                    confidence=0.4,
                )
            )
        except Exception:  # noqa: S112  # defensive fallback
            continue
    return candidates


def probe_uv() -> list[dict]:
    if not _has_cmd("uv"):
        return []
    try:
        r = subprocess.run(
            ["uv", "tool", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        tools = json.loads(r.stdout)
    except Exception:
        return []
    candidates = []
    for t in tools:
        name = t.get("name", "")
        if not name:
            continue
        ver = t.get("version", "")
        desc = (t.get("description") or "")[:100]
        notes = "uv tool"
        if desc:
            notes = f"{desc} (uv)"
        if ver:
            notes += f" v{ver}"
        candidates.append(
            _build_candidate(
                id_str=f"uv-{name}",
                name=f"{name} (uv)",
                provider="PyPI",
                location="uv tool",
                notes=notes,
                install_method="pip",
                install_cmd=f"uv tool install {name}",
                confidence=0.6,
                version=ver,
            )
        )
    return candidates


def probe_pipx() -> list[dict]:
    if not _has_cmd("pipx"):
        return []
    try:
        r = subprocess.run(
            ["pipx", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(r.stdout)
    except Exception:
        return []
    venvs = data.get("venvs", {})
    candidates = []
    for name, info in venvs.items():
        spec = info.get("metadata", {}).get("pipx_metadata", {}).get("spec", "") or ""
        notes = "pipx package"
        if spec:
            notes += f" {spec}"
        candidates.append(
            _build_candidate(
                id_str=f"pipx-{name}",
                name=f"{name} (pipx)",
                provider="PyPI",
                location="pipx",
                notes=notes,
                install_method="pip",
                install_cmd=f"pipx install {name}",
                confidence=0.5,
            )
        )
    return candidates


def probe_cargo() -> list[dict]:
    if not _has_cmd("cargo"):
        return []
    try:
        r = subprocess.run(
            ["cargo", "install", "--list"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return []
    candidates = []
    for line in r.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 2 and parts[0].strip():
            name = parts[0]
            ver = parts[1].lstrip("v")
            candidates.append(
                _build_candidate(
                    id_str=f"cargo-{name}",
                    name=f"{name} (cargo)",
                    provider="crates.io",
                    location="cargo",
                    notes=f"cargo crate v{ver}",
                    install_method="manual",
                    install_cmd=f"cargo install {name}",
                    confidence=0.5,
                    version=ver,
                )
            )
    return candidates


def probe_go() -> list[dict]:
    if not _has_cmd("go"):
        return []
    gobin = Path.home() / "go" / "bin"
    gopath = Path.home() / "go"
    if "GOBIN" in __import__("os").environ:
        gobin = Path(__import__("os").environ["GOBIN"])
    if "GOPATH" in __import__("os").environ:
        gopath = Path(__import__("os").environ["GOPATH"])
    bins = set()
    for d in [gobin, gopath / "bin"]:
        if d.exists():
            for f in d.iterdir():
                if f.is_file() and f.stat().st_mode & 0o100:
                    bins.add(f.name)
    candidates = []
    for name in sorted(bins):
        candidates.append(
            _build_candidate(
                id_str=f"go-{name}",
                name=f"{name} (go)",
                provider="Go",
                location="go/bin",
                notes="Go binary in $GOPATH/bin",
                install_method="manual",
                install_cmd="go install",
                confidence=0.4,
            )
        )
    return candidates


PROBERS = {
    "npm": probe_npm,
    "brew": probe_brew,
    "docker": probe_docker,
    "uv": probe_uv,
    "pipx": probe_pipx,
    "cargo": probe_cargo,
    "go": probe_go,
}


def run(args: list[str]) -> int:
    dry_run = "--dry-run" in args
    write = "--write" in args
    if "--help" in args or "-h" in args:
        print("用法: python3 src/discover_ecosystem.py [--dry-run] [--write] [--eco npm,brew,...]")
        return 0

    ecos = "npm,brew,docker,uv,pipx,cargo,go"
    for i, a in enumerate(args):
        if a == "--eco" and i + 1 < len(args):
            ecos = args[i + 1]
            break
    eco_list = [e.strip() for e in ecos.split(",") if e.strip()]

    reg = _load_registry()
    registered_ids = _get_registered_ids(reg)

    print("=== 生态嗅探报告 ===")
    print(f"探测范围: {', '.join(eco_list)}")
    print()

    all_candidates: list[dict] = []
    total_probed = 0
    total_found = 0

    for eco in eco_list:
        prob_fn = PROBERS.get(eco)
        if not prob_fn:
            print(f"  ⚠️  未知生态: {eco} (跳过)")
            continue
        try:
            result = prob_fn()
        except Exception:
            result = []
        total_probed += len(result)
        new = [c for c in result if c["id"] not in registered_ids]
        total_found += len(new)
        all_candidates.extend(new)
        print(f"  {eco}: {len(new)} 未注册 / {len(result)} 总计")

    reg_count = len(registered_ids)
    print(f"\n已注册: {reg_count} 个")
    print(f"探测总量: {total_probed} 个")
    print(f"未注册 candidate: {total_found} 个")

    if all_candidates and not dry_run and write:
        today = _today()
        for c in all_candidates:
            c["_discovery"]["first_seen"] = today
            c["added"] = today
            c["updated"] = today
            reg["tools"].append(c)
            reg.setdefault("event_log", []).append(
                {
                    "type": "discovery:ecosystem",
                    "tool_id": c["id"],
                    "summary": f"discover-ecosystem 发现新工具: {c['id']}",
                    "timestamp": _now_ts(),
                }
            )
        _save_registry(reg)
        print(f"\n✅ 写入 {len(all_candidates)} 条 candidate")
        for c in all_candidates:
            print(f"  ✅ {c['id']} → candidate")
    elif all_candidates and not write:
        print("\n🔶 --dry-run 模式，未写入。运行 --write 写入注册表")
        for c in all_candidates[:10]:
            print(f"  {c['id']} → [{c['install']['method']}] {c['notes']}")
        if len(all_candidates) > 10:
            print(f"  ... 还有 {len(all_candidates) - 10} 条")
    else:
        print("\n✅ 未发现新工具")
    return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
