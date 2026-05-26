# Core Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core data layer of nextdep_dsp v2 — typed exceptions, layered config, enums, session persistence, remote schema fetching, and file-presence validation checks.

**Architecture:** Protocol-based dependency injection where each I/O boundary (`SessionStore`, `SchemaProvider`) is a `typing.Protocol` satisfied structurally. `CheckRunner` orchestrates all validation using schemas fetched via `SchemaProvider`. Check methods always return `CheckReport`; infrastructure failures raise typed subclasses of `NextDepError`.

**Tech Stack:** Python 3.9+, `jsonschema` (already a dep), `requests` (already a dep), `tomllib`/`tomli` (already a dep), `pytest`, `pytest-httpserver` (new dev dep for schema integration tests).

---

## File map

### New files
| Path | Responsibility |
|---|---|
| `src/nextdep_dsp/exceptions.py` | `NextDepError` hierarchy |
| `src/nextdep_dsp/enums.py` | `Country`, `ExperimentType`, `EMSubType`, `FileType` (moved from `deposition/enum.py`) |
| `src/nextdep_dsp/session/types.py` | `SessionStore` Protocol |
| `src/nextdep_dsp/schemas/__init__.py` | Package init |
| `src/nextdep_dsp/schemas/types.py` | `SchemaProvider` Protocol |
| `src/nextdep_dsp/schemas/remote.py` | `RemoteSchemaProvider` (fetch + disk cache) |
| `src/nextdep_dsp/checks/runner.py` | `CheckRunner` — all check methods |

### Modified files
| Path | Change |
|---|---|
| `src/nextdep_dsp/config.py` | Rewrite: add `schema_base_url`, `schema_cache_dir`, `session_dir`; raise `ConfigError` instead of `ValueError` |
| `src/nextdep_dsp/session/models.py` | Remove `db_path` field; import enums from `nextdep_dsp.enums` |
| `src/nextdep_dsp/session/json_store.py` | Rename from `store.py`; import enums from `nextdep_dsp.enums` |
| `src/nextdep_dsp/checks/report.py` | Import enums from `nextdep_dsp.enums` (otherwise unchanged) |
| `pyproject.toml` | Add `pytest-httpserver` to `[dependency-groups.test]` |

### Files to delete (after all tasks pass)
- `src/nextdep_dsp/session/store.py` → replaced by `json_store.py`
- `src/nextdep_dsp/checks/file_checks.py` → replaced by `checks/runner.py`
- `src/nextdep_dsp/validation/` (entire package) → logic moved to `checks/runner.py`

---

## Task 1: Exception hierarchy

**Files:**
- Create: `src/nextdep_dsp/exceptions.py`
- Create: `tests/test_exceptions.py`

- [ ] **Write the failing test**

```python
# tests/test_exceptions.py
import pytest
from nextdep_dsp.exceptions import (
    ApiError, AuthError, ConfigError, DepositApiException,
    NextDepError, SchemaError,
)

def test_all_errors_inherit_from_nextdep_error():
    assert issubclass(AuthError, NextDepError)
    assert issubclass(ApiError, NextDepError)
    assert issubclass(ConfigError, NextDepError)
    assert issubclass(SchemaError, NextDepError)

def test_api_error_stores_status_code():
    err = ApiError("Not found", 404)
    assert err.status_code == 404
    assert str(err) == "Not found"

def test_deposit_api_exception_is_alias_for_api_error():
    assert DepositApiException is ApiError
    err = DepositApiException("Unauthorized", 401)
    assert isinstance(err, NextDepError)

def test_exceptions_are_catchable_as_base():
    with pytest.raises(NextDepError):
        raise AuthError("bad token")
```

- [ ] **Run test to verify it fails**

```bash
uv run pytest tests/test_exceptions.py -v
```
Expected: `ImportError` — `exceptions` module does not exist yet.

- [ ] **Implement**

```python
# src/nextdep_dsp/exceptions.py
class NextDepError(Exception):
    """Base exception for all nextdep_dsp errors."""


class AuthError(NextDepError):
    """OIDC flow failure or token expired/invalid."""


class ApiError(NextDepError):
    """HTTP error from the OneDep API."""

    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class ConfigError(NextDepError):
    """Missing or invalid configuration."""


class SchemaError(NextDepError):
    """Schema fetch failure, cache corruption, or validation engine error."""


# Public alias — kept for backwards compatibility with PoC consumers
DepositApiException = ApiError
```

- [ ] **Run test to verify it passes**

```bash
uv run pytest tests/test_exceptions.py -v
```
Expected: 4 passed.

- [ ] **Commit**

```bash
git add src/nextdep_dsp/exceptions.py tests/test_exceptions.py
git commit -m "feat: add typed exception hierarchy (NextDepError)"
```

---

## Task 2: DepositConfig

**Files:**
- Modify: `src/nextdep_dsp/config.py`
- Modify: `tests/test_config.py`

- [ ] **Write the failing tests**

```python
# tests/test_config.py
import pytest
from nextdep_dsp.config import DepositConfig
from nextdep_dsp.exceptions import ConfigError


def test_defaults():
    cfg = DepositConfig()
    assert cfg.api_key is None
    assert cfg.hostname == "https://deposit.wwpdb.org/deposition"
    assert cfg.ssl_verify is True
    assert cfg.redirect is True
    assert cfg.schema_base_url == "https://schemas.wwpdb.org/nextdep"
    assert "schemas" in str(cfg.schema_cache_dir)
    assert "sessions" in str(cfg.session_dir)


def test_constructor_overrides(monkeypatch):
    monkeypatch.delenv("ONEDEP_API_KEY", raising=False)
    cfg = DepositConfig.load(api_key="test-key", ssl_verify=False)
    assert cfg.api_key == "test-key"
    assert cfg.ssl_verify is False


def test_env_var_overrides(monkeypatch):
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "false")
    cfg = DepositConfig.load()
    assert cfg.api_key == "env-key"
    assert cfg.ssl_verify is False


def test_constructor_beats_env_var(monkeypatch):
    monkeypatch.setenv("ONEDEP_API_KEY", "env-key")
    cfg = DepositConfig.load(api_key="override-key")
    assert cfg.api_key == "override-key"


def test_invalid_bool_env_var_raises_config_error(monkeypatch):
    monkeypatch.setenv("ONEDEP_SSL_VERIFY", "yes")
    with pytest.raises(ConfigError):
        DepositConfig.load()


def test_schema_base_url_env_override(monkeypatch):
    monkeypatch.setenv("ONEDEP_SCHEMA_URL", "http://localhost:8080/schemas")
    cfg = DepositConfig.load()
    assert cfg.schema_base_url == "http://localhost:8080/schemas"
```

- [ ] **Run test to verify failures**

```bash
uv run pytest tests/test_config.py -v
```
Expected: failures on `schema_base_url`, `schema_cache_dir`, `session_dir`, and `ConfigError`.

- [ ] **Rewrite `config.py`**

