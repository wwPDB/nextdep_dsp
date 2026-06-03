# Plan 3 — API Client + Deposition Facade + Public Surface

**Prerequisite:** Plans 1 (`2026-05-20-core-library.md`) and 2 (`2026-05-20-auth.md`) must be fully applied.

**Branch:** `feat/refactor`

**What this plan delivers:**

| New file | Purpose |
|---|---|
| `src/nextdep_dsp/apis/__init__.py` | Top-level APIs package marker |
| `src/nextdep_dsp/apis/deposit/__init__.py` | Deposit API package marker |
| `src/nextdep_dsp/apis/deposit/enums.py` | `Status` enum (moved from `deposition/enum.py`) |
| `src/nextdep_dsp/apis/deposit/models.py` | Response models as `@dataclass` |
| `src/nextdep_dsp/apis/deposit/types.py` | `ApiClient` Protocol |
| `src/nextdep_dsp/apis/deposit/client.py` | `HttpApiClient` (consolidates `deposit_api.py` + `rest_adapter.py`) |
| `src/nextdep_dsp/dsp.py` | `Deposition` facade refactored with constructor DI |
| `src/nextdep_dsp/__init__.py` | Updated public surface re-exports |
| `tests/unit/apis/deposit/test_models.py` | Model parsing unit tests |
| `tests/unit/apis/deposit/test_http_api_client.py` | HTTP client tests via `pytest-httpserver` |
| `tests/unit/test_deposition_facade.py` | Facade DI tests with stubs |

**Deleted:** `src/nextdep_dsp/deposition/` (entire package — 7 files)


---

## Task 1 — Create the `apis/deposit` package skeleton

Create `src/nextdep_dsp/apis/__init__.py` as an empty file.

Create `src/nextdep_dsp/apis/deposit/__init__.py` as an empty file.

Create `tests/unit/apis/__init__.py` as an empty file.

Create `tests/unit/apis/deposit/__init__.py` as an empty file.

---

## Task 2 — `apis/deposit/enums.py`: move the `Status` enum

Create `src/nextdep_dsp/apis/deposit/enums.py`:

```python
import enum


class Status(enum.Enum):
    # Values are never used for parsing; the API sends names (e.g. "DEP").
    # Parse with Status["DEP"], not Status("1").
    DEP = enum.auto()
    PROC = enum.auto()
    AUTH = enum.auto()
    REPL = enum.auto()
    AUCO = enum.auto()
    AUXS = enum.auto()
    AUXU = enum.auto()
    HOLD = enum.auto()
    HPUB = enum.auto()
    OBS = enum.auto()
    POLC = enum.auto()
    REL = enum.auto()
    REUP = enum.auto()
    WAIT = enum.auto()
    WDRN = enum.auto()
```

Note: `ExperimentType`, `EMSubType`, `Country`, and `FileType` already live in
`src/nextdep_dsp/enums.py` (created in Plan 1). Do not duplicate them here.

---

## Task 3 — `apis/deposit/models.py`: dataclass response models

Create `src/nextdep_dsp/apis/deposit/models.py`. This replaces `deposition/models.py`.
All models are converted to `@dataclass` with a `__post_init__` that handles
API string coercion so that callers never need to worry about raw API types.

Key behavioural rules carried over from the PoC:
- `WwPDBDeposition.status` arrives from the API as an enum **name** string (e.g. `"DEP"`),
  not as the enum value string (`"1"`). Use `Status[status]` to parse it.
- `WwPDBDeposition.pdb_id` / `emdb_id` / `bmrb_id`: the API sends `"?"` for absent IDs;
  these must be normalised to `None`.
- `WwPDBDeposition.created` / `last_login`: ISO 8601 strings (`datetime.fromisoformat`).
- `DepositedFile.created`: non-ISO format — `"%A, %B %d, %Y %H:%M:%S"` (e.g.
  `"Monday, January 01, 2024 12:00:00"`).
- Internal-only `Response` class from the PoC is **not** included here; it is
  now private to `HttpApiClient`.

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Union

from nextdep_dsp.apis.deposit.enums import Status
from nextdep_dsp.enums import EMSubType, ExperimentType, FileType


@dataclass
class Experiment:
    exp_type: ExperimentType
    coordinates: bool = True
    subtype: EMSubType | None = None
    related_emdb: str | None = None
    related_bmrb: str | None = None
    sf_only: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.exp_type, str):
            self.exp_type = ExperimentType(self.exp_type)
        if isinstance(self.subtype, str):
            self.subtype = EMSubType(self.subtype)
        self.coordinates = bool(self.coordinates)
        self.sf_only = bool(self.sf_only)
        if self.related_emdb is not None:
            self.related_emdb = str(self.related_emdb)
        if self.related_bmrb is not None:
            self.related_bmrb = str(self.related_bmrb)

    def to_dict(self) -> dict:
        out: dict = {"type": self.exp_type.value, "coordinates": self.coordinates}
        if self.subtype:
            out["subtype"] = self.subtype.value
        if self.related_emdb:
            out["related_emdb"] = self.related_emdb
        if self.related_bmrb:
            out["related_bmrb"] = self.related_bmrb
        if self.sf_only:
            out["sf_only"] = self.sf_only
        return out


@dataclass
class DepositError:
    code: str
    message: str
    extras: str | None = None

    def __post_init__(self) -> None:
        self.code = str(self.code)
        self.message = str(self.message)


@dataclass
class PixelSpacing:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        self.x = float(self.x)
        self.y = float(self.y)
        self.z = float(self.z)


@dataclass
class EmVoxel:
    spacing: PixelSpacing
    contour: float

    def __post_init__(self) -> None:
        if isinstance(self.spacing, dict):
            self.spacing = PixelSpacing(**self.spacing)
        self.contour = float(self.contour)


@dataclass
class EmMapMetadata:
    voxel: EmVoxel
    description: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.voxel, dict):
            self.voxel = EmVoxel(**self.voxel)
        self.description = str(self.description)


