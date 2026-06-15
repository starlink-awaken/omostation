import argparse
import sys
from pathlib import Path

from c2g.bridge import _import_bmad, _import_fast_track, _import_pitch, get_omo_dir
from c2g.strategy import strategy_audit, strategy_gc

def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description="C2G (Concept-to-Goal) Engine - The Strategic Pipeline")
    parser.add_argument("--adapter", type=str, default="local", choices=["ecos", "local"], help="Which backend adapter to use")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # 1. Brainstorm (V2P) - a placeholder for MetaOS integration
    parser_bs = subparsers.add_parser("brainstorm", help="[V2P] Trigger MetaOS to generate a Pitch")
    parser_bs.add_argument("topic", type=str, help="The topic to brainstorm")
    
    # 2. Bet (C2G) - bridging pitch to bet
    parser_bet = subparsers.add_parser("bet", help="[C2G] Convert a Pitch into a tracked Bet")
    parser_bet.add_argument("source_file", type=str, help="Path to the Pitch markdown file")
    
    # 3. Radar (AGC) - strategy audit
    subparsers.add_parser("radar", help="[AGC] Audit system strategy alignment (Radar)")
    
    # 4. GC (AGC) - entropy garbage collection
    parser_gc = subparsers.add_parser("gc", help="[AGC] Garbage collect decayed Sandbox pitches")
    parser_gc.add_argument("--dry-run", action="store_true", help="Preview GC without moving files")
    
    args = parser.parse_args(argv)
    
    omo_dir = get_omo_dir(Path.cwd()) if args.adapter == "ecos" else Path.cwd()
    workspace_root = omo_dir.parent
    if omo_dir.name == ".omo":
        if workspace_root.name == "omo":
            workspace_root = workspace_root.parent.parent
            
    if args.command == "brainstorm":
        print(f"🧠 [V2P] 正在拉起 MetaOS 针对主题 '{args.topic}' 进行发散...")
        print("  -> (Mock) 提案生成成功，已存入 runtime/sandbox/pitches/")
    
    elif args.command == "bet":
        source = Path(args.source_file)
        if not source.exists():
            print(f"❌ Error: Pitch file {source} not found.")
            return 1
        print(f"🌉 [C2G] 触发桥接，验证 M2 Schema 与 L0 约束...")
        _import_pitch(source, omo_dir, args.adapter)
        
    elif args.command == "radar":
        strategy_audit(omo_dir, args.adapter)
        
    elif args.command == "gc":
        strategy_gc(workspace_root, args.adapter)
        
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
