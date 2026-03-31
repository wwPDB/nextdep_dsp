# DSP Public API — Design Spec

**Date:** 2026-03-31
**Status:** Approved

## Overview

`nextdep_dsp` is a Python library used by third-party crystallography/structural biology suites (CCP4, Phenix, GlobalPhasing, etc.) to stage and submit depositions to the OneDep REST API. This spec covers the **DSP public API layer**: the `Deposition` class and everything it depends on.

The library is imported as a package. Suite developers interact with a single `Deposition` object. Auth configuration (API key) is read transparently from the environment or `~/.config/nextdep/config.toml` — callers never pass keys explicitly.

---

## Module Layout

```
src/nextdep_dsp/
├── dsp.py                  ← public facade: Deposition class + deposit_init()
├── session/
│   ├── __init__.py
│   ├── models.py           ← LocalSession, LocalFile dataclasses
│   └── store.py            ← SQLite CRUD (SessionStore)
├── checks/
│   ├── __init__.py
│   ├── report.py           ← CheckReport, CheckIssue, CheckSeverity dataclasses
│   └── file_checks.py      ← check functions as plain functions (stubs → real impls)
└── deposition/             ← existing, untouched
```

---

## Data Flow

1. `deposit_init(...)` creates a `LocalSession` and a SQLite DB at `~/.nextdep/sessions/<uuid>/session.db`. Returns a `Deposition` object.
2. `Deposition.add_file(path, file_type)` registers the file as a `LocalFile` row in SQLite. Returns a `file_id` (UUID string).
3. `Deposition.check_*()` reads local files and returns a `CheckReport`.
4. `Deposition.deposit()` instantiates `DepositApi`, calls `create_deposition()`, uploads all local files, calls `process()`, saves the remote `dep_id` to the session DB, and returns the `dep_id` immediately (non-blocking).
5. `Deposition.get_status()` reads `remote_dep_id` from the session and delegates to `DepositApi.get_status()`.

---

## Public API (`dsp.py`)

```python
def deposit_init(
    email: str,
    users: list[str],
    country: Country,
    experiment_type: ExperimentType = None,
) -> Deposition:
    """Create a new local deposition session. Returns a Deposition object."""


class Deposition:

    @property
    def session_id(self) -> str: ...          # read-only UUID of the local session
    @property
    def remote_dep_id(self) -> str | None: ...  # populated after deposit()

    # --- Session setup ---
    def set_experiment_type(self, experiment_type: ExperimentType) -> None: ...

    # --- Auth check ---
    def check_auth_key(self) -> bool: ...
    """Returns True if the configured API key is valid, False otherwise. Never raises."""

    # --- File management ---
    def add_file(self, file_path: str, file_type: FileType) -> str: ...
    """Returns a file_id (UUID). Raises FileNotFoundError / ValueError on bad input.
    Stores the path only — does not copy the file. Caller must not move/delete
    the file before deposit() is called."""

    def remove_file(self, file_id: str) -> None: ...

    # --- Pre-submission checks ---
    def check_required_files(self) -> CheckReport: ...
    def check_mmcif_file(self, file_id: str) -> CheckReport: ...
    def check_mmcif_category(self, file_id: str, category: str) -> CheckReport: ...
    def check_mmcif_field(self, file_id: str, category: str, field: str) -> CheckReport: ...
    def check_file_type(self, file_id: str, file_type: FileType) -> CheckReport: ...

    # --- Submission ---
    def deposit(self) -> str: ...
    """Triggers remote deposition and processing. Non-blocking. Returns remote dep_id."""

    # --- Post-submission ---
    def get_status(self) -> DepositStatus: ...
    """Reads remote_dep_id from session. Raises if deposit() has not been called."""

    # --- Utilities ---
    def get_experiment_file_types(self) -> list[FileType]: ...   # stub
```

---

## Session Layer (`session/`)

### `session/models.py`

Pure dataclasses — no DB logic.

```python
@dataclass
class LocalFile:
    file_id: str            # UUID
    session_id: str         # FK to LocalSession
    file_path: str          # absolute path on disk
    file_type: FileType

@dataclass
class LocalSession:
    session_id: str         # UUID
    email: str
    users: list[str]        # stored as JSON in SQLite
    country: Country
    experiment_type: ExperimentType | None
    created_at: datetime
    db_path: str            # path to this session's session.db
    remote_dep_id: str | None = None   # populated by deposit()
```