@dataclass
class WwPDBDeposition:
    dep_id: str
    email: str
    pdb_id: str | None
    emdb_id: str | None
    bmrb_id: str | None
    title: str
    hold_exp_date: str | None
    created: datetime
    last_login: datetime
    site: str
    status: Status
    experiments: list[Experiment] = field(default_factory=list)
    errors: list[DepositError] = field(default_factory=list)
    site_url: str | None = None

    def __post_init__(self) -> None:
        self.dep_id = str(self.dep_id)
        self.email = str(self.email)
        self.pdb_id = str(self.pdb_id) if self.pdb_id and self.pdb_id != "?" else None
        self.emdb_id = str(self.emdb_id) if self.emdb_id and self.emdb_id != "?" else None
        self.bmrb_id = str(self.bmrb_id) if self.bmrb_id and self.bmrb_id != "?" else None
        self.title = str(self.title)
        if isinstance(self.created, str):
            self.created = datetime.fromisoformat(self.created)
        if isinstance(self.last_login, str):
            self.last_login = datetime.fromisoformat(self.last_login)
        if isinstance(self.status, str):
            self.status = Status[self.status]
        parsed_experiments = []
        for exp in self.experiments:
            if isinstance(exp, dict):
                exp = dict(exp)
                if "type" in exp:
                    exp["exp_type"] = exp.pop("type")
                parsed_experiments.append(Experiment(**exp))
            else:
                parsed_experiments.append(exp)
        self.experiments = parsed_experiments
        self.errors = [
            DepositError(**e) if isinstance(e, dict) else e
            for e in self.errors
        ]


@dataclass
class DepositedFile:
    file_id: int
    name: str
    file_type: FileType
    created: datetime
    metadata: EmMapMetadata | None = None
    errors: list[DepositError] = field(default_factory=list)
    warnings: list[DepositError] = field(default_factory=list)

    _DATE_FORMAT: ClassVar[str] = "%A, %B %d, %Y %H:%M:%S"

    def __post_init__(self) -> None:
        self.file_id = int(self.file_id)
        self.name = str(self.name)
        if isinstance(self.file_type, str):
            self.file_type = FileType(self.file_type)
        if isinstance(self.created, str):
            self.created = datetime.strptime(self.created, self._DATE_FORMAT)
        if isinstance(self.metadata, dict):
            self.metadata = EmMapMetadata(**self.metadata)
        self.errors = [
            DepositError(**e) if isinstance(e, dict) else e
            for e in self.errors
            if e != ""
        ]
        self.warnings = [
            DepositError(**w) if isinstance(w, dict) else w
            for w in self.warnings
            if w != ""
        ]


@dataclass
class DepositStatus:
    status: str
    action: str
    step: str
    details: str
    date: datetime

    def __post_init__(self) -> None:
        self.status = str(self.status)
        self.action = str(self.action)
        self.step = str(self.step)
        self.details = str(self.details)
        if isinstance(self.date, str):
            self.date = datetime.fromisoformat(self.date)
```

---

## Task 4 — `apis/deposit/types.py`: `ApiClient` Protocol

Create `src/nextdep_dsp/apis/deposit/types.py`:

```python
from typing import Protocol, Union

from nextdep_dsp.apis.deposit.models import (
    WwPDBDeposition,
    DepositedFile,
    DepositError,
    DepositStatus,
    Experiment,
)
from nextdep_dsp.enums import Country, FileType


class ApiClient(Protocol):
    def create_deposition(
        self,
        email: str,
        users: list[str],
        country: Country,
        experiments: list[Experiment],
        password: str = "",
    ) -> WwPDBDeposition: ...

    def get_all_depositions(self) -> list[WwPDBDeposition]: ...

    def get_deposition(self, dep_id: str) -> WwPDBDeposition: ...

    def upload_file(
        self,
        dep_id: str,
        file_path: str,
        file_type: FileType,
        overwrite: bool = False,
    ) -> DepositedFile: ...

    def update_metadata(
        self,
        dep_id: str,
        file_id: int,
        spacing_x: float,
        spacing_y: float,
        spacing_z: float,
        contour: float,
        description: str,
    ) -> DepositedFile: ...

    def get_files(self, dep_id: str) -> list[DepositedFile]: ...

    def remove_file(self, dep_id: str, file_id: int) -> bool: ...

    def get_status(self, dep_id: str) -> Union[DepositStatus, DepositError]: ...

    def process(self, dep_id: str) -> Union[DepositStatus, DepositError]: ...
```

---

## Task 5 — `apis/deposit/client.py`: `HttpApiClient`

Create `src/nextdep_dsp/apis/deposit/client.py`.

This class consolidates `deposition/rest_adapter.py` and `deposition/deposit_api.py`
into one coherent unit. It also replaces the `handle_invalid_deposit_site` decorator
by handling site redirects inline in `_do()`.

**Auth strategy:**
- If an `AuthProvider` from Plan 2 is provided, call
  `auth_provider.get_access_token()` before each request and set
  `Authorization: Bearer <token>`. The provider owns expiry checks, refresh calls,
  TOML token persistence, refresh-token rotation, and the documented
  `/deposition/auth/tokens/refresh` endpoint.
- Otherwise fall back to `config.api_key` as a static Bearer token (legacy mode
  for API-key-based auth during transition).

**Redirect handling (replaces `handle_invalid_deposit_site` decorator):**
When the API returns `{"code": "invalid_location", "extras": {"base_url": "..."}}`,
update `self._base_url` to `new_base/api/v1/` and retry the request once. Only
retry when `config.redirect` is `True` (mirrors the old `_redirect` flag). If
`config.redirect` is `False`, raise `ApiError` immediately.

**204 No Content:** Django returns 204 on some successful DELETE operations (the
comment in the PoC says "Django is redirecting 204 to OneDep home page"). Treat
it as success and return an empty dict.

**Exceptions:** Raise `ApiError` (from Plan 1's `nextdep_dsp.exceptions`) for all
error conditions. `DepositApiException` remains as a public alias
(also defined in Plan 1).

```python
import logging
import mimetypes
import os
from json import JSONDecodeError
from typing import Union

import requests
import urllib3

from nextdep_dsp.apis.deposit.models import (
    WwPDBDeposition,
    DepositedFile,
    DepositError,
    DepositStatus,
    Experiment,
)
from nextdep_dsp.auths.types import AuthProvider
from nextdep_dsp.config import DepositConfig
from nextdep_dsp.enums import Country, FileType
from nextdep_dsp.exceptions import ApiError


