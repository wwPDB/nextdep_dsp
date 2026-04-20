"""
Example: EM (Single Particle Analysis) deposition using the nextdep_dsp public API.

Follows the sequence diagram in docs/deposit.mermaid:
  1. deposit_init()
  2. set_experiment_type()  — EM
  3. check_required_files()
  4. Per-file checks
  5. add_file() for each file
  6. deposit()   — triggers upload + process(), returns dep_id
  7. get_status() — poll until done
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

EMAIL = "your.email@example.com"   # <<<< CHANGE THIS
USERS = ["0000-0000-0000-0000"]    # <<<< CHANGE THIS  (ORCID iD)

BASE = "/path/to/your/em/files"    # <<<< CHANGE THIS  (directory containing your EM files)

COORD_FILE   = f"{BASE}/coord.cif"            # <<<< CHANGE THIS  (adjust filename)
MAP_FILE     = f"{BASE}/primary.map.gz"       # <<<< CHANGE THIS  (adjust filename)
HALF_MAP_1   = f"{BASE}/half_map_1.map.gz"    # <<<< CHANGE THIS  (adjust filename)
HALF_MAP_2   = f"{BASE}/half_map_2.map.gz"    # <<<< CHANGE THIS  (adjust filename)
IMAGE_FILE   = f"{BASE}/image.png"            # <<<< CHANGE THIS  (adjust filename)
# FSC_XML_FILE = f"{BASE}/fsc.xml"


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
            ("EMAIL", "your.email@example.com", EMAIL),
            ("USERS", ["0000-0000-0000-0000"],  USERS),
            ("BASE",  "/path/to/your/em/files", BASE),
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

    # ── 2. Set experiment type and EM-specific params ─────────────────────────
    dep.set_experiment_type(dsp.ExperimentType.EM)
    dep.set_em_params(em_subtype=dsp.EMSubType.SPA, coordinates=True)
    print(f"  experiment : {dsp.ExperimentType.EM.value}")
    print(f"  em_subtype : {dsp.EMSubType.SPA.value}")
    print(f"  coordinates: True")

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

    coord_id   = dep.add_file(COORD_FILE,   dsp.FileType.MMCIF_COORD)
    map_id     = dep.add_file(MAP_FILE,     dsp.FileType.EM_MAP)
    half1_id   = dep.add_file(HALF_MAP_1,   dsp.FileType.EM_HALF_MAP)
    half2_id   = dep.add_file(HALF_MAP_2,   dsp.FileType.EM_HALF_MAP)
    image_id   = dep.add_file(IMAGE_FILE,   dsp.FileType.ENTRY_IMAGE)
    # fsc_xml_id = dep.add_file(FSC_XML_FILE, dsp.FileType.FSC_XML)

    for file_id, label, ftype in [
        (coord_id,   "coord",   dsp.FileType.MMCIF_COORD),
        (map_id,     "map",     dsp.FileType.EM_MAP),
        (half1_id,   "half1",   dsp.FileType.EM_HALF_MAP),
        (half2_id,   "half2",   dsp.FileType.EM_HALF_MAP),
        (image_id,   "image",   dsp.FileType.ENTRY_IMAGE),
        # (fsc_xml_id, "fsc_xml", dsp.FileType.FSC_XML),
    ]:
        print(f"  added {label:<8} file_id={file_id}  type={ftype.value}")

    # ── 5b. Set voxel values for map files ────────────────────────────────────
    print("\n=== Setting Voxel Values ===")
    dep.set_voxel_values(map_id,   spacing_x=1.0825, spacing_y=1.0825, spacing_z=1.0825, contour=0.01)
    dep.set_voxel_values(half1_id, spacing_x=1.0825, spacing_y=1.0825, spacing_z=1.0825, contour=0.01)
    dep.set_voxel_values(half2_id, spacing_x=1.0825, spacing_y=1.0825, spacing_z=1.0825, contour=0.01)
    print("  voxel values set for map, half1, half2")

    # ── 6. File checks ────────────────────────────────────────────────────────
    print("\n=== File Checks ===")

    # mmCIF coordinate file
    print_report("check_mmcif_file (coord)", dep.check_mmcif_file(coord_id))
    print_report(
        "check_mmcif_category (coord, _atom_site)",
        dep.check_mmcif_category(coord_id, "_atom_site"),
    )
    print_report(
        "check_file_type (coord, MMCIF_COORD)",
        dep.check_file_type(coord_id, dsp.FileType.MMCIF_COORD),
    )

    # Map files — file-type check only (not mmCIF)
    print_report("check_file_type (map,   EM_MAP)",      dep.check_file_type(map_id,   dsp.FileType.EM_MAP))
    print_report("check_file_type (half1, EM_HALF_MAP)", dep.check_file_type(half1_id, dsp.FileType.EM_HALF_MAP))
    print_report("check_file_type (half2, EM_HALF_MAP)", dep.check_file_type(half2_id, dsp.FileType.EM_HALF_MAP))
    print_report("check_file_type (image, ENTRY_IMAGE)", dep.check_file_type(image_id, dsp.FileType.ENTRY_IMAGE))
    # print_report("check_file_type (fsc,   FSC_XML)",     dep.check_file_type(fsc_xml_id, dsp.FileType.FSC_XML))

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
