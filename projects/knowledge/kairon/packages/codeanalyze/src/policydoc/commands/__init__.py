"""Load and register all policydoc commands."""

from .analyze_cmd import analyze
from .audit_cmd import audit
from .dashboard_cmd import dashboard
from .docscan_cmd import docscan
from .documents_cmd import documents
from .export_cmd import export
from .install_cmd import install
from .status_cmd import status
from .wiki_cmd import wiki


def load_commands(cli):
    cli.add_command(status)
    cli.add_command(analyze)
    cli.add_command(documents)
    cli.add_command(docscan)
    cli.add_command(wiki)
    cli.add_command(audit)
    cli.add_command(export)
    cli.add_command(install)
    cli.add_command(dashboard)