class HttpApiClient:
    def __init__(
        self,
        config: DepositConfig,
        auth_provider: AuthProvider | None = None,
        ver: str = "v1",
        logger: logging.Logger | None = None,
    ) -> None:
        self._config = config
        self._auth_provider = auth_provider
        self._ver = ver
        self._logger = logger or logging.getLogger(__name__)
        self._base_url = f"{config.hostname}/api/{ver}/"
        if not config.ssl_verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self._session = requests.Session()
        self._session.verify = config.ssl_verify

    def _refresh_auth_header(self) -> None:
        if self._auth_provider is not None:
            token = self._auth_provider.get_access_token()
        else:
            token = self._config.api_key or ""
        self._session.headers["Authorization"] = f"Bearer {token}"

    def _do(
        self,
        http_method: str,
        endpoint: str,
        params: dict | None = None,
        data: Union[dict, list, None] = None,
        files: dict | None = None,
        content_type: str = "application/json",
    ) -> dict:
        full_url = self._base_url + endpoint
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type

        self._refresh_auth_header()

        try:
            self._logger.debug("method=%s url=%s", http_method, full_url)
            response = self._session.request(
                method=http_method,
                url=full_url,
                headers=headers,
                params=params,
                json=data if content_type == "application/json" else None,
                data=data if content_type != "application/json" else None,
                files=files,
                timeout=300,
            )
        except requests.exceptions.RequestException as e:
            self._logger.error(str(e))
            raise ApiError("Failed to access the API", 403) from e

        if response.status_code == 204:
            return {}

        if not (200 <= response.status_code <= 299):
            self._logger.error("status=%s reason=%s", response.status_code, response.reason)
            raise ApiError(response.reason, response.status_code)

        try:
            data_out = response.json()
        except (ValueError, JSONDecodeError) as e:
            raise ApiError("Bad JSON in response", 502) from e

        if (
            isinstance(data_out, dict)
            and data_out.get("code") == "invalid_location"
            and "base_url" in data_out.get("extras", {})
        ):
            new_base = data_out["extras"]["base_url"]
            self._logger.warning("Invalid deposit site, redirecting to %s", new_base)
            if not self._config.redirect:
                raise ApiError(f"Invalid deposit site; correct site is {new_base}", 400)
            self._base_url = f"{new_base}/api/{self._ver}/"
            full_url = self._base_url + endpoint
            try:
                response = self._session.request(
                    method=http_method,
                    url=full_url,
                    headers=headers,
                    params=params,
                    json=data if content_type == "application/json" else None,
                    data=data if content_type != "application/json" else None,
                    files=files,
                    timeout=300,
                )
            except requests.exceptions.RequestException as e:
                raise ApiError("Retry after redirect failed", 503) from e
            if response.status_code == 204:
                return {}
            if not (200 <= response.status_code <= 299):
                raise ApiError(response.reason, response.status_code)
            try:
                data_out = response.json()
            except (ValueError, JSONDecodeError) as e:
                raise ApiError("Bad JSON in response after redirect", 502) from e

        return data_out

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        return self._do("GET", endpoint, params=params)

    def _post(
        self,
        endpoint: str,
        data: Union[dict, list, None] = None,
        files: dict | None = None,
        content_type: str = "application/json",
    ) -> dict:
        return self._do("POST", endpoint, data=data, files=files, content_type=content_type)

    def _delete(self, endpoint: str) -> None:
        self._do("DELETE", endpoint)

    # --- ApiClient Protocol implementation ---

    def create_deposition(
        self,
        email: str,
        users: list[str],
        country: Country,
        experiments: list[Experiment],
        password: str = "",
    ) -> WwPDBDeposition:
        body: dict = {
            "email": email,
            "users": users,
            "country": country.value,
            "experiments": [exp.to_dict() for exp in experiments],
        }
        if password:
            body["password"] = password
        data = self._post("depositions/new", data=body)
        data["dep_id"] = data.pop("id")
        return WwPDBDeposition(**data)

    def get_deposition(self, dep_id: str) -> WwPDBDeposition:
        data = self._get(f"depositions/{dep_id}")
        data["dep_id"] = data.pop("id")
        return WwPDBDeposition(**data)

    def get_all_depositions(self) -> list[WwPDBDeposition]:
        data = self._get("depositions/")
        depositions = []
        for item in data.get("items", []):
            item["dep_id"] = item.pop("id")
            depositions.append(WwPDBDeposition(**item))
        return depositions

    def upload_file(
        self,
        dep_id: str,
        file_path: str,
        file_type: FileType,
        overwrite: bool = False,
    ) -> DepositedFile:
        if not os.path.exists(file_path):
            raise ApiError("Invalid input file", 404)
        file_type_str = file_type.value if isinstance(file_type, FileType) else file_type
        mime_type, _ = mimetypes.guess_type(file_path)
        file_name = os.path.basename(file_path)
        form = {"name": file_name, "type": file_type_str}
        if overwrite:
            for existing_file in self.get_files(dep_id):
                if existing_file.file_type.value == file_type_str:
                    self.remove_file(dep_id, existing_file.file_id)
        with open(file_path, "rb") as fp:
            files = {"file": (file_name, fp, mime_type)}
            data = self._post(f"depositions/{dep_id}/files/", data=form, files=files, content_type="")
        data["file_type"] = data.pop("type")
        data["file_id"] = data.pop("id")
        return DepositedFile(**data)

    def update_metadata(
        self,
        dep_id: str,
        file_id: int,
        spacing_x: float,
        spacing_y: float,
        spacing_z: float,
        contour: float,
        description: str,
    ) -> DepositedFile:
        body = {
            "voxel": {
                "spacing": {"x": spacing_x, "y": spacing_y, "z": spacing_z},
                "contour": contour,
            },
            "description": description,
        }
        data = self._post(f"depositions/{dep_id}/files/{file_id}/metadata", data=body)
        data["file_type"] = data.pop("type")
        data["file_id"] = data.pop("id")
        return DepositedFile(**data)

    def get_files(self, dep_id: str) -> list[DepositedFile]:
        data = self._get(f"depositions/{dep_id}/files/")
        result = []
        for f in data.get("files", []):
            f = dict(f)
            f["file_type"] = f.pop("type", f.get("file_type"))
            f["file_id"] = f.pop("id", f.get("file_id"))
            result.append(DepositedFile(**f))
        return result

    def remove_file(self, dep_id: str, file_id: int) -> bool:
        self._delete(f"depositions/{dep_id}/files/{file_id}")
        return True

    def get_status(self, dep_id: str) -> Union[DepositStatus, DepositError]:
        data = self._get(f"depositions/{dep_id}/status")
        if "action" in data:
            return DepositStatus(**data)
        return DepositError(**data)

    def process(self, dep_id: str) -> Union[DepositStatus, DepositError]:
        data = self._post(f"depositions/{dep_id}/process", data={})
        if "action" in data:
            return DepositStatus(**data)
        return DepositError(**data)
