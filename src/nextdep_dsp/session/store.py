from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from nextdep_dsp.deposition.enum import Country, ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile, LocalSession

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    email         TEXT NOT NULL,
    users         TEXT NOT NULL,
    country       TEXT NOT NULL,
    experiment_type TEXT,
    created_at    TEXT NOT NULL,
    db_path       TEXT NOT NULL,
    remote_dep_id TEXT
)
"""

_CREATE_FILES = """
CREATE TABLE IF NOT EXISTS files (
    file_id    TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    file_path  TEXT NOT NULL,
    file_type  TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
)
"""


class SessionStore:
    def __init__(self, session_id: str, base_dir: Path | None = None) -> None:
        _base = base_dir or (Path.home() / ".nextdep" / "sessions")
        self._session_id = session_id
        self._db_path = _base / session_id / "session.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute(_CREATE_SESSIONS)
            self._conn.execute(_CREATE_FILES)

    def __enter__(self) -> "SessionStore":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    @property
    def db_path(self) -> Path:
        return self._db_path

    def create_session(self, session: LocalSession) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session.session_id,
                    session.email,
                    json.dumps(session.users),
                    session.country.value,
                    session.experiment_type.value if session.experiment_type else None,
                    session.created_at.isoformat(),
                    session.db_path,
                    session.remote_dep_id,
                ),
            )

    def get_session(self) -> LocalSession:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (self._session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"No session found for session_id {self._session_id!r}")
        return LocalSession(
            session_id=row["session_id"],
            email=row["email"],
            users=json.loads(row["users"]),
            country=Country(row["country"]),
            experiment_type=ExperimentType(row["experiment_type"]) if row["experiment_type"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            db_path=str(self._db_path),
            remote_dep_id=row["remote_dep_id"],
        )

    def update_experiment_type(self, experiment_type: ExperimentType) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE sessions SET experiment_type = ? WHERE session_id = ?",
                (experiment_type.value, self._session_id),
            )

    def set_remote_dep_id(self, dep_id: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE sessions SET remote_dep_id = ? WHERE session_id = ?",
                (dep_id, self._session_id),
            )

    def add_file(self, file: LocalFile) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO files VALUES (?, ?, ?, ?)",
                (file.file_id, file.session_id, file.file_path, file.file_type.value),
            )

    def remove_file(self, file_id: str) -> None:
        with self._conn:
            cursor = self._conn.execute("DELETE FROM files WHERE file_id = ?", (file_id,))
        if cursor.rowcount == 0:
            raise KeyError(f"File {file_id!r} not found in session")

    def get_file(self, file_id: str) -> LocalFile:
        row = self._conn.execute(
            "SELECT * FROM files WHERE file_id = ?", (file_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"File {file_id!r} not found in session")
        return LocalFile(
            file_id=row["file_id"],
            session_id=row["session_id"],
            file_path=row["file_path"],
            file_type=FileType(row["file_type"]),
        )

    def get_all_files(self) -> list[LocalFile]:
        rows = self._conn.execute(
            "SELECT * FROM files WHERE session_id = ?", (self._session_id,)
        ).fetchall()
        return [
            LocalFile(
                file_id=row["file_id"],
                session_id=row["session_id"],
                file_path=row["file_path"],
                file_type=FileType(row["file_type"]),
            )
            for row in rows
        ]

    def close(self) -> None:
        self._conn.close()
