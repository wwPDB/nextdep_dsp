"""Console script for nextdep_dsp."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

app = typer.Typer()
sessions_app = typer.Typer(help="Manage local deposition sessions.")
app.add_typer(sessions_app, name="sessions")

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RichHandler(console=console, show_time=False)],
)
log = logging.getLogger(__name__)


@sessions_app.command("list")
def sessions_list(
    base_dir: Optional[Path] = typer.Option(None, "--base-dir", help="Override session storage directory."),
) -> None:
    """List all local deposition sessions."""
    from nextdep_dsp.dsp import list_sessions

    entries = list_sessions(base_dir=base_dir)

    if not entries:
        console.print("[yellow]No sessions found.[/yellow]")
        raise typer.Exit()

    table = Table(
        show_header=True,
        header_style="bold cyan",
        show_lines=True,
    )
    table.add_column("Session ID", style="dim", no_wrap=True, min_width=36)
    table.add_column("Created", no_wrap=True, min_width=16)
    table.add_column("Email", min_width=20)
    table.add_column("Experiment", justify="center", min_width=10)
    table.add_column("Remote dep ID", justify="center", min_width=12)
    table.add_column("Files", min_width=30)

    for session, files in entries:
        remote = session.remote_dep_id or "[dim](none)[/dim]"
        experiment = session.experiment_type.value if session.experiment_type else "[dim]-[/dim]"
        created = session.created_at.strftime("%Y-%m-%d %H:%M")

        if files:
            files_text = "\n".join(
                f"[green]{Path(f.file_path).name}[/green]  [dim]{f.file_type.value}[/dim]"
                for f in files
            )
        else:
            files_text = "[dim](none)[/dim]"

        table.add_row(
            session.session_id,
            created,
            session.email,
            experiment,
            remote,
            files_text,
        )

    console.print(table)


if __name__ == "__main__":
    app()
