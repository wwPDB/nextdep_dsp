from datetime import datetime

import pytest

from nextdep_dsp.deposition.enum import Country, ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile, LocalSession


def test_local_file_stores_fields():
    f = LocalFile(
        file_id="abc-123",
        session_id="sess-456",
        file_path="/tmp/model.cif",
        file_type=FileType.MMCIF_COORD,
    )
    assert f.file_id == "abc-123"
    assert f.session_id == "sess-456"
    assert f.file_path == "/tmp/model.cif"
    assert f.file_type == FileType.MMCIF_COORD


def test_local_session_stores_fields():
    now = datetime(2026, 1, 1, 12, 0, 0)
    s = LocalSession(
        session_id="sess-1",
        email="user@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.UK,
        experiment_type=ExperimentType.XRAY,
        created_at=now,
        db_path="/home/user/.nextdep/sessions/sess-1/session.json",
    )
    assert s.session_id == "sess-1"
    assert s.email == "user@example.com"
    assert s.users == ["0000-0001-2345-6789"]
    assert s.country == Country.UK
    assert s.experiment_type == ExperimentType.XRAY
    assert s.created_at == now
    assert s.remote_dep_id is None


def test_local_session_remote_dep_id_defaults_to_none():
    s = LocalSession(
        session_id="s",
        email="x@x.com",
        users=[],
        country=Country.USA,
        experiment_type=None,
        created_at=datetime.now(),
        db_path="/tmp/s.json",
    )
    assert s.remote_dep_id is None


def test_local_session_accepts_remote_dep_id():
    s = LocalSession(
        session_id="s",
        email="x@x.com",
        users=[],
        country=Country.USA,
        experiment_type=None,
        created_at=datetime.now(),
        db_path="/tmp/s.json",
        remote_dep_id="D_8000000001",
    )
    assert s.remote_dep_id == "D_8000000001"
