from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAIM_SCRIPT = ROOT / "bin" / "gac" / "gac-worktree.sh"
CLEANUP_SCRIPT = ROOT / "bin" / "gac" / "gac-worktree-cleanup.sh"


def test_claim_creates_and_cleans_initialization_marker() -> None:
    source = CLAIM_SCRIPT.read_text()

    marker_assignment = 'claim_in_progress="$WS_PARENT/.ws-$session.claiming"'
    marker_creation = ': > "$claim_in_progress"'
    marker_cleanup = "cleanup_claim_marker"

    assert marker_assignment in source
    assert marker_creation in source
    assert source.index(marker_assignment) < source.index(marker_creation)
    assert source.count(marker_cleanup) >= 3
    assert "trap cleanup_claim_marker EXIT INT TERM" in source
    assert "trap - EXIT INT TERM" in source


def test_cleanup_skips_worktree_during_claim_initialization() -> None:
    source = CLEANUP_SCRIPT.read_text()

    marker_check = 'if [ -f "$claim_in_progress" ]; then'
    removal = 'git worktree remove "$wt_path"'

    assert 'session=${wt_name#ws-}' in source
    assert marker_check in source
    assert source.index(marker_check) < source.index(removal)
    assert "claim 初始化进行中, 跳过" in source
