from __future__ import annotations

from pathlib import Path

from nextdep_dsp.checks.report import CheckIssue, CheckReport, CheckSeverity
from nextdep_dsp.deposition.enum import ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile
from nextdep_dsp.validation.support.filecompliance import FileCompliance

_FILES_SCHEMA = str(Path(__file__).parent.parent / "validation" / "schema" / "files.json")


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
    em_subtype: str | None = None,
) -> CheckReport:
    """Check that the session contains all required files for the experiment type.

    Returns a warning-only report when experiment_type is unset, fatal issues when
    required files are missing, and a clean report when validation passes.
    """
    if experiment_type is None:
        return CheckReport(
            source="session",
            issues=[
                CheckIssue(
                    severity=CheckSeverity.WARNING,
                    code="EXPERIMENT_TYPE_UNSET",
                    message="Experiment type not set — required-file check skipped",
                )
            ],
        )

    filetypes = [file.file_type.value for file in files]
    compliance = FileCompliance(_FILES_SCHEMA)
    compliance.datafile = compliance.generate_data_file(
        experiment_type.value,
        filetypes,
        em_subtype or "",
    )
    result = compliance.validate()

    if result.valid.value is False:
        issues = [
            CheckIssue(
                severity=CheckSeverity.FATAL,
                code="REQ_FILES_MISSING",
                message=message,
            )
            for message in (result.errors or ["Required files not satisfied"])
        ]
        return CheckReport(source="session", issues=issues)

    return CheckReport(source="session")