```python
# src/nextdep_dsp/config.py
from __future__ import annotations

import os
from dataclasses import dataclass, field, fields
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from nextdep_dsp.exceptions import ConfigError


def _parse_bool(value: str, var_name: str) -> bool:
    lowered = value.lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise ConfigError(
        f"{var_name}={value!r} is not a valid boolean. Use 'true', 'false', '1', or '0'."
    )


_ENV_MAP: dict[str, tuple[str, object]] = {
    "ONEDEP_API_KEY": ("api_key", str),
    "ONEDEP_HOSTNAME": ("hostname", str),
    "ONEDEP_SSL_VERIFY": ("ssl_verify", lambda v: _parse_bool(v, "ONEDEP_SSL_VERIFY")),
    "ONEDEP_REDIRECT": ("redirect", lambda v: _parse_bool(v, "ONEDEP_REDIRECT")),
    "ONEDEP_SCHEMA_URL": ("schema_base_url", str),
}


@dataclass
class DepositConfig:
    api_key: str | None = None
    hostname: str = "https://deposit.wwpdb.org/deposition"
    ssl_verify: bool = True
    redirect: bool = True
    schema_base_url: str = "https://schemas.wwpdb.org/nextdep"
    schema_cache_dir: Path = field(
        default_factory=lambda: Path.home() / ".nextdep" / "schemas"
    )
    session_dir: Path = field(
        default_factory=lambda: Path.home() / ".nextdep" / "sessions"
    )

    @classmethod
    def load(cls, **overrides: object) -> DepositConfig:
        valid_fields = {f.name for f in fields(cls)}
        merged: dict[str, object] = {}

        # Layer 1: config file
        config_file = Path.home() / ".config" / "nextdep" / "config.toml"
        if config_file.exists():
            try:
                with open(config_file, "rb") as fp:
                    raw = tomllib.load(fp)
            except tomllib.TOMLDecodeError as exc:
                raise ConfigError(f"Failed to parse {config_file}: {exc}") from exc
            for key, value in raw.get("default", {}).items():
                if key in valid_fields:
                    if key == "hostname" and value == "":
                        continue
                    merged[key] = value

        # Layer 2: env vars
        for env_var, (field_name, coerce) in _ENV_MAP.items():
            raw_val = os.environ.get(env_var)
            if raw_val is not None:
                merged[field_name] = coerce(raw_val)  # type: ignore[operator]

        # Layer 3: caller overrides
        for key, value in overrides.items():
            if key in valid_fields:
                merged[key] = value

        return cls(**merged)  # type: ignore[arg-type]
```

- [ ] **Run test to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```
Expected: 6 passed.

- [ ] **Commit**

```bash
git add src/nextdep_dsp/config.py tests/test_config.py
git commit -m "feat: extend DepositConfig with schema_base_url, schema_cache_dir, session_dir"
```

---

## Task 3: Enums module

Move enums out of `deposition/enum.py` into a top-level `enums.py`. The old file stays until the cleanup task.

**Files:**
- Create: `src/nextdep_dsp/enums.py`
- Create: `tests/test_enums.py`

- [ ] **Write the failing test**

```python
# tests/test_enums.py
from nextdep_dsp.enums import Country, EMSubType, ExperimentType, FileType


def test_experiment_types_have_expected_values():
    assert ExperimentType.XRAY.value == "xray"
    assert ExperimentType.EM.value == "em"
    assert ExperimentType.NMR.value == "nmr"


def test_file_types_have_expected_values():
    assert FileType.MMCIF_COORD.value == "co-cif"
    assert FileType.EM_MAP.value == "vo-map"
    assert FileType.EM_HALF_MAP.value == "half-map"


def test_em_subtypes_have_expected_values():
    assert EMSubType.SPA.value == "single"
    assert EMSubType.HELICAL.value == "helical"


def test_country_usa():
    assert Country.USA.value == "United States"
```

- [ ] **Run test to verify it fails**

```bash
uv run pytest tests/test_enums.py -v
```
Expected: `ImportError` — `nextdep_dsp.enums` does not exist yet.

- [ ] **Create `src/nextdep_dsp/enums.py`**

Copy the four domain enums from `src/nextdep_dsp/deposition/enum.py`. `Status` stays in `deposition/enum.py` for now (it moves to `api/enums.py` in Plan 3).

```python
# src/nextdep_dsp/enums.py
"""Domain enums shared across all nextdep_dsp components."""
import enum


class ExperimentType(enum.Enum):
    XRAY = "xray"
    FIBER = "fiber"
    NEUTRON = "neutron"
    EM = "em"
    EC = "ec"
    NMR = "nmr"
    SSNMR = "ssnmr"


class EMSubType(enum.Enum):
    HELICAL = "helical"
    SPA = "single"
    SUBTOMOGRAM = "subtomogram"
    TOMOGRAPHY = "tomography"


class FileType(enum.Enum):
    LAYER = "layer-lines"
    FSC_XML = "fsc-xml"
    PDB_COORD = "co-pdb"
    MMCIF_COORD = "co-cif"
    EM_MAP = "vo-map"
    ENTRY_IMAGE = "img-emdb"
    EM_ADDITIONAL_MAP = "add-map"
    EM_MASK = "mask-map"
    EM_HALF_MAP = "half-map"
    CRYSTAL_STRUC_FACTORS = "xs-cif"
    CRYSTAL_MTZ = "xs-mtz"
    CRYSTAL_PARAMETER = "xa-par"
    CRYSTAL_TOPOLOGY = "xa-top"
    VIRUS_MATRIX = "xa-mat"
    NMR_ACS = "nm-shi"
    NMR_RESTRAINT_AMBER = "nm-res-amb"
    NMR_TOPOLOGY_AMBER = "nm-aux-amb"
    NMR_RESTRAINT_BIOSYM = "nm-res-bio"
    NMR_RESTRAINT_CHARMM = "nm-res-cha"
    NMR_RESTRAINT_CNS = "nm-res-cns"
    NMR_RESTRAINT_CYANA = "nm-res-cya"
    NMR_RESTRAINT_DYNAMO = "nm-res-dyn"
    NMR_RESTRAINT_PALES = "nm-res-dyn"
    NMR_RESTRAINT_TALOS = "nm-res-dyn"
    NMR_RESTRAINT_GROMACS = "nm-res-gro"
    NMR_TOPOLOGY_GROMACS = "nm-aux-gro"
    NMR_RESTRAINT_ISD = "nm-res-isd"
    NMR_RESTRAINT_ROSETTA = "nm-res-ros"
    NMR_RESTRAINT_SYBYL = "nm-res-syb"
    NMR_RESTRAINT_XPLOR = "nm-res-xpl"
    NMR_RESTRAINT_OTHER = "nm-res-oth"
    NMR_SPECTRAL_PEAK = "nm-pea-any"
    NMR_UNIFIED_NEF = "nm-uni-nef"
    NMR_UNIFIED_STAR = "nm-uni-str"


