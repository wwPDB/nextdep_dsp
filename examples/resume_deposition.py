"""
Example: Resume an existing local session and add more files.

Usage:
    uv run python examples/resume_deposition.py <session_id>

Typical flow:
  1. A previous run of xray_deposition.py created a session and printed a session_id.
  2. This script resumes that session, adds an extra file, and re-submits.
     On re-submit, deposit() reuses the existing remote deposition (no new
     deposition is created on the server) and uploads all currently registered
     files, then triggers processing again.
"""

from __future__ import annotations

import sys
import time

import nextdep_dsp as dsp

# File to add on resume — swap for any valid file
EXTRA_FILE = "/home/wbueno/repos/test_files/xray/2gc2.cif"
# EXTRA_FILE = "/home/wbueno/repos/test_files/xray/2gc2-sf.cif"


def print_report(label: str, report: dsp.CheckReport) -> None:
    status = "OK" if report.ok else "ISSUES FOUND"
    print(f"  [{status}] {label}")
    for issue in report.issues:
        print(f"    {issue.severity.value.upper()}: [{issue.code}] {issue.message}")


def main(session_id: str) -> None:
    # ── 1. Resume session ─────────────────────────────────────────────────────
    print("=== Resuming Session ===")
    try:
        dep = dsp.deposit_resume(session_id)
    except KeyError:
        print(f"  No session found for id: {session_id}")
        sys.exit(1)

    print(f"  session_id    : {dep.session_id}")
    print(f"  remote_dep_id : {dep.remote_dep_id or '(not yet submitted)'}")

    # ── 2. Inspect current state ──────────────────────────────────────────────
    print("\n=== Current Required Files Check ===")
    report = dep.check_required_files()
    print_report("check_required_files", report)

    # ── 3. Add a new file ─────────────────────────────────────────────────────
    print("\n=== Adding Extra File ===")
    try:
        # file_id = dep.add_file(EXTRA_FILE, dsp.FileType.CRYSTAL_REFLN_CIF)
        file_id = dep.add_file(EXTRA_FILE, dsp.FileType.MMCIF_COORD)
        print(f"  added file_id={file_id}  path={EXTRA_FILE}")
    except FileNotFoundError as exc:
        print(f"  skipping add_file: {exc}")
        file_id = None

    # ── 4. Check the new file ─────────────────────────────────────────────────
    if file_id is not None:
        print("\n=== File Checks ===")
        print_report("check_mmcif_file", dep.check_mmcif_file(file_id))
        print_report(
            "check_file_type (MMCIF_COORD)",
            dep.check_file_type(file_id, dsp.FileType.MMCIF_COORD),
        )

    # ── 5. Re-submit ──────────────────────────────────────────────────────────
    # deposit() skips deposition creation when remote_dep_id is already set.
    # It uploads all currently registered files and triggers processing again.
    print("\n=== Re-submit ===")
    try:
        dep_id = dep.deposit()
        print(f"  submitted  dep_id={dep_id}")
    except (RuntimeError, dsp.DepositApiException) as exc:
        print(f"  deposit() failed: {exc}")
        return

    # ── 6. Poll status ────────────────────────────────────────────────────────
    print("\n=== Polling Status ===")
    for attempt in range(1, 64):
        status = dep.get_status()
        print(f"  [{attempt}] {status.status}")
        if isinstance(status, dsp.DepositStatus) and status.status.lower() == "finished":
            break
        time.sleep(5)

    print("\nDone. Log in to the DepUI to complete your submission.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <session_id>")
        sys.exit(1)
    main(sys.argv[1])
