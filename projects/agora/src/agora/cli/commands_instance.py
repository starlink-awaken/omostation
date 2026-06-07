"""Instance management CLI commands."""

from agora.cli.errors import CLIError
from agora.cli.output import OutputFormatter


def cmd_instance(args):
    from agora.instance import AgoraInstance, InstanceManager  # type: ignore[import-not-found]

    out = OutputFormatter(json_mode=getattr(args, 'json', False))
    try:
        im = InstanceManager()
        if args.instance_cmd == "list":
            insts = im.list()
            if not insts:
                out.print_info("没有注册的实例。使用 'agora instance register' 注册新实例")
                return 0
            for inst in insts:
                print(f"  {inst.instance_id:30s} {inst.instance_type:12s} {inst.display_name}")
                print(f"  {'':30s} A2A: {inst.a2a_endpoint}")
                print(f"  {'':30s} peers: {', '.join(inst.peers[:3])}")
                print()
            return 0
        elif args.instance_cmd == "register":
            inst = AgoraInstance(
                instance_id=args.instance_id,
                instance_type=args.type,
                display_name=args.display_name,
                endpoint=args.endpoint,
                a2a_endpoint=args.a2a_endpoint or f"{args.endpoint}/a2a",
                owner=args.owner or "org:starlink",
                capabilities=args.capabilities.split(",") if args.capabilities else ["identity"],
                services=[],
                peers=[],
            )
            im.register(inst)
            out.print_success(f"Registered: {inst.instance_id}")
            return 0
        elif args.instance_cmd == "peer":
            im.add_peer(args.instance_id, args.peer_id)
            out.print_success(f"Peer added: {args.peer_id} -> {args.instance_id}")
            return 0
    except CLIError as e:
        out.print_error(e.message, e.suggestion)
        return e.exit_code
    except Exception as e:
        out.print_error(str(e), "使用 'agora --help' 获取帮助")
        return 1