class Country(enum.Enum):
    # Copy every Country member verbatim from src/nextdep_dsp/deposition/enum.py.
    # All ~250 entries must be present. The list below is the full list.
    AFGHANISTAN = "Afghanistan"
    ALAND = "Aland Islands"
    ALBANIA = "Albania"
    ALGERIA = "Algeria"
    AMERICAN_SAMOA = "American Samoa"
    ANDORRA = "Andorra"
    ANGOLA = "Angola"
    ANGUILLA = "Anguilla"
    ANTARCTICA = "Antarctica"
    ANTIGUA_BARBUDA = "Antigua And Barbuda"
    ARGENTINA = "Argentina"
    ARMENIA = "Armenia"
    ARUBA = "Aruba"
    AUSTRALIA = "Australia"
    AUSTRIA = "Austria"
    AZERBAIJAN = "Azerbaijan"
    BAHAMAS = "Bahamas"
    BAHRAIN = "Bahrain"
    BANGLADESH = "Bangladesh"
    BARBADOS = "Barbados"
    BELARUS = "Belarus"
    BELGIUM = "Belgium"
    BELIZE = "Belize"
    BENIN = "Benin"
    BERMUDA = "Bermuda"
    BHUTAN = "Bhutan"
    BOLIVIA = "Bolivia, Plurinational State Of"
    BONAIRE = "Bonaire, Sint Eustatius And Saba"
    BOSNIA_HERZEGOVINA = "Bosnia And Herzegovina"
    BOTSWANA = "Botswana"
    BOUVET = "Bouvet Island"
    BRAZIL = "Brazil"
    BRUNEI = "Brunei Darussalam"
    BULGARIA = "Bulgaria"
    BURKINA_FASO = "Burkina Faso"
    BURUNDI = "Burundi"
    CAMBODIA = "Cambodia"
    CAMEROON = "Cameroon"
    CANADA = "Canada"
    CAPE_VERDE = "Cape Verde"
    CAR = "Central African Republic"
    CAYMAN = "Cayman Islands"
    CHAD = "Chad"
    CHILE = "Chile"
    CHINA = "China"
    CHRISTMAS = "Christmas Island"
    COCOS = "Cocos (Keeling) Islands"
    COLOMBIA = "Colombia"
    COMOROS = "Comoros"
    CONGO = "Congo"
    COOK = "Cook Islands"
    COSTA_RICA = "Costa Rica"
    CROATIA = "Croatia"
    CUBA = "Cuba"
    CURAAAO = "CuraAao"
    CYPRUS = "Cyprus"
    CZECH_REPUBLIC = "Czech Republic"
    DENMARK = "Denmark"
    DJIBOUTI = "Djibouti"
    DOMINICA = "Dominica"
    DOMINICAN_REPUBLIC = "Dominican Republic"
    DRC = "Congo, The Democratic Republic Of The"
    ECUADOR = "Ecuador"
    EGYPT = "Egypt"
    EL_SALVADOR = "El Salvador"
    EQUATORIAL_GUINEA = "Equatorial Guinea"
    ERITREA = "Eritrea"
    ESTONIA = "Estonia"
    ETHIOPIA = "Ethiopia"
    FAROE = "Faroe Islands"
    FIJI = "Fiji"
    FINLAND = "Finland"
    FRANCE = "France"
    FRENCH_GUIANA = "French Guiana"
    FRENCH_POLYNESIA = "French Polynesia"
    FRENCH_SOUTHERN = "French Southern Territories"
    GABON = "Gabon"
    GAMBIA = "Gambia"
    GEORGIA = "Georgia"
    GERMANY = "Germany"
    GHANA = "Ghana"
    GIBRALTAR = "Gibraltar"
    GREECE = "Greece"
    GREENLAND = "Greenland"
    GRENADA = "Grenada"
    GUADELOUPE = "Guadeloupe"
    GUAM = "Guam"
    GUATEMALA = "Guatemala"
    GUERNSEY = "Guernsey"
    GUINEA = "Guinea"
    GUINEA_BISSAU = "Guinea-Bissau"
    GUYANA = "Guyana"
    HAITI = "Haiti"
    HEARD_MCDONALD = "Heard Island And Mcdonald Islands"
    HONDURAS = "Honduras"
    HONG_KONG = "Hong Kong"
    HUNGARY = "Hungary"
    ICELAND = "Iceland"
    INDIA = "India"
    INDONESIA = "Indonesia"
    IRAN = "Iran, Islamic Republic Of"
    IRAQ = "Iraq"
    IRELAND = "Ireland"
    ISLE_OF_MAN = "Isle Of Man"
    ISRAEL = "Israel"
    ITALY = "Italy"
    IVORY_COAST = "CAte D'Ivoire"
    JAMAICA = "Jamaica"
    JAPAN = "Japan"
    JERSEY = "Jersey"
    JORDAN = "Jordan"
    KAZAKHSTAN = "Kazakhstan"
    KENYA = "Kenya"
    KIRIBATI = "Kiribati"
    KUWAIT = "Kuwait"
    KYRGYZSTAN = "Kyrgyzstan"
    LAOS = "Lao People'S Democratic Republic"
    LATVIA = "Latvia"
    LEBANON = "Lebanon"
    LESOTHO = "Lesotho"
    LIBERIA = "Liberia"
    LIBYA = "Libya"
    LIECHTENSTEIN = "Liechtenstein"
    LITHUANIA = "Lithuania"
    LUXEMBOURG = "Luxembourg"
    MACAO = "Macao"
    MACEDONIA = "Macedonia"
    MADAGASCAR = "Madagascar"
    MALAWI = "Malawi"
    MALAYSIA = "Malaysia"
    MALDIVES = "Maldives"
    MALI = "Mali"
    MALTA = "Malta"
    MALVINAS = "Falkland Islands (Malvinas)"
    MARSHALL = "Marshall Islands"
    MARTINIQUE = "Martinique"
    MAURITANIA = "Mauritania"
    MAURITIUS = "Mauritius"
    MAYOTTE = "Mayotte"
    MEXICO = "Mexico"
    MICRONESIA = "Micronesia, Federated States Of"
    MOLDOVA = "Moldova, Republic Of"
    MONACO = "Monaco"
    MONGOLIA = "Mongolia"
    MONTENEGRO = "Montenegro"
    MONTSERRAT = "Montserrat"
    MOROCCO = "Morocco"
    MOZAMBIQUE = "Mozambique"
    MYANMAR = "Myanmar"
    NAMIBIA = "Namibia"
    NAURU = "Nauru"
    NEPAL = "Nepal"
    NETHERLANDS = "Netherlands"
    NEW_CALEDONIA = "New Caledonia"
    NEW_ZEALAND = "New Zealand"
    NICARAGUA = "Nicaragua"
    NIGER = "Niger"
    NIGERIA = "Nigeria"
    NIUE = "Niue"
    NORFOLK = "Norfolk Island"
    NORTH_KOREA = "Korea, Democratic People'S Republic Of"
    NORTHERN_MARIANA = "Northern Mariana Islands"
    NORWAY = "Norway"
    OMAN = "Oman"
    PAKISTAN = "Pakistan"
    PALAU = "Palau"
    PALESTINIAN = "Palestinian Territory"
    PANAMA = "Panama"
    PAPUA_NEW_GUINEA = "Papua New Guinea"
    PARAGUAY = "Paraguay"
    PERU = "Peru"
    PHILIPPINES = "Philippines"
    PITCAIRN = "Pitcairn"
    POLAND = "Poland"
    PORTUGAL = "Portugal"
    PUERTO_RICO = "Puerto Rico"
    QATAR = "Qatar"
    RAUNION = "RAunion"
    ROMANIA = "Romania"
    RUSSIA = "Russian Federation"
    RWANDA = "Rwanda"
    SAINT_BARTHALEMY = "Saint BarthAlemy"
    SAINT_HELENA = "Saint Helena, Ascension And Tristan Da Cunha"
    SAINT_KITTS = "Saint Kitts And Nevis"
    SAINT_LUCIA = "Saint Lucia"
    SAINT_MARTIN = "Saint Martin (French Part)"
    SAINT_PIERRE = "Saint Pierre And Miquelon"
    SAINT_VINCENT = "Saint Vincent And The Grenadines"
    SAMOA = "Samoa"
    SAN_MARINO = "San Marino"
    SAO_TOME_PRINCIPE = "Sao Tome And Principe"
    SAUDI_ARABIA = "Saudi Arabia"
    SENEGAL = "Senegal"
    SERBIA = "Serbia"
    SEYCHELLES = "Seychelles"
    SIERRA_LEONE = "Sierra Leone"
    SINGAPORE = "Singapore"
    SINT_MAARTEN = "Sint Maarten (Dutch Part)"
    SLOVAKIA = "Slovakia"
    SLOVENIA = "Slovenia"
    SOLOMON = "Solomon Islands"
    SOMALIA = "Somalia"
    SOUTH_AFRICA = "South Africa"
    SOUTH_GEORGIA = "South Georgia And The South Sandwich Islands"
    SOUTH_KOREA = "Korea, Republic Of"
    SOUTH_SUDAN = "South Sudan"
    SPAIN = "Spain"
    SRI_LANKA = "Sri Lanka"
    SUDAN = "Sudan"
    SURINAME = "Suriname"
    SVALBARD = "Svalbard And Jan Mayen"
    SWAZILAND = "Swaziland"
    SWEDEN = "Sweden"
    SWITZERLAND = "Switzerland"
    SYRIA = "Syrian Arab Republic"
    TAIWAN = "Taiwan"
    TAJIKISTAN = "Tajikistan"
    TANZANIA = "Tanzania, United Republic Of"
    THAILAND = "Thailand"
    TIMOR_LESTE = "Timor-Leste"
    TOGO = "Togo"
    TOKELAU = "Tokelau"
    TONGA = "Tonga"
    TRINIDAD_TOBAGO = "Trinidad And Tobago"
    TUNISIA = "Tunisia"
    TURKEY = "Turkey"
    TURKMENISTAN = "Turkmenistan"
    TURKS_CAICOS = "Turks And Caicos Islands"
    TUVALU = "Tuvalu"
    UAE = "United Arab Emirates"
    UGANDA = "Uganda"
    UK = "United Kingdom"
    UKRAINE = "Ukraine"
    URUGUAY = "Uruguay"
    USA = "United States"
    USA_ISLANDS = "United States Minor Outlying Islands"
    UZBEKISTAN = "Uzbekistan"
    VANUATU = "Vanuatu"
    VATICAN = "Holy See (Vatican City State)"
    VENEZUELA = "Venezuela, Bolivarian Republic Of"
    VIETNAM = "Viet Nam"
    VIRGIN_BRITISH = "Virgin Islands, British"
    VIRGIN_USA = "Virgin Islands, U.S."
    WALLIS_FUTUNA = "Wallis And Futuna"
    WESTERN_SAHARA = "Western Sahara"
    YEMEN = "Yemen"
    ZAMBIA = "Zambia"
    ZIMBABWE = "Zimbabwe"
