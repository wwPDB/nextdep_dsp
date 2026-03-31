from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from nextdep_dsp.checks.file_checks import (
    check_file_type as _check_file_type,
    check_mmcif_category as _check_mmcif_category,
    check_mmcif_field as _check_mmcif_field,
    check_mmcif_file as _check_mmcif_file,
    check_required_files as _check_required_files,
)
from nextdep_dsp.checks.report import CheckReport
from nextdep_dsp.deposition.deposit_api import DepositApi
from nextdep_dsp.deposition.enum import Country, ExperimentType, FileType
from nextdep_dsp.deposition.models import DepositError, DepositStatus, Experiment
from nextdep_dsp.session.models import LocalFile, LocalSession
from nextdep_dsp.session.store import SessionStore


def deposit_init(
    email: str,
    users: list[str],
    country: Country,
    experiment_type: ExperimentType | None = None,
    _base_dir: Path | None = None,
) -> "Deposition":
    """Create a new local deposition session.

    Args:
        email: Depositor e-mail address.
        users: List of ORCID IDs granted access to this deposition.
        country: Depositor country (use the Country enum).
        experiment_type: Experiment type (can be set later via set_experiment_type).
        _base_dir: Override session storage directory (for testing only).

    Returns:
        A Deposition object representing the local session.
    """
    session_id = str(uuid.uuid4())
    store = SessionStore(session_id, base_dir=_base_dir)
    session = LocalSession(
        session_id=session_id,
        email=email,
        users=users,
        country=country,
        experiment_type=experiment_type,
        created_at=datetime.now(),
        db_path=str(store.db_path),
    )
    store.create_session(session)
    return Deposition(store=store)


class Deposition:
    """Local deposition session. Created via deposit_init()."""

    def __init__(self, store: SessionStore) -> None:
        self._store = store
        self._session = store.get_session()

    @property
    def session_id(self) -> str:
        """Unique ID of the local session."""
        return self._session.session_id

    @property
    def remote_dep_id(self) -> str | None:
        """Remote deposition ID, populated after deposit() is called."""
        return self._session.remote_dep_id

    def set_experiment_type(self, experiment_type: ExperimentType) -> None:
        """Set or update the experiment type for this deposition."""
        self._store.update_experiment_type(experiment_type)
        self._session.experiment_type = experiment_type

    def check_auth_key(self) -> bool:
        """Return True if the configured API key is valid, False otherwise."""
        try:
            api = DepositApi()
            api.get_all_depositions()
            return True
        except Exception:  # noqa: BLE001 - intentionally broad: covers auth errors and config issues; will be narrowed later
            return False

    def add_file(self, file_path: str, file_type: FileType) -> str:
        """Register a local file for this deposition.

        The file path is stored as-is — the file is not copied. Do not
        move or delete the file before calling deposit().

        Returns:
            A file_id (UUID string) to reference this file in check methods.

        Raises:
            FileNotFoundError: If file_path does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        file_id = str(uuid.uuid4())
        local_file = LocalFile(
            file_id=file_id,
            session_id=self._session.session_id,
            file_path=str(path.resolve()),
            file_type=file_type,
        )
        self._store.add_file(local_file)
        return file_id

    def remove_file(self, file_id: str) -> None:
        """Remove a file from this local session by its file_id."""
        self._store.remove_file(file_id)

    def check_required_files(self) -> CheckReport:
        """Check that the session contains all required files for the experiment type."""
        files = self._store.get_all_files()
        return _check_required_files(files, self._session.experiment_type)

    def check_mmcif_file(self, file_id: str) -> CheckReport:
        """Check that the file identified by file_id is a valid mmCIF."""
        file = self._store.get_file(file_id)
        return _check_mmcif_file(file)

    def check_mmcif_category(self, file_id: str, category: str) -> CheckReport:
        """Check that the mmCIF file contains the given category."""
        file = self._store.get_file(file_id)
        return _check_mmcif_category(file, category)

    def check_mmcif_field(self, file_id: str, category: str, field: str) -> CheckReport:
        """Check that the mmCIF file contains the given field in the given category."""
        file = self._store.get_file(file_id)
        return _check_mmcif_field(file, category, field)

    def check_file_type(self, file_id: str, file_type: FileType) -> CheckReport:
        """Check that the file matches the expected FileType."""
        file = self._store.get_file(file_id)
        return _check_file_type(file, file_type)

    def deposit(self) -> str:
        """Submit this deposition to the OneDep API.

        Creates a remote deposition, uploads all registered files, and
        triggers processing. Returns immediately without waiting for
        processing to finish (non-blocking). Use get_status() to poll.

        Returns:
            The remote deposition ID (e.g. "D_8000000001").

        Raises:
            ValueError: If experiment_type has not been set, or if this
                session has already been deposited.
            DepositApiException: If any API call fails.
        """
        if self._session.experiment_type is None:
            raise ValueError(
                "experiment_type must be set before calling deposit(). "
                "Use set_experiment_type() or pass experiment_type to deposit_init()."
            )
        if self._session.remote_dep_id is not None:
            raise ValueError(
                f"This session has already been deposited (dep_id={self._session.remote_dep_id!r}). "
                "Create a new session with deposit_init() to start a new deposition."
            )
        api = DepositApi()
        experiment = Experiment(exp_type=self._session.experiment_type.value)
        remote_deposit = api.create_deposition(
            email=self._session.email,
            users=self._session.users,
            country=self._session.country,
            experiments=[experiment],
        )
        dep_id = remote_deposit.dep_id
        # Persist remote ID immediately so it survives any subsequent failure
        self._store.set_remote_dep_id(dep_id)
        self._session.remote_dep_id = dep_id
        for file in self._store.get_all_files():
            api.upload_file(dep_id, file.file_path, file.file_type)
        api.process(dep_id)
        return dep_id

    def close(self) -> None:
        """Close the underlying session store connection."""
        self._store.close()

    def __enter__(self) -> "Deposition":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_status(self) -> DepositStatus | DepositError:
        """Return the current processing status of the remote deposition.

        Raises:
            RuntimeError: If deposit() has not been called yet.
        """
        if self._session.remote_dep_id is None:
            raise RuntimeError(
                "deposit() has not been called yet for this session. "
                "Call deposit() first to obtain a remote deposition ID."
            )
        api = DepositApi()
        return api.get_status(self._session.remote_dep_id)

    def get_experiment_file_types(self) -> list[FileType]:
        """Return the accepted file types for the current experiment type. (stub)"""
        return []
