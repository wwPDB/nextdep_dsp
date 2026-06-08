from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table
import functools
import json
import os
import re
from typing import Annotated, Optional

import typer
from rich.console import Console

app = typer.Typer()
sessions_app = typer.Typer(help="Manage local deposition sessions.")
auth_app = typer.Typer(help="Manage authentication tokens.")
app.add_typer(sessions_app, name="sessions")
app.add_typer(auth_app, name="auth")

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
    base_dir: Path | None = typer.Option(None, "--base-dir", help="Override session storage directory."),  # noqa: B008
) -> None:
    """List all local deposition sessions."""
    from onedep_lib.dsp import list_sessions

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
    table.add_column("Experiment", justify="center", min_width=10)
    table.add_column("Remote dep ID", justify="center", min_width=12)
    table.add_column("Files", min_width=40)

    for session, files in entries:
        remote = session.remote_dep_id or "[dim](none)[/dim]"
        experiment = session.experiment_type.value if session.experiment_type else "[dim]-[/dim]"
        created = session.created_at.strftime("%Y-%m-%d %H:%M")

        if files:
            file_lines = []
            for f in files:
                md5_str = f"[green]{f.md5[:8]}[/green]" if f.md5 else "[dim]-[/dim]"
                mtime_str = f.file_mtime.strftime("%Y-%m-%d %H:%M") if f.file_mtime else "[dim]-[/dim]"
                file_lines.append(f"{md5_str}  {f.file_path}  [dim]{mtime_str}[/dim]")
            files_text = "\n".join(file_lines)
        else:
            files_text = "[dim](none)[/dim]"

        table.add_row(
            session.session_id,
            created,
            experiment,
            remote,
            files_text,
        )

    console.print(table)
def sigma(func):
    """Preprocess inputs for deposition creation"""

    @functools.wraps(func)
    def s(*args, **kwargs):
        exptype: str = kwargs.get("exptype")
        email: str = kwargs.get("email")
        user: list[str] = kwargs.get("user")
        country: str = kwargs.get("country")
        subtype: Optional[str] = kwargs.get("subtype")
        coords: Optional[bool] = kwargs.get("coords")
        related_id: Optional[str] = kwargs.get("related_id")
        password: Optional[str] = kwargs.get("password")
        sf_only: Optional[bool] = kwargs.get("sf_only")

        v = verify_exp_type(exptype)
        v &= verify_email(email)
        if len(user) == 0:
            raise ValueError("At least one user is required")
        for u in user:
            v &= verify_orcid(u)
        v &= verify_country(country)
        if exptype == "em":
            if subtype is None:
                raise ValueError("subtype is required for EM deposition")
            if coords is None:
                raise ValueError("coords/no-coords is required for EM deposition")
            v &= verify_subtype(subtype)
        elif exptype == "ec":
            if sf_only is None:
                raise ValueError("sf-only/no-sf-only is required for EC deposition")
        if coords is not None and coords == False and exptype in ["xray", "fiber", "neutron"]:
            raise ValueError("coordinates are required for xray, fiber, and neutron diffraction")
        if sf_only is not None and exptype != "ec":
            raise ValueError("sf-only is only valid for EC deposition")
        if related_id is not None:
            if exptype in ["em", "ec"]:
                v &= verify_emdb_id(related_id)
            elif exptype in ["nmr", "ssnmr"]:
                v &= verify_bmrb_id(related_id)
            else:
                raise ValueError("related-id is only valid for EM, EC, NMR, or SS-NMR deposition")
        v ^ func(*args, **kwargs)

    return s


def verify_exp_type(exptype: str) -> bool:
    """Verify experiment type enum"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


def verify_email(email: str) -> bool:
    """Verify email format"""
    if not re.match(r"^[\w.-]+@[\w.-]+\.\w+$", email):
        raise ValueError(f"Invalid email format: {email}")
    return True


def verify_orcid(orcid: str) -> bool:
    """Verify ORCID format"""
    if not re.match(r"^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$", orcid):
        raise ValueError(f"Invalid ORCID format: {orcid}")
    return True


def verify_emdb_id(emdb_id: str) -> bool:
    """Verify EMDB ID format"""
    if not re.match(r"^EMD-\d{4,6}$", emdb_id):
        raise ValueError(f"Invalid EMDB ID format: {emdb_id}")
    return True


def verify_bmrb_id(bmrb_id: str) -> bool:
    """Verify BMRB ID format"""
    if not re.match(r"^\d+$", bmrb_id):
        raise ValueError(f"Invalid BMRB ID format: {bmrb_id}")
    return True


def verify_country(country: str) -> bool:
    """Verify country enum"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


