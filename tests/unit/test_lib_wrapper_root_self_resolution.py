"""lib/ wrapper 的仓根必须由脚本自身位置自推，检测器一次扫描同时给出改前 N 与改后 0。

契约: `docs/superpowers/specs/2026-10-28-bet-275-lib-wrapper-root-self-resolution.md` (C-1..C-4)
BET: BET-Y2Q4-T10-275

三层判据，缺一层就留下"绿着但根还是钉死"的缝:
- **反基线**: `PRE_FIX_WRAPPERS` 是 origin/main 上这三份的逐字节内容 (见 BET receipt 的
  `git archive origin/main lib` 读数)，同一把尺在其上命中 3 处。只断言"现在是 0"，
  那么"少认一种形状 + 多认一处合法"也能凑出绿 (AGENTS.md §7⑤)。
- **自证**: 合成违规必须被点名到行，`/opt/homebrew/bin/uv` 这类外部二进制不得被点名。
- **语义**: 改法只允许动"根从哪来"，命令语义逐行等值 (C-3)，否则这条 BET 就成了偷改行为。
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

CHECKOUT_LITERAL = "/Users/xiamingxing/Workspace"
SEAM_ASSIGNMENTS = ("_SELF_DIR=", "_REPO_ROOT=")
WRAPPERS = ("lib/agora-daemon.sh", "lib/agora-sse.sh", "lib/bet-claim-gc.sh")


def _repo_root() -> Path:
    """被检对象的根走显式 resolver，不由本测试文件反推 (AGENTS.md §7③)。"""
    spec = importlib.util.spec_from_file_location(
        "t275_repo_root", Path(__file__).resolve().parents[2] / "bin/lib/repo_root.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.code_root()


# origin/main 上这三份 wrapper 的逐字节内容 (改前基线，反基线读数由它产出)
PRE_FIX_WRAPPERS: dict[str, str] = {
    "lib/agora-daemon.sh": """\
#!/usr/bin/env bash
# agora-daemon wrapper (ADR-0435 模式, 2026-09-10 修复 exit 78 崩循环).
# 旧 plist 双重死: WorkingDirectory 指向已清理的 T1-12 临时 worktree
# (ws-t1-12-agora-launchd-deploy) + 裸 python3 无依赖环境。
# 正确形态: uv run (装齐 agora 依赖) + 绝对路径 cd 后跑 daemon.py。
set -euo pipefail
cd /Users/xiamingxing/Workspace/projects/agora
exec /opt/homebrew/bin/uv run python src/agora/daemon.py
""",
    "lib/agora-sse.sh": """\
#!/usr/bin/env bash
# agora-sse wrapper (ADR-0435 判例第四例修复, 2026-09-08).
# 坏形态: uv <agora-dir> agora-mcp --sse (缺 run 动词, exit 2 死循环).
# 正确形态: uv run --project <agora> agora-mcp --sse
set -euo pipefail
exec /opt/homebrew/bin/uv run --project /Users/xiamingxing/Workspace/projects/agora \\
  agora-mcp --sse
""",
    "lib/bet-claim-gc.sh": """\
#!/usr/bin/env bash
# bet-claim-gc wrapper (T10-140 迭代: T10-139 claim-gc 的调度补全).
#
# claim-bet 广播文件 7d TTL 自清理 — 过期视为放弃, 只删广播文件不动 ledger
# status (后续认领自然接管)。launchd com.l4.bet-claim-gc 每日触发。
# bet-ledger.py 需要 pyyaml, 走 uv (ADR-0435: uv-run 形态一律 wrapper)。
set -euo pipefail
exec /opt/homebrew/bin/uv run --with pyyaml \\
  python /Users/xiamingxing/Workspace/bin/plan/bet-ledger.py claim-gc
