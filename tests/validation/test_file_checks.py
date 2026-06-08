from nextdep_dsp.checks.file_checks import check_required_files
from nextdep_dsp.checks.report import CheckSeverity
from nextdep_dsp.deposition.enum import ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile


def _make_file(file_type: FileType) -> LocalFile:
    return LocalFile(
        file_id="f1",
        session_id="s1",
        file_path="/data/file",
        file_type=file_type,
    )


def test_passes_for_valid_xray_set():
    files = [_make_file(FileType.MMCIF_COORD), _make_file(FileType.CRYSTAL_MTZ)]
    report = check_required_files(files, ExperimentType.XRAY)
    assert report.ok is True
    assert report.issues == []


def test_fatal_for_missing_required_files():
    files = [_make_file(FileType.MMCIF_COORD)]
    report = check_required_files(files, ExperimentType.XRAY)
    assert report.ok is False
    fatal_issues = [i for i in report.issues if i.severity == CheckSeverity.FATAL]
    assert len(fatal_issues) >= 1
    assert all(i.code == "REQ_FILES_MISSING" for i in fatal_issues)
    assert fatal_issues[0].message == ("Missing required structure factors file: expected one of xs-cif or xs-mtz")


def test_warning_when_experiment_type_unset():
    report = check_required_files([], None)
    assert report.ok is True
    assert len(report.issues) == 1
    assert report.issues[0].code == "EXPERIMENT_TYPE_UNSET"
    assert report.issues[0].severity == CheckSeverity.WARNING
