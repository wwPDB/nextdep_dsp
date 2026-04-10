from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nextdep_dsp.deposition.enum import Country, ExperimentType, FileType
from nextdep_dsp.dsp import Deposition, deposit_init, deposit_resume

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_deposition(tmp_path, experiment_type=ExperimentType.XRAY):
    return deposit_init(
        email="user@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.UK,
        experiment_type=experiment_type,
        _base_dir=tmp_path,
    )


# ---------------------------------------------------------------------------
# deposit_init
# ---------------------------------------------------------------------------

def test_deposit_init_returns_deposition(tmp_path):
    dep = _make_deposition(tmp_path)
    assert isinstance(dep, Deposition)


def test_deposit_init_session_id_is_uuid(tmp_path):
    import uuid
    dep = _make_deposition(tmp_path)
    uuid.UUID(dep.session_id)  # raises if not a valid UUID


def test_deposit_init_creates_session_file(tmp_path):
    dep = _make_deposition(tmp_path)
    db = tmp_path / dep.session_id / "session.json"
    assert db.exists()


def test_add_file_stores_md5_and_mtime(tmp_path):
    dep = deposit_init(
        email="user@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.UK,
        _base_dir=tmp_path,
    )

    test_file = tmp_path / "model.cif"
    test_file.write_bytes(b"hello")

    file_id = dep.add_file(str(test_file), FileType.MMCIF_COORD)

    from nextdep_dsp.session.store import SessionStore
    with SessionStore(dep.session_id, base_dir=tmp_path) as store:
        f = store.get_file(file_id)

    import hashlib
    expected_md5 = hashlib.md5(b"hello").hexdigest()
    assert f.md5 == expected_md5
    assert f.file_mtime is not None


def test_deposit_init_remote_dep_id_is_none(tmp_path):
    dep = _make_deposition(tmp_path)
    assert dep.remote_dep_id is None


# ---------------------------------------------------------------------------
# deposit_resume
# ---------------------------------------------------------------------------

def test_deposit_resume_returns_same_session(tmp_path):
    dep = _make_deposition(tmp_path)
    session_id = dep.session_id
    dep.close()

    resumed = deposit_resume(session_id, _base_dir=tmp_path)
    assert resumed.session_id == session_id


def test_deposit_resume_restores_state(tmp_path):
    dep = deposit_init(
        email="user@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.UK,
        experiment_type=ExperimentType.EM,
        _base_dir=tmp_path,
    )
    session_id = dep.session_id
    dep.close()

    resumed = deposit_resume(session_id, _base_dir=tmp_path)
    assert resumed.session_id == session_id
    from nextdep_dsp.session.store import SessionStore
    store = SessionStore(session_id, base_dir=tmp_path)
    session = store.get_session()
    assert session.experiment_type == ExperimentType.EM
    assert session.email == "user@example.com"
    store.close()


def test_deposit_resume_restores_files(tmp_path):
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data\n")
    file_id = dep.add_file(str(cif), FileType.MMCIF_COORD)
    session_id = dep.session_id
    dep.close()

    resumed = deposit_resume(session_id, _base_dir=tmp_path)
    result = resumed.check_mmcif_file(file_id)
    from nextdep_dsp.checks.report import CheckReport
    assert isinstance(result, CheckReport)


def test_deposit_resume_raises_for_unknown_session(tmp_path):
    with pytest.raises(KeyError):
        deposit_resume("00000000-0000-0000-0000-000000000000", _base_dir=tmp_path)


# ---------------------------------------------------------------------------
# set_experiment_type
# ---------------------------------------------------------------------------

def test_set_experiment_type_updates_session(tmp_path):
    dep = deposit_init(
        email="user@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.UK,
        _base_dir=tmp_path,
    )
    dep.set_experiment_type(ExperimentType.EM)
    # Read back from store to confirm persistence
    from nextdep_dsp.session.store import SessionStore
    store = SessionStore(dep.session_id, base_dir=tmp_path)
    session = store.get_session()
    assert session.experiment_type == ExperimentType.EM
    store.close()