```

- [ ] **Run test to verify it passes**

```bash
uv run pytest tests/test_enums.py -v
```
Expected: 4 passed.

- [ ] **Commit**

```bash
git add src/nextdep_dsp/enums.py tests/test_enums.py
git commit -m "feat: add top-level enums module (moved from deposition/enum.py)"
```

---

## Task 4: Session models

Remove `db_path` (was SQLite-specific); import enums from `nextdep_dsp.enums`.

**Files:**
- Modify: `src/nextdep_dsp/session/models.py`
- Create: `tests/session/__init__.py`
- Create: `tests/session/test_models.py`

- [ ] **Write the failing test**

```python
# tests/session/test_models.py
from datetime import datetime
from nextdep_dsp.session.models import LocalFile, LocalSession
from nextdep_dsp.enums import Country, ExperimentType, FileType


def test_local_session_fields():
    session = LocalSession(
        session_id="abc-123",
        email="user@lab.org",
        users=["0000-0002-5109-8728"],
        country=Country.USA,
        experiment_type=ExperimentType.XRAY,
        created_at=datetime.now(),
    )
    assert session.session_id == "abc-123"
    assert session.remote_dep_id is None
    assert session.em_subtype is None
    assert session.coordinates is None


def test_local_session_has_no_db_path():
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(LocalSession)}
    assert "db_path" not in field_names


def test_local_file_fields():
    f = LocalFile(
        file_id="f1",
        session_id="abc-123",
        file_path="/tmp/model.cif",
        file_type=FileType.MMCIF_COORD,
    )
    assert f.file_id == "f1"
    assert f.voxel is None
    assert f.md5 is None
```

- [ ] **Run test to verify it fails**

```bash
uv run pytest tests/session/test_models.py -v
```
Expected: `ImportError` or failure on `db_path` assertion if the old model is still present.

- [ ] **Rewrite `src/nextdep_dsp/session/models.py`**

```python
# src/nextdep_dsp/session/models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from nextdep_dsp.enums import Country, ExperimentType, FileType


@dataclass
class LocalFile:
    file_id: str
    session_id: str
    file_path: str
    file_type: FileType
    voxel: dict | None = None
    md5: str | None = None
    file_mtime: datetime | None = None


@dataclass
class LocalSession:
    session_id: str
    email: str
    users: list[str]
    country: Country
    experiment_type: ExperimentType | None
    created_at: datetime
    remote_dep_id: str | None = None
    em_subtype: str | None = None
    coordinates: bool | None = None
```

- [ ] **Run test to verify it passes**

```bash
uv run pytest tests/session/test_models.py -v
```
Expected: 3 passed.

- [ ] **Commit**

```bash
git add src/nextdep_dsp/session/models.py tests/session/
git commit -m "feat: remove db_path from LocalSession; import enums from nextdep_dsp.enums"
```

---

## Task 5: SessionStore Protocol

**Files:**
- Create: `src/nextdep_dsp/session/types.py`

No separate test file — the Protocol is verified structurally by the `JsonSessionStore` tests in Task 6.

- [ ] **Create `src/nextdep_dsp/session/types.py`**

```python
# src/nextdep_dsp/session/types.py
from __future__ import annotations

from typing import Protocol

from nextdep_dsp.enums import ExperimentType
from nextdep_dsp.session.models import LocalFile, LocalSession


class SessionStore(Protocol):
    def create_session(self, session: LocalSession) -> None: ...
    def get_session(self) -> LocalSession: ...
    def update_experiment_type(self, experiment_type: ExperimentType) -> None: ...
    def update_em_params(self, em_subtype: str | None, coordinates: bool | None) -> None: ...
    def set_remote_dep_id(self, dep_id: str) -> None: ...
    def add_file(self, file: LocalFile) -> None: ...
    def remove_file(self, file_id: str) -> None: ...
    def get_file(self, file_id: str) -> LocalFile: ...
    def get_all_files(self) -> list[LocalFile]: ...
    def set_voxel_values(
        self,
        file_id: str,
        spacing_x: float,
        spacing_y: float,
        spacing_z: float,
        contour: float,
    ) -> None: ...
    def close(self) -> None: ...
```

- [ ] **Verify import works**

```bash
uv run python -c "from nextdep_dsp.session.types import SessionStore; print('ok')"
```
Expected: `ok`

- [ ] **Commit**

```bash
git add src/nextdep_dsp/session/types.py
git commit -m "feat: add SessionStore Protocol"
```

---

## Task 6: JsonSessionStore

Refactor from `session/store.py`. Key change: import enums from `nextdep_dsp.enums`.

**Files:**
- Create: `src/nextdep_dsp/session/json_store.py`
- Create: `tests/session/test_json_store.py`

- [ ] **Write the failing tests**

```python
# tests/session/test_json_store.py
import pytest
from datetime import datetime, timezone
from pathlib import Path
from nextdep_dsp.session.json_store import JsonSessionStore
from nextdep_dsp.session.models import LocalFile, LocalSession
from nextdep_dsp.enums import Country, ExperimentType, FileType


@pytest.fixture
def store(tmp_path: Path) -> JsonSessionStore:
    return JsonSessionStore("test-session", base_dir=tmp_path)


@pytest.fixture
def session() -> LocalSession:
    return LocalSession(
        session_id="test-session",
        email="user@lab.org",
        users=["0000-0002-5109-8728"],
        country=Country.USA,
        experiment_type=ExperimentType.XRAY,
        created_at=datetime.now(),
    )


def test_create_and_get_session(store: JsonSessionStore, session: LocalSession):
    store.create_session(session)
    loaded = store.get_session()
    assert loaded.session_id == session.session_id
    assert loaded.email == session.email
    assert loaded.country == Country.USA
    assert loaded.experiment_type == ExperimentType.XRAY


def test_get_session_raises_when_no_session(store: JsonSessionStore):
    with pytest.raises(KeyError):
        store.get_session()


def test_add_and_get_file(store: JsonSessionStore, session: LocalSession):
    store.create_session(session)
    f = LocalFile(
        file_id="f1",
        session_id="test-session",
        file_path="/tmp/model.cif",
        file_type=FileType.MMCIF_COORD,
        md5="abc123",
        file_mtime=datetime.now(tz=timezone.utc),
    )
    store.add_file(f)
    loaded = store.get_file("f1")
    assert loaded.file_id == "f1"
    assert loaded.file_type == FileType.MMCIF_COORD


def test_remove_file(store: JsonSessionStore, session: LocalSession):
    store.create_session(session)
    f = LocalFile(
        file_id="f1",
        session_id="test-session",
        file_path="/tmp/model.cif",
        file_type=FileType.MMCIF_COORD,
        file_mtime=datetime.now(tz=timezone.utc),
    )
    store.add_file(f)
    store.remove_file("f1")
    with pytest.raises(KeyError):
        store.get_file("f1")


def test_set_voxel_values(store: JsonSessionStore, session: LocalSession):
    store.create_session(session)
    f = LocalFile(
        file_id="f1",
        session_id="test-session",
        file_path="/tmp/map.map",
        file_type=FileType.EM_MAP,
        file_mtime=datetime.now(tz=timezone.utc),
    )
    store.add_file(f)
    store.set_voxel_values("f1", 1.08, 1.08, 1.08, 0.01)
    loaded = store.get_file("f1")
    assert loaded.voxel == {
        "spacing_x": 1.08, "spacing_y": 1.08, "spacing_z": 1.08, "contour": 0.01
    }