```

---

## Task 6 — Refactor `src/nextdep_dsp/dsp.py`

Replace the full contents of `src/nextdep_dsp/dsp.py` with the DI-based version below.

**Key changes from the PoC:**

1. `Deposition.__init__` takes three injected dependencies:
   `store: SessionStore`, `api_client: ApiClient`, `check_runner: CheckRunner`.
2. `deposit_init` and `deposit_resume` construct `JsonSessionStore`, `HttpApiClient`,
   and `JsonCheckRunner` by default; all three accept `_xxx` overrides for testing.
3. `deposit_init` accepts an optional `config: DepositConfig | None = None` parameter
   so callers can pass pre-built config (e.g. in tests).
4. `deposit()` builds one `Experiment` object and calls `self._api_client.create_deposition()`
   directly, removing the EM-specific convenience method branch.
5. `check_*` methods delegate entirely to `self._check_runner`; the free functions
   from `checks/file_checks.py` are gone.
6. `LocalSession` construction no longer passes `db_path` (Plan 1 removes that field).
7. `list_sessions` uses `JsonSessionStore` instead of the old `SessionStore`.

**Assumed interfaces from Plan 1:**

`CheckRunner` Protocol (in `nextdep_dsp.checks.types`) has:
```python
def check_required_files(self, files, experiment_type, em_subtype) -> CheckReport: ...
def check_mmcif_file(self, file) -> CheckReport: ...
def check_mmcif_category(self, file, category) -> CheckReport: ...
def check_mmcif_field(self, file, category, field) -> CheckReport: ...
def check_file_type(self, file, file_type) -> CheckReport: ...
```

`SessionStore` Protocol (in `nextdep_dsp.session.types`) has:
```python
def get_session(self) -> LocalSession: ...
def create_session(self, session) -> None: ...
def get_all_files(self) -> list[LocalFile]: ...
def get_file(self, file_id) -> LocalFile: ...
def add_file(self, file) -> None: ...
def remove_file(self, file_id) -> None: ...
def set_voxel_values(self, file_id, spacing_x, spacing_y, spacing_z, contour) -> None: ...
def set_remote_dep_id(self, dep_id) -> None: ...
def update_experiment_type(self, experiment_type) -> None: ...
def update_em_params(self, em_subtype, coordinates) -> None: ...
def close(self) -> None: ...
```

`JsonSessionStore` is in `nextdep_dsp.session.json_store`.
`JsonCheckRunner` is in `nextdep_dsp.checks.runner`.
`RemoteSchemaProvider` is in `nextdep_dsp.validation.schema`.

```python
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from nextdep_dsp.apis.deposit.client import HttpApiClient
from nextdep_dsp.apis.deposit.models import DepositError, DepositStatus, Experiment
from nextdep_dsp.apis.deposit.types import ApiClient
from nextdep_dsp.checks.report import CheckReport
from nextdep_dsp.checks.runner import JsonCheckRunner
from nextdep_dsp.checks.types import CheckRunner
from nextdep_dsp.config import DepositConfig
from nextdep_dsp.enums import Country, EMSubType, ExperimentType, FileType
from nextdep_dsp.session.json_store import JsonSessionStore
from nextdep_dsp.session.models import LocalFile, LocalSession
from nextdep_dsp.session.types import SessionStore
from nextdep_dsp.validation.schema import RemoteSchemaProvider


