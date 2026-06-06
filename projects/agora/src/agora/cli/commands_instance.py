"""Instance management CLI commands."""


def cmd_instance(args):
    from agora.instance import AgoraInstance, InstanceManager  # type: ignore[import-not-found]

    im = InstanceManager()
    if args.instance_cmd == "list":
        insts = im.list()
        if not insts:
            print("No instances registered.")
            return
        for inst in insts:
            print(f"  {inst.instance_id:30s} {inst.instance_type:12s} {inst.display_name}")
            print(f"  {'':30s} A2A: {inst.a2a_endpoint}")
            print(f"  {'':30s} peers: {', '.join(inst.peers[:3])}")
            print()
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
        print(f"Registered: {inst.instance_id}")
    elif args.instance_cmd == "peer":
        im.add_peer(args.instance_id, args.peer_id)
        print(f"Peer added: {args.peer_id} → {args.instance_id}")