def test_update_experiment_type(store: JsonSessionStore, session: LocalSession):
    store.create_session(session)
    store.update_experiment_type(ExperimentType.EM)
    loaded = store.get_session()
    assert loaded.experiment_type == ExperimentType.EM


def test_set_remote_dep_id(store: JsonSessionStore, session: LocalSession):
    store.create_session(session)
    store.set_remote_dep_id("D_8000000001")
    loaded = store.get_session()
    assert loaded.remote_dep_id == "D_8000000001"


def test_persists_across_store_instances(tmp_path: Path, session: LocalSession):
    store1 = JsonSessionStore("test-session", base_dir=tmp_path)
    store1.create_session(session)
    store1.close()

    store2 = JsonSessionStore("test-session", base_dir=tmp_path)
    loaded = store2.get_session()
    assert loaded.email == session.email
```

- [ ] **Run test to verify failures**

```bash
uv run pytest tests/session/test_json_store.py -v
```
Expected: `ImportError` — `json_store` does not exist yet.

- [ ] **Create `src/nextdep_dsp/session/json_store.py`**

```python
# src/nextdep_dsp/session/json_store.py
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from nextdep_dsp.enums import Country, ExperimentType, FileType
from nextdep_dsp.session.models import LocalFile, LocalSession


class JsonSessionStore:
    def __init__(self, session_id: str, base_dir: Path | None = None) -> None:
        _base = base_dir or (Path.home() / ".nextdep" / "sessions")
        self._session_id = session_id
        self._json_path = _base / session_id / "session.json"
        self._json_path.parent.mkdir(parents=True, exist_ok=True)

        tmp = self._json_path.with_suffix(".json.tmp")
        if tmp.exists():
            tmp.unlink()

        if self._json_path.exists():
            with self._json_path.open() as f:
                self._data: dict = json.load(f)
        else:
            self._data = {"session": None, "files": {}}
            self._save()

    @property
    def json_path(self) -> Path:
        return self._json_path

    def _save(self) -> None:
        tmp = self._json_path.with_suffix(".json.tmp")
        try:
            with tmp.open("w") as f:
                json.dump(self._data, f, indent=2)
            os.replace(tmp, self._json_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    def _require_session(self) -> dict:
        s = self._data["session"]
        if s is None:
            raise RuntimeError(
                f"No session initialised for {self._session_id!r}. "
                "Call create_session() first."
            )
        return s

    def create_session(self, session: LocalSession) -> None:
        self._data["session"] = {
            "session_id": session.session_id,
            "email": session.email,
            "users": session.users,
            "country": session.country.value,
            "experiment_type": session.experiment_type.value if session.experiment_type else None,
            "created_at": session.created_at.isoformat(),
            "remote_dep_id": session.remote_dep_id,
            "em_subtype": session.em_subtype,
            "coordinates": session.coordinates,
        }
        self._save()

    def get_session(self) -> LocalSession:
        s = self._data["session"]
        if s is None:
            raise KeyError(f"No session found for {self._session_id!r}")
        return LocalSession(
            session_id=s["session_id"],
            email=s["email"],
            users=s["users"],
            country=Country(s["country"]),
            experiment_type=ExperimentType(s["experiment_type"]) if s["experiment_type"] else None,
            created_at=datetime.fromisoformat(s["created_at"]),
            remote_dep_id=s.get("remote_dep_id"),
            em_subtype=s.get("em_subtype"),
            coordinates=s.get("coordinates"),
        )

    def update_experiment_type(self, experiment_type: ExperimentType) -> None:
        s = self._require_session()
        s["experiment_type"] = experiment_type.value
        self._save()

    def update_em_params(self, em_subtype: str | None, coordinates: bool | None) -> None:
        s = self._require_session()
        s["em_subtype"] = em_subtype
        s["coordinates"] = coordinates
        self._save()

    def set_remote_dep_id(self, dep_id: str) -> None:
        s = self._require_session()
        s["remote_dep_id"] = dep_id
        self._save()

    def add_file(self, file: LocalFile) -> None:
        if file.session_id != self._session_id:
            raise ValueError(
                f"File session_id {file.session_id!r} does not match "
                f"store session_id {self._session_id!r}"
            )
        if file.file_mtime is not None and file.file_mtime.tzinfo is None:
            raise ValueError("file_mtime must be timezone-aware")
        self._data["files"][file.file_id] = {
            "file_id": file.file_id,
            "session_id": file.session_id,
            "file_path": file.file_path,
            "file_type": file.file_type.value,
            "voxel": file.voxel,
            "md5": file.md5,
            "file_mtime": file.file_mtime.isoformat() if file.file_mtime else None,
        }
        self._save()

    def set_voxel_values(
        self,
        file_id: str,
        spacing_x: float,
        spacing_y: float,
        spacing_z: float,
        contour: float,
    ) -> None:
        if file_id not in self._data["files"]:
            raise KeyError(f"File {file_id!r} not found in session")
        self._data["files"][file_id]["voxel"] = {
            "spacing_x": spacing_x,
            "spacing_y": spacing_y,
            "spacing_z": spacing_z,
            "contour": contour,
        }
        self._save()

    def remove_file(self, file_id: str) -> None:
        if file_id not in self._data["files"]:
            raise KeyError(f"File {file_id!r} not found in session")
        del self._data["files"][file_id]
        self._save()

    def get_file(self, file_id: str) -> LocalFile:
        entry = self._data["files"].get(file_id)
        if entry is None:
            raise KeyError(f"File {file_id!r} not found in session")
        return LocalFile(
            file_id=entry["file_id"],
            session_id=entry["session_id"],
            file_path=entry["file_path"],
            file_type=FileType(entry["file_type"]),
            voxel=entry.get("voxel"),
            md5=entry.get("md5"),
            file_mtime=datetime.fromisoformat(entry["file_mtime"])
            if entry.get("file_mtime")
            else None,
        )

    def get_all_files(self) -> list[LocalFile]:
        return [
            LocalFile(
                file_id=e["file_id"],
                session_id=e["session_id"],
                file_path=e["file_path"],
                file_type=FileType(e["file_type"]),
                voxel=e.get("voxel"),
                md5=e.get("md5"),
                file_mtime=datetime.fromisoformat(e["file_mtime"])
                if e.get("file_mtime")
                else None,
            )
            for e in self._data["files"].values()
        ]

    def close(self) -> None:
        pass

    def __enter__(self) -> JsonSessionStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
```

- [ ] **Run test to verify it passes**

```bash
uv run pytest tests/session/test_json_store.py -v
```
Expected: 8 passed.

- [ ] **Commit**

```bash
git add src/nextdep_dsp/session/json_store.py src/nextdep_dsp/session/types.py \
        tests/session/test_json_store.py
git commit -m "feat: add JsonSessionStore (replaces session/store.py)"
```

---

## Task 7: CheckReport (cleanup)

The existing `checks/report.py` is already well-designed. Ensure there are no stray imports from `deposition/` and that `CifLocation` is exported.

**Files:**
- Modify: `src/nextdep_dsp/checks/report.py` (if needed)
- Create: `tests/checks/__init__.py`
- Create: `tests/checks/test_report.py`

- [ ] **Write tests**

```python
# tests/checks/test_report.py
from nextdep_dsp.checks.report import CheckIssue, CheckReport, CheckSeverity, CifLocation


def test_empty_report_is_ok():
    report = CheckReport(source="test")
    assert report.ok is True
    assert report.errors() == []
    assert report.warnings() == []


def test_fatal_issue_makes_report_not_ok():
    issue = CheckIssue(
        severity=CheckSeverity.FATAL,
        code="REQ_FILES_MISSING",
        message="Missing coordinate file",
    )
    report = CheckReport(source="test", issues=[issue])
    assert report.ok is False
    assert len(report.errors()) == 1


def test_warning_does_not_affect_ok():
    issue = CheckIssue(
        severity=CheckSeverity.WARNING,
        code="EXPERIMENT_TYPE_UNSET",
        message="No experiment type set",
    )
    report = CheckReport(source="test", issues=[issue])
    assert report.ok is True
    assert len(report.warnings()) == 1


def test_cif_location_defaults():
    loc = CifLocation()
    assert loc.data_block is None
    assert loc.category is None


def test_check_severity_coercion():
    issue = CheckIssue(severity="fatal", code="X", message="Y")
    assert issue.severity == CheckSeverity.FATAL
```

- [ ] **Run tests**

```bash
uv run pytest tests/checks/test_report.py -v
```
Expected: 5 passed. If any fail, fix the imports in `checks/report.py`.

- [ ] **Ensure `checks/report.py` has no imports from `deposition/`**

Open `src/nextdep_dsp/checks/report.py` and verify there are no imports from `nextdep_dsp.deposition`. If imports exist, remove them.

- [ ] **Commit**

```bash
git add src/nextdep_dsp/checks/report.py tests/checks/
git commit -m "test: add CheckReport unit tests"
```

---

## Task 8: Add pytest-httpserver and SchemaProvider Protocol

**Files:**
- Modify: `pyproject.toml`
- Create: `src/nextdep_dsp/schemas/__init__.py`
- Create: `src/nextdep_dsp/schemas/types.py`

- [ ] **Add `pytest-httpserver` to dev dependencies**

Edit `pyproject.toml` — update the `test` dependency group:

```toml
[dependency-groups]
test = [
    "coverage",
    "pytest",
    "pytest-httpserver",
]
```

- [ ] **Install**

```bash
uv sync
```
Expected: `pytest-httpserver` installed with no errors.

- [ ] **Create `src/nextdep_dsp/schemas/__init__.py`**

```python
# src/nextdep_dsp/schemas/__init__.py
from nextdep_dsp.schemas.types import SchemaProvider

__all__ = ["SchemaProvider"]
```

- [ ] **Create `src/nextdep_dsp/schemas/types.py`**

```python
# src/nextdep_dsp/schemas/types.py
from __future__ import annotations

from typing import Protocol


class SchemaProvider(Protocol):
    def get_schema(self, schema_name: str) -> dict: ...
```

- [ ] **Verify import**

```bash
uv run python -c "from nextdep_dsp.schemas import SchemaProvider; print('ok')"
```
Expected: `ok`

- [ ] **Commit**

```bash
git add pyproject.toml src/nextdep_dsp/schemas/
git commit -m "feat: add SchemaProvider Protocol and pytest-httpserver dev dep"
```

---

## Task 9: RemoteSchemaProvider

**Files:**
- Create: `src/nextdep_dsp/schemas/remote.py`
- Create: `tests/schemas/__init__.py`
- Create: `tests/schemas/test_remote.py`

- [ ] **Write the failing tests**

```python
# tests/schemas/test_remote.py
import json
import pytest
from pathlib import Path
from nextdep_dsp.schemas.remote import RemoteSchemaProvider
from nextdep_dsp.exceptions import SchemaError

SAMPLE_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}


