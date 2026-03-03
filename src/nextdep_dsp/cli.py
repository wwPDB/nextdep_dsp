"""Console script for nextdep_dsp."""

import typer
from rich.console import Console

from nextdep_dsp import utils

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Console script for nextdep_dsp."""
    console.print("Replace this message by putting your code into "
               "nextdep_dsp.cli.main")
    console.print("See Typer documentation at https://typer.tiangolo.com/")
    utils.do_something_useful()


if __name__ == "__main__":
    app()
