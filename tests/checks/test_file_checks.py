from nextdep_dsp.checks.file_checks import (
    check_file_type,
    check_mmcif_category,
    check_mmcif_field,
    check_mmcif_file,
    check_required_files,
)
from nextdep_dsp.checks.report import CheckReport
from nextdep_dsp.deposition.enum import ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile


def _make_file(file_type: FileType = FileType.MMCIF_COORD) -> LocalFile:
    return LocalFile(
        file_id="f1",
        session_id="s1",
        file_path="/data/model.cif",
        file_type=file_type,
    )


def test_check_mmcif_file_returns_check_report():
    result = check_mmcif_file(_make_file())
    assert isinstance(result, CheckReport)
    assert result.source == "f1"


def test_check_mmcif_file_ok_stub():
    result = check_mmcif_file(_make_file())
    assert result.ok is True


def test_check_mmcif_category_returns_check_report():
    result = check_mmcif_category(_make_file(), "atom_site")
    assert isinstance(result, CheckReport)
    assert result.ok is True


def test_check_mmcif_field_returns_check_report():
    result = check_mmcif_field(_make_file(), "atom_site", "Cartn_x")
    assert isinstance(result, CheckReport)
    assert result.ok is True


def test_check_file_type_returns_check_report():
    result = check_file_type(_make_file(), FileType.MMCIF_COORD)
    assert isinstance(result, CheckReport)
    assert result.ok is True


def test_check_required_files_returns_check_report():
    files = [_make_file()]
    result = check_required_files(files, ExperimentType.XRAY)
    assert isinstance(result, CheckReport)
    assert result.source == "session"


def test_check_required_files_ok_with_no_experiment_type():
    result = check_required_files([], None)
    assert isinstance(result, CheckReport)
    assert result.ok is True