def test_fetches_schema_from_server(httpserver, tmp_path: Path):
    httpserver.expect_request("/required_files.json").respond_with_json(SAMPLE_SCHEMA)
    provider = RemoteSchemaProvider(httpserver.url_for("/"), cache_dir=tmp_path)
    schema = provider.get_schema("required_files")
    assert schema == SAMPLE_SCHEMA


def test_caches_schema_to_disk(httpserver, tmp_path: Path):
    httpserver.expect_request("/required_files.json").respond_with_json(SAMPLE_SCHEMA)
    provider = RemoteSchemaProvider(httpserver.url_for("/"), cache_dir=tmp_path)
    provider.get_schema("required_files")
    cache_file = tmp_path / "required_files.json"
    assert cache_file.exists()
    assert json.loads(cache_file.read_text()) == SAMPLE_SCHEMA


def test_serves_from_cache_without_network(tmp_path: Path):
    cache_file = tmp_path / "required_files.json"
    cache_file.write_text(json.dumps(SAMPLE_SCHEMA))
    provider = RemoteSchemaProvider("http://unreachable.invalid/", cache_dir=tmp_path)
    schema = provider.get_schema("required_files")
    assert schema == SAMPLE_SCHEMA


def test_raises_schema_error_on_network_failure(tmp_path: Path):
    provider = RemoteSchemaProvider("http://unreachable.invalid/", cache_dir=tmp_path)
    with pytest.raises(SchemaError, match="required_files"):
        provider.get_schema("required_files")


def test_raises_schema_error_on_404(httpserver, tmp_path: Path):
    httpserver.expect_request("/missing.json").respond_with_data("Not Found", status=404)
    provider = RemoteSchemaProvider(httpserver.url_for("/"), cache_dir=tmp_path)
    with pytest.raises(SchemaError):
        provider.get_schema("missing")
```

- [ ] **Run test to verify failures**

```bash
uv run pytest tests/schemas/test_remote.py -v
```
Expected: `ImportError` — `remote` module does not exist yet.

- [ ] **Create `src/nextdep_dsp/schemas/remote.py`**

```python
# src/nextdep_dsp/schemas/remote.py
from __future__ import annotations

import json
from pathlib import Path

import requests

from nextdep_dsp.exceptions import SchemaError


class RemoteSchemaProvider:
    def __init__(self, base_url: str, cache_dir: Path) -> None:
        self._base_url = base_url.rstrip("/")
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_schema(self, schema_name: str) -> dict:
        cache_path = self._cache_dir / f"{schema_name}.json"
        if cache_path.exists():
            with cache_path.open() as f:
                return json.load(f)
        return self._fetch_and_cache(schema_name, cache_path)

    def _fetch_and_cache(self, schema_name: str, cache_path: Path) -> dict:
        url = f"{self._base_url}/{schema_name}.json"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise SchemaError(
                f"Failed to fetch schema '{schema_name}' from {url}: {exc}"
            ) from exc
        try:
            schema = response.json()
        except ValueError as exc:
            raise SchemaError(
                f"Invalid JSON in schema '{schema_name}' from {url}"
            ) from exc
        with cache_path.open("w") as f:
            json.dump(schema, f)
        return schema
```

- [ ] **Run test to verify it passes**

```bash
uv run pytest tests/schemas/test_remote.py -v
```
Expected: 5 passed.

- [ ] **Commit**

```bash
git add src/nextdep_dsp/schemas/remote.py tests/schemas/
git commit -m "feat: add RemoteSchemaProvider with disk cache"
```

---

## Task 10: CheckRunner — required files check

**Files:**
- Create: `src/nextdep_dsp/checks/runner.py`
- Create: `tests/fixtures/files.json`
- Create: `tests/checks/test_runner.py`

- [ ] **Copy `files.json` to the test fixtures directory**

This schema file will be deleted with `validation/` in Task 13. Copy it to a stable test location first:

```bash
mkdir -p tests/fixtures
cp src/nextdep_dsp/validation/schema/files.json tests/fixtures/files.json
git add tests/fixtures/files.json
git commit -m "test: copy required-files schema to tests/fixtures for use as test data"
```

- [ ] **Write the failing tests**

```python
# tests/checks/test_runner.py
import json
import pytest
from pathlib import Path
from nextdep_dsp.checks.runner import CheckRunner
from nextdep_dsp.checks.report import CheckReport, CheckSeverity
from nextdep_dsp.enums import ExperimentType, FileType
from nextdep_dsp.exceptions import SchemaError
from nextdep_dsp.session.models import LocalFile


# --- Stub SchemaProvider (satisfies SchemaProvider Protocol structurally) ---

class StubSchemaProvider:
    def __init__(self, schemas: dict[str, dict]) -> None:
        self._schemas = schemas

    def get_schema(self, schema_name: str) -> dict:
        if schema_name not in self._schemas:
            raise SchemaError(f"Schema '{schema_name}' not available")
        return self._schemas[schema_name]


def _load_files_schema() -> dict:
    schema_path = Path(__file__).parent.parent / "fixtures" / "files.json"
    with schema_path.open() as f:
        return json.load(f)