""",
}


def _scan(files: dict[str, str]) -> list[tuple[str, int, str]]:
    """检出根字面量检测器: 命中 (相对路径, 行号, 行)。

    尺只认 `/Users/<name>/` 这一形 (个人主目录绝对前缀)。`/opt/homebrew/`、`/usr/bin/`
    这类系统/外部二进制路径不是仓根，合法，不得命中。
    """
    hits: list[tuple[str, int, str]] = []
    for rel, text in sorted(files.items()):
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "/Users/" in line:
                hits.append((rel, lineno, line))
    return hits


def _tracked_wrappers() -> dict[str, str]:
    root = _repo_root()
    return {rel: (root / rel).read_text(encoding="utf-8") for rel in WRAPPERS}


def _command_lines(text: str) -> list[str]:
    """命令负载行: 去掉 shebang / 注释 / set 头 / 自推根的两行赋值，再归一化。

    归一化 = 把自推根变量代回字面量根 + 剥掉 shell 引号。引号对不含空格与 glob 的路径
    不改变分词结果，所以这是语义等值而不是文本等值 —— 明说不然会读成后者。
    """
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "set -euo pipefail":
            continue
        if stripped.startswith(SEAM_ASSIGNMENTS):
            continue
        normalized = stripped.replace('"$_REPO_ROOT"', CHECKOUT_LITERAL).replace(
            "$_REPO_ROOT", CHECKOUT_LITERAL
        )
        out.append(normalized.replace('"', ""))
    return out


def test_pre_fix_baseline_scans_to_three_hits() -> None:
    """反基线: 同一把尺在改前内容上必须命中 3 处，且三份都被点名。"""
    hits = _scan(PRE_FIX_WRAPPERS)
    assert len(hits) == 3, f"反基线读数应为 3，实为 {len(hits)}: {hits}"
    assert {rel for rel, _, _ in hits} == set(WRAPPERS)


def test_tracked_lib_wrappers_have_no_checkout_root_literal() -> None:
    """改后: 跟踪中的三份 wrapper 命中 0 处。"""
    files = _tracked_wrappers()
    assert set(files) == set(WRAPPERS)
    hits = _scan(files)
    assert hits == [], f"lib/ wrapper 仍有检出根字面量: {hits}"


def test_detector_is_not_a_no_op_and_names_the_synthetic_violation(
    tmp_path: Path,
) -> None:
    """自证: 向一份干净 wrapper 注入别人的主目录字面量，检测器必须点名到那一行。

    注入的是 `/Users/someone/...` 而非本机根 (spec done_when-3) —— 若尺写死成只匹配
    `Workspace` 那台机器的那个根，它既命中不了合成样本，也就对任何机器都"绿"。
    没有这条，上面两条的"绿"可能只是尺压根没命中 (AGENTS.md §7②)。
    """
    victim = tmp_path / "lib" / "synthetic.sh"
    victim.parent.mkdir(parents=True)
    foreign_literal = "/Users/someone/Workspace/projects/x"
    body = (
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"exec python {foreign_literal}/run.py --claim-gc\n"
    )
    victim.write_text(body, encoding="utf-8")
    hits = _scan({str(victim.relative_to(tmp_path)): body})
    assert len(hits) == 1, f"合成违规未被命中: {hits}"
    rel, lineno, line = hits[0]
    assert rel == "lib/synthetic.sh"
    assert lineno == 3, f"命中行号应指向注入行，实为 {lineno}"
    assert "run.py" in line
    # 本机根之外的主目录同样命中 —— 尺的判准是"个人主目录绝对前缀"，不是某一个具体检出
    assert _scan({"lib/other.sh": f'cd {CHECKOUT_LITERAL}/projects/agora\n'}) == [
        ("lib/other.sh", 1, f"cd {CHECKOUT_LITERAL}/projects/agora")
    ]


def test_allowed_external_binary_path_is_not_named() -> None:
    """反面: 外部二进制绝对路径合法，不得计入违规 (否则尺过宽，靠加豁免也能凑绿)。"""
    allowed = {
        "lib/allowed.sh": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "exec /opt/homebrew/bin/uv run --project /some/other/root/projects/agora \\\n"
            "  agora-mcp --sse\n"
        )
    }
    assert _scan(allowed) == []
    # 而同一份内容换成个人主目录前缀必须命中 —— 证明差异是尺的判准，不是它没跑
    widened = {
        "lib/allowed.sh": allowed["lib/allowed.sh"].replace(
            "/some/other/root", CHECKOUT_LITERAL
        )
    }
    assert len(_scan(widened)) == 1


def test_every_wrapper_derives_repo_root_from_its_own_location() -> None:
    """C-1: 三份都携带自推根缝，并且真正消费它，互不引用另一棵树。"""
    for rel, text in _tracked_wrappers().items():
        lines = text.splitlines()
        assert any(ln.strip().startswith("_SELF_DIR=") for ln in lines), f"{rel} 缺 _SELF_DIR"
        assert any(ln.strip().startswith("_REPO_ROOT=") for ln in lines), f"{rel} 缺 _REPO_ROOT"
        assert any("$_REPO_ROOT" in ln and not ln.strip().startswith(SEAM_ASSIGNMENTS)
                   for ln in lines), f"{rel} 推了根却没消费"
        # 安装位与检出根各自自推: 不得出现指向另一棵树的字面量 (C-2)
        assert "/Users/" not in text, f"{rel} 仍有主目录字面量"


def test_wrapper_command_semantics_are_unchanged() -> None:
    """C-3: 命令负载逐行等值 —— 改动只允许发生在"根从哪来"。"""
    for rel, before in PRE_FIX_WRAPPERS.items():
        after = _tracked_wrappers()[rel]
        assert _command_lines(after) == _command_lines(before), (
            f"{rel} 的命令语义发生变化: "
            f"before={_command_lines(before)} after={_command_lines(after)}"
        )


def test_wrappers_are_syntax_valid() -> None:
    """bash -n 三份都通过 —— 自推根那两行是 shell 语法，写错就当场红。"""
    root = _repo_root()
    for rel in WRAPPERS:
        proc = subprocess.run(
            ["bash", "-n", str(root / rel)], capture_output=True, text=True
        )
        assert proc.returncode == 0, f"{rel}: {proc.stderr}"
