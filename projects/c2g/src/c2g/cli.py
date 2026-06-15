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
    
    # 1.5 Draft (V2P) - Interactive Pitch Wizard
    parser_draft = subparsers.add_parser("draft", help="[V2P] Interactive wizard to draft a Pitch")
    
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
        
    elif args.command == "draft":
        print("\n🧠 [C2G 战略向导] 让我们把模糊的点子变成具体的行动：")
        try:
            idea = input("? 一句话描述您的点子 (Core Idea): ").strip()
            upstream = input("? 这个点子的北极星/上游愿景是什么 (Upstream, e.g. 提升工程质量): ").strip()
            appetite = input("? 您的胃口/预算是多少 (Appetite, e.g. 2小时 / 1周): ").strip()
            context = input("? 补充一些背景信息 (可选): ").strip()
        except KeyboardInterrupt:
            print("\n❌ 已取消。")
            return 1
            
        if not idea:
            print("❌ 点子不能为空，已取消。")
            return 1
            
        import re
        safe_title = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]+', '-', idea)[:20].strip('-')
        file_name = f"Idea-{safe_title}.md"
        
        if args.adapter == "ecos":
            pitches_dir = workspace_root / "runtime" / "sandbox" / "pitches"
        else:
            pitches_dir = Path(".c2g_data") / "pitches"
            
        pitches_dir.mkdir(parents=True, exist_ok=True)
        pitch_path = pitches_dir / file_name
        
        content = f"# {idea}\n\n> **Upstream**: {upstream or 'Unknown'}\n> **Appetite:** {appetite or 'Unknown'}\n\n## 背景与上下文\n{context}\n"
        pitch_path.write_text(content, encoding="utf-8")
        
        print(f"\n✅ 成功！Pitch 已生成于 {pitch_path}")
        print(f"➡️ 下一步：您可以执行 `workspace compass bet {pitch_path}` 进行下注转换。")
    
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