# ---------------------------------------------------------------------------
# add_file / remove_file
# ---------------------------------------------------------------------------

def test_add_file_returns_file_id(tmp_path):
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data_test\n")
    file_id = dep.add_file(str(cif), FileType.MMCIF_COORD)
    assert isinstance(file_id, str)
    assert len(file_id) > 0


def test_add_file_raises_for_missing_path(tmp_path):
    dep = _make_deposition(tmp_path)
    with pytest.raises(FileNotFoundError):
        dep.add_file("/nonexistent/path/model.cif", FileType.MMCIF_COORD)


def test_remove_file_deletes_from_store(tmp_path):
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data_test\n")
    file_id = dep.add_file(str(cif), FileType.MMCIF_COORD)
    dep.remove_file(file_id)
    from nextdep_dsp.session.store import SessionStore
    store = SessionStore(dep.session_id, base_dir=tmp_path)
    with pytest.raises(KeyError):
        store.get_file(file_id)
    store.close()


# ---------------------------------------------------------------------------
# check_auth_key
# ---------------------------------------------------------------------------

def test_check_auth_key_returns_true_on_success(tmp_path):
    dep = _make_deposition(tmp_path)
    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_api.get_all_depositions.return_value = []
        assert dep.check_auth_key() is True


def test_check_auth_key_returns_false_on_exception(tmp_path):
    dep = _make_deposition(tmp_path)
    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_cls.side_effect = Exception("auth failed")
        assert dep.check_auth_key() is False


# ---------------------------------------------------------------------------
# check_* methods
# ---------------------------------------------------------------------------

def test_check_required_files_returns_check_report(tmp_path):
    from nextdep_dsp.checks.report import CheckReport
    dep = _make_deposition(tmp_path)
    result = dep.check_required_files()
    assert isinstance(result, CheckReport)


def test_check_mmcif_file_returns_check_report(tmp_path):
    from nextdep_dsp.checks.report import CheckReport
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data_test\n")
    file_id = dep.add_file(str(cif), FileType.MMCIF_COORD)
    result = dep.check_mmcif_file(file_id)
    assert isinstance(result, CheckReport)


def test_check_mmcif_category_returns_check_report(tmp_path):
    from nextdep_dsp.checks.report import CheckReport
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data_test\n")
    file_id = dep.add_file(str(cif), FileType.MMCIF_COORD)
    result = dep.check_mmcif_category(file_id, "atom_site")
    assert isinstance(result, CheckReport)


def test_check_mmcif_field_returns_check_report(tmp_path):
    from nextdep_dsp.checks.report import CheckReport
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data_test\n")
    file_id = dep.add_file(str(cif), FileType.MMCIF_COORD)
    result = dep.check_mmcif_field(file_id, "atom_site", "Cartn_x")
    assert isinstance(result, CheckReport)


def test_check_file_type_returns_check_report(tmp_path):
    from nextdep_dsp.checks.report import CheckReport
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data_test\n")
    file_id = dep.add_file(str(cif), FileType.MMCIF_COORD)
    result = dep.check_file_type(file_id, FileType.MMCIF_COORD)
    assert isinstance(result, CheckReport)


# ---------------------------------------------------------------------------
# deposit
# ---------------------------------------------------------------------------

def test_deposit_raises_without_experiment_type(tmp_path):
    dep = deposit_init(
        email="user@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.UK,
        _base_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="experiment_type"):
        dep.deposit()


def test_deposit_returns_dep_id(tmp_path):
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data_test\n")
    dep.add_file(str(cif), FileType.MMCIF_COORD)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_deposit = MagicMock()
        mock_deposit.dep_id = "D_8000000001"
        mock_api.create_deposition.return_value = mock_deposit

        result = dep.deposit()

    assert result == "D_8000000001"


def test_deposit_saves_remote_dep_id(tmp_path):
    dep = _make_deposition(tmp_path)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_deposit = MagicMock()
        mock_deposit.dep_id = "D_8000000002"
        mock_api.create_deposition.return_value = mock_deposit

        dep.deposit()

    assert dep.remote_dep_id == "D_8000000002"