@pytest.fixture
def runner_with_files_schema() -> CheckRunner:
    provider = StubSchemaProvider({"required_files": _load_files_schema()})
    return CheckRunner(schema_provider=provider)


@pytest.fixture
def runner_no_schema() -> CheckRunner:
    provider = StubSchemaProvider({})
    return CheckRunner(schema_provider=provider)


def _make_file(file_type: FileType) -> LocalFile:
    return LocalFile(
        file_id="f1",
        session_id="s1",
        file_path="/tmp/file",
        file_type=file_type,
    )


# --- check_required_files ---

def test_returns_warning_when_experiment_type_unset(runner_with_files_schema: CheckRunner):
    report = runner_with_files_schema.check_required_files([], None)
    assert report.ok is True
    assert any(i.code == "EXPERIMENT_TYPE_UNSET" for i in report.warnings())


def test_returns_warning_when_schema_unavailable(runner_no_schema: CheckRunner):
    report = runner_no_schema.check_required_files([], ExperimentType.XRAY)
    assert report.ok is True
    assert any(i.code == "SCHEMA_UNAVAILABLE" for i in report.warnings())


def test_xray_passes_with_correct_files(runner_with_files_schema: CheckRunner):
    files = [
        LocalFile("f1", "s1", "/tmp/model.cif", FileType.MMCIF_COORD),
        LocalFile("f2", "s1", "/tmp/data.cif", FileType.CRYSTAL_STRUC_FACTORS),
    ]
    report = runner_with_files_schema.check_required_files(files, ExperimentType.XRAY)
    assert report.ok is True


def test_xray_fails_without_coordinate_file(runner_with_files_schema: CheckRunner):
    files = [LocalFile("f1", "s1", "/tmp/data.cif", FileType.CRYSTAL_STRUC_FACTORS)]
    report = runner_with_files_schema.check_required_files(files, ExperimentType.XRAY)
    assert report.ok is False
    assert any("coordinate" in i.message.lower() for i in report.errors())


def test_xray_fails_without_structure_factors(runner_with_files_schema: CheckRunner):
    files = [LocalFile("f1", "s1", "/tmp/model.cif", FileType.MMCIF_COORD)]
    report = runner_with_files_schema.check_required_files(files, ExperimentType.XRAY)
    assert report.ok is False
    assert any("structure factor" in i.message.lower() for i in report.errors())


def test_em_spa_passes_with_correct_files(runner_with_files_schema: CheckRunner):
    files = [
        LocalFile("f1", "s1", "/tmp/model.cif", FileType.MMCIF_COORD),
        LocalFile("f2", "s1", "/tmp/map.map", FileType.EM_MAP),
        LocalFile("f3", "s1", "/tmp/img.png", FileType.ENTRY_IMAGE),
        LocalFile("f4", "s1", "/tmp/h1.map", FileType.EM_HALF_MAP),
        LocalFile("f5", "s1", "/tmp/h2.map", FileType.EM_HALF_MAP),
    ]
    report = runner_with_files_schema.check_required_files(
        files, ExperimentType.EM, em_subtype="single"
    )
    assert report.ok is True


def test_em_fails_without_subtype(runner_with_files_schema: CheckRunner):
    files = [LocalFile("f1", "s1", "/tmp/map.map", FileType.EM_MAP)]
    report = runner_with_files_schema.check_required_files(files, ExperimentType.EM)
    assert report.ok is False
```

- [ ] **Run tests to verify failures**

```bash
uv run pytest tests/checks/test_runner.py -v
```
Expected: `ImportError` — `runner` module does not exist yet.

- [ ] **Create `src/nextdep_dsp/checks/runner.py`**

```python
# src/nextdep_dsp/checks/runner.py
from __future__ import annotations

from collections import Counter

import jsonschema

from nextdep_dsp.checks.report import CheckIssue, CheckReport, CheckSeverity
from nextdep_dsp.enums import ExperimentType, FileType
from nextdep_dsp.exceptions import SchemaError
from nextdep_dsp.schemas.types import SchemaProvider
from nextdep_dsp.session.models import LocalFile


_COORD_TYPES = {"co-pdb", "co-cif"}
_SF_TYPES = {"xs-cif", "xs-mtz"}
_EC_DATA_TYPES = {"vo-map", "xs-cif", "xs-mtz"}
_NMR_UNIFIED_TYPES = {"nm-uni-nef", "nm-uni-str"}
_NMR_RESTRAINT_TYPES = {
    "nm-res-amb", "nm-res-bio", "nm-res-cha", "nm-res-cns", "nm-res-cya",
    "nm-res-dyn", "nm-res-gro", "nm-res-isd", "nm-res-ros", "nm-res-syb",
    "nm-res-xpl", "nm-res-oth",
}
_HALF_MAP_SUBTYPES = {"single", "helical", "subtomogram"}


def _human_readable_messages(
    filetypes: list[str],
    experiment_type: ExperimentType,
    em_subtype: str | None,
) -> list[str]:
    counts = Counter(filetypes)
    present = set(filetypes)
    messages: list[str] = []

    if experiment_type != ExperimentType.EM and not present.intersection(_COORD_TYPES):
        messages.append("Missing required coordinate file: expected one of co-pdb or co-cif")

    if experiment_type in {ExperimentType.XRAY, ExperimentType.NEUTRON}:
        if not present.intersection(_SF_TYPES):
            messages.append(
                "Missing required structure factors file: expected one of xs-cif or xs-mtz"
            )

    if experiment_type == ExperimentType.FIBER and "layer-lines" not in present:
        messages.append("Missing required fiber diffraction file: expected layer-lines")

    if experiment_type == ExperimentType.EM:
        if not em_subtype:
            messages.append("Missing required EM subtype")
        if "img-emdb" not in present:
            messages.append("Missing required EM image file: expected img-emdb")
        if "vo-map" not in present:
            messages.append("Missing required EM map file: expected vo-map")
        if em_subtype in _HALF_MAP_SUBTYPES and counts["half-map"] < 2:
            messages.append("Missing required half-map files: expected 2 half-map files")

    if experiment_type == ExperimentType.EC and not present.intersection(_EC_DATA_TYPES):
        messages.append(
            "Missing required EC data file: expected at least one of vo-map, xs-cif, or xs-mtz"
        )

    if experiment_type in {ExperimentType.NMR, ExperimentType.SSNMR}:
        if not present.intersection(_NMR_UNIFIED_TYPES):
            if "nm-shi" not in present:
                messages.append("Missing required chemical shifts file: expected nm-shi")
            if not present.intersection(_NMR_RESTRAINT_TYPES):
                messages.append(
                    "Missing required NMR restraints file: expected at least one nm-res-* file"
                )

    return messages


class CheckRunner:
    def __init__(self, schema_provider: SchemaProvider) -> None:
        self._schema_provider = schema_provider

    def check_required_files(
        self,
        files: list[LocalFile],
        experiment_type: ExperimentType | None,
        em_subtype: str | None = None,
    ) -> CheckReport:
        if experiment_type is None:
            return CheckReport(
                source="session",
                issues=[
                    CheckIssue(
                        severity=CheckSeverity.WARNING,
                        code="EXPERIMENT_TYPE_UNSET",
                        message="Experiment type not set — required-file check skipped",
                    )
                ],
            )

        try:
            schema = self._schema_provider.get_schema("required_files")
        except SchemaError as exc:
            return CheckReport(
                source="session",
                issues=[
                    CheckIssue(
                        severity=CheckSeverity.WARNING,
                        code="SCHEMA_UNAVAILABLE",
                        message=f"Required-files schema not available: {exc}",
                    )
                ],
            )

        data: dict = {
            "method": experiment_type.value,
            "files": [f.file_type.value for f in files],
        }
        if em_subtype:
            data["subtype"] = em_subtype

        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(data))
        if not errors:
            return CheckReport(source="session")

        filetypes = [f.file_type.value for f in files]
        messages = _human_readable_messages(filetypes, experiment_type, em_subtype)
        if not messages:
            messages = [e.message for e in errors]

        return CheckReport(
            source="session",
            issues=[
                CheckIssue(
                    severity=CheckSeverity.FATAL,
                    code="REQ_FILES_MISSING",
                    message=m,
                )
                for m in messages
            ],
        )

    def check_mmcif_file(self, file: LocalFile) -> CheckReport:
        return self._schema_check(file, "mmcif_base")

    def check_mmcif_category(self, file: LocalFile, category: str) -> CheckReport:
        return self._schema_check(file, f"mmcif_category_{category}")

    def check_mmcif_field(self, file: LocalFile, category: str, field: str) -> CheckReport:
        return self._schema_check(file, f"mmcif_field_{category}_{field}")

    def check_file_type(self, file: LocalFile, file_type: FileType) -> CheckReport:
        return self._schema_check(file, f"filetype_{file_type.value.replace('-', '_')}")

    def _schema_check(self, file: LocalFile, schema_name: str) -> CheckReport:
        try:
            self._schema_provider.get_schema(schema_name)
        except SchemaError:
            return CheckReport(
                source=file.file_id,
                issues=[
                    CheckIssue(
                        severity=CheckSeverity.INFO,
                        code="SCHEMA_UNAVAILABLE",
                        message=f"Schema '{schema_name}' not available — check skipped",
                    )
                ],
            )
        # Schema exists but mmCIF parsing is not yet implemented.
        return CheckReport(source=file.file_id)
