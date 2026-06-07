"""MCP server lifecycle commands: mcp, web, init, completion."""

from __future__ import annotations


def cmd_mcp(_args):
    """Start MCP server."""
    from agora.server.mcp import main as mcp_main  # type: ignore[import-not-found]

    return mcp_main()


def cmd_web(_args):
    """Start Web Dashboard."""
    from agora.web.app import main as web_main  # type: ignore[import-not-found]

    print("Agora Dashboard -> http://localhost:7430")
    return web_main()


def cmd_init(_args):
    """Guided setup wizard."""
    from agora.plugins.identity.wizard import run_wizard  # type: ignore[import-not-found]

    return run_wizard()


def cmd_completion(args):
    """Generate shell completion (bash/zsh/fish)."""
    from agora.cli.parser import build_parser

    parser = build_parser()
    cmds = []
    for action in parser._subparsers._group_actions:
        for choice in action.choices:
            cmds.append(choice)
    cmd_str = " ".join(sorted(cmds))

    shell = getattr(args, 'shell', 'bash')
    if shell == 'fish':
        print(f"# Add to ~/.config/fish/config.fish:")
        print(f'#   agora completion --shell fish | source')
        print()
        print(f"complete -c agora -f")
        for c in sorted(cmds):
            print(f"complete -c agora -n 'not __fish_seen_subcommand_from {' '.join(cmds)}' -a {c}")
    else:
        print("# Add to ~/.bashrc or ~/.zshrc:")
        print('#   eval "$(agora completion)"')
        print()
        print("_agora_completion() {")
        print("  local cur=${COMP_WORDS[COMP_CWORD]}")
        print(f'  local cmds="{cmd_str}"')
        print('  COMPREPLY=($(compgen -W "$cmds" -- "$cur"))')
        print("  return 0")
        print("}")
        print("complete -F _agora_completion agora")
    print("}")
    print("complete -F _agora_completion agora")
    return 0