**Note:** `Deposit` from `deposition/models.py` is a server-side model and is intentionally NOT reused here. It requires fields (`pdb_id`, `emdb_id`, `status`, `last_login`, etc.) that only exist after a server round-trip.

### `session/store.py`

`SessionStore` owns all SQLite I/O. The `Deposition` facade holds one instance and never accesses SQLite directly.

```python
class SessionStore:
    def __init__(self, session_id: str): ...
    # opens ~/.nextdep/sessions/<session_id>/session.db

    # Session
    def create_session(self, session: LocalSession) -> None: ...
    def get_session(self) -> LocalSession: ...
    def update_experiment_type(self, experiment_type: ExperimentType) -> None: ...
    def set_remote_dep_id(self, dep_id: str) -> None: ...

    # Files
    def add_file(self, file: LocalFile) -> None: ...
    def remove_file(self, file_id: str) -> None: ...
    def get_file(self, file_id: str) -> LocalFile: ...
    def get_all_files(self) -> list[LocalFile]: ...
```

SQLite schema: two tables — `sessions` and `files`.

---

## Check Reports (`checks/report.py`)

Adapted from the `DSP API.md` proposal with purpose-specific names.

```python
class CheckSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"

@dataclass(frozen=True)
class CifLocation:
    data_block: str | None = None
    category: str | None = None
    item: str | None = None
    row: int | None = None
    line: int | None = None
    column: int | None = None

@dataclass(frozen=True)
class CheckIssue:
    severity: CheckSeverity
    code: str               # e.g. "MMCIF.MISSING_MANDATORY_ITEM"
    message: str
    location: CifLocation = CifLocation()
    expected: Any = None
    actual: Any = None

@dataclass
class CheckReport:
    source: str             # file_id, or "session" for session-level checks
    issues: list[CheckIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(i.severity in (CheckSeverity.ERROR, CheckSeverity.FATAL) for i in self.issues)

    def errors(self) -> list[CheckIssue]: ...
    def warnings(self) -> list[CheckIssue]: ...
```

### `checks/file_checks.py`

Check logic lives here as plain functions — not methods on `Deposition`. This keeps them independently testable.

```python
def check_mmcif_file(file: LocalFile) -> CheckReport: ...
def check_mmcif_category(file: LocalFile, category: str) -> CheckReport: ...
def check_mmcif_field(file: LocalFile, category: str, field: str) -> CheckReport: ...
def check_file_type(file: LocalFile, file_type: FileType) -> CheckReport: ...
def check_required_files(files: list[LocalFile], experiment_type: ExperimentType) -> CheckReport: ...
```

All check functions **never raise** — errors are returned as `FATAL` issues in the report.

---

## `deposit()` Internal Flow

1. Assert `experiment_type` is set — raise `ValueError` if not.
2. Instantiate `DepositApi` (reads auth from `DepositConfig` automatically).
3. Call `DepositApi.create_deposition(email, users, country, [Experiment(experiment_type)])` → remote `dep_id`.
4. For each `LocalFile` from `SessionStore.get_all_files()`, call `DepositApi.upload_file(dep_id, file_path, file_type)`.
5. Call `DepositApi.process(dep_id)` — does not wait for completion.
6. Call `SessionStore.set_remote_dep_id(dep_id)` — links local session to remote deposition.
7. Return `dep_id`.

On any `DepositApiException`, the exception propagates to the caller. The local session is preserved in SQLite so the deposit can be retried.

---

## Error Handling Summary

| Method | On failure |
|---|---|
| `deposit_init()` | `ValueError` for invalid inputs |
| `add_file()` | `FileNotFoundError` (bad path), `ValueError` (unsupported type) |
| `check_auth_key()` | Returns `False` — never raises |
| `check_*()` | Returns `CheckReport` with `FATAL` issue — never raises |
| `deposit()` | Raises `DepositApiException` — session preserved for retry |
| `get_status()` | Raises `RuntimeError` if `deposit()` not yet called |

---

## Out of Scope (this spec)

- Session resumption (reconnecting to an existing session by `session_id`)
- `get_experiment_file_types()` implementation (stub only)
- Real implementations of `check_mmcif_*` functions (stubs that return empty `CheckReport`)
- `replace_file()`, `add_files()` (batch), mmCIF field editing
