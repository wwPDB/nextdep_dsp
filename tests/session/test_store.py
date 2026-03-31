from __future__ import annotations

from datetime import datetime

import pytest

from nextdep_dsp.deposition.enum import Country, ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile, LocalSession
from nextdep_dsp.session.store import SessionStore


def _make_session(session_id: str = "sess-1") -> LocalSession:
    return LocalSession(
        session_id=session_id,
        email="user@example.com",
        users=["0000-0001-2345-6789", "0000-0002-3456-7890"],
        country=Country.UK,
        experiment_type=ExperimentType.XRAY,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        db_path="",  # store sets this; we leave blank here
    )


def test_store_creates_db_file(tmp_path):
    store = SessionStore("sess-1", base_dir=tmp_path)
    assert store.db_path.exists()
    store.close()


def test_create_and_get_session(tmp_path):
    store = SessionStore("sess-1", base_dir=tmp_path)
    session = _make_session()
    session.db_path = str(store.db_path)
    store.create_session(session)

    result = store.get_session()
    assert result.session_id == "sess-1"
    assert result.email == "user@example.com"
    assert result.users == ["0000-0001-2345-6789", "0000-0002-3456-7890"]
    assert result.country == Country.UK
    assert result.experiment_type == ExperimentType.XRAY
    assert result.remote_dep_id is None
    store.close()


def test_session_with_no_experiment_type(tmp_path):
    store = SessionStore("sess-2", base_dir=tmp_path)
    session = LocalSession(
        session_id="sess-2",
        email="x@x.com",
        users=[],
        country=Country.USA,
        experiment_type=None,
        created_at=datetime(2026, 1, 1),
        db_path=str(store.db_path),
    )
    store.create_session(session)
    result = store.get_session()
    assert result.experiment_type is None
    store.close()


def test_update_experiment_type(tmp_path):
    store = SessionStore("sess-1", base_dir=tmp_path)
    session = _make_session()
    session.db_path = str(store.db_path)
    session.experiment_type = None
    store.create_session(session)

    store.update_experiment_type(ExperimentType.EM)
    result = store.get_session()
    assert result.experiment_type == ExperimentType.EM
    store.close()


def test_set_remote_dep_id(tmp_path):
    store = SessionStore("sess-1", base_dir=tmp_path)
    session = _make_session()
    session.db_path = str(store.db_path)
    store.create_session(session)

    store.set_remote_dep_id("D_8000000001")
    result = store.get_session()
    assert result.remote_dep_id == "D_8000000001"
    store.close()


def test_add_and_get_file(tmp_path):
    store = SessionStore("sess-1", base_dir=tmp_path)
    session = _make_session()
    session.db_path = str(store.db_path)
    store.create_session(session)

    f = LocalFile(
        file_id="file-abc",
        session_id="sess-1",
        file_path="/data/model.cif",
        file_type=FileType.MMCIF_COORD,
    )
    store.add_file(f)
    result = store.get_file("file-abc")
    assert result.file_id == "file-abc"
    assert result.file_path == "/data/model.cif"
    assert result.file_type == FileType.MMCIF_COORD
    store.close()


def test_get_file_raises_for_unknown_id(tmp_path):
    store = SessionStore("sess-1", base_dir=tmp_path)
    session = _make_session()
    session.db_path = str(store.db_path)
    store.create_session(session)

    with pytest.raises(KeyError):
        store.get_file("nonexistent")
    store.close()


def test_remove_file(tmp_path):
    store = SessionStore("sess-1", base_dir=tmp_path)
    session = _make_session()
    session.db_path = str(store.db_path)
    store.create_session(session)

    f = LocalFile(file_id="f1", session_id="sess-1", file_path="/a.cif", file_type=FileType.MMCIF_COORD)
    store.add_file(f)
    store.remove_file("f1")

    with pytest.raises(KeyError):
        store.get_file("f1")
    store.close()


def test_get_all_files(tmp_path):
    store = SessionStore("sess-1", base_dir=tmp_path)
    session = _make_session()
    session.db_path = str(store.db_path)
    store.create_session(session)

    store.add_file(LocalFile("f1", "sess-1", "/a.cif", FileType.MMCIF_COORD))
    store.add_file(LocalFile("f2", "sess-1", "/b.mtz", FileType.CRYSTAL_MTZ))
    files = store.get_all_files()
    assert len(files) == 2
    assert {f.file_id for f in files} == {"f1", "f2"}
    store.close()


def test_context_manager_closes_connection(tmp_path):
    with SessionStore("sess-cm", base_dir=tmp_path) as store:
        session = _make_session("sess-cm")
        session.db_path = str(store.db_path)
        store.create_session(session)
    # After exiting the context, store should be closed
    # Re-opening should work fine (proves the file was properly closed)
    with SessionStore("sess-cm", base_dir=tmp_path) as store2:
        result = store2.get_session()
        assert result.session_id == "sess-cm"


def test_get_session_raises_key_error_on_empty_db(tmp_path):
    store = SessionStore("sess-empty", base_dir=tmp_path)
    with pytest.raises(KeyError):
        store.get_session()
    store.close()