def test_deposit_uploads_each_file(tmp_path):
    dep = _make_deposition(tmp_path)
    for name in ("model.cif", "sf.cif"):
        f = tmp_path / name
        f.write_text("data\n")
        dep.add_file(str(f), FileType.MMCIF_COORD)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_deposit = MagicMock()
        mock_deposit.dep_id = "D_X"
        mock_api.create_deposition.return_value = mock_deposit

        dep.deposit()

    assert mock_api.upload_file.call_count == 2


def test_deposit_calls_process(tmp_path):
    dep = _make_deposition(tmp_path)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_deposit = MagicMock()
        mock_deposit.dep_id = "D_Y"
        mock_api.create_deposition.return_value = mock_deposit

        dep.deposit()

    mock_api.process.assert_called_once_with("D_Y")


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

def test_get_status_raises_before_deposit(tmp_path):
    dep = _make_deposition(tmp_path)
    with pytest.raises(RuntimeError, match="deposit\\(\\)"):
        dep.get_status()


def test_get_status_delegates_to_api(tmp_path):
    dep = _make_deposition(tmp_path)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_deposit = MagicMock()
        mock_deposit.dep_id = "D_Z"
        mock_api.create_deposition.return_value = mock_deposit
        dep.deposit()

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        dep.get_status()
        mock_api.get_status.assert_called_once_with("D_Z")


# ---------------------------------------------------------------------------
# get_experiment_file_types (stub)
# ---------------------------------------------------------------------------

def test_get_experiment_file_types_returns_list(tmp_path):
    dep = _make_deposition(tmp_path)
    result = dep.get_experiment_file_types()
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# re-submit to existing deposition
# ---------------------------------------------------------------------------

def test_deposit_skips_create_if_remote_dep_id_set(tmp_path):
    """Second deposit() reuses the existing remote deposition."""
    dep = _make_deposition(tmp_path)
    cif = tmp_path / "model.cif"
    cif.write_text("data\n")
    dep.add_file(str(cif), FileType.MMCIF_COORD)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_deposit = MagicMock()
        mock_deposit.dep_id = "D_1"
        mock_api.create_deposition.return_value = mock_deposit
        dep.deposit()

    extra = tmp_path / "extra.cif"
    extra.write_text("data\n")
    dep.add_file(str(extra), FileType.CRYSTAL_STRUC_FACTORS)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        result = dep.deposit()

    mock_api.create_deposition.assert_not_called()
    assert result == "D_1"


def test_deposit_resubmit_uploads_all_files(tmp_path):
    """Re-submit uploads all currently registered files."""
    dep = _make_deposition(tmp_path)
    for name in ("model.cif", "sf.cif"):
        f = tmp_path / name
        f.write_text("data\n")
        dep.add_file(str(f), FileType.MMCIF_COORD)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        mock_deposit = MagicMock()
        mock_deposit.dep_id = "D_1"
        mock_api.create_deposition.return_value = mock_deposit
        dep.deposit()

    extra = tmp_path / "extra.cif"
    extra.write_text("data\n")
    dep.add_file(str(extra), FileType.CRYSTAL_STRUC_FACTORS)

    with patch("nextdep_dsp.dsp.DepositApi") as mock_cls:
        mock_api = MagicMock()
        mock_cls.return_value = mock_api
        dep.deposit()

    # 3 files registered at re-submit time
    assert mock_api.upload_file.call_count == 3


# ---------------------------------------------------------------------------
# context manager
# ---------------------------------------------------------------------------

def test_deposition_context_manager(tmp_path):
    with deposit_init(
        email="user@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.UK,
        experiment_type=ExperimentType.XRAY,
        _base_dir=tmp_path,
    ) as dep:
        assert isinstance(dep, Deposition)
    # After exiting, the store should be closed; re-opening should work
    from nextdep_dsp.session.store import SessionStore
    with SessionStore(dep.session_id, base_dir=tmp_path) as store:
        session = store.get_session()
        assert session.session_id == dep.session_id
