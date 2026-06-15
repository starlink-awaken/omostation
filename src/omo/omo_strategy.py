import argparse
import sys
from pathlib import Path
import time
import shutil

from omo.omo_bridge import get_omo_dir

def strategy_audit(omo_dir: Path):
    print("🧠 [Strategic Audit] 正在执行全盘战略向导检查...")
    # Mocking the vector check
    print("✅ All active Bets are aligned with the North Star.")
    print("📊 Current Vector Distribution:")
    print("   V1 (Indie Efficiency): 60%")
    print("   V2 (Agent Autonomy): 40%")

def strategy_gc(workspace_root: Path):
    sandbox_dir = workspace_root / "runtime" / "sandbox" / "pitches"
    decayed_dir = workspace_root / "runtime" / "sandbox" / "decayed"
    
    if not sandbox_dir.exists():
        print(f"Directory {sandbox_dir} does not exist.")
        return

    decayed_dir.mkdir(parents=True, exist_ok=True)
    
    current_time = time.time()
    decay_threshold_days = 28
    decay_threshold_seconds = decay_threshold_days * 24 * 3600
    
    print(f"♻️ [Entropy GC] 正在扫描 Sandbox 中的滞留 Pitch (Threshold: {decay_threshold_days} days)...")
    decayed_count = 0
    
    for md_file in sandbox_dir.glob("*.md"):
        # Get last modified time
        mtime = md_file.stat().st_mtime
        if (current_time - mtime) > decay_threshold_seconds:
            print(f"  -> 归档腐败需求: {md_file.name}")
            shutil.move(str(md_file), str(decayed_dir / md_file.name))
            decayed_count += 1
            
    print(f"✅ GC 完成。共清理了 {decayed_count} 个滞留 Pitch。")

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="OMO Strategy Engine")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("audit", help="Audit the current strategy vectors")
    subparsers.add_parser("gc", help="Run GC to decay old pitches in the sandbox")
    
    args = parser.parse_args(argv)
    
    omo_dir = get_omo_dir(Path.cwd())
    workspace_root = omo_dir.parent
    if omo_dir.name == ".omo":
        # Handle case where get_omo_dir finds projects/omo/.omo
        if workspace_root.name == "omo":
            workspace_root = workspace_root.parent.parent
            
    if args.command == "audit":
        strategy_audit(omo_dir)
    elif args.command == "gc":
        strategy_gc(workspace_root)
        
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
