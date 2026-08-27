#!/usr/bin/env python3
"""
Workspace CLI — omostation 统一命令行入口
统一操作所有域的工具链
"""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


def cmd_status(args):
    """查看全域状态"""
    base = Path(args.base)
    print("📊 omostation 全域状态")
    print("=" * 50)
    
    for domain_dir in sorted(base.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith("_") or domain_dir.name.startswith("."):
            continue
        
        claude = domain_dir / "CLAUDE.md"
        if not claude.exists():
            continue
        
        # Quick stats
        knowledge = domain_dir / "_knowledge"
        control = domain_dir / "_control"
        ocr = domain_dir / "_ocr_text"
        
        k_count = len(list(knowledge.glob("*.md"))) if knowledge.exists() else 0
        c_count = len(list(control.glob("*.md"))) if control.exists() else 0
        o_count = len(list(ocr.glob("*.txt"))) if ocr.exists() else 0
        
        print(f"\n📁 {domain_dir.name}")
        print(f"   知识: {k_count} | 控制: {c_count} | OCR: {o_count}")


def cmd_health(args):
    """域健康检查"""
    base = Path(args.base)
    print("🏥 全域健康检查")
    print("=" * 50)
    
    for domain_dir in sorted(base.iterdir()):
        if not domain_dir.is_dir() or domain_dir.name.startswith("_") or domain_dir.name.startswith("."):
            continue
        
        claude = domain_dir / "CLAUDE.md"
        if not claude.exists():
            continue
        
        control = domain_dir / "_control"
        required = ["sensors.md", "control-rules.md", "executor-rules.md", "l4-kernel.md"]
        
        print(f"\n📁 {domain_dir.name}")
        for name in required:
            path = control / name
            status = "✅" if path.exists() else "❌"
            print(f"   {status} {name}")


def cmd_ocr(args):
    """运行 OCR"""
    from tools.kems import KEMEngine
    
    domain_root = Path(args.base) / args.domain
    if not domain_root.exists():
        print(f"域不存在: {domain_root}")
        return
    
    engine = KEMEngine(domain_root)
    engine.run_full_pipeline()


def cmd_discover(args):
    """发现域"""
    from tools.domain import DomainRegistry
    
    base = Path(args.base)
    domains = DomainRegistry.discover(str(base))
    
    print(f"发现 {len(domains)} 个域:")
    for d in domains:
        print(f"  📁 {d['name']}")
        print(f"     知识: {'✅' if d['has_knowledge'] else '❌'} | "
              f"控制: {'✅' if d['has_control'] else '❌'} | "
              f"OCR: {'✅' if d['has_ocr'] else '❌'}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="omostation workspace CLI")
    sub = parser.add_subparsers(dest="command")
    
    # status
    p_status = sub.add_parser("status", help="查看全域状态")
    p_status.add_argument("--base", default="/Users/xiamingxing/Documents/@工作文档")
    p_status.set_defaults(func=cmd_status)
    
    # health
    p_health = sub.add_parser("health", help="健康检查")
    p_health.add_argument("--base", default="/Users/xiamingxing/Documents/@工作文档")
    p_health.set_defaults(func=cmd_health)
    
    # ocr
    p_ocr = sub.add_parser("ocr", help="运行 OCR 流水线")
    p_ocr.add_argument("--domain", required=True)
    p_ocr.add_argument("--base", default="/Users/xiamingxing/Documents/@工作文档")
    p_ocr.set_defaults(func=cmd_ocr)
    
    # discover
    p_discover = sub.add_parser("discover", help="发现域")
    p_discover.add_argument("--base", default="/Users/xiamingxing/Documents/@工作文档")
    p_discover.set_defaults(func=cmd_discover)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
