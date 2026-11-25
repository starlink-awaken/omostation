"""anchor-install-root.sh 的参考基准判据 —— 安装位按 ADR-0456 §5 锚在 `origin/main` SHA。

背景 (2026-11-17 实测): 旧实现把**检出根 HEAD** 当基准, 而检出根是**读平面**、
可能任意陈旧。实测 `~/Workspace` 停在 `db1b13813` (比安装位锚点旧 7 天), 于是
`--check` 报「锚点落后 0 个提交」并同时说「常驻族在跑旧代码」—— 真实读数是
**落后 origin/main 206 个提交**; 更危险的是默认重锚目标也是检出根 HEAD,
照做会把安装位**往回降级**。

本文件用临时 git 仓自造「检出根陈旧 / origin/main 前进」的形态, 不读 host 状态。
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin/ssot/anchor-install-root.sh"

_ENV_BASE = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
}


def _git(repo: Path, *a: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = {**os.environ, **_ENV_BASE, **(env_extra or {})}
    return subprocess.run(
        ["git", "-C", str(repo), *a], capture_output=True, text=True, env=env, check=False
    )


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def planes(tmp_path: Path) -> dict[str, str]:
    """origin(裸) / install(安装位) / checkout(陈旧的读平面) 三仓。"""
    origin = tmp_path / "origin.git"
    origin.mkdir()
    _git(origin, "init", "-q", "--bare", "-b", "main")

    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init", "-q", "-b", "main")
    c1 = _commit(seed, "c1.txt")
    _git(seed, "remote", "add", "origin", str(origin))
    _git(seed, "push", "-q", "origin", "main")

    install = tmp_path / "install"
    _git(tmp_path, "clone", "-q", str(origin), str(install))
    _git(install, "checkout", "-q", "--detach", c1)

    checkout = tmp_path / "checkout"
    _git(tmp_path, "clone", "-q", str(origin), str(checkout))
    _git(checkout, "checkout", "-q", "main")

    return {"origin": str(origin), "install": str(install), "checkout": str(checkout), "c1": c1}


def _run(planes: dict[str, str], *a: str, checkout_commit: str | None = None,
         env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    if checkout_commit:
        _git(Path(planes["checkout"]), "checkout", "-q", "--detach", checkout_commit)
    env = {
        **os.environ,
        **_ENV_BASE,
        "OMOSTATION_INSTALL_ROOT": planes["install"],
        "OMOSTATION_CHECKOUT": planes["checkout"],
        "OMOSTATION_CODE_MAIN": "",
        **(env_extra or {}),
    }
    return subprocess.run(["bash", str(SCRIPT), *a], capture_output=True, text=True, env=env, check=False)


def _advance_origin_main(planes: dict[str, str], tmp_path: Path, n: int) -> str:
    """在 origin/main 上追加 n 个提交, 返回新 HEAD。"""
    scratch = tmp_path / "scratch"
    _git(tmp_path, "clone", "-q", planes["origin"], str(scratch))
    _git(scratch, "checkout", "-q", "main")
    sha = ""
    for i in range(n):
        sha = _commit(scratch, f"adv{i}.txt")
    _git(scratch, "push", "-q", "origin", "main")
    return sha


def test_check_measures_against_origin_main_not_the_stale_checkout(planes, tmp_path):
    """检出根陈旧时, --check 仍须报「落后 origin/main」—— 旧实现这里报「锚点一致」exit 0。"""
    _advance_origin_main(planes, tmp_path, 2)
    r = _run(planes, "--check")
    assert r.returncode == 1, f"落后 origin/main 必须 exit 1: {r.stdout} {r.stderr}"
    assert "落后 origin/main 2 个提交" in r.stdout, r.stdout
    # 检出根 HEAD 只作参考, 不得成为基准
    assert "仅参考" in r.stdout, r.stdout


def test_check_ok_when_anchor_equals_origin_main_even_if_checkout_stale(planes, tmp_path):
    """锚点 == origin/main 而检出根陈旧 ⇒ 必须 exit 0 (旧实现此时也 exit 0, 但理由不同)。"""
    sha = _advance_origin_main(planes, tmp_path, 2)
    _git(Path(planes["install"]), "fetch", "-q", "origin")
    _git(Path(planes["install"]), "checkout", "-q", "--detach", sha)
    r = _run(planes, "--check")
    assert r.returncode == 0, f"{r.stdout} {r.stderr}"
    assert "锚点一致" in r.stdout, r.stdout


def test_status_reports_origin_main(planes, tmp_path):
    _advance_origin_main(planes, tmp_path, 1)
    r = _run(planes, "--status")
    assert r.returncode == 0, r.stderr
    assert "origin_main:" in r.stdout, r.stdout
    assert "checkout_sha:" in r.stdout and "仅参考" in r.stdout, r.stdout


def test_reanchor_refuses_to_downgrade(planes, tmp_path):
    """显式传当前锚点的祖先 ⇒ 拒绝 (exit 5), 不得静默把安装位往回切。"""
    c1 = planes["c1"]
    sha = _advance_origin_main(planes, tmp_path, 2)
    _git(Path(planes["install"]), "fetch", "-q", "origin")
    _git(Path(planes["install"]), "checkout", "-q", "--detach", sha)
    r = _run(planes, c1)
    assert r.returncode == 5, f"降级必须被拒: {r.stdout} {r.stderr}"
    assert "降级" in r.stdout + r.stderr
    assert _git(Path(planes["install"]), "rev-parse", "HEAD").stdout.strip() == sha


def test_reanchor_downgrade_allowed_only_with_explicit_opt_in(planes, tmp_path):
    """显式放行后才降级 —— 守卫不是无条件拦截。"""
    c1 = planes["c1"]
    sha = _advance_origin_main(planes, tmp_path, 1)
    _git(Path(planes["install"]), "fetch", "-q", "origin")
    _git(Path(planes["install"]), "checkout", "-q", "--detach", sha)
    r = _run(planes, c1, env_extra={"ANCHOR_ALLOW_DOWNGRADE": "1"})
    assert r.returncode == 0, f"{r.stdout} {r.stderr}"
    assert _git(Path(planes["install"]), "rev-parse", "HEAD").stdout.strip() == c1


def test_default_target_is_origin_main(planes, tmp_path):
    """无参调用 = 重锚到 origin/main (不是检出根 HEAD)。"""
    _advance_origin_main(planes, tmp_path, 2)
    r = _run(planes)
    assert r.returncode == 0, f"{r.stdout} {r.stderr}"
    head = _git(Path(planes["install"]), "rev-parse", "HEAD").stdout.strip()
    want = _git(Path(planes["install"]), "rev-parse", "origin/main").stdout.strip()
    assert head == want, f"默认目标应是 origin/main: head={head} origin/main={want}"


def test_dirty_install_root_is_rejected_without_opt_in(planes, tmp_path):
    """安装位工作树有未提交修改时拒绝重锚 (exit 6)，ANCHOR_ALLOW_DIRTY=1 方可放行。"""
    sha = _advance_origin_main(planes, tmp_path, 2)
    install = Path(planes["install"])
    (install / "dirty_file.txt").write_text("uncommitted", encoding="utf-8")

    # 1. 默认应拒绝
    r = _run(planes)
    assert r.returncode == 6, f"dirty install_root 必须 exit 6: {r.stdout} {r.stderr}"
    assert "未提交的修改" in r.stderr or "dirty" in r.stderr

    # 2. ANCHOR_ALLOW_DIRTY=1 放行
    r_allowed = _run(planes, env_extra={"ANCHOR_ALLOW_DIRTY": "1"})
    assert r_allowed.returncode == 0, f"ANCHOR_ALLOW_DIRTY=1 必须放行: {r_allowed.stdout} {r_allowed.stderr}"


def test_reanchor_generates_and_inspects_release_manifest(planes, tmp_path):
    """重锚成功后在 runtime/ 下产生结构化 release-manifest.json，并支持 --manifest 读取。"""
    sha = _advance_origin_main(planes, tmp_path, 1)
    r = _run(planes)
    assert r.returncode == 0, f"{r.stdout} {r.stderr}"

    manifest_file = Path(planes["install"]) / "runtime" / "release-manifest.json"
    assert manifest_file.is_file(), "必须生成 release-manifest.json"

    import json
    data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert data["source_commit"] == sha
    assert data["install_root"] == planes["install"]
    assert "released_at" in data
    assert data["producer"] == "bin/ssot/anchor-install-root.sh"

    # 测试 --manifest 子命令
    r_man = _run(planes, "--manifest")
    assert r_man.returncode == 0, f"{r_man.stdout} {r_man.stderr}"
    data_out = json.loads(r_man.stdout)
    assert data_out["source_commit"] == sha


def test_reanchor_is_idempotent_on_consecutive_runs(planes, tmp_path):
    """连续重锚不因自身产出的 untracked runtime/release-manifest.json 自阻 (exit 6), 且同 SHA 重锚幂等."""
    sha1 = _advance_origin_main(planes, tmp_path, 1)
    r1 = _run(planes)
    assert r1.returncode == 0, f"第一次重锚应成功: {r1.stdout} {r1.stderr}"
    assert _git(Path(planes["install"]), "rev-parse", "HEAD").stdout.strip() == sha1
    assert (Path(planes["install"]) / "runtime" / "release-manifest.json").is_file()

    # 同 SHA 第二次重锚（验证非降级且不被自身 release-manifest.json 阻断）
    r_same = _run(planes)
    assert r_same.returncode == 0, f"同 SHA 连续重锚应幂等成功: {r_same.stdout} {r_same.stderr}"
    assert _git(Path(planes["install"]), "rev-parse", "HEAD").stdout.strip() == sha1

    # 前进新提交后再次重锚 (使用不同文件名, 避免复用 _advance_origin_main 的 adv0.txt 导致空提交)
    step2 = tmp_path / "step2"
    step2.mkdir()
    scratch2 = step2 / "scratch"
    _git(step2, "clone", "-q", planes["origin"], str(scratch2))
    _git(scratch2, "checkout", "-q", "main")
    sha2 = _commit(scratch2, "adv_step2.txt")
    _git(scratch2, "push", "-q", "origin", "main")
    assert sha2 != sha1
    r2 = _run(planes)
    assert r2.returncode == 0, f"前进后重锚不应因自身 manifest 自阻: {r2.stdout} {r2.stderr}"
    assert _git(Path(planes["install"]), "rev-parse", "HEAD").stdout.strip() == sha2


def test_reanchor_syncs_code_main_without_regressing_from_stale_checkout_origin(planes, tmp_path):
    """code-main 的 origin 指向陈旧只读检出时，重锚必须从安装位直拉并更新 origin/main，绝不倒退。"""
    code_main = tmp_path / "code-main"
    _git(tmp_path, "clone", "-q", planes["checkout"], str(code_main))

    sha = _advance_origin_main(planes, tmp_path, 2)
    extra = {"OMOSTATION_CODE_MAIN": str(code_main)}

    r = _run(planes, env_extra=extra)
    assert r.returncode == 0, f"{r.stdout} {r.stderr}"
    assert _git(code_main, "rev-parse", "HEAD").stdout.strip() == sha
    assert _git(code_main, "rev-parse", "refs/remotes/origin/main").stdout.strip() == sha

    import json
    data = json.loads((Path(planes["install"]) / "runtime" / "release-manifest.json").read_text(encoding="utf-8"))
    assert data["code_main"] == str(code_main)
    assert data["code_main_sha"] == sha

    # 连续重锚与 --check 均须幂等通过
    assert _run(planes, env_extra=extra).returncode == 0
    assert _run(planes, "--check", env_extra=extra).returncode == 0
    st = _run(planes, "--status", env_extra=extra)
    assert st.returncode == 0
    assert f"code_main_sha: {sha}" in st.stdout


def test_check_fails_when_code_main_lags_behind_target(planes, tmp_path):
    """安装位已对齐 origin/main、但 code-main 滞后时，--check 必须失败 (exit 1)。"""
    code_main = tmp_path / "code-main"
    _git(tmp_path, "clone", "-q", planes["origin"], str(code_main))

    sha = _advance_origin_main(planes, tmp_path, 1)
    _git(Path(planes["install"]), "fetch", "-q", "origin")
    _git(Path(planes["install"]), "checkout", "-q", "--detach", sha)

    r = _run(planes, "--check", env_extra={"OMOSTATION_CODE_MAIN": str(code_main)})
    assert r.returncode == 1, f"code-main 滞后必须 exit 1: {r.stdout} {r.stderr}"
    assert "code-main" in r.stdout


def test_dirty_code_main_is_rejected_without_opt_in(planes, tmp_path):
    """code-main 工作区存在未提交改动时拒绝重锚 (exit 6)，ANCHOR_ALLOW_DIRTY=1 方可放行。"""
    code_main = tmp_path / "code-main"
    _git(tmp_path, "clone", "-q", planes["origin"], str(code_main))
    sha = _advance_origin_main(planes, tmp_path, 1)
    (code_main / "dirty_cm.txt").write_text("uncommitted", encoding="utf-8")

    r = _run(planes, env_extra={"OMOSTATION_CODE_MAIN": str(code_main)})
    assert r.returncode == 6, f"dirty code-main 必须 exit 6: {r.stdout} {r.stderr}"
    assert "code-main" in r.stderr
    assert _git(Path(planes["install"]), "rev-parse", "HEAD").stdout.strip() == planes["c1"]

    r_ok = _run(planes, env_extra={"OMOSTATION_CODE_MAIN": str(code_main), "ANCHOR_ALLOW_DIRTY": "1"})
    assert r_ok.returncode == 0, f"{r_ok.stdout} {r_ok.stderr}"
    assert _git(code_main, "rev-parse", "HEAD").stdout.strip() == sha


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