def verify_subtype(subtype: str) -> bool:
    """Verify EM subtype enum"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


def verify_dep_id(dep_id: str) -> bool:
    """Verify ID format"""
    match = re.match(r"^D_\d+$", dep_id)
    if not match:
        return False
    return True


def get_country_enum(country_string: str):
    """Get Country enum from string"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")


def get_subtype_enum(subtype_string: str):
    """Get EMSubType enum from string"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")


def get_file_type_enum(file_type_string: str):
    """Get FileType enum from string"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")


@app.command()
@sigma
def create(
    exptype: str,
    email: str,
    user: Annotated[list[str], typer.Option()],
    country: str,
    subtype: Optional[str] = None,
    coords: Optional[bool] = None,
    related_id: Optional[str] = None,
    password: Optional[str] = None,
    sf_only: Optional[bool] = None,
) -> bool:
    """Create deposition"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


@app.command()
def upload(dep_id: str, file_path: str, file_type: str, overwrite: bool = False) -> bool:
    """Upload file to OneDep system"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


@app.command()
def status(dep_id: str) -> bool:
    """Get status of deposition"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


@app.command()
def remove_file(dep_id: str, file_id: int) -> bool:
    """Remove file from OneDep system"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return False


@app.command()
def get_files(dep_id: str) -> bool:
    """Get file info from deposition"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


@app.command()
def process(
    dep_id: str,
    voxels_json: Optional[str] = None,
    copy_dep_id: Optional[str] = None,
    copy_all: bool = False,
    copy_contact: bool = False,
    copy_authors: bool = False,
    copy_citation: bool = False,
    copy_grant: bool = False,
    copy_em_exp: bool = False,
) -> bool:
    """Process deposition files

    Args:
        dep_id (str): Deposition ID to process
        voxels_json (Optional[str], optional): Path to voxels JSON file with voxel values in the following format: ([{"file_id": X, "spacing": Y, "contour": Z}, ...])
        copy_dep_id (Optional[str], optional): Deposition ID to copy elements from. Defaults to None.
        copy_all (bool, optional): Copy all elements. Defaults to False.
        copy_contact (bool, optional): Copy contact information. Defaults to False.
        copy_authors (bool, optional): Copy authors. Defaults to False.
        copy_citation (bool, optional): Copy citation. Defaults to False.
        copy_grant (bool, optional): Copy grant information. Defaults to False.
        copy_em_exp (bool, optional): Copy EM experiment data. Defaults to False.
    """
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return False


@app.command()
def get_deposition(dep_id: str) -> bool:
    """Get deposition from deposition id"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


@app.command()
def add_users(dep_id: str, orcid: Annotated[list[str], typer.Option()]) -> bool:
    """Add users to deposition"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


@app.command()
def get_users(dep_id: str) -> bool:
    """Get users from deposition"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


@app.command()
def remove_user(dep_id: str, orcid: str) -> bool:
    """Remove user from deposition"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return False


@app.command()
def update(
    dep_id: str,
    file_id: int,
    spacing_x: float,
    spacing_y: float,
    spacing_z: float,
    contour: float,
    description: str,
) -> bool:
    """Update data for previously deposited file"""
    raise NotImplementedError("CLI support for deposition is no longer available; use the programmatic API instead")
    return True


@auth_app.command("store-tokens")
def auth_store_tokens(
    access_token: str = typer.Option(..., prompt=True, hide_input=True, help="JWT access token."),
    refresh_token: str = typer.Option(..., prompt=True, hide_input=True, help="JWT refresh token."),
    hostname: Optional[str] = typer.Option(None, "--hostname", help="Override target hostname."),
) -> None:
    """Store an access/refresh token pair in the local config file."""
    from onedep_lib.auths.token import TokenStore
    from onedep_lib.config import DepositConfig
    from onedep_lib.exceptions import AuthError

    overrides = {}
    if hostname:
        overrides["hostname"] = hostname
    config = DepositConfig.load(**overrides)

    try:
        TokenStore(config).store_tokens(access_token, refresh_token)
    except AuthError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1)

    console.print(f"[green]Tokens stored[/green] in {config.config_path}")


if __name__ == "__main__":
    app()
