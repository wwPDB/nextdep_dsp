from __future__ import annotations

from collections import Counter
from pathlib import Path

from nextdep_dsp.checks.report import CheckIssue, CheckReport, CheckSeverity
from nextdep_dsp.deposition.enum import ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile
from nextdep_dsp.validation.support.filecompliance import FileCompliance

_FILES_SCHEMA = str(Path(__file__).parent.parent / "validation" / "schema" / "files.json")
_COORD_FILE_TYPES = {"co-pdb", "co-cif"}
_STRUCTURE_FACTOR_FILE_TYPES = {"xs-cif", "xs-mtz"}
_EC_DATA_FILE_TYPES = {"vo-map", "xs-cif", "xs-mtz"}
_NMR_UNIFIED_FILE_TYPES = {"nm-uni-nef", "nm-uni-str"}
_NMR_RESTRAINT_FILE_TYPES = {
    "nm-res-amb",
    "nm-res-bio",
    "nm-res-cha",
    "nm-res-cns",
    "nm-res-cya",
    "nm-res-dyn",
    "nm-res-gro",
    "nm-res-isd",
    "nm-res-ros",
    "nm-res-syb",
    "nm-res-xpl",
    "nm-res-oth",
}
_HALF_MAP_REQUIRED_SUBTYPES = {"single", "helical", "subtomogram"}


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


def _missing_required_file_messages(
    filetypes: list[str],
    experiment_type: ExperimentType,
    em_subtype: str | None,
) -> list[str]:
    """Return human-readable missing-requirement messages for known schema rules."""
    counts = Counter(filetypes)
    present = set(filetypes)
    messages: list[str] = []

    if experiment_type != ExperimentType.EM and not present.intersection(_COORD_FILE_TYPES):
        messages.append("Missing required coordinate file: expected one of co-pdb or co-cif")

    if experiment_type in {ExperimentType.XRAY, ExperimentType.NEUTRON}:
        if not present.intersection(_STRUCTURE_FACTOR_FILE_TYPES):
            messages.append(
                "Missing required structure factors file: expected one of xs-cif or xs-mtz"
            )

    if experiment_type == ExperimentType.FIBER and "layer-lines" not in present:
        messages.append("Missing required fiber diffraction file: expected layer-lines")

    if experiment_type == ExperimentType.EM:
        if not em_subtype:
            messages.append("Missing required EM subtype")
        if "img-emdb" not in present:
            messages.append("Missing required EM image stack file: expected img-emdb")
        if "vo-map" not in present:
            messages.append("Missing required EM map file: expected vo-map")
        if em_subtype in _HALF_MAP_REQUIRED_SUBTYPES and counts["half-map"] < 2:
            messages.append("Missing required half-map files: expected 2 half-map files")

    if experiment_type == ExperimentType.EC and not present.intersection(_EC_DATA_FILE_TYPES):
        messages.append(
            "Missing required experimental data file: expected at least one of vo-map, xs-cif, or xs-mtz"
        )

    if experiment_type in {ExperimentType.NMR, ExperimentType.SSNMR}:
        if not present.intersection(_NMR_UNIFIED_FILE_TYPES):
            if "nm-shi" not in present:
                messages.append("Missing required chemical shifts file: expected nm-shi")
            if not present.intersection(_NMR_RESTRAINT_FILE_TYPES):
                messages.append(
                    "Missing required NMR restraints file: expected at least one nm-res-* file"
                )

    return messages


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
        error_messages = _missing_required_file_messages(filetypes, experiment_type, em_subtype)
        if not error_messages:
            error_messages = result.errors or ["Required files not satisfied"]
        issues = [
            CheckIssue(
                severity=CheckSeverity.FATAL,
                code="REQ_FILES_MISSING",
                message=message,
            )
            for message in error_messages
        ]
        return CheckReport(source="session", issues=issues)

    return CheckReport(source="session")
