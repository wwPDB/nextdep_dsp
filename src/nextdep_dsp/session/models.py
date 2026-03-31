from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from nextdep_dsp.deposition.enum import Country, ExperimentType, FileType


@dataclass
class LocalFile:
    file_id: str
    session_id: str
    file_path: str
    file_type: FileType


@dataclass
class LocalSession:
    session_id: str
    email: str
    users: list[str]
    country: Country
    experiment_type: ExperimentType | None
    created_at: datetime
    db_path: str
    remote_dep_id: str | None = None
