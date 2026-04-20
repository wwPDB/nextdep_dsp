"""
Example: X-ray deposition using the nextdep_dsp public API.

Follows the sequence diagram in docs/deposit.mermaid:
  1. deposit_init()
  2. set_experiment_type()
  3. check_required_files()
  4. Per-file checks (mmCIF + file-type)
  5. add_file() for each file
  6. deposit()   — triggers upload + process(), returns dep_id
  7. get_status() — poll until done (or just print the dep_id)
"""

from __future__ import annotations

import time

import nextdep_dsp as dsp
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

_console = Console(stderr=True)

# ── Configuration ─────────────────────────────────────────────────────────────
# Change all values marked with  <<<< CHANGE THIS  before running.

EMAIL      = "your.email@example.com"   # <<<< CHANGE THIS
USERS      = ["0000-0000-0000-0000"]    # <<<< CHANGE THIS  (ORCID iD)
COORD_FILE = "/path/to/your/coord.cif"  # <<<< CHANGE THIS
SF_FILE    = "/path/to/your/sf.cif"     # <<<< CHANGE THIS


def print_report(label: str, report: dsp.CheckReport) -> None:
    status = "OK" if report.ok else "ISSUES FOUND"
    print(f"  [{status}] {label}")
    for issue in report.issues:
        print(f"    {issue.severity.value.upper()}: [{issue.code}] {issue.message}")


def main() -> None:
    # ── 0. Validate configuration ─────────────────────────────────────────────
    _unset = [
        name
        for name, placeholder, value in [
            ("EMAIL",      "your.email@example.com",   EMAIL),
            ("USERS",      ["0000-0000-0000-0000"],    USERS),
            ("COORD_FILE", "/path/to/your/coord.cif",  COORD_FILE),
            ("SF_FILE",    "/path/to/your/sf.cif",     SF_FILE),
        ]
        if value == placeholder
    ]
    if _unset:
        msg = Text()
        msg.append("Placeholder values not changed:\n", style="bold yellow")
        for name in _unset:
            msg.append(f"  • {name}\n", style="yellow")
        msg.append("\nEdit the constants at the top of this file before running.", style="dim")
        _console.print(Panel(msg, title="[bold red]⚠  Configuration[/bold red]", border_style="red"))

    # ── 1. Initialization ────────────────────────────────────────────────────
    print("=== Deposit Initialization ===")
    dep = dsp.deposit_init(
        email=EMAIL,
        users=USERS,
        country=dsp.Country.USA,
    )
    print(f"  session_id : {dep.session_id}")

    # ── 2. Set experiment type ────────────────────────────────────────────────
    dep.set_experiment_type(dsp.ExperimentType.XRAY)
    print(f"  experiment : {dsp.ExperimentType.XRAY.value}")

    # ── 3. Check auth key ─────────────────────────────────────────────────────
    print("\n=== Auth Key Check ===")
    auth_ok = dep.check_auth_key()
    print(f"  auth key valid: {auth_ok}")

    # ── 4. Check required files (before adding any) ───────────────────────────
    print("\n=== Pre-add Required Files Check ===")
    report = dep.check_required_files()
    print_report("check_required_files (empty session)", report)

    # ── 5. Add files ──────────────────────────────────────────────────────────
    print("\n=== Adding Files ===")
    coord_id = dep.add_file(COORD_FILE, dsp.FileType.MMCIF_COORD)
    print(f"  added coord   file_id={coord_id}  type={dsp.FileType.MMCIF_COORD.value}")

    sf_id = dep.add_file(SF_FILE, dsp.FileType.CRYSTAL_STRUC_FACTORS)
    print(f"  added sf      file_id={sf_id}  type={dsp.FileType.CRYSTAL_STRUC_FACTORS.value}")

    # ── 6. File checks ────────────────────────────────────────────────────────
    print("\n=== File Checks ===")

    # mmCIF coordinate file checks
    print_report("check_mmcif_file (coord)", dep.check_mmcif_file(coord_id))
    print_report(
        "check_mmcif_category (coord, _atom_site)",
        dep.check_mmcif_category(coord_id, "_atom_site"),
    )
    print_report(
        "check_mmcif_field (coord, _atom_site, id)",
        dep.check_mmcif_field(coord_id, "_atom_site", "id"),
    )
    print_report(
        "check_file_type (coord, MMCIF_COORD)",
        dep.check_file_type(coord_id, dsp.FileType.MMCIF_COORD),
    )

    # Structure factors file checks
    print_report("check_mmcif_file (sf)", dep.check_mmcif_file(sf_id))
    print_report(
        "check_file_type (sf, CRYSTAL_STRUC_FACTORS)",
        dep.check_file_type(sf_id, dsp.FileType.CRYSTAL_STRUC_FACTORS),
    )

    # ── 7. Required files check (after adding files) ──────────────────────────
    print("\n=== Post-add Required Files Check ===")
    report = dep.check_required_files()
    print_report("check_required_files (with files)", report)

    if not report.ok:
        print("  Aborting: required files check failed.")
        return

    # ── 8. Deposit ────────────────────────────────────────────────────────────
    print("\n=== Deposit ===")
    try:
        dep_id = dep.deposit()
        print(f"  deposition submitted  dep_id={dep_id}")
    except (RuntimeError, dsp.DepositApiException) as exc:
        print(f"  deposit() failed: {exc}")
        return

    # ── 9. Poll status ────────────────────────────────────────────────────────
    print("\n=== Polling Status ===")
    for attempt in range(1, 64):
        status = dep.get_status()
        print(f"  [{attempt}] {status.status}")
        if isinstance(status, dsp.DepositStatus) and status.status.lower() == "finished":
            break
        time.sleep(5)

    print("\nDone. Log in to the DepUI to complete your submission.")


if __name__ == "__main__":
    main()
