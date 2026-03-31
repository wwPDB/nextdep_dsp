from __future__ import annotations

from nextdep_dsp.checks.report import CheckReport
from nextdep_dsp.deposition.enum import ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile


def check_mmcif_file(file: LocalFile) -> CheckReport:
    """Check that a file is a valid mmCIF. Stub — always passes."""
    return CheckReport(source=file.file_id)


def check_mmcif_category(file: LocalFile, category: str) -> CheckReport:
    """Check that an mmCIF file contains the given category. Stub — always passes."""
    return CheckReport(source=file.file_id)


def check_mmcif_field(file: LocalFile, category: str, field: str) -> CheckReport:
    """Check that an mmCIF file contains the given field in category. Stub — always passes."""
    return CheckReport(source=file.file_id)


def check_file_type(file: LocalFile, file_type: FileType) -> CheckReport:
    """Check that a file matches the expected file type. Stub — always passes."""
    return CheckReport(source=file.file_id)


def check_required_files(
    files: list[LocalFile],
    experiment_type: ExperimentType | None,
) -> CheckReport:
    """Check that the session contains all required files for the experiment type. Stub — always passes."""
    return CheckReport(source="session")
