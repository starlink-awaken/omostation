import datetime
import json
import sys

import httpx
from rich.console import Console
from rich.live import Live
from rich.table import Table


def run_events_dashboard(url: str = "http://127.0.0.1:8080/v1/events"):
    console = Console()
    console.print(f"[bold cyan]🚀 Connecting to Agora SSE Event Stream: {url}[/bold cyan]")

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Time", style="dim", width=10)
    table.add_column("Type", style="cyan", width=15)
    table.add_column("Source", style="green", width=15)
    table.add_column("Target", style="blue", width=15)
    table.add_column("Payload", style="white")

    with Live(table, console=console, refresh_per_second=4) as live:
        try:
            with httpx.Client(timeout=None) as client:  # noqa: S113
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line.startswith("data:"):
                            try:
                                data_str = line[5:].strip()
                                if not data_str:
                                    continue
                                event = json.loads(data_str)

                                # Extract fields
                                etype = event.get("type", "unknown")
                                src = event.get("source", "-")
                                target = event.get("target", "-")
                                payload = event.get("payload", {})

                                ts = datetime.datetime.now().strftime("%H:%M:%S")

                                payload_str = str(payload)
                                if len(payload_str) > 60:
                                    payload_str = payload_str[:57] + "..."

                                table.add_row(ts, etype, src, target, payload_str)
                            except Exception:
                                pass
        except httpx.ConnectError:
            live.stop()
            console.print(
                "[bold red]❌ Failed to connect to Agora. Is it running? (Are you missing `agora` or `uv run agora`?)[/bold red]"
            )
            sys.exit(1)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            live.stop()
            console.print(f"[bold red]❌ Stream disconnected: {e}[/bold red]")