```

- [ ] **Run tests to verify they pass**

```bash
uv run pytest tests/checks/test_runner.py -v
```
Expected: 9 passed.

- [ ] **Commit**

```bash
git add src/nextdep_dsp/checks/runner.py tests/checks/test_runner.py
git commit -m "feat: add CheckRunner with required-files validation via SchemaProvider"
```

---

## Task 11: CheckRunner — mmCIF stubs test

- [ ] **Add tests to `tests/checks/test_runner.py`**

Append these test functions to the existing file:

```python
# --- mmCIF checks (schema-not-available path) ---

def test_check_mmcif_file_returns_info_when_no_schema(runner_no_schema: CheckRunner):
    file = LocalFile("f1", "s1", "/tmp/model.cif", FileType.MMCIF_COORD)
    report = runner_no_schema.check_mmcif_file(file)
    assert report.ok is True
    assert any(i.severity == CheckSeverity.INFO for i in report.issues)


def test_check_mmcif_category_returns_info_when_no_schema(runner_no_schema: CheckRunner):
    file = LocalFile("f1", "s1", "/tmp/model.cif", FileType.MMCIF_COORD)
    report = runner_no_schema.check_mmcif_category(file, "_atom_site")
    assert report.ok is True


def test_check_mmcif_field_returns_info_when_no_schema(runner_no_schema: CheckRunner):
    file = LocalFile("f1", "s1", "/tmp/model.cif", FileType.MMCIF_COORD)
    report = runner_no_schema.check_mmcif_field(file, "_atom_site", "Cartn_x")
    assert report.ok is True


def test_check_file_type_returns_info_when_no_schema(runner_no_schema: CheckRunner):
    file = LocalFile("f1", "s1", "/tmp/model.cif", FileType.MMCIF_COORD)
    report = runner_no_schema.check_file_type(file, FileType.MMCIF_COORD)
    assert report.ok is True
```

- [ ] **Run tests**

```bash
uv run pytest tests/checks/test_runner.py -v
```
Expected: 13 passed.

- [ ] **Commit**

```bash
git add tests/checks/test_runner.py
git commit -m "test: verify mmCIF check methods degrade gracefully without schemas"
```

---

## Task 12: Integration test — session + schema provider together

**Files:**
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_session_schema.py`

- [ ] **Write integration test**

```python
# tests/integration/test_session_schema.py
"""Integration test: real JsonSessionStore + real RemoteSchemaProvider."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from nextdep_dsp.checks.runner import CheckRunner
from nextdep_dsp.enums import Country, ExperimentType, FileType
from nextdep_dsp.schemas.remote import RemoteSchemaProvider
from nextdep_dsp.session.json_store import JsonSessionStore
from nextdep_dsp.session.models import LocalFile, LocalSession


@pytest.fixture
def files_schema() -> dict:
    schema_path = Path(__file__).parent.parent / "fixtures" / "files.json"
    with schema_path.open() as f:
        return json.load(f)


def test_full_session_create_add_check(tmp_path: Path, httpserver, files_schema: dict):
    httpserver.expect_request("/required_files.json").respond_with_json(files_schema)

    store = JsonSessionStore("integ-session", base_dir=tmp_path / "sessions")
    session = LocalSession(
        session_id="integ-session",
        email="user@lab.org",
        users=["0000-0002-5109-8728"],
        country=Country.USA,
        experiment_type=ExperimentType.XRAY,
        created_at=datetime.now(),
    )
    store.create_session(session)

    f1 = LocalFile(
        file_id="f1",
        session_id="integ-session",
        file_path="/tmp/model.cif",
        file_type=FileType.MMCIF_COORD,
        file_mtime=datetime.now(tz=timezone.utc),
    )
    f2 = LocalFile(
        file_id="f2",
        session_id="integ-session",
        file_path="/tmp/data.cif",
        file_type=FileType.CRYSTAL_STRUC_FACTORS,
        file_mtime=datetime.now(tz=timezone.utc),
    )
    store.add_file(f1)
    store.add_file(f2)

    provider = RemoteSchemaProvider(
        httpserver.url_for("/"), cache_dir=tmp_path / "schemas"
    )
    runner = CheckRunner(schema_provider=provider)

    files = store.get_all_files()
    loaded = store.get_session()
    report = runner.check_required_files(files, loaded.experiment_type)
    assert report.ok is True
```

- [ ] **Run integration test**

```bash
uv run pytest tests/integration/test_session_schema.py -v
```
Expected: 1 passed.

- [ ] **Commit**

```bash
git add tests/integration/
git commit -m "test: add integration test for session store + schema provider"
```

---

## Task 13: Cleanup — delete superseded files

Only do this after the full test suite passes.

**Files to delete:**
- `src/nextdep_dsp/session/store.py`
- `src/nextdep_dsp/checks/file_checks.py`
- `src/nextdep_dsp/validation/` (entire directory)

- [ ] **Run full test suite to confirm green**

```bash
uv run pytest -v
```
Expected: all tests pass.

- [ ] **Delete superseded files**

```bash
rm src/nextdep_dsp/session/store.py
rm src/nextdep_dsp/checks/file_checks.py
rm -rf src/nextdep_dsp/validation/
```

- [ ] **Update `pyproject.toml` entry points**

Remove the `nextdep_schema_compliance` script entry (it pointed into `validation/`):

```toml
[project.scripts]
nextdep_dsp = "nextdep_dsp.cli:app"
nextdep_api_token = "nextdep_dsp.authorization.token:app"
```

- [ ] **Run full test suite again**

```bash
uv run pytest -v
```
Expected: all tests still pass.

- [ ] **Commit**

```bash
git add -A
git commit -m "chore: delete superseded validation/, session/store.py, checks/file_checks.py"
```

---

## Notes for Plan 2 (Auth)

Plan 2 implements:
- `src/nextdep_dsp/auth/types.py` — `AuthProvider` Protocol
- `src/nextdep_dsp/auth/token.py` — `TokenStore`: file-based token persistence at `~/.config/nextdep/tokens.json`, JWT expiry checking via `pyjwt`
- `src/nextdep_dsp/auth/oidc.py` — `OidcAuth`: browser launch, loopback HTTP callback, one-time code exchange

Plan 2 depends only on `exceptions.py` and `config.py` from this plan.

## Notes for Plan 3 (API + Facade)

Plan 3 implements:
- `src/nextdep_dsp/api/enums.py` — `Status` enum
- `src/nextdep_dsp/api/models.py` — response models as `@dataclass`
- `src/nextdep_dsp/api/types.py` — `ApiClient` Protocol
- `src/nextdep_dsp/api/client.py` — `HttpApiClient`
- `src/nextdep_dsp/dsp.py` — `Deposition` facade + factories
- `src/nextdep_dsp/__init__.py` — public surface

Plan 3 depends on Plans 1 and 2 being complete.