def _md5_of_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def list_sessions(base_dir: Path | None = None) -> list[tuple[LocalSession, list[LocalFile]]]:
    """Return all local sessions with their registered files, newest first."""
    _base = base_dir or (Path.home() / ".nextdep" / "sessions")
    if not _base.exists():
        return []

    results: list[tuple[LocalSession, list[LocalFile]]] = []
    for entry in sorted(_base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        json_path = entry / "session.json"
        if not json_path.exists():
            continue
        try:
            store = JsonSessionStore(entry.name, base_dir=_base)
            session = store.get_session()
            files = store.get_all_files()
            store.close()
            results.append((session, files))
        except Exception:  # noqa: BLE001
            continue

    return results


def deposit_init(
    email: str,
    users: list[str],
    country: Country,
    experiment_type: ExperimentType | None = None,
    em_subtype: EMSubType | str | None = None,
    coordinates: bool | None = None,
    config: DepositConfig | None = None,
    _base_dir: Path | None = None,
    _api_client: ApiClient | None = None,
    _check_runner: CheckRunner | None = None,
) -> Deposition:
    """Create a new local deposition session.

    Args:
        email: Depositor e-mail address.
        users: List of ORCID IDs granted access to this deposition.
        country: Depositor country (use the Country enum).
        experiment_type: Experiment type (can be set later via set_experiment_type).
        em_subtype: EM experiment subtype (can be set later via set_em_params).
        coordinates: Whether coordinates are being deposited (can be set later).
        config: Optional pre-built DepositConfig; loaded from default sources if None.
        _base_dir: Override session storage directory (for testing only).
        _api_client: Override API client (for testing only).
        _check_runner: Override check runner (for testing only).

    Returns:
        A Deposition object representing the local session.
    """
    config = config or DepositConfig.load()
    session_id = str(uuid.uuid4())
    base_dir = _base_dir or config.session_dir
    store: SessionStore = JsonSessionStore(session_id, base_dir=base_dir)
    api_client: ApiClient = _api_client or HttpApiClient(config)
    check_runner: CheckRunner = _check_runner or JsonCheckRunner(RemoteSchemaProvider(config))
    em_subtype_str = em_subtype.value if isinstance(em_subtype, EMSubType) else em_subtype
    session = LocalSession(
        session_id=session_id,
        email=email,
        users=users,
        country=country,
        experiment_type=experiment_type,
        created_at=datetime.now(),
        em_subtype=em_subtype_str,
        coordinates=coordinates,
    )
    store.create_session(session)
    return Deposition(store=store, api_client=api_client, check_runner=check_runner)


def deposit_resume(
    session_id: str,
    config: DepositConfig | None = None,
    _base_dir: Path | None = None,
    _api_client: ApiClient | None = None,
    _check_runner: CheckRunner | None = None,
) -> Deposition:
    """Resume an existing local deposition session.

    Args:
        session_id: The session_id returned by a previous deposit_init() call.
        config: Optional pre-built DepositConfig; loaded from default sources if None.
        _base_dir: Override session storage directory (for testing only).
        _api_client: Override API client (for testing only).
        _check_runner: Override check runner (for testing only).

    Returns:
        A Deposition object for the existing session.

    Raises:
        KeyError: If no session with the given session_id exists.
    """
    config = config or DepositConfig.load()
    base_dir = _base_dir or config.session_dir
    store: SessionStore = JsonSessionStore(session_id, base_dir=base_dir)
    store.get_session()  # raises KeyError if not found
    api_client: ApiClient = _api_client or HttpApiClient(config)
    check_runner: CheckRunner = _check_runner or JsonCheckRunner(RemoteSchemaProvider(config))
    return Deposition(store=store, api_client=api_client, check_runner=check_runner)


class Deposition:
    """Local deposition session. Created via deposit_init() or deposit_resume()."""

    def __init__(
        self,
        store: SessionStore,
        api_client: ApiClient,
        check_runner: CheckRunner,
    ) -> None:
        self._store = store
        self._api_client = api_client
        self._check_runner = check_runner
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

    def set_em_params(
        self,
        em_subtype: EMSubType | str | None = None,
        coordinates: bool | None = None,
    ) -> None:
        """Set EM-specific parameters for this deposition."""
        em_subtype_str = em_subtype.value if isinstance(em_subtype, EMSubType) else em_subtype
        self._store.update_em_params(em_subtype_str, coordinates)
        self._session.em_subtype = em_subtype_str
        self._session.coordinates = coordinates

    def check_auth_key(self) -> bool:
        """Return True if the configured credentials are valid, False otherwise."""
        try:
            self._api_client.get_all_depositions()
            return True
        except Exception:  # noqa: BLE001
            return False

    def add_file(self, file_path: str, file_type: FileType) -> str:
        """Register a local file for this deposition.

        Returns:
            A file_id (UUID string) to reference this file in check methods.

        Raises:
            FileNotFoundError: If file_path does not exist.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        stat = path.stat()
        file_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        md5 = _md5_of_file(path)
        file_id = str(uuid.uuid4())
        local_file = LocalFile(
            file_id=file_id,
            session_id=self._session.session_id,
            file_path=str(path.resolve()),
            file_type=file_type,
            md5=md5,
            file_mtime=file_mtime,
        )
        self._store.add_file(local_file)
        return file_id

    def remove_file(self, file_id: str) -> None:
        """Remove a file from this local session by its file_id."""
        self._store.remove_file(file_id)

    def set_voxel_values(
        self,
        file_id: str,
        spacing_x: float,
        spacing_y: float,
        spacing_z: float,
        contour: float,
    ) -> None:
        """Set voxel spacing and contour level for a map file.

        Args:
            file_id: Local file ID returned by add_file().
            spacing_x: Pixel spacing along X axis (Å).
            spacing_y: Pixel spacing along Y axis (Å).
            spacing_z: Pixel spacing along Z axis (Å).
            contour: Contour level for the map.
        """
        self._store.set_voxel_values(file_id, spacing_x, spacing_y, spacing_z, contour)

    def check_required_files(self) -> CheckReport:
        """Check that the session contains all required files for the experiment type."""
        files = self._store.get_all_files()
        return self._check_runner.check_required_files(
            files, self._session.experiment_type, self._session.em_subtype
        )

    def check_mmcif_file(self, file_id: str) -> CheckReport:
        """Check that the file identified by file_id is a valid mmCIF."""
        file = self._store.get_file(file_id)
        return self._check_runner.check_mmcif_file(file)

    def check_mmcif_category(self, file_id: str, category: str) -> CheckReport:
        """Check that the mmCIF file contains the given category."""
        file = self._store.get_file(file_id)
        return self._check_runner.check_mmcif_category(file, category)

    def check_mmcif_field(self, file_id: str, category: str, field: str) -> CheckReport:
        """Check that the mmCIF file contains the given field in the given category."""
        file = self._store.get_file(file_id)
        return self._check_runner.check_mmcif_field(file, category, field)

    def check_file_type(self, file_id: str, file_type: FileType) -> CheckReport:
        """Check that the file matches the expected FileType."""
        file = self._store.get_file(file_id)
        return self._check_runner.check_file_type(file, file_type)

    def deposit(self) -> str:
        """Submit this deposition to the OneDep API.

        Creates a remote deposition, uploads all registered files, and triggers
        processing. Returns immediately without waiting for processing to finish
        (non-blocking). Use get_status() to poll.

        Returns:
            The remote deposition ID (e.g. "D_8000000001").

        Raises:
            ValueError: If experiment_type has not been set, or if no experiment type
                is configured.
            ApiError: If any API call fails.
        """
        if self._session.experiment_type is None:
            raise ValueError(
                "experiment_type must be set before calling deposit(). "
                "Use set_experiment_type() or pass experiment_type to deposit_init()."
            )
        if self._session.remote_dep_id is None:
            experiment = Experiment(
                exp_type=self._session.experiment_type,
                coordinates=self._session.coordinates if self._session.coordinates is not None else True,
                subtype=self._session.em_subtype,
            )
            remote_dep = self._api_client.create_deposition(
                email=self._session.email,
                users=self._session.users,
                country=self._session.country,
                experiments=[experiment],
            )
            dep_id = remote_dep.dep_id
            self._store.set_remote_dep_id(dep_id)
            self._session.remote_dep_id = dep_id
        else:
            dep_id = self._session.remote_dep_id

        for file in self._store.get_all_files():
            deposited = self._api_client.upload_file(dep_id, file.file_path, file.file_type)
            if file.voxel:
                v = file.voxel
                self._api_client.update_metadata(
                    dep_id,
                    deposited.file_id,
                    spacing_x=v["spacing_x"],
                    spacing_y=v["spacing_y"],
                    spacing_z=v["spacing_z"],
                    contour=v["contour"],
                    description="",
                )

        self._api_client.process(dep_id)
        return dep_id

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
        return self._api_client.get_status(self._session.remote_dep_id)

    def get_experiment_file_types(self) -> list[FileType]:
        """Return the accepted file types for the current experiment type. (stub)"""
        return []

    def close(self) -> None:
        """Close the underlying session store connection."""
        self._store.close()

    def __enter__(self) -> Deposition:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
```

---

## Task 7 — Update `src/nextdep_dsp/__init__.py`

Replace the full contents of `src/nextdep_dsp/__init__.py`:

```python
"""nextdep_dsp — Deposition Software Provider library for OneDep."""

from nextdep_dsp.apis.deposit.enums import Status
from nextdep_dsp.apis.deposit.models import DepositError, DepositStatus
from nextdep_dsp.apis.deposit.types import ApiClient
from nextdep_dsp.auths.token import TokenStore
from nextdep_dsp.auths.types import AuthProvider
from nextdep_dsp.checks.report import CheckIssue, CheckReport, CheckSeverity, CifLocation
from nextdep_dsp.dsp import Deposition, deposit_init, deposit_resume, list_sessions
from nextdep_dsp.enums import Country, EMSubType, ExperimentType, FileType
from nextdep_dsp.exceptions import ApiError, DepositApiException, NextDepError

__all__ = [
    # factories / facade
    "deposit_init",
    "deposit_resume",
    "list_sessions",
    "Deposition",
    # check result types
    "CheckReport",
    "CheckIssue",
    "CheckSeverity",
    "CifLocation",
    # domain enums
    "Country",
    "EMSubType",
    "ExperimentType",
    "FileType",
    # API response models
    "DepositStatus",
    "DepositError",
    "Status",
    # exceptions
    "NextDepError",
    "ApiError",
    "DepositApiException",
    # auth
    "TokenStore",
    "AuthProvider",
    # protocols
    "ApiClient",
]
```

---

## Task 8 — Tests

### 8a. Shared test fixture in `tests/unit/apis/deposit/conftest.py`

```python
import pytest
from pytest_httpserver import HTTPServer
from nextdep_dsp.apis.deposit.client import HttpApiClient
from nextdep_dsp.config import DepositConfig


@pytest.fixture
def api_config(httpserver: HTTPServer) -> DepositConfig:
    return DepositConfig(
        hostname=httpserver.url_for("").rstrip("/"),
        api_key="test-key",
        ssl_verify=False,
        redirect=True,
    )


@pytest.fixture
def client(api_config: DepositConfig) -> HttpApiClient:
    return HttpApiClient(api_config)
```

### 8b. `tests/unit/apis/deposit/test_models.py`

```python
from datetime import datetime
import pytest
from nextdep_dsp.apis.deposit.models import (
    WwPDBDeposition, DepositError, DepositedFile, DepositStatus, Experiment, PixelSpacing,
)
from nextdep_dsp.apis.deposit.enums import Status
from nextdep_dsp.enums import ExperimentType, FileType


def _deposit(**overrides) -> WwPDBDeposition:
    defaults = dict(
        dep_id="D_1", email="a@b.com",
        pdb_id="?", emdb_id="?", bmrb_id="?",
        title="T", hold_exp_date=None,
        created="2024-01-01T00:00:00",
        last_login="2024-01-01T00:00:00",
        site="pdbe", status="DEP",
    )
    return WwPDBDeposition(**{**defaults, **overrides})


def test_deposit_normalises_question_mark_ids():
    d = _deposit()
    assert d.pdb_id is None
    assert d.emdb_id is None
    assert d.bmrb_id is None


def test_deposit_parses_status_by_name():
    d = _deposit(status="PROC")
    assert d.status is Status.PROC


def test_deposit_parses_created_datetime():
    d = _deposit(created="2024-06-15T10:30:00")
    assert d.created == datetime(2024, 6, 15, 10, 30, 0)


def test_deposit_parses_nested_experiments():
    d = _deposit(experiments=[{"type": "xray", "coordinates": True}])
    assert len(d.experiments) == 1
    assert d.experiments[0].exp_type is ExperimentType.XRAY


def test_experiment_coerces_string_type():
    exp = Experiment(exp_type="xray")
    assert exp.exp_type is ExperimentType.XRAY


def test_deposited_file_parses_custom_date_format():
    f = DepositedFile(
        file_id=1, name="f.cif",
        file_type="co-cif",
        created="Monday, January 01, 2024 12:00:00",
    )
    assert f.file_id == 1
    assert f.file_type is FileType.MMCIF_COORD
    assert f.created == datetime(2024, 1, 1, 12, 0, 0)


def test_deposit_status_parses_iso_date():
    s = DepositStatus(
        status="DEP", action="deposit", step="1",
        details="deposited", date="2024-01-01T00:00:00",
    )
    assert s.date == datetime(2024, 1, 1)


def test_deposit_error_coerces_strings():
    e = DepositError(code=42, message=99)
    assert e.code == "42"
    assert e.message == "99"
```

### 8c. `tests/unit/apis/deposit/test_http_api_client.py`

```python
import json
import pytest
from pytest_httpserver import HTTPServer
from nextdep_dsp.apis.deposit.client import HttpApiClient
from nextdep_dsp.apis.deposit.models import WwPDBDeposition, DepositedFile, DepositStatus
from nextdep_dsp.enums import Country, ExperimentType, FileType
from nextdep_dsp.apis.deposit.models import Experiment
from nextdep_dsp.exceptions import ApiError


class StubAuthProvider:
    def __init__(self) -> None:
        self.calls = 0

    def get_access_token(self) -> str:
        self.calls += 1
        return f"token-{self.calls}"


_DEPOSIT_RESPONSE = {
    "id": "D_800001",
    "email": "test@example.com",
    "pdb_id": "?",
    "emdb_id": "?",
    "bmrb_id": "?",
    "title": "Test",
    "hold_exp_date": None,
    "created": "2024-01-01T00:00:00",
    "last_login": "2024-01-01T00:00:00",
    "site": "pdbe",
    "status": "DEP",
    "experiments": [],
    "errors": [],
}

_FILE_RESPONSE = {
    "id": 1,
    "name": "test.cif",
    "type": "co-cif",
    "created": "Monday, January 01, 2024 00:00:00",
    "errors": [],
    "warnings": [],
}

_STATUS_RESPONSE = {
    "status": "DEP",
    "action": "deposit",
    "step": "1",
    "details": "deposited",
    "date": "2024-01-01T00:00:00",
}


def test_create_deposition(httpserver: HTTPServer, client: HttpApiClient):
    httpserver.expect_request("/api/v1/depositions/new", method="POST").respond_with_json(
        _DEPOSIT_RESPONSE
    )
    dep = client.create_deposition(
        email="test@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.USA,
        experiments=[Experiment(exp_type=ExperimentType.XRAY)],
    )
    assert isinstance(dep, WwPDBDeposition)
    assert dep.dep_id == "D_800001"


def test_auth_provider_sets_bearer_token_before_request(httpserver: HTTPServer, api_config):
    auth = StubAuthProvider()
    httpserver.expect_request(
        "/api/v1/depositions/D_800001/status",
        method="GET",
        headers={"Authorization": "Bearer token-1"},
    ).respond_with_json(_STATUS_RESPONSE)
    client = HttpApiClient(api_config, auth_provider=auth)
    status = client.get_status("D_800001")
    assert isinstance(status, DepositStatus)
    assert auth.calls == 1


def test_get_status(httpserver: HTTPServer, client: HttpApiClient):
    httpserver.expect_request("/api/v1/depositions/D_800001/status", method="GET").respond_with_json(
        _STATUS_RESPONSE
    )
    status = client.get_status("D_800001")
    assert isinstance(status, DepositStatus)
    assert status.status == "DEP"


def test_upload_file(httpserver: HTTPServer, client: HttpApiClient, tmp_path):
    test_file = tmp_path / "test.cif"
    test_file.write_text("data_test")
    httpserver.expect_request("/api/v1/depositions/D_800001/files/", method="POST").respond_with_json(
        _FILE_RESPONSE
    )
    deposited = client.upload_file("D_800001", str(test_file), FileType.MMCIF_COORD)
    assert isinstance(deposited, DepositedFile)
    assert deposited.file_id == 1
    assert deposited.file_type is FileType.MMCIF_COORD


def test_upload_file_missing_raises(client: HttpApiClient):
    with pytest.raises(ApiError):
        client.upload_file("D_800001", "/nonexistent/path.cif", FileType.MMCIF_COORD)


def test_non_2xx_raises_api_error(httpserver: HTTPServer, client: HttpApiClient):
    httpserver.expect_request("/api/v1/depositions/D_999/status").respond_with_data(
        "Not Found", status=404
    )
    with pytest.raises(ApiError):
        client.get_status("D_999")


def test_redirect_updates_base_url_and_retries(httpserver: HTTPServer, api_config):
    correct_base = httpserver.url_for("").rstrip("/")
    httpserver.expect_ordered_request("/api/v1/depositions/", method="GET").respond_with_json({
        "code": "invalid_location",
        "extras": {"base_url": correct_base},
    })
    httpserver.expect_ordered_request("/api/v1/depositions/", method="GET").respond_with_json({
        "items": []
    })
    client = HttpApiClient(api_config)
    result = client.get_all_depositions()
    assert result == []


def test_204_returns_empty(httpserver: HTTPServer, client: HttpApiClient):
    httpserver.expect_request("/api/v1/depositions/D_1/files/1", method="DELETE").respond_with_data(
        "", status=204
    )
    result = client.remove_file("D_1", 1)
    assert result is True
```

### 8d. `tests/unit/apis/deposit/test_stub_api_client.py`

Defines `StubApiClient` (shared by facade tests) and verifies structural compatibility.

```python
from typing import Union
from nextdep_dsp.apis.deposit.models import (
    WwPDBDeposition, DepositedFile, DepositError, DepositStatus, Experiment,
)
from nextdep_dsp.enums import Country, FileType


def _stub_deposit(dep_id: str = "D_999", email: str = "test@example.com") -> WwPDBDeposition:
    return WwPDBDeposition(
        dep_id=dep_id, email=email, pdb_id=None, emdb_id=None, bmrb_id=None,
        title="", hold_exp_date=None,
        created="2024-01-01T00:00:00",
        last_login="2024-01-01T00:00:00",
        site="pdbe", status="DEP",
    )


def _stub_file(file_id: int = 1, file_type: FileType = FileType.MMCIF_COORD) -> DepositedFile:
    return DepositedFile(
        file_id=file_id, name="f.cif", file_type=file_type,
        created="Monday, January 01, 2024 00:00:00",
    )


class StubApiClient:
    """In-memory ApiClient for unit-testing the Deposition facade.
    Satisfies the ApiClient Protocol structurally — no import of ApiClient needed.
    """

    def __init__(self) -> None:
        self.deposited_files: list[str] = []
        self.processed: list[str] = []

    def create_deposition(self, email, users, country, experiments, password="") -> WwPDBDeposition:
        return _stub_deposit(email=email)

    def get_all_depositions(self) -> list[WwPDBDeposition]:
        return []

    def get_deposition(self, dep_id: str) -> WwPDBDeposition:
        return _stub_deposit(dep_id=dep_id)

    def upload_file(self, dep_id, file_path, file_type, overwrite=False) -> DepositedFile:
        self.deposited_files.append(file_path)
        return _stub_file(file_type=file_type)

    def update_metadata(self, dep_id, file_id, spacing_x, spacing_y, spacing_z, contour, description) -> DepositedFile:
        return _stub_file(file_id=file_id)

    def get_files(self, dep_id) -> list[DepositedFile]:
        return []

    def remove_file(self, dep_id, file_id) -> bool:
        return True

    def get_status(self, dep_id) -> Union[DepositStatus, DepositError]:
        return DepositStatus(
            status="DEP", action="deposit", step="1",
            details="deposited", date="2024-01-01T00:00:00",
        )

    def process(self, dep_id) -> Union[DepositStatus, DepositError]:
        self.processed.append(dep_id)
        return DepositStatus(
            status="PROC", action="process", step="1",
            details="processing", date="2024-01-01T00:00:00",
        )


def test_stub_api_client_is_structurally_compatible():
    from nextdep_dsp.apis.deposit.types import ApiClient
    # Protocol compatibility is verified at type-check time; at runtime just
    # confirm all required methods exist.
    stub = StubApiClient()
    required = [
        "create_deposition", "get_all_depositions", "get_deposition",
        "upload_file", "update_metadata", "get_files", "remove_file",
        "get_status", "process",
    ]
    for method in required:
        assert callable(getattr(stub, method, None)), f"Missing: {method}"
```

### 8e. `tests/unit/test_deposition_facade.py`

```python
import pytest
from pathlib import Path
from nextdep_dsp.checks.report import CheckReport
from nextdep_dsp.dsp import deposit_init, deposit_resume
from nextdep_dsp.enums import Country, ExperimentType, FileType
from tests.unit.apis.deposit.test_stub_api_client import StubApiClient


class StubCheckRunner:
    """Structurally satisfies the CheckRunner Protocol."""

    def check_required_files(self, files, experiment_type, em_subtype) -> CheckReport:
        return CheckReport(issues=[])

    def check_mmcif_file(self, file) -> CheckReport:
        return CheckReport(issues=[])

    def check_mmcif_category(self, file, category) -> CheckReport:
        return CheckReport(issues=[])

    def check_mmcif_field(self, file, category, field) -> CheckReport:
        return CheckReport(issues=[])

    def check_file_type(self, file, file_type) -> CheckReport:
        return CheckReport(issues=[])


@pytest.fixture
def stub_api():
    return StubApiClient()


@pytest.fixture
def dep(tmp_path, stub_api):
    return deposit_init(
        email="test@example.com",
        users=["0000-0001-2345-6789"],
        country=Country.USA,
        experiment_type=ExperimentType.XRAY,
        _base_dir=tmp_path,
        _api_client=stub_api,
        _check_runner=StubCheckRunner(),
    )


def test_session_id_is_set(dep):
    assert dep.session_id is not None


def test_remote_dep_id_initially_none(dep):
    assert dep.remote_dep_id is None


def test_deposit_returns_remote_id(dep, stub_api):
    remote_id = dep.deposit()
    assert remote_id == "D_999"
    assert dep.remote_dep_id == "D_999"


def test_deposit_calls_process(dep, stub_api):
    dep.deposit()
    assert "D_999" in stub_api.processed


def test_get_status_after_deposit(dep):
    dep.deposit()
    status = dep.get_status()
    assert status.status == "DEP"


def test_get_status_before_deposit_raises(dep):
    with pytest.raises(RuntimeError, match="deposit\\(\\) has not been called"):
        dep.get_status()


def test_deposit_without_experiment_type_raises(tmp_path):
    dep = deposit_init(
        email="test@example.com",
        users=[],
        country=Country.USA,
        _base_dir=tmp_path,
        _api_client=StubApiClient(),
        _check_runner=StubCheckRunner(),
    )
    with pytest.raises(ValueError, match="experiment_type must be set"):
        dep.deposit()


def test_add_and_remove_file(dep, tmp_path):
    test_file = tmp_path / "coords.cif"
    test_file.write_text("data_test")
    file_id = dep.add_file(str(test_file), FileType.MMCIF_COORD)
    assert file_id is not None
    dep.remove_file(file_id)


def test_add_nonexistent_file_raises(dep):
    with pytest.raises(FileNotFoundError):
        dep.add_file("/nonexistent/path.cif", FileType.MMCIF_COORD)


def test_check_auth_key_returns_bool(dep):
    result = dep.check_auth_key()
    assert isinstance(result, bool)


def test_deposit_resume_restores_session(dep, tmp_path, stub_api):
    session_id = dep.session_id
    dep.close()
    resumed = deposit_resume(
        session_id,
        _base_dir=tmp_path,
        _api_client=stub_api,
        _check_runner=StubCheckRunner(),
    )
    assert resumed.session_id == session_id
    resumed.close()


def test_context_manager(tmp_path, stub_api):
    with deposit_init(
        email="test@example.com",
        users=[],
        country=Country.USA,
        experiment_type=ExperimentType.XRAY,
        _base_dir=tmp_path,
        _api_client=stub_api,
        _check_runner=StubCheckRunner(),
    ) as dep:
        assert dep.session_id is not None
```

---

## Task 9 — Delete `src/nextdep_dsp/deposition/`

Delete the entire `src/nextdep_dsp/deposition/` package. The following files must
all be removed:

- `src/nextdep_dsp/deposition/__init__.py`
- `src/nextdep_dsp/deposition/decorators.py`
- `src/nextdep_dsp/deposition/deposit_api.py`
- `src/nextdep_dsp/deposition/enum.py`
- `src/nextdep_dsp/deposition/exceptions.py`
- `src/nextdep_dsp/deposition/models.py`
- `src/nextdep_dsp/deposition/rest_adapter.py`

After deletion, verify no remaining source file imports from `nextdep_dsp.deposition`:

```bash
grep -r "nextdep_dsp.deposition" src/ tests/
# must return no results
```

---

## Task 10 — Final verification

Run the full test suite (excluding e2e):

```bash
python -m pytest tests/ -x -q --ignore=tests/e2e
```

Run a smoke import to confirm the public surface is intact:

```bash
python -c "
from nextdep_dsp import (
    deposit_init, deposit_resume, list_sessions, Deposition,
    CheckReport, CheckIssue, CheckSeverity, CifLocation,
    Country, EMSubType, ExperimentType, FileType,
    DepositStatus, DepositError, Status,
    NextDepError, ApiError, DepositApiException,
    TokenStore, AuthProvider, ApiClient,
)
print('All imports OK')
"
```

Both must succeed with no errors.
